# P1b — Service FastAPI (WS + REST) — Design

> **Auteur :** Souleymane Diallo · **Date :** 2026-07-26 · **Phase :** P1b

## Objectif

Exposer le pipeline d'inférence de conformité (P1a, `FramePipeline`) via un **service FastAPI** : un WebSocket qui traite un flux de frames en temps réel, et une API REST pour configurer les zones. C'est la couche qui permettra au frontend (P2) d'envoyer des frames et d'afficher les résultats/alertes en direct.

## Périmètre

**Dans P1b :**
- WebSocket d'inférence (frame → détections + conformité + événements).
- REST de configuration des zones (lecture/écriture).
- Chargement du modèle une fois au démarrage.

**Hors P1b (→ P3 « Alertes, RGPD, preuves, rapports ») :** persistance SQLite, journal d'événements historique, snapshots floutés, notifications email/Telegram/webhook, rapports PDF, stats agrégées.

**Hypothèse V1 :** **un seul flux actif à la fois** (une caméra). Le multi-caméras simultané est V2.

## Architecture

Le service n'ajoute qu'une couche `app/api/` au-dessus des couches existantes, **inchangées** : `app.domain` (moteur pur) et `app.pipeline` (`FramePipeline`, P1a).

- Au **démarrage**, le service charge le modèle YOLO (`PPEDetector.from_path`, chemin via variable d'env `ARGUS_MODEL_PATH`, défaut `best.pt`) — opération lourde faite une seule fois. Le détecteur (donc le modèle) est **partagé**.
- La **config des zones** vit en mémoire dans un petit état applicatif (`ZonesStore`), réglable par REST.
- Chaque **connexion WebSocket** = un flux vidéo = un `FramePipeline` neuf (état de tracking + debounce propres au flux), construit à partir des zones courantes + du détecteur partagé. Le tracker Ultralytics est réinitialisé en début de connexion.

## Endpoints

### `GET /health`
Liveness. Réponse : `{"status": "ok", "model_loaded": true}`.

### `GET /zones`
Renvoie la config de zones courante :
```json
{"zones": [{"name": "entrée", "polygon": [[0,0],[640,0],[640,480],[0,480]], "required_ppe": ["helmet","safety-vest"]}]}
```

### `PUT /zones`
Remplace la config de zones. Même schéma que `GET`. Validation : `polygon` = liste de ≥3 points `[x,y]` ; `required_ppe` ⊆ `{helmet, safety-vest, mask, shoes}`. Payload invalide → **HTTP 422**.

### `WS /ws/stream`
Le client envoie, par frame, un message JSON texte :
```json
{"frame": "<jpeg encodé en base64>", "timestamp": 12.5}
```
Le serveur décode (base64 → OpenCV), passe la frame au `FramePipeline` (zones courantes), et renvoie :
```json
{
  "detections": [{"cls": "person", "bbox": [x1,y1,x2,y2], "confidence": 0.9, "track_id": 3}],
  "results":    [{"track_id": 3, "zone": "entrée", "required": ["helmet"], "present": [], "missing": ["helmet"], "compliant": false}],
  "events":     [{"track_id": 3, "zone": "entrée", "missing": ["helmet"], "timestamp": 12.5, "camera": "cam-1"}]
}
```
Frame illisible / base64 invalide → message `{"error": "..."}` sur le WS, sans fermer la connexion.

## Composants (unités à responsabilité unique)

| Fichier | Responsabilité |
|---|---|
| `app/api/schemas.py` | Modèles Pydantic (requête/réponse) : `ZoneModel`, `ZonesConfig`, `FrameMessage`, et la sérialisation `Detection`/`ComplianceResult`/`ViolationEvent` → dict. |
| `app/api/zones_store.py` | `ZonesStore` : détient la liste de `Zone` (domaine) en mémoire, get/set, conversion depuis/vers les modèles Pydantic. |
| `app/api/decode.py` | `decode_frame(b64: str) -> np.ndarray` : base64 → OpenCV. Lève une erreur claire si illisible. |
| `app/api/app.py` | L'app FastAPI (`create_app()`) : `lifespan` (charge le modèle une fois au démarrage ; sauté si un détecteur est déjà présent dans `app.state`), routes REST, endpoint WS. Le détecteur et le décodeur vivent dans `app.state` (`app.state.detector` / `app.state.decode`), surchargés par des stubs dans les tests. Le tracker est réinitialisé (`detector.reset()`) à chaque nouvelle connexion WS. |

## Gestion d'erreurs
- `PUT /zones` avec payload malformé → 422 (validation Pydantic).
- WS : frame non décodable → `{"error": "frame illisible"}`, la connexion reste ouverte.
- Modèle introuvable au démarrage → **échec immédiat** avec un message clair (le service n'a aucun sens sans modèle ; pas de mode dégradé).

## Tests
- FastAPI `TestClient` (REST) + `TestClient.websocket_connect` (WS).
- Le **détecteur est injecté** via `app.state.detector` → les tests y placent un **stub** (`.detect(frame) -> list[Detection]` canné, + `.reset()` no-op) **avant** d'instancier le `TestClient` (utilisé sans context manager, donc le `lifespan` ne charge jamais le vrai modèle) : **pas de vrai modèle, pas d'ultralytics dans la suite de tests**.
- Le **décodage** est isolé (`decode.py`) et injecté via `app.state.decode` : dans les tests WS on le remplace par une fonction identité, donc on peut envoyer un base64 factice sans OpenCV. `decode_frame` est testé à part avec une vraie petite image encodée.
- Cas couverts : `GET/PUT /zones` (aller-retour + validation 422), cycle WS (frame → JSON détections/résultats/événements), frame illisible et **JSON malformé** (message `{"error": ...}` sans fermer la connexion, prouvé par un aller-retour valide ensuite), erreur d'inférence en plein flux (le flux survit).
- La CI installe `backend/requirements-dev.txt` (`pytest`, `fastapi`, `httpx`, `opencv-python-headless`, `numpy`) — **sans `ultralytics`**, donc la suite tourne vite et le vrai modèle n'est jamais chargé en test.

## Frontières & DRY
Aucune modification de `app.domain` ni de `app.pipeline`. La sérialisation des types du domaine → JSON vit dans `schemas.py` (un seul endroit). Le service réutilise `FramePipeline.process` tel quel. Seule exception côté P1a : ajout d'une méthode `PPEDetector.reset()` (couche `app.inference`) pour réinitialiser le tracker Ultralytics en début de connexion.
