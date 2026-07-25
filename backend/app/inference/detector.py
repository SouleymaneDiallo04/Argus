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
