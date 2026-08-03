# P3-b — RGPD & preuves (snapshots floutés) — Design

**Date :** 2026-08-01
**Phase :** P3 (Alertes, RGPD, preuves, rapports) — sous-projet **b**
**Dépend de :** P3-a (journal & persistance, mergé PR #8)
**Statut :** validé

## 1. Objectif

Produire une **preuve conforme au RGPD** pour chaque infraction : au moment où une
infraction est confirmée, capturer un **snapshot de la frame avec toutes les têtes
floutées** (côté serveur, avant tout stockage), le persister et l'exposer en REST.

Répond à l'exigence du cahier des charges (§5.4, §6) : « floutage des visages côté serveur
avant tout stockage de preuve ; snapshots de preuve toujours floutés ».

## 2. Décisions de conception (validées)

- **Localisation de la tête = heuristique région-tête** : le haut ~30 % du bbox de chaque
  personne (réutilise la bande `helmet` de `association.py`, `(0.0, 0.30)`). Le modèle n'a
  pas de classe tête/visage ; un détecteur de visage échouerait précisément sur casque /
  angle / occlusion (le cas industriel). L'heuristique **garantit** le floutage.
- **Floutage = pixelisation (mosaïque)** : resize down → up, plus fiable pour
  l'anonymisation qu'un flou gaussien léger.
- **Portée = preuves stockées uniquement.** Le flux live est la vidéo locale de l'opérateur
  (aucune image renvoyée par le serveur) ; un floutage live éventuel sera **client-side**,
  hors P3-b.
- **Snapshot plein cadre**, toutes les têtes floutées (garde le contexte HSE), **un
  snapshot par frame** à infraction (partagé par tous les events du frame), nom **uuid4**.

## 3. Périmètre

**Dans P3-b :**
- Package `app/evidence/` : floutage (`redaction.py`) + stockage (`snapshots.py`).
- Colonne `snapshot` sur `events` + attache du snapshot à l'enregistrement.
- Capture au chemin WS (non bloquante) quand une infraction est confirmée.
- `GET /events/{event_id}/snapshot` (image) ; `snapshot` inclus dans `GET /events`.

**Hors P3-b :**
- Floutage du flux **live** (client-side, plus tard).
- Notifications email/Telegram → **P3-c**.
- Rapports PDF/CSV → **P3-d**.

## 4. Composants

### `app/evidence/redaction.py` (pur, cv2/numpy déjà présents)
```
head_region(bbox, band=(0.0, 0.30)) -> tuple[int, int, int, int]
    # (x1, y1, x2, y2) entiers : pleine largeur du bbox, bande verticale [band] de la hauteur.

blur_head_regions(image: np.ndarray, person_bboxes: list[BBox]) -> np.ndarray
    # copie l'image, pixelise la région-tête de chaque personne, retourne la copie.
    # pixelisation : sous-échantillonnage fort (ex. bloc ~16 px) resize DOWN puis UP (INTER_NEAREST).
    # régions hors cadre clampées ; bbox dégénéré (w/h <= 0) ignoré.
```

### `app/evidence/snapshots.py`
```
class SnapshotStore:
    def __init__(self, directory: str)          # crée le dossier si absent
    def save(self, image, person_bboxes) -> str # floute -> JPEG, nom = f"{uuid4().hex}.jpg", retourne le nom
    def path(self, filename: str) -> str         # chemin absolu, sans traverser hors du dossier
```
Dossier via `ARGUS_SNAPSHOT_DIR` (défaut `snapshots/`). `.gitignore` : `snapshots/`.

## 5. Persistance (extension du `Journal`)

- **Schéma** : `events` gagne `snapshot TEXT` (nullable). `CREATE TABLE` mis à jour **et**
  migration défensive dans `__init__` :
  `try: ALTER TABLE events ADD COLUMN snapshot TEXT except sqlite3.OperationalError: pass`
  (idempotent : ne fait rien si la colonne existe déjà).
- `record_event(event, ts, snapshot: str | None = None)` — insère `snapshot`.
- `record_frame(result, now, snapshot: str | None = None)` — passe `snapshot` à chaque
  `record_event` du frame (les observations restent inchangées).
- `events(...)` — le dict retourné inclut `"snapshot"`.
- `event(event_id: int) -> dict | None` — une ligne par id (pour l'endpoint image).

**Rétro-compatibilité :** les appels P3-a de `record_event`/`record_frame` sans `snapshot`
restent valides (défaut `None`).

## 6. API REST

- **`GET /events/{event_id}/snapshot`** :
  - `event = journal.event(event_id)` ; si `None` ou `event["snapshot"] is None` → **404**.
  - sinon `FileResponse(snapshots.path(event["snapshot"]), media_type="image/jpeg")` ;
    fichier absent → **404**.
- **`GET /events`** : la réponse inclut `snapshot` (nom de fichier ou `null`). Le front
  construit l'URL `/events/{id}/snapshot`.

## 7. Intégration WS (non bloquante)

Dans le handler `/ws/stream`, après `pipeline.process` (bloc existant) :
```
snapshot = None
if result.events:
    persons = [d.bbox for d in detections if d.cls == "person"]
    snapshot = await run_in_threadpool(app.state.snapshots.save, frame, persons)
await run_in_threadpool(app.state.journal.record_frame, result, now, snapshot)
```
- Le blur + encode + écriture disque passent par `run_in_threadpool` (hors boucle asyncio).
- Enveloppé dans le même `try/except` défensif que la persistance P3-a (une panne
  d'écriture de preuve ne tue pas le flux live).
- `SnapshotStore` ouvert au `lifespan` (`app.state.snapshots`), défaut `None`, **injectable
  en test** comme `journal`/`detector`. Le `conftest` de test pointe `ARGUS_SNAPSHOT_DIR`
  vers un dossier temporaire.

## 8. Structure de fichiers

```
backend/app/evidence/
  __init__.py
  redaction.py          # head_region, blur_head_regions
  snapshots.py          # SnapshotStore
backend/app/persistence/journal.py   # + colonne snapshot, event(), params snapshot
backend/app/api/app.py               # lifespan snapshots, capture WS, GET .../snapshot
backend/tests/
  test_redaction.py
  test_snapshots.py
  test_journal.py       # ajouts snapshot + event()
  test_snapshot_api.py  # WS -> snapshot -> GET image ; 404
  conftest.py           # + ARGUS_SNAPSHOT_DIR -> tmp
backend/.gitignore      # + snapshots/
```

## 9. Tests (TDD)

- **`test_redaction.py`** : `head_region` = pleine largeur × haut 30 % (coords entières,
  clampées). `blur_head_regions` : sur une image contrôlée, la région-tête change (variance
  effondrée / pixels différents) tandis qu'une zone basse reste identique ; bbox hors cadre
  ou dégénéré n'explose pas.
- **`test_snapshots.py`** : `save` écrit un fichier `.jpg` **relisible par cv2** dans le
  dossier, renvoie un nom unique ; `path` résout dans le dossier.
- **`test_journal.py`** (ajouts) : `record_event(..., snapshot="x.jpg")` → `events()[0]["snapshot"] == "x.jpg"` ; `event(id)` renvoie la ligne, `None` si absent ;
  `record_frame(result, now, "x.jpg")` attache le snapshot à l'event.
- **`test_snapshot_api.py`** : flux WS produisant une infraction → un fichier snapshot créé,
  `GET /events` expose son nom, `GET /events/{id}/snapshot` renvoie **200** `image/jpeg` ;
  event sans snapshot ou id inconnu → **404**.
- Suite backend existante (**79**) reste verte.

## 10. Critères d'acceptation

1. Une infraction confirmée via WS crée un JPEG **flouté** (têtes pixelisées) sur disque et
   renseigne `events.snapshot`.
2. `GET /events/{id}/snapshot` sert l'image ; 404 propre si absente.
3. `GET /events` expose le nom du snapshot.
4. Zéro nouvelle dépendance (cv2/numpy déjà présents) ; suite backend verte (79 + nouveaux).
5. Aucune image non floutée n'est jamais écrite sur disque (le seul chemin d'écriture passe
   par `blur_head_regions`).
