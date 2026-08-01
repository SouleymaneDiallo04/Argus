# P3-a — Persistance & journal d'événements — Design

**Date :** 2026-07-29
**Phase :** P3 (Alertes, RGPD, preuves, rapports) — sous-projet **a** (fondation)
**Statut :** validé

## 1. Objectif

Persister les infractions détectées (journal HSE) et des agrégats de conformité, puis
les exposer en REST (`GET /events`, `GET /stats`). C'est la fondation de P3 : la
persistance débloque les preuves (P3-b), les notifications (P3-c) et les rapports (P3-d).

Aucune logique métier nouvelle : on persiste ce que le pipeline produit déjà
(`FrameResult.results` + `FrameResult.events`) et on l'interroge.

## 2. Périmètre

**Dans P3-a :**
- Couche de persistance SQLite (module repository pur, testable en `:memory:`).
- Écriture depuis le handler WebSocket (journal + agrégats), non bloquante.
- `GET /events` (journal filtrable) et `GET /stats` (taux de conformité).
- Décision documentée dans `docs/DECISIONS.md`.

**Hors P3-a (rappel feuille de route) :**
- Floutage têtes + snapshots de preuve → **P3-b**.
- Notifications email/Telegram → **P3-c**.
- Rapports PDF/CSV → **P3-d**.
- Dashboard front consommant `/stats` → **P2-b** (après P3).

## 3. Modèle de données (SQLite)

Backend : `sqlite3` de la stdlib — **zéro nouvelle dépendance**. Mode WAL activé pour
que lecteurs (REST) et l'unique écrivain (WS) coexistent.

### Table `events` — journal d'infractions
Une ligne par `ViolationEvent` (déjà dédupliqué par le debounce : une infraction = un
événement, pas un par frame).

| Colonne | Type | Rôle |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `ts` | TEXT (ISO 8601 UTC) | Horloge murale serveur à l'enregistrement — **fait autorité** pour la preuve. |
| `stream_ts` | REAL | Timestamp du flux (fourni par le client), pour recouper la vidéo. |
| `camera` | TEXT | Identifiant de caméra (issu du `ViolationEvent`). |
| `zone` | TEXT NULL | Zone de l'infraction. |
| `track_id` | INTEGER | ID de suivi de la personne. |
| `missing` | TEXT | EPI manquants, JSON trié (`["helmet","shoes"]`). |

Index : `(ts)`, `(zone)` pour les filtres.

### Table `observations` — agrégats de conformité
Upsert par fenêtre de temps × zone.

| Colonne | Type | Rôle |
|---|---|---|
| `bucket` | TEXT | Horloge murale UTC tronquée à la **minute** (`YYYY-MM-DDTHH:MM`). |
| `zone` | TEXT | Zone (chaîne vide `""` = hors zone ; NULL interdit pour garder la PK dédupliquante). |
| `person_frames` | INTEGER | Nombre d'observations de personnes (une par `ComplianceResult` de zone). |
| `compliant_frames` | INTEGER | Parmi elles, celles conformes. |

PK : `(bucket, zone)`. Upsert atomique :
`INSERT … ON CONFLICT(bucket, zone) DO UPDATE SET person_frames = person_frames + excluded.person_frames, compliant_frames = compliant_frames + excluded.compliant_frames`.

Taux de conformité = `compliant_frames / person_frames` (part des observations
personne-frame conformes — métrique « temps de conformité », honnête et classique en HSE).

**Personnes hors zone** (`zone is None`) : pas d'EPI requis → toujours « conformes »,
non pertinent pour un taux. Elles sont agrégées sous `zone=""` et **exclues** du
`by_zone` et du `global` (qui somment les zones nommées).

### Décision : pas de sévérité stockée
La sévérité dépend du **risque de zone**, qui vit côté front (`localStorage`,
cf. P2-a). Le backend reste **factuel** (zone + EPI manquants) ; la sévérité est
recalculée à l'affichage (`severityFor`). Cohérent avec la séparation front/back.

## 4. API REST

### `GET /events`
Paramètres (query) : `zone`, `ppe`, `since` (ISO), `until` (ISO), `camera`,
`limit` (défaut 100, max 1000), `offset` (défaut 0).
Réponse : `{ "events": [ {id, ts, stream_ts, camera, zone, track_id, missing:[…]} ] }`,
**plus récent d'abord** (`ORDER BY ts DESC, id DESC`).
Filtrage `ppe` : l'événement match si `ppe` ∈ `missing`.

### `GET /stats`
Paramètres (query) : `since` (ISO), `until` (ISO), `zone` (optionnel — restreint).
Réponse :
```json
{
  "global":    {"person_frames": 0, "compliant_frames": 0, "rate": null},
  "by_zone":   [{"zone": "Fonderie", "person_frames": 0, "compliant_frames": 0, "rate": null}],
  "over_time": [{"bucket": "2026-07-29T14:30", "person_frames": 0, "compliant_frames": 0, "rate": null}],
  "violations":{"total": 0, "by_zone": {"Fonderie": 0}}
}
```
- `rate` = `compliant_frames / person_frames`, ou `null` si `person_frames == 0`
  (jamais de division par zéro, pas de faux « 0 % »).
- `global` et `by_zone` somment les `observations` de zones **nommées** sur la fenêtre.
- `over_time` : agrégat par `bucket` (toutes zones nommées, ou la zone filtrée).
- `violations` : comptes issus de la table `events` sur la même fenêtre.

## 5. Sémantique temps

L'axe principal est l'**horloge murale serveur (UTC)** : c'est ce qu'un déploiement réel
(caméras live/RTSP) consigne. Sur une **vidéo uploadée** de démo, toutes les infractions
tombent dans « maintenant » — acceptable et honnête (le système consigne *quand il
observe*). `stream_ts` est conservé pour recouper la timeline vidéo. Documenté dans
`DECISIONS.md`.

## 6. Intégration (non bloquante)

- `Journal` (classe repository) ouvert au `lifespan`, exposé via `app.state.journal`,
  **injectable en test** exactement comme `app.state.detector` (les tests passent un
  `Journal(":memory:")`, la prod ouvre `ARGUS_DB_PATH`, défaut `argus.db`).
- Connexion unique persistante, `check_same_thread=False`, écritures protégées par un
  `threading.Lock` ; WAL activé pour les fichiers.
- **Chemin d'écriture WS** : après `pipeline.process`, le handler appelle
  `await run_in_threadpool(app.state.journal.record_frame, result, now)` où
  `now = datetime.now(UTC)` — la boucle asyncio n'est jamais bloquée par le disque.
- **Chemin de lecture REST** : `/events` et `/stats` sont des handlers `def` sync
  (FastAPI les exécute déjà dans un threadpool) qui appellent `app.state.journal`.
- `record_frame(result, now)` : insère chaque `event` de `result.events` (chacun porte
  déjà son `camera`), puis upsert les observations groupées par zone à partir de
  `result.results`. `now` fournit `events.ts` et le `bucket` (tronqué à la minute).

## 7. Structure de fichiers

```
backend/app/persistence/
  __init__.py
  journal.py        # classe Journal : record_frame / record_event /
                    # record_observations / events() / stats() + schéma
backend/tests/
  test_journal.py   # repository sur sqlite3(":memory:")
  test_events_api.py# GET /events via TestClient + Journal injecté
  test_stats_api.py # GET /stats via TestClient + Journal injecté
docs/DECISIONS.md   # créé/complété : horloge murale, pas de sévérité stockée
```

Modifs : `backend/app/api/app.py` (lifespan ouvre le Journal, WS persiste, endpoints
REST). Le `camera` du journal provient directement de `ViolationEvent.camera`
(constante de pipeline en V1, multi-caméras en V2) ; les observations ne stockent pas
la caméra.

## 8. Tests (TDD)

- **Repository** (`test_journal.py`) : création du schéma ; insert + relecture d'events
  avec chaque filtre (zone, ppe, since/until, limit/offset, ordre décroissant) ; upsert
  idempotent des observations (deux appels même bucket/zone → somme) ; `stats()` calcule
  `global`/`by_zone`/`over_time`/`violations` et renvoie `rate=null` si dénominateur nul.
- **API** (`test_events_api.py`, `test_stats_api.py`) : `TestClient` avec
  `app.state.journal = Journal(":memory:")` pré-injecté ; on insère des lignes puis on
  vérifie les réponses JSON et le filtrage.
- La suite backend existante (**67 tests**) doit rester verte (le nouveau chemin de
  persistance ne doit pas casser le WS existant ; test d'un flux WS qui persiste bien
  un event).

## 9. Critères d'acceptation

1. Un flux WS produisant une infraction crée exactement une ligne `events` et incrémente
   `observations` pour la fenêtre/zone.
2. `GET /events` renvoie le journal filtré, plus récent d'abord.
3. `GET /stats` renvoie un taux de conformité correct (global/zone/temps) et `null` sans
   observation.
4. Zéro nouvelle dépendance ; suite backend verte (67 + nouveaux tests) ; CI verte.
5. `DECISIONS.md` documente l'horloge murale et l'absence de sévérité stockée.
