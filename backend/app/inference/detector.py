from __future__ import annotations

from app.domain.types import BBox, Detection
from app.config import ARGUS_CLASSES


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


class PPEDetector:
    """Enveloppe le modèle YOLO (Ultralytics) : frame -> list[Detection], tracking inclus.

    `model` doit exposer `.track(frame, **kwargs)` renvoyant une liste de résultats
    dont `[0].boxes` a `.xyxy`, `.cls`, `.conf`, `.id` (chacun avec `.tolist()`).
    """

    def __init__(self, model, names=None, conf: float = 0.25, imgsz: int = 640):
        self._model = model
        self._names = names if names is not None else ARGUS_CLASSES
        self._conf = conf
        self._imgsz = imgsz
        self._reset_next = False

    @classmethod
    def from_path(cls, model_path, names=None, conf: float = 0.25, imgsz: int = 640) -> "PPEDetector":
        from ultralytics import YOLO

        return cls(YOLO(model_path), names, conf, imgsz)

    def reset(self) -> None:
        """Marque le prochain detect() comme début d'un nouveau flux : le tracker
        Ultralytics est réinitialisé (persist=False) puis reprend en continuation."""
        self._reset_next = True

    def detect(self, frame, conf: float | None = None, imgsz: int | None = None) -> list[Detection]:
        effective_conf = self._conf if conf is None else conf
        effective_imgsz = self._imgsz if imgsz is None else imgsz
        persist = not self._reset_next
        self._reset_next = False
        results = self._model.track(
            frame, persist=persist, conf=effective_conf, imgsz=effective_imgsz, verbose=False
        )
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []
        track_ids = boxes.id.tolist() if boxes.id is not None else None
        return to_detections(
            boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist(),
            track_ids, self._names,
        )
