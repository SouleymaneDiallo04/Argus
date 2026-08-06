# RTSP — Ingestion serveur d'un flux caméra IP — Design

**Date :** 2026-08-06
**Contexte :** clôture V1 (§ « 1 RTSP » du cahier des charges). Sous-projet indépendant.
**Statut :** validé

## 1. Objectif

Permettre au backend de **tirer un flux RTSP** (caméra IP) côté serveur, d'y faire tourner le
pipeline complet (détection → conformité → preuve → notification → journal) et d'en rendre le
résultat visible dans le **dashboard**. Aucune vidéo live RTSP dans l'UI (headless).

## 2. Décisions de conception (validées)

- **Headless → dashboard** : le worker RTSP alimente journal / stats / preuves / notifications ;
  l'opérateur voit tout dans le dashboard existant. Re-diffusion vidéo annotée = V2.
- **Contrôle REST** : `POST /sources/rtsp`, `DELETE /sources/rtsp`, `GET /sources/rtsp`.
  **Un seul flux** à la fois (« 1 RTSP ») ; démarrer remplace le worker courant.
- **Zéro nouvelle dépendance** : `cv2.VideoCapture` (OpenCV 5.0, backend FFmpeg confirmé).
- **Sink partagé** : la logique par-frame (snapshot + `record_frame` + notify) est extraite en
  `ingest_frame(...)`, réutilisée par le handler WS **et** le worker RTSP (DRY).

## 3. Limite assumée (V1)

Le modèle YOLO + tracker est **partagé**. Faire tourner le worker RTSP **et** la console live
WS simultanément mélangerait les tracks → **hors périmètre**. Le worker RTSP est la source
active unique quand il tourne (multi-caméras = V2). Documenté dans `DECISIONS.md`.

## 4. Périmètre

**Dans ce sous-projet (backend seul) :**
- Sink partagé `ingest_frame` + refactor du handler WS pour l'utiliser.
- `RtspWorker` (thread, `VideoCapture` injectable, throttle).
- Endpoints `POST/DELETE/GET /sources/rtsp`.
- `DECISIONS.md` + note README (dont test manuel MediaMTX/ffmpeg).

**Hors périmètre :** vue vidéo annotée live, multi-caméras, contrôle depuis l'UI (curl/REST
suffit en V1) → V2.

## 5. Composants (`app/ingest/`)

### `frame_sink.py`
```
ingest_frame(journal, snapshots, notifier, frame, detections, result, now) -> None
    # snapshot flouté si result.events (et snapshots != None), sinon None ;
    # journal.record_frame(result, now, snapshot) ;
    # notifier.notify(event) pour chaque event (si notifier != None).
    # Chaque étape en try/except : une panne (preuve/persistance/notif) n'interrompt rien.
```
Comportement **identique** au bloc actuel du handler WS (qui l'appellera désormais).

### `rtsp_worker.py`
```
class RtspWorker:
    def __init__(self, url, handle, capture_factory=cv2.VideoCapture, fps=5)
        # handle(frame, timestamp) -> None ; capture_factory(url) -> objet .read()/.release()
    def start(self)      # lance un thread daemon
    def stop(self)       # signale l'arrêt + join(timeout=5)
    def status(self) -> dict   # {running, url, frames, error}
```
Boucle : `ok, frame = cap.read()` ; si `not ok` → arrêt ; sinon `handle(frame, ts)` avec
`ts = frames / fps` (temps de flux) ; throttle `stop.wait(1/fps)` (interruptible).
`cap.release()` en fin.

## 6. API REST (contrôle du flux)

`app.state.rtsp` = worker courant ou `None`. `app.state.rtsp_capture_factory` = `cv2.VideoCapture`
(**injectable en test**).

- **`POST /sources/rtsp`** body `{"url": "rtsp://…"}` :
  - arrête le worker courant s'il existe ;
  - `app.state.detector.reset()` (tracker frais) ; construit
    `pipeline = FramePipeline(detector, zones_store.get_zones(), camera="rtsp")` ;
  - `handle(frame, ts)` = `ingest_frame(journal, snapshots, notifier, frame, *pipeline.process(frame, ts), now)` ;
  - crée `RtspWorker(url, handle, app.state.rtsp_capture_factory)`, `start()`, stocke sur
    `app.state.rtsp` ; renvoie `status()`.
- **`DELETE /sources/rtsp`** : `stop()` + `app.state.rtsp = None` → `{"stopped": true}`.
- **`GET /sources/rtsp`** : `app.state.rtsp.status()` ou `{"running": false}`.

## 7. Fichiers

```
backend/app/ingest/__init__.py
backend/app/ingest/frame_sink.py      # ingest_frame
backend/app/ingest/rtsp_worker.py     # RtspWorker
backend/app/api/app.py                # refactor WS -> ingest_frame ; state rtsp ; endpoints
backend/tests/test_frame_sink.py
backend/tests/test_rtsp_worker.py
backend/tests/test_rtsp_api.py
docs/DECISIONS.md                     # ingestion RTSP headless + source unique
README.md                             # section « Flux RTSP »
```

## 8. Tests (TDD)

- **`frame_sink`** : `ingest_frame` avec journal `:memory:` + snapshots tmp + notifier espion
  → snapshot écrit si events, `record_frame` appelé, notify par event ; `snapshots=None` /
  `notifier=None` tolérés.
- **`rtsp_worker`** : `VideoCapture` factice (N frames puis `(False, None)`) + `handle` espion
  → `handle` appelé N fois, `frames == N`, `release()` appelé, `status()["running"]` False après
  fin ; `stop()` interrompt.
- **`rtsp_api`** : `capture_factory` injecté (frames d'une personne sans casque dans une zone
  helmet) → `POST /sources/rtsp` = 200 running ; après quelques frames
  `stats().global.person_frames >= 1` (le worker ingère et persiste, sans dépendre du debounce) ;
  `DELETE` = 200 ; `GET` running False.
- **WS existant** : `test_persistence_ws` / `test_notify_ws` restent verts (comportement du sink
  préservé). Suite backend (**103**) verte.

## 9. Validation manuelle (optionnelle, réelle)

Servir un vrai RTSP local :
```
# MediaMTX (serveur RTSP) puis ffmpeg qui boucle une vidéo dessus :
ffmpeg -re -stream_loop -1 -i demo.mp4 -c copy -f rtsp rtsp://localhost:8554/cam
curl -X POST localhost:8000/sources/rtsp -d '{"url":"rtsp://localhost:8554/cam"}' -H 'content-type: application/json'
# puis observer le dashboard se remplir ; DELETE pour arrêter.
```

## 10. Critères d'acceptation

1. `POST /sources/rtsp` démarre l'ingestion serveur d'un flux ; `GET` reflète le statut ;
   `DELETE` l'arrête proprement.
2. Les frames RTSP traversent le pipeline et alimentent journal / stats / preuves / notifications
   (via le sink partagé).
3. Le handler WS utilise le même sink (aucune régression ; tests WS verts).
4. Zéro nouvelle dépendance ; suite backend verte (103 + nouveaux).
5. Limite « source unique » documentée (`DECISIONS.md`) ; test manuel RTSP documenté (README).
