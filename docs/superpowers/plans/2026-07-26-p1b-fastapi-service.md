# P1b — Service FastAPI (WS + REST) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exposer le pipeline de conformité (P1a) via un service FastAPI : WebSocket d'inférence temps réel + REST de config des zones.

**Architecture:** Une couche `app/api/` au-dessus de `app.pipeline`/`app.domain` (inchangés). Modèle chargé une fois au démarrage (état applicatif). Zones en mémoire, réglables par REST. Chaque connexion WS = un `FramePipeline` neuf (tracking + debounce du flux).

**Tech Stack:** FastAPI, Pydantic v2, Uvicorn ; OpenCV pour décoder les frames ; `FramePipeline` existant.

## Global Constraints

- Python ≥ 3.10 ; chaque module commence par `from __future__ import annotations`.
- **`app.domain` et `app.pipeline` NE DOIVENT PAS être modifiés** — P1b n'ajoute que `app/api/`.
- Taxonomie EPI (verbatim) : `{helmet, safety-vest, mask, shoes}` (= `PPE_CLASSES`).
- **Les tests ne doivent PAS importer `ultralytics`** (détecteur remplacé par un stub via `app.state.detector`) ni exiger le vrai modèle. Les **tests de l'API ne doivent PAS exiger OpenCV** (décodage remplacé par un stub via `app.state.decode`) ; seul `test_decode.py` importe `cv2`.
- Pydantic **v2** (`field_validator`, `.model_dump()`).
- Lancer les tests avec `py -m pytest` depuis `backend/`.
- Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`**.

Interfaces du domaine consommées (existantes, ne pas redéfinir) — `app/domain/types.py` :
- `Detection(cls: str, bbox: BBox, confidence: float, track_id: int | None)` ; `BBox(x1,y1,x2,y2)`.
- `Zone(name: str, polygon: tuple[tuple[float,float],...], required_ppe: frozenset[str])`.
- `ComplianceResult(track_id, zone, required, present, missing, compliant)` ; `ViolationEvent(track_id, zone, missing, timestamp, camera)` ; `FrameResult(results, events)` ; `PPE_CLASSES`.
- `app/pipeline.py` : `FramePipeline(detector, zones).process(frame, timestamp) -> (list[Detection], FrameResult)`.

---

### Task 1: Schémas API + dépendances + CI

**Files:**
- Create: `backend/app/api/__init__.py` (vide)
- Create: `backend/app/api/schemas.py`
- Create: `backend/requirements-dev.txt`
- Modify: `backend/requirements.txt` (ajouter fastapi, uvicorn)
- Modify: `.github/workflows/tests.yml` (installer les deps de test pour le job backend)
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Consumes: `app.domain.types.{Zone, Detection, ComplianceResult, ViolationEvent, FrameResult, PPE_CLASSES}`.
- Produces: `ZoneModel`, `ZonesConfig`, `FrameMessage` (Pydantic) ; `frame_response(detections, result) -> dict` ; `ZoneModel.to_domain()`, `ZoneModel.from_domain(zone)`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_schemas.py`

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.types import BBox, ComplianceResult, Detection, FrameResult, ViolationEvent, Zone
from app.api.schemas import FrameMessage, ZoneModel, ZonesConfig, frame_response


def test_zone_model_roundtrip_to_domain():
    zm = ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]], required_ppe=["helmet"])
    zone = zm.to_domain()
    assert isinstance(zone, Zone)
    assert zone.name == "z"
    assert zone.polygon == ((0, 0), (10, 0), (10, 10))
    assert zone.required_ppe == frozenset({"helmet"})
    back = ZoneModel.from_domain(zone)
    assert back.required_ppe == ["helmet"]


def test_zone_model_rejects_short_polygon():
    with pytest.raises(ValidationError):
        ZoneModel(name="z", polygon=[[0, 0], [10, 0]], required_ppe=["helmet"])


def test_zone_model_rejects_unknown_ppe():
    with pytest.raises(ValidationError):
        ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]], required_ppe=["banana"])


def test_frame_response_serializes_all_parts():
    det = Detection("person", BBox(1, 2, 3, 4), 0.9, track_id=7)
    res = ComplianceResult(7, "z", frozenset({"helmet"}), frozenset(), frozenset({"helmet"}), False)
    evt = ViolationEvent(7, "z", frozenset({"helmet"}), 5.0, "cam-1")
    out = frame_response([det], FrameResult(results=[res], events=[evt]))
    assert out["detections"] == [{"cls": "person", "bbox": [1.0, 2.0, 3.0, 4.0], "confidence": 0.9, "track_id": 7}]
    assert out["results"][0] == {"track_id": 7, "zone": "z", "required": ["helmet"],
                                 "present": [], "missing": ["helmet"], "compliant": False}
    assert out["events"][0] == {"track_id": 7, "zone": "z", "missing": ["helmet"],
                                "timestamp": 5.0, "camera": "cam-1"}


def test_frame_message_parses():
    msg = FrameMessage(frame="abc", timestamp=1.5)
    assert msg.frame == "abc" and msg.timestamp == 1.5
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api'` (ou `fastapi`/`pydantic` absent).

- [ ] **Step 3: Écrire l'implémentation minimale**

`backend/requirements-dev.txt` :
```
pytest
fastapi
httpx
opencv-python-headless
numpy
```

Ajouter à `backend/requirements.txt` (après `numpy`) :
```
fastapi
uvicorn[standard]
```

`.github/workflows/tests.yml` — remplacer l'étape `Install pytest` et l'étape backend par :
```yaml
      - name: Install backend test deps
        run: pip install --quiet -r backend/requirements-dev.txt

      - name: Backend tests (domain + inference + pipeline + api)
        run: python -m pytest -q
        working-directory: backend

      - name: Install pytest (data)
        run: pip install --quiet pytest

      - name: Data pipeline tests (remap / convert / fuse)
        run: python -m pytest -q
        working-directory: data
```

`backend/app/api/__init__.py` : fichier vide.

`backend/app/api/schemas.py` :
```python
from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.domain.types import (
    ComplianceResult,
    Detection,
    FrameResult,
    PPE_CLASSES,
    ViolationEvent,
    Zone,
)


class ZoneModel(BaseModel):
    name: str
    polygon: list[tuple[float, float]]
    required_ppe: list[str]

    @field_validator("polygon")
    @classmethod
    def _min_three_points(cls, v: list) -> list:
        if len(v) < 3:
            raise ValueError("polygon must have at least 3 points")
        return v

    @field_validator("required_ppe")
    @classmethod
    def _known_ppe(cls, v: list) -> list:
        unknown = set(v) - PPE_CLASSES
        if unknown:
            raise ValueError(f"unknown PPE classes: {sorted(unknown)}")
        return v

    def to_domain(self) -> Zone:
        return Zone(self.name, tuple(tuple(p) for p in self.polygon), frozenset(self.required_ppe))

    @classmethod
    def from_domain(cls, zone: Zone) -> "ZoneModel":
        return cls(
            name=zone.name,
            polygon=[list(p) for p in zone.polygon],
            required_ppe=sorted(zone.required_ppe),
        )


class ZonesConfig(BaseModel):
    zones: list[ZoneModel]


class FrameMessage(BaseModel):
    frame: str  # JPEG encodé en base64
    timestamp: float


def _detection_to_dict(d: Detection) -> dict:
    return {"cls": d.cls, "bbox": [d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2],
            "confidence": d.confidence, "track_id": d.track_id}


def _result_to_dict(r: ComplianceResult) -> dict:
    return {"track_id": r.track_id, "zone": r.zone, "required": sorted(r.required),
            "present": sorted(r.present), "missing": sorted(r.missing), "compliant": r.compliant}


def _event_to_dict(e: ViolationEvent) -> dict:
    return {"track_id": e.track_id, "zone": e.zone, "missing": sorted(e.missing),
            "timestamp": e.timestamp, "camera": e.camera}


def frame_response(detections: list[Detection], result: FrameResult) -> dict:
    return {
        "detections": [_detection_to_dict(d) for d in detections],
        "results": [_result_to_dict(r) for r in result.results],
        "events": [_event_to_dict(e) for e in result.events],
    }
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_schemas.py -v` (installer d'abord `pip install -r requirements-dev.txt` en local si besoin)
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/__init__.py backend/app/api/schemas.py backend/tests/test_schemas.py backend/requirements.txt backend/requirements-dev.txt .github/workflows/tests.yml
git commit -m "feat(api): pydantic schemas + domain serialization; wire CI test deps"
```

---

### Task 2: ZonesStore

**Files:**
- Create: `backend/app/api/zones_store.py`
- Test: `backend/tests/test_zones_store.py`

**Interfaces:**
- Consumes: `ZoneModel`, `ZonesConfig` (Task 1) ; `app.domain.types.Zone`.
- Produces: `ZonesStore()` avec `.get_zones() -> list[Zone]`, `.set_from_config(config: ZonesConfig)`, `.to_config() -> ZonesConfig`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_zones_store.py`

```python
from __future__ import annotations

from app.api.schemas import ZoneModel, ZonesConfig
from app.api.zones_store import ZonesStore
from app.domain.types import Zone


def test_store_starts_empty():
    assert ZonesStore().get_zones() == []


def test_set_from_config_produces_domain_zones():
    store = ZonesStore()
    config = ZonesConfig(zones=[ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]],
                                          required_ppe=["helmet"])])
    store.set_from_config(config)
    zones = store.get_zones()
    assert len(zones) == 1
    assert isinstance(zones[0], Zone)
    assert zones[0].required_ppe == frozenset({"helmet"})


def test_to_config_roundtrips():
    store = ZonesStore()
    config = ZonesConfig(zones=[ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]],
                                          required_ppe=["helmet", "mask"])])
    store.set_from_config(config)
    out = store.to_config()
    assert out.zones[0].name == "z"
    assert out.zones[0].required_ppe == ["helmet", "mask"]
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_zones_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.zones_store'`.

- [ ] **Step 3: Écrire l'implémentation minimale** — `backend/app/api/zones_store.py`

```python
from __future__ import annotations

from app.api.schemas import ZoneModel, ZonesConfig
from app.domain.types import Zone


class ZonesStore:
    """Détient la config de zones en mémoire (reset au redémarrage ; persistance = P3)."""

    def __init__(self, zones: list[Zone] | None = None):
        self._zones: list[Zone] = list(zones) if zones else []

    def get_zones(self) -> list[Zone]:
        return list(self._zones)

    def set_from_config(self, config: ZonesConfig) -> None:
        self._zones = [zm.to_domain() for zm in config.zones]

    def to_config(self) -> ZonesConfig:
        return ZonesConfig(zones=[ZoneModel.from_domain(z) for z in self._zones])
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_zones_store.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/zones_store.py backend/tests/test_zones_store.py
git commit -m "feat(api): in-memory ZonesStore (config <-> domain zones)"
```

---

### Task 3: Décodage des frames

**Files:**
- Create: `backend/app/api/decode.py`
- Test: `backend/tests/test_decode.py`

**Interfaces:**
- Produces: `decode_frame(b64: str) -> np.ndarray` (image BGR OpenCV) ; lève `ValueError` si base64 invalide ou image illisible.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_decode.py`

```python
from __future__ import annotations

import base64

import cv2
import numpy as np
import pytest

from app.api.decode import decode_frame


def _tiny_jpeg_b64() -> str:
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return base64.b64encode(buf.tobytes()).decode("ascii")


def test_decode_frame_returns_image():
    img = decode_frame(_tiny_jpeg_b64())
    assert img.shape == (8, 8, 3)


def test_decode_frame_rejects_bad_base64():
    with pytest.raises(ValueError):
        decode_frame("not@@base64")


def test_decode_frame_rejects_non_image_bytes():
    # base64 valide mais pas une image
    b64 = base64.b64encode(b"hello world not an image").decode("ascii")
    with pytest.raises(ValueError):
        decode_frame(b64)
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_decode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.decode'`.

- [ ] **Step 3: Écrire l'implémentation minimale** — `backend/app/api/decode.py`

```python
from __future__ import annotations

import base64

import cv2
import numpy as np


def decode_frame(b64: str) -> np.ndarray:
    """Décode une frame JPEG encodée en base64 vers une image BGR OpenCV.

    Lève ValueError si le base64 est invalide ou si l'image est illisible.
    """
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as exc:
        raise ValueError("base64 invalide") from exc
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("frame illisible (décodage image échoué)")
    return img
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_decode.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/decode.py backend/tests/test_decode.py
git commit -m "feat(api): base64 -> OpenCV frame decoder"
```

---

### Task 4: App FastAPI (REST + WebSocket)

**Files:**
- Create: `backend/app/api/app.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `frame_response`, `ZonesConfig`, `FrameMessage` (Task 1) ; `ZonesStore` (Task 2) ; `decode_frame` (Task 3) ; `FramePipeline` ; `PPEDetector`.
- Produces: `create_app() -> FastAPI` avec `GET /health`, `GET /zones`, `PUT /zones`, `WS /ws/stream`. Le détecteur et le décodeur vivent dans `app.state` (`app.state.detector`, `app.state.decode`) — les tests les remplacent par des stubs.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_api.py`

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, Detection


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets


def _client(detector):
    app = create_app()
    app.state.detector = detector           # évite le chargement du vrai modèle au démarrage
    app.state.decode = lambda b64: b64      # bypass OpenCV : la frame "décodée" = la chaîne
    return TestClient(app)


def test_health_reports_model_loaded():
    resp = _client(_StubDetector([])).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "model_loaded": True}


def test_put_then_get_zones_roundtrip():
    client = _client(_StubDetector([]))
    payload = {"zones": [{"name": "z", "polygon": [[0, 0], [10, 0], [10, 10]],
                          "required_ppe": ["helmet"]}]}
    assert client.put("/zones", json=payload).status_code == 200
    got = client.get("/zones").json()
    assert got["zones"][0]["name"] == "z"
    assert got["zones"][0]["required_ppe"] == ["helmet"]


def test_put_zones_rejects_bad_polygon():
    client = _client(_StubDetector([]))
    payload = {"zones": [{"name": "z", "polygon": [[0, 0], [10, 0]], "required_ppe": ["helmet"]}]}
    assert client.put("/zones", json=payload).status_code == 422


def test_ws_stream_returns_compliance():
    person = Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)
    client = _client(_StubDetector([person]))
    client.put("/zones", json={"zones": [{"name": "z", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
                                          "required_ppe": ["helmet"]}]})
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "FAKE", "timestamp": 0.0})
        msg = ws.receive_json()
    assert msg["detections"][0]["cls"] == "person"
    assert msg["results"][0]["compliant"] is False
    assert msg["results"][0]["missing"] == ["helmet"]


def test_ws_invalid_frame_returns_error_without_closing():
    person = Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)
    client = _client(_StubDetector([person]))
    client.put("/zones", json={"zones": [{"name": "z", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
                                          "required_ppe": ["helmet"]}]})
    app = client.app

    def _bad_decode(b64):
        raise ValueError("frame illisible")

    with client.websocket_connect("/ws/stream") as ws:
        app.state.decode = _bad_decode
        ws.send_json({"frame": "BAD", "timestamp": 0.0})
        assert "error" in ws.receive_json()
        # la connexion reste ouverte : une frame valide ensuite est traitée normalement
        app.state.decode = lambda b64: b64
        ws.send_json({"frame": "OK", "timestamp": 1.0})
        msg = ws.receive_json()
    assert msg["detections"][0]["cls"] == "person"


def test_ws_malformed_json_returns_error_without_closing():
    client = _client(_StubDetector([]))
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_text("this is not json")          # receive_json -> JSONDecodeError (ValueError)
        assert "error" in ws.receive_json()
        # la connexion reste ouverte : un message JSON valide ensuite reçoit une réponse normale
        ws.send_json({"frame": "OK", "timestamp": 0.0})
        msg = ws.receive_json()
    assert "detections" in msg
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.app'`.

- [ ] **Step 3: Écrire l'implémentation minimale** — `backend/app/api/app.py`

```python
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.api.decode import decode_frame
from app.api.schemas import FrameMessage, ZonesConfig, frame_response
from app.api.zones_store import ZonesStore
from app.pipeline import FramePipeline


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # les tests pré-injectent un stub -> on saute le chargement du vrai modèle
        if app.state.detector is None:
            from app.inference.detector import PPEDetector

            path = os.environ.get("ARGUS_MODEL_PATH", "best.pt")
            app.state.detector = PPEDetector.from_path(path)
        yield

    app = FastAPI(title="Argus", lifespan=lifespan)
    app.state.zones_store = ZonesStore()
    app.state.detector = None            # remplacé par un stub dans les tests
    app.state.decode = decode_frame

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_loaded": app.state.detector is not None}

    @app.get("/zones")
    def get_zones() -> ZonesConfig:
        return app.state.zones_store.to_config()

    @app.put("/zones")
    def put_zones(config: ZonesConfig) -> ZonesConfig:
        app.state.zones_store.set_from_config(config)
        return app.state.zones_store.to_config()

    @app.websocket("/ws/stream")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        app.state.detector.reset()  # nouveau flux : réinitialise le tracker
        pipeline = FramePipeline(app.state.detector, app.state.zones_store.get_zones())
        try:
            while True:
                try:
                    data = await ws.receive_json()  # json.loads -> ValueError (JSONDecodeError) si non-JSON
                    msg = FrameMessage(**data)
                    frame = app.state.decode(msg.frame)
                except (ValidationError, ValueError) as exc:
                    await ws.send_json({"error": str(exc)})
                    continue
                try:
                    detections, result = pipeline.process(frame, msg.timestamp)
                except Exception as exc:  # une frame défaillante ne doit pas tuer le flux
                    await ws.send_json({"error": str(exc)})
                    continue
                await ws.send_json(frame_response(detections, result))
        except WebSocketDisconnect:
            return

    return app
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_api.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Lancer la suite backend complète**

Run: `cd backend && py -m pytest -q`
Expected: tous verts (domaine + inférence + pipeline + api).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/app.py backend/tests/test_api.py
git commit -m "feat(api): FastAPI app with health, zones REST, and WS inference stream"
```

---

## Self-Review

**1. Couverture spec :** WS d'inférence ✅ (Task 4), REST zones GET/PUT + validation 422 ✅ (Task 4, schémas Task 1), health ✅, modèle chargé au démarrage ✅ (Task 4, sauté si stub), V1 mono-flux ✅ (un pipeline par connexion), erreurs (frame illisible / zones invalides) ✅. Hors périmètre (persistance, notifications, RGPD) : non présent ✅.

**2. Placeholders :** aucun — code complet à chaque étape.

**3. Cohérence des types :** `ZoneModel.to_domain -> Zone` (Task 1) consommé par `ZonesStore.set_from_config` (Task 2) ; `frame_response(list[Detection], FrameResult) -> dict` (Task 1) consommé par le WS (Task 4) ; `FramePipeline(detector, zones).process(frame, ts) -> (list[Detection], FrameResult)` (P1a) appelé en Task 4 ; `decode_frame(str) -> np.ndarray` (Task 3) branché via `app.state.decode` (Task 4). Cohérent.

**4. Contrainte tests légers :** `test_schemas`/`test_zones_store` = Pydantic seul ; `test_api` = FastAPI + stub détecteur + stub décodeur (ni ultralytics ni OpenCV) ; `test_decode` = seul à importer `cv2`. La CI installe `requirements-dev.txt` (fastapi/httpx/opencv-headless/numpy/pytest), **sans ultralytics** → CI rapide.

---

## Ajustements post-revue (appliqués après exécution)

Corrections issues des revues (par tâche + revue finale de branche), au-delà du plan initial :

1. **Placement de `receive_json()` (fix WS JSON malformé)** — `receive_json()` déplacé *dans* le `try` interne : un JSON malformé lève `json.JSONDecodeError` (sous-classe de `ValueError`) désormais capturé → `{"error": ...}` sans fermer la connexion. Tests renforcés (`test_ws_invalid_frame_...`, `test_ws_malformed_json_...`) pour prouver la continuité par un aller-retour valide ensuite.
2. **Reset du tracker par connexion (touche `app.inference`, décision utilisateur)** — ajout de `PPEDetector.reset()` : passe le prochain `detect()` en `persist=False` (le tracker Ultralytics repart de zéro) puis reprend en `persist=True`. Appelé au `ws.accept()`. Les stubs de test exposent un `reset()` no-op. Tests : `test_ppedetector_persists_tracking_by_default`, `test_ppedetector_reset_forces_new_stream_once`.
3. **Robustesse flux (wrapper défensif)** — `pipeline.process(...)` entouré d'un `try/except Exception` : une frame défaillante renvoie `{"error": ...}` et le flux continue au lieu de tomber. Test : `test_ws_pipeline_error_returns_error_without_closing`.

Suite finale : **65 tests, sortie pristine**. Hors périmètre (→ P3) : cap taille de frame, auth, CORS, persistance.
