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
