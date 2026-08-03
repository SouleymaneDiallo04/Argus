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
