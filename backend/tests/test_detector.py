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
