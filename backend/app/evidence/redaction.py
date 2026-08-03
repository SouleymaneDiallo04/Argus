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
