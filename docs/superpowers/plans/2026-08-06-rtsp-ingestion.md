# RTSP — Ingestion serveur d'un flux caméra IP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Le backend tire un flux RTSP côté serveur (contrôle REST), y fait tourner le pipeline complet, et alimente le dashboard — headless, un seul flux.

**Architecture:** Un sink partagé `ingest_frame` (snapshot + persistance + notif), réutilisé par le handler WS et par un `RtspWorker` (thread lisant `cv2.VideoCapture`), piloté par `POST/DELETE/GET /sources/rtsp`.

**Tech Stack:** Python 3.13, FastAPI, OpenCV (`cv2.VideoCapture`, FFmpeg — déjà présent), `threading`, pytest.

## Global Constraints

- **Zéro nouvelle dépendance** (`cv2` déjà là). **Un seul flux RTSP** à la fois.
- **Headless** : le worker alimente journal/stats/preuves/notifications ; pas de vidéo live RTSP.
- **Sink partagé** : `ingest_frame(...)` remplace le bloc par-frame du handler WS (comportement
  identique) et sert au worker.
- **Thread-safety** : le worker (thread) écrit pendant que l'API lit sur la **même connexion
  sqlite** → les lectures du `Journal` (`events`/`stats`/`event`) doivent aussi prendre le lock.
- **`VideoCapture` injectable** (`app.state.rtsp_capture_factory`) pour tester sans vrai flux.
- Interpréteur test : **`py -3`**. Suite backend existante (**103**) verte. Commits conventionnels,
  anglais, **sans `Co-Authored-By`**.
- `ViolationEvent(track_id, zone, missing: frozenset, timestamp, camera)` ; `FramePipeline(detector, zones, **engine_kwargs).process(frame, ts) -> (detections, FrameResult)`.

---

### Task 1: Sink partagé `ingest_frame` + Journal thread-safe + refactor WS

**Files:**
- Create: `backend/app/ingest/__init__.py` (vide), `backend/app/ingest/frame_sink.py`
- Modify: `backend/app/persistence/journal.py` (lock sur les lectures), `backend/app/api/app.py` (WS utilise le sink)
- Test: `backend/tests/test_frame_sink.py`

**Interfaces:**
- Produces: `ingest_frame(journal, snapshots, notifier, frame, detections, result, now) -> None`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_frame_sink.py`
```python
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from app.domain.types import BBox, ComplianceResult, Detection, FrameResult, ViolationEvent
from app.evidence.snapshots import SnapshotStore
from app.ingest.frame_sink import ingest_frame
from app.notify.base import NotificationDispatcher
from app.persistence.journal import Journal


class _Spy:
    def __init__(self):
        self.events = []

    def notify(self, e):
        self.events.append(e)


def _result_with_event():
    return FrameResult(
        results=[ComplianceResult(1, "z", frozenset(), frozenset(), frozenset({"helmet"}), False)],
        events=[ViolationEvent(1, "z", frozenset({"helmet"}), 0.0, "cam")])


def _now():
    return datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def test_ingest_frame_persists_snapshot_and_notifies(tmp_path):
    j = Journal(":memory:")
    spy = _Spy()
    ingest_frame(j, SnapshotStore(str(tmp_path)), NotificationDispatcher([spy]),
                 np.zeros((100, 100, 3), np.uint8),
                 [Detection("person", BBox(10, 10, 90, 90), 0.9, 1)],
                 _result_with_event(), _now())
    ev = j.events()
    assert len(ev) == 1 and ev[0]["snapshot"] is not None
    assert (tmp_path / ev[0]["snapshot"]).exists()
    assert len(spy.events) == 1


def test_ingest_frame_tolerates_none_collaborators():
    j = Journal(":memory:")
    ingest_frame(j, None, None, "F", [], _result_with_event(), _now())
    assert len(j.events()) == 1 and j.events()[0]["snapshot"] is None
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_frame_sink.py -q` → FAIL.

- [ ] **Step 3: Écrire le sink** — `backend/app/ingest/__init__.py` (vide) + `backend/app/ingest/frame_sink.py`
```python
from __future__ import annotations

from datetime import datetime


def ingest_frame(journal, snapshots, notifier, frame, detections, result,
                 now: datetime) -> None:
    """Snapshot flouté (si infraction) + persistance + notifications, tolérant aux pannes.

    Partagé par le handler WS et le worker RTSP.
    """
    snapshot = None
    if result.events and snapshots is not None:
        try:
            persons = [d.bbox for d in detections if d.cls == "person"]
            snapshot = snapshots.save(frame, persons)
        except Exception:
            snapshot = None  # preuve indisponible ne bloque pas le journal
    try:
        journal.record_frame(result, now, snapshot)
    except Exception:
        pass  # une panne de persistance ne doit pas tuer le flux
    if notifier is not None:
        for event in result.events:
            try:
                notifier.notify(event)
            except Exception:
                pass  # une panne de notification ne doit pas tuer le flux
```

- [ ] **Step 4: Rendre les lectures du `Journal` thread-safe** — `backend/app/persistence/journal.py`

Envelopper le corps de `stats`, `events` et `event` dans `with self._lock:`. Exemple pour
`event` (faire de même pour `stats` et `events`) :
```python
    def event(self, event_id: int) -> dict | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT id, ts, stream_ts, camera, zone, track_id, missing, snapshot "
                "FROM events WHERE id = ?", (event_id,),
            ).fetchone()
        if r is None:
            return None
        return {"id": r["id"], "ts": r["ts"], "stream_ts": r["stream_ts"],
                "camera": r["camera"], "zone": r["zone"], "track_id": r["track_id"],
                "missing": json.loads(r["missing"]), "snapshot": r["snapshot"]}
```
Pour `events` : `with self._lock:` autour du `rows = self._conn.execute(...).fetchall()`.
Pour `stats` : `with self._lock:` autour de l'ensemble des `self._conn.execute(...)` de la
méthode (englober tout le corps qui lit la connexion).

- [ ] **Step 5: Refactor du handler WS** — `backend/app/api/app.py`

Ajouter l'import : `from app.ingest.frame_sink import ingest_frame`.

Remplacer le bloc (snapshot + record + notify + send) du handler `/ws/stream` :
```python
                snapshot = None
                if result.events:
                    try:
                        persons = [d.bbox for d in detections if d.cls == "person"]
                        snapshot = await run_in_threadpool(
                            app.state.snapshots.save, frame, persons)
                    except Exception:
                        snapshot = None  # preuve indisponible ne bloque pas le journal
                try:
                    await run_in_threadpool(
                        app.state.journal.record_frame, result,
                        datetime.now(timezone.utc), snapshot)
                except Exception:
                    pass  # une panne de persistance ne doit pas tuer le flux live
                for event in result.events:
                    try:
                        await run_in_threadpool(app.state.notifier.notify, event)
                    except Exception:
                        pass  # une panne de notification ne doit pas tuer le flux
                await ws.send_json(frame_response(detections, result))
```
par :
```python
                await run_in_threadpool(
                    ingest_frame, app.state.journal, app.state.snapshots,
                    app.state.notifier, frame, detections, result,
                    datetime.now(timezone.utc))
                await ws.send_json(frame_response(detections, result))
```

- [ ] **Step 6: Lancer les tests** — `cd backend && py -3 -m pytest tests/test_frame_sink.py tests/test_persistence_ws.py tests/test_notify_ws.py tests/test_journal.py -q`
Expected: PASS (sink OK ; WS persistance/notif inchangés ; journal inchangé).

- [ ] **Step 7: Commit**
```bash
git add backend/app/ingest/__init__.py backend/app/ingest/frame_sink.py backend/app/persistence/journal.py backend/app/api/app.py backend/tests/test_frame_sink.py
git commit -m "refactor(backend): shared ingest_frame sink + thread-safe Journal reads"
```

---

### Task 2: `RtspWorker`

**Files:**
- Create: `backend/app/ingest/rtsp_worker.py`
- Test: `backend/tests/test_rtsp_worker.py`

**Interfaces:**
- Produces: `RtspWorker(url, handle, capture_factory=cv2.VideoCapture, fps=5)` avec
  `.start()`, `.stop()`, `.status() -> dict`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_rtsp_worker.py`
```python
from __future__ import annotations

from app.ingest.rtsp_worker import RtspWorker


class _FakeCap:
    def __init__(self, n):
        self._n = n
        self.released = False

    def read(self):
        if self._n > 0:
            self._n -= 1
            return True, "FRAME"
        return False, None

    def release(self):
        self.released = True


def test_worker_processes_all_frames_then_stops():
    calls = []
    cap = _FakeCap(3)
    w = RtspWorker("rtsp://x", handle=lambda f, ts: calls.append(f),
                   capture_factory=lambda url: cap, fps=1000)
    w.start()
    w._thread.join(timeout=3)          # se termine seul après 3 frames
    assert calls == ["FRAME", "FRAME", "FRAME"]
    assert w.status()["frames"] == 3
    assert w.status()["running"] is False
    assert cap.released is True


def test_worker_stop_is_idempotent():
    w = RtspWorker("rtsp://x", handle=lambda f, ts: None,
                   capture_factory=lambda url: _FakeCap(0), fps=1000)
    w.start()
    w.stop()
    w.stop()                            # ne lève pas
    assert w.status()["running"] is False
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_rtsp_worker.py -q` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/ingest/rtsp_worker.py`
```python
from __future__ import annotations

import threading


class RtspWorker:
    """Ingestion d'un flux RTSP dans un thread : read -> handle(frame, ts), throttlé."""

    def __init__(self, url: str, handle, capture_factory=None, fps: float = 5.0):
        if capture_factory is None:
            import cv2
            capture_factory = cv2.VideoCapture
        self._url = url
        self._handle = handle
        self._cap_factory = capture_factory
        self._interval = 1.0 / fps
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.frames = 0
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        cap = self._cap_factory(self._url)
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                try:
                    self._handle(frame, self.frames * self._interval)
                except Exception as exc:  # une frame défaillante ne tue pas l'ingestion
                    self.error = str(exc)
                self.frames += 1
                self._stop.wait(self._interval)  # throttle interruptible
        finally:
            cap.release()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def status(self) -> dict:
        running = self._thread is not None and self._thread.is_alive()
        return {"running": running, "url": self._url, "frames": self.frames,
                "error": self.error}
```

- [ ] **Step 4: Lancer le test** — PASS (2).

- [ ] **Step 5: Commit**
```bash
git add backend/app/ingest/rtsp_worker.py backend/tests/test_rtsp_worker.py
git commit -m "feat(backend): RtspWorker — threaded RTSP frame ingestion"
```

---

### Task 3: Endpoints `/sources/rtsp` (start / stop / status)

**Files:**
- Modify: `backend/app/api/app.py`, `backend/app/api/schemas.py`
- Test: `backend/tests/test_rtsp_api.py`

**Interfaces:**
- Consumes: `RtspWorker` (T2), `ingest_frame` (T1), `FramePipeline`.
- Produces: `POST /sources/rtsp` (démarre), `DELETE /sources/rtsp` (arrête),
  `GET /sources/rtsp` (statut). `app.state.rtsp`, `app.state.rtsp_capture_factory`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_rtsp_api.py`
```python
from __future__ import annotations

import time

import numpy as np
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, Detection
from app.persistence.journal import Journal


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets

    def reset(self):
        pass


class _FakeCap:
    def __init__(self, n):
        self._n = n

    def read(self):
        if self._n > 0:
            self._n -= 1
            return True, np.zeros((480, 640, 3), np.uint8)
        return False, None

    def release(self):
        pass


def _client(journal, frames):
    app = create_app()
    app.state.detector = _StubDetector(
        [Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)])
    app.state.decode = lambda b: b
    app.state.journal = journal
    app.state.rtsp_capture_factory = lambda url: _FakeCap(frames)
    return TestClient(app)


def test_rtsp_start_ingests_then_stop():
    journal = Journal(":memory:")
    client = _client(journal, frames=8)
    client.put("/zones", json={"zones": [{"name": "z",
               "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
               "required_ppe": ["helmet"]}]})

    r = client.post("/sources/rtsp", json={"url": "rtsp://x"})
    assert r.status_code == 200 and r.json()["running"] is True

    for _ in range(60):                          # attendre l'ingestion de quelques frames
        if journal.stats()["global"]["person_frames"] >= 1:
            break
        time.sleep(0.05)
    assert journal.stats()["global"]["person_frames"] >= 1

    assert client.delete("/sources/rtsp").json()["stopped"] is True
    assert client.get("/sources/rtsp").json()["running"] is False
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_rtsp_api.py -q` → FAIL (404).

- [ ] **Step 3: Écrire l'implémentation**

(a) `backend/app/api/schemas.py` — ajouter le modèle de corps :
```python
class RtspSource(BaseModel):
    url: str
```

(b) `backend/app/api/app.py` :

Ajouter aux imports :
```python
from app.api.schemas import FrameMessage, RtspSource, ZonesConfig, frame_response
from app.ingest.rtsp_worker import RtspWorker
```
*(fusionner `RtspSource` dans l'import existant de `app.api.schemas`.)*

Après `app.state.notifier = None`, initialiser l'état RTSP :
```python
    app.state.rtsp = None                # worker RTSP courant (un seul flux)
    app.state.rtsp_capture_factory = None  # None -> cv2.VideoCapture ; injecté en test
```

Ajouter les endpoints après le bloc `/reports/*` (avant le handler websocket) :
```python
    @app.post("/sources/rtsp")
    def start_rtsp(source: RtspSource) -> dict:
        if app.state.rtsp is not None:
            app.state.rtsp.stop()
        app.state.detector.reset()
        pipeline = FramePipeline(
            app.state.detector, app.state.zones_store.get_zones(), camera="rtsp")

        def handle(frame, ts):
            detections, result = pipeline.process(frame, ts)
            ingest_frame(app.state.journal, app.state.snapshots, app.state.notifier,
                         frame, detections, result, datetime.now(timezone.utc))

        factory = app.state.rtsp_capture_factory
        if factory is None:
            import cv2
            factory = cv2.VideoCapture
        worker = RtspWorker(source.url, handle, capture_factory=factory)
        worker.start()
        app.state.rtsp = worker
        return worker.status()

    @app.delete("/sources/rtsp")
    def stop_rtsp() -> dict:
        if app.state.rtsp is not None:
            app.state.rtsp.stop()
            app.state.rtsp = None
        return {"stopped": True}

    @app.get("/sources/rtsp")
    def rtsp_status() -> dict:
        return app.state.rtsp.status() if app.state.rtsp is not None else {"running": False}
```
*(`ingest_frame` est déjà importé depuis la Task 1.)*

- [ ] **Step 4: Lancer le test** — `cd backend && py -3 -m pytest tests/test_rtsp_api.py -q` → PASS (1).

- [ ] **Step 5: Commit**
```bash
git add backend/app/api/app.py backend/app/api/schemas.py backend/tests/test_rtsp_api.py
git commit -m "feat(backend): REST control for RTSP source (start/stop/status)"
```

---

### Task 4: Documentation — décision + README RTSP

**Files:**
- Modify: `docs/DECISIONS.md`, `README.md`

- [ ] **Step 1: Ajouter l'entrée `DECISIONS.md`** (en haut de la liste, après l'intro)
```markdown
## 2026-08-06 — RTSP : ingestion serveur headless, source unique (V1)
**Contexte.** Le cahier des charges demande « 1 RTSP ». Le navigateur ne lit pas le RTSP ;
le serveur doit tirer le flux. Le modèle YOLO + tracker est partagé et non concurrent-safe.
**Décision.** Worker serveur en thread (`cv2.VideoCapture`) qui alimente le pipeline via le
**sink partagé** (`ingest_frame`) → journal/preuves/notifications visibles dans le **dashboard**
(headless, pas de vidéo live). Contrôle REST (`/sources/rtsp`), **un seul flux à la fois**.
**Conséquence.** RTSP et la console live WS ne doivent pas tourner en même temps (tracks
mélangées) ; multi-caméras + vue annotée live = V2. Lectures du `Journal` verrouillées
(worker écrit / API lit, même connexion sqlite).
```

- [ ] **Step 2: Ajouter une section RTSP au README** (après « Lancer avec Docker »)
```markdown
## Flux RTSP (caméra IP)

Le backend peut ingérer un flux RTSP côté serveur (headless — résultats visibles dans le
dashboard). Un seul flux à la fois.

```bash
# démarrer
curl -X POST localhost:8000/sources/rtsp \
  -H 'content-type: application/json' -d '{"url":"rtsp://user:pass@camera/stream"}'
# statut / arrêt
curl localhost:8000/sources/rtsp
curl -X DELETE localhost:8000/sources/rtsp
```

Tester sans caméra réelle (MediaMTX + ffmpeg qui boucle une vidéo) :
```bash
ffmpeg -re -stream_loop -1 -i demo.mp4 -c copy -f rtsp rtsp://localhost:8554/cam
```
```

- [ ] **Step 3: Commit**
```bash
git add docs/DECISIONS.md README.md
git commit -m "docs: RTSP ingestion decision + README usage"
```

---

## Self-Review

**1. Couverture spec (RTSP) :** sink partagé `ingest_frame` ✅ (T1) ; Journal reads thread-safe
✅ (T1) ; refactor WS sur le sink ✅ (T1) ; `RtspWorker` ✅ (T2) ; endpoints start/stop/status +
état + capture injectable ✅ (T3) ; décision + README ✅ (T4). Zéro dépendance ✅. Source unique
+ headless documentés ✅.

**2. Placeholders :** aucun — sink, worker, endpoints, tests complets. Les éditions `app.py`
(T1 handler, T3 endpoints/état) et `journal.py` (T1 locks) sont ancrées sur le code existant.

**3. Cohérence des types :** `ingest_frame(journal, snapshots, notifier, frame, detections,
result, now)` (T1) appelé par le handler WS (T1) et par `handle` du worker (T3). `RtspWorker`
(T2) consommé par `POST /sources/rtsp` (T3) ; `capture_factory` injectable partagé entre worker
(T2) et test API (T3). `RtspSource.url` (T3) = corps du POST. `FramePipeline(..., camera="rtsp")`
réutilise l'API existante. Aucune signature de domaine modifiée.
```
