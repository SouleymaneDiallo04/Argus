from __future__ import annotations

import os

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
    assert store.path("../evil.jpg") == os.path.join(str(tmp_path), "evil.jpg")
