# P3-b — RGPD & preuves (snapshots floutés) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturer, à chaque infraction confirmée, un snapshot de la frame avec toutes les têtes floutées (côté serveur), le persister et l'exposer en REST.

**Architecture:** Nouveau package `app/evidence/` (floutage pur `redaction.py` + stockage `snapshots.py`), extension du `Journal` (colonne `snapshot` + `event()`), capture non bloquante au chemin WS, endpoint image.

**Tech Stack:** Python 3.13, FastAPI, OpenCV (`cv2`) + NumPy **déjà présents**, pytest.

## Global Constraints

- **Zéro nouvelle dépendance** — `cv2`/`numpy` déjà utilisés (`app/api/decode.py`).
- **Heuristique région-tête** : haut 30 % du bbox personne (bande `helmet` `(0.0, 0.30)`). Pas de détecteur de visage.
- **Floutage = pixelisation (mosaïque)** : resize down → up (`INTER_NEAREST`).
- **Aucune image non floutée n'est jamais écrite sur disque** : le seul chemin d'écriture passe par `blur_head_regions`.
- **Snapshot plein cadre**, un par frame à infraction, partagé par tous les events du frame ; nom `uuid4().hex + ".jpg"`.
- **Non bloquant** : blur + encode + disque via `run_in_threadpool` ; une panne de preuve ne tue pas le flux ni le journal.
- `SnapshotStore` injectable en test comme `journal`/`detector` (`ARGUS_SNAPSHOT_DIR`, défaut `snapshots/`).
- Rétro-compat : `record_event`/`record_frame` gardent un `snapshot=None` par défaut ; suite backend existante (**79**) reste verte.
- Interpréteur local : **`py -3`** (pas `python`). Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`**.

---

### Task 1: Floutage — `head_region` + `blur_head_regions`

**Files:**
- Create: `backend/app/evidence/__init__.py` (vide), `backend/app/evidence/redaction.py`
- Test: `backend/tests/test_redaction.py`

**Interfaces:**
- Consumes: `BBox` (`app.domain.types`).
- Produces: `head_region(bbox, band=(0.0, 0.30)) -> tuple[int,int,int,int]` ; `blur_head_regions(image, person_bboxes: list[BBox]) -> np.ndarray`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_redaction.py`

```python
from __future__ import annotations

import numpy as np

from app.domain.types import BBox
from app.evidence.redaction import blur_head_regions, head_region


def test_head_region_is_full_width_top_30pct():
    # bbox x 100..200, y 100..300 (hauteur 200) -> tête = y 100..160, pleine largeur
    assert head_region(BBox(100, 100, 200, 300)) == (100, 100, 200, 160)


def test_blur_changes_head_region_only():
    rng = np.random.default_rng(0)
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    img[100:160, 100:200] = rng.integers(0, 256, (60, 100, 3), dtype=np.uint8)
    low = img[250:260, 100:200].copy()
    out = blur_head_regions(img, [BBox(100, 100, 200, 300)])
    assert np.array_equal(out[250:260, 100:200], low)              # zone basse intacte
    assert not np.array_equal(out[100:160, 100:200], img[100:160, 100:200])  # tête pixelisée


def test_blur_ignores_degenerate_and_offscreen():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    out = blur_head_regions(img, [BBox(10, 10, 10, 10), BBox(500, 500, 600, 700)])
    assert out.shape == img.shape                                  # aucune exception
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_redaction.py -q`
Expected: FAIL (`ModuleNotFoundError: app.evidence.redaction`).

- [ ] **Step 3: Écrire l'implémentation**

`backend/app/evidence/__init__.py` : fichier vide.

`backend/app/evidence/redaction.py` :
```python
from __future__ import annotations

import cv2
import numpy as np

from app.domain.types import BBox

HEAD_BAND: tuple[float, float] = (0.0, 0.30)
_PIXEL_BLOCK = 16  # côté cible d'un bloc de mosaïque (px)


def head_region(bbox: BBox, band: tuple[float, float] = HEAD_BAND) -> tuple[int, int, int, int]:
    x1 = int(round(bbox.x1))
    x2 = int(round(bbox.x2))
    y1 = int(round(bbox.y1 + band[0] * bbox.height))
    y2 = int(round(bbox.y1 + band[1] * bbox.height))
    return (max(0, x1), max(0, y1), max(0, x2), max(0, y2))


def blur_head_regions(image: np.ndarray, person_bboxes: list[BBox]) -> np.ndarray:
    out = image.copy()
    h, w = out.shape[:2]
    for bbox in person_bboxes:
        x1, y1, x2, y2 = head_region(bbox)
        x2, y2 = min(x2, w), min(y2, h)
        if x2 - x1 <= 0 or y2 - y1 <= 0:
            continue
        roi = out[y1:y2, x1:x2]
        rh, rw = roi.shape[:2]
        small = cv2.resize(
            roi, (max(1, rw // _PIXEL_BLOCK), max(1, rh // _PIXEL_BLOCK)),
            interpolation=cv2.INTER_LINEAR)
        out[y1:y2, x1:x2] = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)
    return out
```

- [ ] **Step 4: Lancer le test** — `cd backend && py -3 -m pytest tests/test_redaction.py -q`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/evidence/__init__.py backend/app/evidence/redaction.py backend/tests/test_redaction.py
git commit -m "feat(backend): head-region pixelation blur (RGPD redaction)"
```

---

### Task 2: `SnapshotStore` — floute puis écrit un JPEG

**Files:**
- Create: `backend/app/evidence/snapshots.py`
- Test: `backend/tests/test_snapshots.py`

**Interfaces:**
- Consumes: `blur_head_regions` (Task 1), `BBox`.
- Produces: `SnapshotStore(directory)` ; `.save(image, person_bboxes) -> str` (nom de fichier) ; `.path(filename) -> str`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_snapshots.py`

```python
from __future__ import annotations

import cv2
import numpy as np

from app.domain.types import BBox
from app.evidence.snapshots import SnapshotStore


def test_save_writes_readable_jpeg_with_unique_names(tmp_path):
    store = SnapshotStore(str(tmp_path))
    img = np.full((200, 200, 3), 127, dtype=np.uint8)
    name = store.save(img, [BBox(50, 50, 150, 150)])
    assert name.endswith(".jpg")
    assert cv2.imread(store.path(name)) is not None      # JPEG relisible
    assert store.save(img, []) != name                   # noms uniques


def test_path_stays_inside_directory(tmp_path):
    store = SnapshotStore(str(tmp_path))
    import os
    assert store.path("../evil.jpg") == os.path.join(str(tmp_path), "evil.jpg")
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_snapshots.py -q`
Expected: FAIL (`ModuleNotFoundError: app.evidence.snapshots`).

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/evidence/snapshots.py`

```python
from __future__ import annotations

import os
import uuid

import cv2
import numpy as np

from app.domain.types import BBox
from app.evidence.redaction import blur_head_regions


class SnapshotStore:
    """Écrit des snapshots de preuve — toujours floutés — dans un dossier."""

    def __init__(self, directory: str):
        self._dir = directory
        os.makedirs(directory, exist_ok=True)

    def save(self, image: np.ndarray, person_bboxes: list[BBox]) -> str:
        blurred = blur_head_regions(image, person_bboxes)
        name = f"{uuid.uuid4().hex}.jpg"
        cv2.imwrite(os.path.join(self._dir, name), blurred)
        return name

    def path(self, filename: str) -> str:
        return os.path.join(self._dir, os.path.basename(filename))
```

- [ ] **Step 4: Lancer le test** — `cd backend && py -3 -m pytest tests/test_snapshots.py -q`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add backend/app/evidence/snapshots.py backend/tests/test_snapshots.py
git commit -m "feat(backend): SnapshotStore — blurred evidence JPEG writer"
```

---

### Task 3: `Journal` — colonne `snapshot` + `event()`

**Files:**
- Modify: `backend/app/persistence/journal.py`
- Test: `backend/tests/test_journal.py` (ajouts)

**Interfaces:**
- Produces: `record_event(event, ts, snapshot=None)` ; `record_frame(result, now, snapshot=None)` ; `events()` inclut `"snapshot"` ; `event(event_id) -> dict | None`.

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `backend/tests/test_journal.py`

```python
def test_record_event_stores_snapshot():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30), snapshot="abc.jpg")
    assert j.events()[0]["snapshot"] == "abc.jpg"


def test_event_lookup_by_id():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30), snapshot="abc.jpg")
    row_id = j.events()[0]["id"]
    assert j.event(row_id)["snapshot"] == "abc.jpg"
    assert j.event(9999) is None


def test_record_frame_attaches_snapshot():
    j = Journal(":memory:")
    result = FrameResult(results=[_cr(1, "Z", False, ["helmet"])],
                         events=[_ev(1, "Z", ["helmet"])])
    j.record_frame(result, _ts(30), snapshot="snap.jpg")
    assert j.events()[0]["snapshot"] == "snap.jpg"
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_journal.py -q`
Expected: FAIL (`record_event() got an unexpected keyword argument 'snapshot'`).

- [ ] **Step 3: Écrire l'implémentation** — éditer `backend/app/persistence/journal.py`

(a) Ajouter la colonne dans `_SCHEMA` (table `events`) — remplacer :
```python
    track_id INTEGER NOT NULL,
    missing TEXT NOT NULL
);
```
par :
```python
    track_id INTEGER NOT NULL,
    missing TEXT NOT NULL,
    snapshot TEXT
);
```

(b) Migration défensive dans `__init__` — remplacer :
```python
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
```
par :
```python
        self._conn.executescript(_SCHEMA)
        try:
            self._conn.execute("ALTER TABLE events ADD COLUMN snapshot TEXT")
        except sqlite3.OperationalError:
            pass  # colonne déjà présente (DB créée avant P3-b)
        self._conn.commit()
```

(c) `record_event` — remplacer toute la méthode par :
```python
    def record_event(self, event: ViolationEvent, ts: datetime,
                     snapshot: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, stream_ts, camera, zone, track_id, missing, snapshot) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ts.isoformat(), event.timestamp, event.camera, event.zone,
                 event.track_id, json.dumps(sorted(event.missing)), snapshot),
            )
            self._conn.commit()
```

(d) `record_frame` — remplacer la signature et la boucle d'events :
```python
    def record_frame(self, result: FrameResult, now: datetime,
                     snapshot: str | None = None) -> None:
        for event in result.events:
            self.record_event(event, now, snapshot)
```
(le reste de `record_frame` — bucket + observations — est inchangé.)

(e) `events()` — inclure `snapshot`. Remplacer le `SELECT ... FROM events` par (ajout de `snapshot` à la liste des colonnes) :
```python
        rows = self._conn.execute(
            f"SELECT id, ts, stream_ts, camera, zone, track_id, missing, snapshot FROM events"
            f"{where} ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, int(offset)),
        ).fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "stream_ts": r["stream_ts"],
             "camera": r["camera"], "zone": r["zone"], "track_id": r["track_id"],
             "missing": json.loads(r["missing"]), "snapshot": r["snapshot"]}
            for r in rows
        ]
```

(f) Ajouter la méthode `event()` juste après `events()` :
```python
    def event(self, event_id: int) -> dict | None:
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

- [ ] **Step 4: Lancer le test** — `cd backend && py -3 -m pytest tests/test_journal.py -q`
Expected: PASS (11 : 8 P3-a + 3 nouveaux).

- [ ] **Step 5: Commit**

```bash
git add backend/app/persistence/journal.py backend/tests/test_journal.py
git commit -m "feat(backend): Journal — snapshot column + event() lookup"
```

---

### Task 4: Capture WS non bloquante + isolation snapshots

**Files:**
- Modify: `backend/app/api/app.py`, `backend/tests/conftest.py`, `backend/.gitignore`
- Test: `backend/tests/test_persistence_ws.py` (ajout)

**Interfaces:**
- Consumes: `SnapshotStore` (T2), `Journal.record_frame(..., snapshot)` (T3).
- Produces: `app.state.snapshots` (défaut `None`, ouvert au `lifespan`, injectable) ; le handler `/ws/stream` capture un snapshot flouté quand `result.events`.

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `backend/tests/test_persistence_ws.py`

Ajouter l'import en tête du fichier :
```python
import numpy as np

from app.evidence.snapshots import SnapshotStore
```

Ajouter le test :
```python
def test_ws_captures_blurred_snapshot(tmp_path):
    journal = Journal(":memory:")
    app = create_app()
    app.state.detector = _StubDetector(
        [Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)])
    app.state.decode = lambda b64: np.zeros((480, 640, 3), dtype=np.uint8)
    app.state.journal = journal
    app.state.snapshots = SnapshotStore(str(tmp_path))
    client = TestClient(app)
    client.put("/zones", json={"zones": [{"name": "z",
               "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
               "required_ppe": ["helmet"]}]})
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "F", "timestamp": 0.0}); ws.receive_json()
        ws.send_json({"frame": "F", "timestamp": 3.5}); ws.receive_json()
    ev = journal.events()
    assert len(ev) == 1
    assert ev[0]["snapshot"] is not None
    assert (tmp_path / ev[0]["snapshot"]).exists()   # fichier de preuve écrit
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_persistence_ws.py -q`
Expected: FAIL (`snapshot` reste `None` — le handler ne capture pas encore).

- [ ] **Step 3: Écrire l'implémentation**

(a) `backend/tests/conftest.py` — remplacer par :
```python
import pytest


@pytest.fixture(autouse=True)
def _ephemeral_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGUS_DB_PATH", ":memory:")
    monkeypatch.setenv("ARGUS_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
```

(b) `backend/.gitignore` — ajouter une ligne :
```
snapshots/
```

(c) `backend/app/api/app.py` :

Dans `lifespan`, après le bloc `journal`, ajouter :
```python
        if app.state.snapshots is None:
            from app.evidence.snapshots import SnapshotStore

            app.state.snapshots = SnapshotStore(
                os.environ.get("ARGUS_SNAPSHOT_DIR", "snapshots"))
```

Après `app.state.journal = None`, ajouter l'init d'état :
```python
    app.state.snapshots = None           # remplacé par un SnapshotStore(tmp) dans les tests
```

Dans le handler `/ws/stream`, remplacer le bloc de persistance existant :
```python
                try:
                    await run_in_threadpool(
                        app.state.journal.record_frame, result, datetime.now(timezone.utc))
                except Exception:
                    pass  # une panne de persistance ne doit pas tuer le flux live
                await ws.send_json(frame_response(detections, result))
```
par :
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
                await ws.send_json(frame_response(detections, result))
```

- [ ] **Step 4: Lancer les tests** — `cd backend && py -3 -m pytest tests/test_persistence_ws.py tests/test_api.py -q`
Expected: PASS (le nouveau test de snapshot + les tests WS existants restent verts : quand la frame décodée est une chaîne — anciens tests — le `save` échoue silencieusement, `snapshot=None`, le journal est quand même écrit).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/app.py backend/tests/conftest.py backend/tests/test_persistence_ws.py backend/.gitignore
git commit -m "feat(backend): capture blurred evidence snapshot on WS violation"
```

---

### Task 5: Endpoint `GET /events/{event_id}/snapshot`

**Files:**
- Modify: `backend/app/api/app.py`
- Test: `backend/tests/test_snapshot_api.py`

**Interfaces:**
- Consumes: `Journal.event()` (T3), `SnapshotStore.path()` (T2).
- Produces: `GET /events/{event_id}/snapshot` → image JPEG ou 404. (`GET /events` inclut déjà `snapshot` depuis T3.)

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_snapshot_api.py`

```python
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, ViolationEvent
from app.evidence.snapshots import SnapshotStore
from app.persistence.journal import Journal


def _client(journal, snapshots):
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    app.state.snapshots = snapshots
    return TestClient(app)


def _ev(track_id, zone, missing):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=0.0, camera="cam-1")


def test_get_event_snapshot_served_and_404(tmp_path):
    journal = Journal(":memory:")
    snapshots = SnapshotStore(str(tmp_path))
    name = snapshots.save(np.full((100, 100, 3), 127, dtype=np.uint8), [BBox(10, 10, 90, 90)])
    journal.record_event(_ev(1, "Z", ["helmet"]),
                         datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc), snapshot=name)
    client = _client(journal, snapshots)

    row = client.get("/events").json()["events"][0]
    assert row["snapshot"] == name

    ok = client.get(f"/events/{row['id']}/snapshot")
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/jpeg"

    assert client.get("/events/9999/snapshot").status_code == 404


def test_get_snapshot_404_when_event_has_none(tmp_path):
    journal = Journal(":memory:")
    journal.record_event(_ev(2, "Z", ["mask"]),
                         datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc))  # pas de snapshot
    client = _client(journal, SnapshotStore(str(tmp_path)))
    row = client.get("/events").json()["events"][0]
    assert client.get(f"/events/{row['id']}/snapshot").status_code == 404
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_snapshot_api.py -q`
Expected: FAIL (404 sur la route servie — endpoint absent).

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/api/app.py`

Ajouter aux imports :
```python
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
```
(remplacer la ligne `from fastapi import FastAPI, WebSocket, WebSocketDisconnect` et ajouter l'import `FileResponse`.)

Ajouter l'endpoint après `get_stats` (avant le handler websocket) :
```python
    @app.get("/events/{event_id}/snapshot")
    def get_event_snapshot(event_id: int):
        event = app.state.journal.event(event_id)
        if event is None or event["snapshot"] is None:
            raise HTTPException(status_code=404, detail="snapshot introuvable")
        path = app.state.snapshots.path(event["snapshot"])
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="fichier snapshot absent")
        return FileResponse(path, media_type="image/jpeg")
```

- [ ] **Step 4: Lancer le test** — `cd backend && py -3 -m pytest tests/test_snapshot_api.py -q`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/app.py backend/tests/test_snapshot_api.py
git commit -m "feat(backend): GET /events/{id}/snapshot — serve blurred evidence"
```

---

### Task 6: Journal de décisions (RGPD)

**Files:**
- Modify: `docs/DECISIONS.md`

**Interfaces:** aucune (documentation).

- [ ] **Step 1: Ajouter l'entrée** en haut de la liste dans `docs/DECISIONS.md`, juste après la ligne de titre/intro et **avant** l'entrée `## 2026-07-29 — P3-a : sémantique temps ...` :

```markdown
## 2026-08-01 — P3-b : floutage RGPD par heuristique région-tête (pas de détecteur de visage)
**Contexte.** Le floutage des preuves exige de localiser la tête, mais le modèle n'a pas de
classe tête/visage. Un détecteur de visage (Haar/DNN) échoue précisément sur casque, angle
et occlusion — le cas industriel.
**Décision.** Flouter par **pixelisation** le **haut 30 % du bbox de chaque personne** (bande
`helmet` de `association.py`). Zéro dépendance, robuste, **garantit** le floutage. Snapshot
plein cadre, écrit uniquement après floutage (aucune image nette sur disque).
**Conséquence.** Sur-floutage léger accepté (côté sûr RGPD). Un vrai détecteur tête/visage
reste envisageable en V2 via l'active-learning.
```

- [ ] **Step 2: Commit**

```bash
git add docs/DECISIONS.md
git commit -m "docs: decision log (P3-b RGPD head-region blur heuristic)"
```

---

## Self-Review

**1. Couverture spec (P3-b) :** floutage région-tête par pixelisation ✅ (T1) ; `SnapshotStore` écrit un JPEG flouté ✅ (T2) ; colonne `snapshot` + `event()` + params ✅ (T3) ; capture WS non bloquante + injection + isolation tests ✅ (T4) ; `GET /events/{id}/snapshot` + `snapshot` dans `GET /events` ✅ (T5, T3) ; décision documentée ✅ (T6). Zéro nouvelle dépendance ✅. « Aucune image nette écrite » ✅ (seul chemin d'écriture = `SnapshotStore.save` → `blur_head_regions`).

**2. Placeholders :** aucun — code complet (floutage, store, requêtes SQL, endpoint, tests). Les modifs de `journal.py` (T3) et `app.py` (T4-T5) sont des éditions ciblées avec ancrage exact sur le code P3-a existant.

**3. Cohérence des types :** `BBox` (domaine) → `head_region`/`blur_head_regions` (T1) → `SnapshotStore.save` (T2) → handler WS (T4). `snapshot: str | None` traverse `record_event`/`record_frame`/`events`/`event` (T3), le handler WS (T4) et l'endpoint (T5) de façon cohérente. `app.state.snapshots` injecté comme `app.state.journal`/`detector`. Rétro-compat : `snapshot=None` par défaut → les tests et appels P3-a inchangés.
```
