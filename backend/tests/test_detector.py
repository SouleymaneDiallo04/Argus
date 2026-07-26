from __future__ import annotations

from app.config import ARGUS_CLASSES
from app.domain.types import BBox, Detection
from app.inference.detector import to_detections, PPEDetector


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


class _RecordingModel:
    def __init__(self, boxes):
        self._boxes = boxes
        self.last_conf = None
        self.last_imgsz = None

    def track(self, frame, **kwargs):
        self.last_conf = kwargs.get("conf")
        self.last_imgsz = kwargs.get("imgsz")
        return [_FakeResults(self._boxes)]


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


def test_ppedetector_converts_tracked_boxes():
    model = _FakeModel(_FakeBoxes([[10, 20, 30, 40]], [1], [0.9], [7]))
    dets = PPEDetector(model).detect(frame=None)
    assert dets == [Detection("helmet", BBox(10.0, 20.0, 30.0, 40.0), 0.9, 7)]


def test_ppedetector_empty_when_no_boxes():
    model = _FakeModel(_FakeBoxes([], [], [], None))
    assert PPEDetector(model).detect(frame=None) == []


def test_ppedetector_uses_configured_conf():
    model = _RecordingModel(_FakeBoxes([], [], [], None))
    PPEDetector(model, conf=0.5).detect(frame=None)
    assert model.last_conf == 0.5


def test_ppedetector_uses_configured_imgsz():
    model = _RecordingModel(_FakeBoxes([], [], [], None))
    PPEDetector(model, imgsz=1280).detect(frame=None)
    assert model.last_imgsz == 1280
