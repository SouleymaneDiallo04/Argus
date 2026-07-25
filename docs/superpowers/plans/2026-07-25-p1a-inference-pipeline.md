# P1a — Pipeline d'inférence & validation vidéo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brancher le modèle YOLOv8 entraîné au moteur de conformité déjà écrit, et prouver le end-to-end sur une vidéo (sans frontend).

**Architecture:** Une couche `inference` convertit les sorties YOLO (Ultralytics `.track()`, tracking ByteTrack inclus) en objets `Detection` du domaine. Un `FramePipeline` orchestre frame → détections → `ComplianceEngine.process_frame` → `FrameResult`. Un script `run_video.py` fait tourner le tout sur une vidéo avec overlays et journal d'infractions.

**Tech Stack:** Python 3.10+, Ultralytics YOLO (inférence + ByteTrack), OpenCV (I/O vidéo + overlays), le moteur de domaine pur existant (`app.domain`).

## Global Constraints

- Python ≥ 3.10 ; chaque module commence par `from __future__ import annotations`.
- **La couche `app.domain` est PURE et NE DOIT PAS être modifiée** — P1a n'AJOUTE qu'une couche autour d'elle.
- Type d'entrée du moteur : `Detection(cls: str, bbox: BBox, confidence: float, track_id: int | None)` ; `BBox(x1, y1, x2, y2)`.
- Carte des classes du modèle (ordre du data.yaml d'entraînement) : `{0: person, 1: helmet, 2: safety-vest, 3: mask, 4: shoes}`.
- **Les tests unitaires ne doivent PAS dépendre de `ultralytics` ni d'`opencv`** (utiliser des faux/stubs) ; seul `run_video.py` les importe réellement.
- Imports via le package `app.` (ex. `from app.domain.types import Detection`), comme le moteur existant.
- Lancer les tests avec `py -m pytest` depuis `backend/` (le `python` nu est un stub Windows Store).
- Commits : préfixe conventionnel, en anglais, **sans ligne `Co-Authored-By`**.

---

### Task 1: Carte des classes + conversion des détections (pur)

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/inference/__init__.py`
- Create: `backend/app/inference/detector.py`
- Test: `backend/tests/test_detector.py`

**Interfaces:**
- Consumes: `app.domain.types.Detection`, `app.domain.types.BBox`.
- Produces: `ARGUS_CLASSES: dict[int, str]` (dans `app/config.py`) ; `to_detections(xyxy, cls_ids, confs, track_ids, names) -> list[Detection]` (dans `app/inference/detector.py`).

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_detector.py`

```python
from __future__ import annotations

from app.config import ARGUS_CLASSES
from app.domain.types import BBox, Detection
from app.inference.detector import to_detections


def test_to_detections_maps_class_box_conf_track():
    dets = to_detections(
        xyxy=[[10, 20, 30, 40]], cls_ids=[1], confs=[0.9], track_ids=[5],
        names=ARGUS_CLASSES,
    )
    assert dets == [Detection("helmet", BBox(10.0, 20.0, 30.0, 40.0), 0.9, 5)]


def test_to_detections_handles_missing_track_ids():
    dets = to_detections([[0, 0, 1, 1]], [0], [0.5], None, ARGUS_CLASSES)
    assert dets[0].cls == "person"
    assert dets[0].track_id is None


def test_to_detections_skips_unknown_class_id():
    dets = to_detections([[0, 0, 1, 1]], [99], [0.5], [1], ARGUS_CLASSES)
    assert dets == []
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Écrire l'implémentation minimale**

`backend/app/config.py` :
```python
from __future__ import annotations

# IDs de classe du modèle YOLOv8 entraîné (ordre du data.yaml / mapping.yaml).
ARGUS_CLASSES: dict[int, str] = {
    0: "person",
    1: "helmet",
    2: "safety-vest",
    3: "mask",
    4: "shoes",
}
```

`backend/app/inference/__init__.py` : fichier vide.

`backend/app/inference/detector.py` :
```python
from __future__ import annotations

from app.domain.types import BBox, Detection


def to_detections(xyxy, cls_ids, confs, track_ids, names) -> list[Detection]:
    """Convertit des sorties YOLO (listes parallèles) en Detection du moteur.

    - xyxy : liste de [x1, y1, x2, y2] en pixels
    - cls_ids : liste d'IDs de classe (int)
    - confs : liste de confidences
    - track_ids : liste d'IDs de suivi (int) ou None si non suivi
    - names : dict {id -> nom de classe}
    Les classes absentes de `names` sont ignorées.
    """
    detections: list[Detection] = []
    tids = track_ids if track_ids is not None else [None] * len(cls_ids)
    for i in range(len(cls_ids)):
        name = names.get(int(cls_ids[i]))
        if name is None:
            continue
        x1, y1, x2, y2 = xyxy[i]
        tid = tids[i]
        detections.append(
            Detection(
                cls=name,
                bbox=BBox(float(x1), float(y1), float(x2), float(y2)),
                confidence=float(confs[i]),
                track_id=int(tid) if tid is not None else None,
            )
        )
    return detections
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_detector.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/inference/__init__.py backend/app/inference/detector.py backend/tests/test_detector.py
git commit -m "feat(inference): YOLO output -> domain Detection conversion"
```

---

### Task 2: PPEDetector (enveloppe Ultralytics)

**Files:**
- Modify: `backend/app/inference/detector.py` (ajouter la classe `PPEDetector`)
- Create: `backend/requirements.txt`
- Test: `backend/tests/test_detector.py` (ajouter des tests avec un faux modèle)

**Interfaces:**
- Consumes: `to_detections(...)` (Task 1), `ARGUS_CLASSES` (Task 1).
- Produces: `PPEDetector(model, names=None)` avec `.detect(frame, conf=0.25) -> list[Detection]` et classmethod `.from_path(model_path, names=None)`.

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `backend/tests/test_detector.py`

```python
from app.inference.detector import PPEDetector


class _Arr:
    def __init__(self, v):
        self._v = v

    def tolist(self):
        return self._v


class _FakeBoxes:
    def __init__(self, xyxy, cls, conf, ids):
        self.xyxy = _Arr(xyxy)
        self.cls = _Arr(cls)
        self.conf = _Arr(conf)
        self.id = _Arr(ids) if ids is not None else None

    def __len__(self):
        return len(self.cls.tolist())


class _FakeResults:
    def __init__(self, boxes):
        self.boxes = boxes


class _FakeModel:
    def __init__(self, boxes):
        self._boxes = boxes

    def track(self, frame, **kwargs):
        return [_FakeResults(self._boxes)]


def test_ppedetector_converts_tracked_boxes():
    model = _FakeModel(_FakeBoxes([[10, 20, 30, 40]], [1], [0.9], [7]))
    dets = PPEDetector(model).detect(frame=None)
    assert dets == [Detection("helmet", BBox(10.0, 20.0, 30.0, 40.0), 0.9, 7)]


def test_ppedetector_empty_when_no_boxes():
    model = _FakeModel(_FakeBoxes([], [], [], None))
    assert PPEDetector(model).detect(frame=None) == []
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_detector.py -v`
Expected: FAIL — `ImportError: cannot import name 'PPEDetector'`.

- [ ] **Step 3: Écrire l'implémentation minimale**

Ajouter en haut de `backend/app/inference/detector.py` (après l'import existant) :
```python
from app.config import ARGUS_CLASSES
```

Ajouter à la fin de `backend/app/inference/detector.py` :
```python
class PPEDetector:
    """Enveloppe le modèle YOLO (Ultralytics) : frame -> list[Detection], tracking inclus.

    `model` doit exposer `.track(frame, **kwargs)` renvoyant une liste de résultats
    dont `[0].boxes` a `.xyxy`, `.cls`, `.conf`, `.id` (chacun avec `.tolist()`).
    """

    def __init__(self, model, names=None):
        self._model = model
        self._names = names if names is not None else ARGUS_CLASSES

    @classmethod
    def from_path(cls, model_path, names=None) -> "PPEDetector":
        from ultralytics import YOLO

        return cls(YOLO(model_path), names)

    def detect(self, frame, conf: float = 0.25) -> list[Detection]:
        results = self._model.track(frame, persist=True, conf=conf, verbose=False)
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []
        track_ids = boxes.id.tolist() if boxes.id is not None else None
        return to_detections(
            boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist(),
            track_ids, self._names,
        )
```

`backend/requirements.txt` :
```
ultralytics
opencv-python
numpy
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_detector.py -v`
Expected: PASS (5 tests au total).

- [ ] **Step 5: Commit**

```bash
git add backend/app/inference/detector.py backend/requirements.txt backend/tests/test_detector.py
git commit -m "feat(inference): PPEDetector wrapping Ultralytics track()"
```

---

### Task 3: FramePipeline (orchestration détecteur + moteur)

**Files:**
- Create: `backend/app/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `app.domain.engine.ComplianceEngine`, `app.domain.types.{Detection, FrameResult, Zone}` ; un détecteur exposant `.detect(frame) -> list[Detection]` (ex. `PPEDetector` de Task 2, ou un stub).
- Produces: `FramePipeline(detector, zones, **engine_kwargs)` avec `.process(frame, timestamp) -> tuple[list[Detection], FrameResult]`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_pipeline.py`

```python
from __future__ import annotations

from app.domain.types import BBox, Detection, Zone
from app.pipeline import FramePipeline


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets


def test_pipeline_feeds_detections_to_engine_and_flags_violation():
    # une personne sans casque dans une zone qui exige un casque -> non conforme
    person = Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)
    zone = Zone("z", [(0, 0), (500, 0), (500, 500), (0, 500)], frozenset({"helmet"}))
    pipe = FramePipeline(_StubDetector([person]), [zone])

    detections, result = pipe.process(frame=None, timestamp=0.0)

    assert detections == [person]
    assert result.results[0].compliant is False
    assert result.results[0].missing == frozenset({"helmet"})


def test_pipeline_compliant_when_ppe_present():
    person = Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)
    helmet = Detection("helmet", BBox(120, 100, 180, 140), 0.9, track_id=None)
    zone = Zone("z", [(0, 0), (500, 0), (500, 500), (0, 500)], frozenset({"helmet"}))
    pipe = FramePipeline(_StubDetector([person, helmet]), [zone])

    _, result = pipe.process(frame=None, timestamp=0.0)
    assert result.results[0].compliant is True
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline'`.

- [ ] **Step 3: Écrire l'implémentation minimale**

`backend/app/pipeline.py` :
```python
from __future__ import annotations

from app.domain.engine import ComplianceEngine
from app.domain.types import Detection, FrameResult, Zone


class FramePipeline:
    """Orchestration temps réel : frame -> détections -> moteur de conformité.

    `detector` doit exposer `.detect(frame) -> list[Detection]`. Renvoie aussi les
    détections brutes (pour les overlays d'affichage) en plus du FrameResult.
    """

    def __init__(self, detector, zones: list[Zone], **engine_kwargs):
        self._detector = detector
        self._engine = ComplianceEngine(zones, **engine_kwargs)

    def process(self, frame, timestamp: float) -> tuple[list[Detection], FrameResult]:
        detections = self._detector.detect(frame)
        result = self._engine.process_frame(detections, timestamp)
        return detections, result
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_pipeline.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(pipeline): FramePipeline wiring detector to compliance engine"
```

---

### Task 4: Script de validation vidéo (`run_video.py`)

**Files:**
- Create: `backend/scripts/run_video.py`

**Interfaces:**
- Consumes: `PPEDetector.from_path` (Task 2), `FramePipeline` (Task 3), `app.domain.types.Zone`.
- Produces: un exécutable CLI qui traite une vidéo, dessine les overlays et imprime les infractions. Pas de test unitaire (validation par exécution réelle — le détecteur et OpenCV nécessitent le modèle et la vidéo).

- [ ] **Step 1: Écrire le script complet** — `backend/scripts/run_video.py`

```python
from __future__ import annotations

"""Validation P1 : fait tourner le pipeline sur une vidéo, dessine les overlays,
imprime les événements d'infraction. Aucun frontend.

Usage :
    py backend/scripts/run_video.py --model best.pt --video sample.mp4 --required helmet
    (ajouter --show pour l'affichage fenêtré, --save out.mp4 pour écrire la vidéo annotée)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ sur le path

import cv2  # noqa: E402

from app.domain.types import Zone  # noqa: E402
from app.inference.detector import PPEDetector  # noqa: E402
from app.pipeline import FramePipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="chemin du modèle .pt ou .onnx")
    ap.add_argument("--video", required=True, help="chemin de la vidéo")
    ap.add_argument("--required", default="helmet", help="EPI requis, séparés par des virgules")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--save", default=None, help="chemin de sortie vidéo annotée (optionnel)")
    args = ap.parse_args()

    required = frozenset(args.required.split(","))
    detector = PPEDetector.from_path(args.model)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Impossible d'ouvrir la vidéo : {args.video}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    zone = Zone("all", [(0, 0), (width, 0), (width, height), (0, height)], required)
    pipe = FramePipeline(detector, [zone])

    writer = None
    if args.save:
        writer = cv2.VideoWriter(
            args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        timestamp = frame_idx / fps
        detections, result = pipe.process(frame, timestamp)

        status = {r.track_id: r.compliant for r in result.results}
        for d in detections:
            b = d.bbox
            if d.cls == "person":
                color = (0, 255, 0) if status.get(d.track_id, True) else (0, 0, 255)
            else:
                color = (255, 200, 0)
            cv2.rectangle(frame, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), color, 2)
            cv2.putText(frame, d.cls, (int(b.x1), int(b.y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        for e in result.events:
            print(f"[{e.timestamp:5.1f}s] INFRACTION id={e.track_id} "
                  f"manque={sorted(e.missing)} zone={e.zone}")

        if writer is not None:
            writer.write(frame)
        if args.show:
            cv2.imshow("Argus", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        frame_idx += 1

    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()
    print(f"Terminé : {frame_idx} frames traitées.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Vérifier la syntaxe (sans exécuter le modèle)**

Run: `py -m py_compile backend/scripts/run_video.py`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/run_video.py
git commit -m "feat(pipeline): video validation script (overlays + violation log)"
```

- [ ] **Step 4: Validation réelle (manuelle, par l'auteur)**

Sur la machine locale, avec `best.pt` et une vidéo de test :
```bash
pip install -r backend/requirements.txt
py backend/scripts/run_video.py --model best.pt --video sample.mp4 --required helmet --save annotated.mp4
```
Attendu : la vidéo annotée montre des boîtes (personnes en vert/rouge selon conformité, EPI en bleu), et le terminal imprime les infractions confirmées après le debounce.

---

## Self-Review

**1. Couverture spec (§13-P1) :** inférence ✅ (Task 1-2), logique métier ✅ (moteur existant, câblé Task 3), tracking ✅ (Ultralytics `.track()` = ByteTrack, Task 2), validé sur vidéo échantillon sans front ✅ (Task 4). Le service FastAPI WS/REST est **hors périmètre** de ce plan → **P1b** (plan suivant).

**2. Placeholders :** aucun — chaque étape contient le code réel.

**3. Cohérence des types :** `to_detections` (Task 1) renvoie `list[Detection]` ; `PPEDetector.detect` (Task 2) l'appelle et renvoie `list[Detection]` ; `FramePipeline.process` (Task 3) consomme `.detect` et appelle `ComplianceEngine.process_frame(detections, timestamp)` (signature vérifiée dans `engine.py`) ; `run_video.py` (Task 4) consomme `.from_path` et `.process`. Cohérent.
