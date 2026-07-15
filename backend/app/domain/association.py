from __future__ import annotations

import math

from app.domain.types import Detection
from app.domain.geometry import center, containment_ratio

# Bande verticale attendue (fraction de la hauteur de la personne : 0 = haut, 1 = bas)
BODY_BANDS: dict[str, tuple[float, float]] = {
    "helmet": (0.0, 0.30),
    "glasses": (0.0, 0.30),
    "mask": (0.0, 0.35),
    "safety-vest": (0.20, 0.60),
    "gloves": (0.30, 0.80),
    "shoes": (0.80, 1.0),
}


def _distance(a: Detection, b: Detection) -> float:
    ax, ay = center(a.bbox)
    bx, by = center(b.bbox)
    return math.hypot(ax - bx, ay - by)


def _in_band(ppe_det: Detection, person: Detection) -> bool:
    band = BODY_BANDS.get(ppe_det.cls)
    if band is None or person.bbox.height <= 0:
        return False
    _, ppe_cy = center(ppe_det.bbox)
    rel_y = (ppe_cy - person.bbox.y1) / person.bbox.height
    return band[0] <= rel_y <= band[1]


def _best_person(ppe_det: Detection, persons: list[Detection], threshold: float) -> Detection | None:
    contained = [
        p for p in persons
        if containment_ratio(ppe_det.bbox, p.bbox) >= threshold
    ]
    if contained:
        in_band = [p for p in contained if _in_band(ppe_det, p)]
        pool = in_band if in_band else contained
        return min(pool, key=lambda p: _distance(ppe_det, p))
    if persons:  # fallback ambigu : personne la plus proche
        return min(persons, key=lambda p: _distance(ppe_det, p))
    return None


def associate(
    persons: list[Detection],
    ppe: list[Detection],
    containment_threshold: float = 0.5,
) -> dict[int, set[str]]:
    tracked = [p for p in persons if p.track_id is not None]
    result: dict[int, set[str]] = {}
    for ppe_det in ppe:
        chosen = _best_person(ppe_det, tracked, containment_threshold)
        if chosen is None:
            continue
        result.setdefault(chosen.track_id, set()).add(ppe_det.cls)
    return result
