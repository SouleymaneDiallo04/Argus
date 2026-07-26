from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.types import BBox, ComplianceResult, Detection, FrameResult, ViolationEvent, Zone
from app.api.schemas import FrameMessage, ZoneModel, ZonesConfig, frame_response


def test_zone_model_roundtrip_to_domain():
    zm = ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]], required_ppe=["helmet"])
    zone = zm.to_domain()
    assert isinstance(zone, Zone)
    assert zone.name == "z"
    assert zone.polygon == ((0, 0), (10, 0), (10, 10))
    assert zone.required_ppe == frozenset({"helmet"})
    back = ZoneModel.from_domain(zone)
    assert back.required_ppe == ["helmet"]


def test_zone_model_rejects_short_polygon():
    with pytest.raises(ValidationError):
        ZoneModel(name="z", polygon=[[0, 0], [10, 0]], required_ppe=["helmet"])


def test_zone_model_rejects_unknown_ppe():
    with pytest.raises(ValidationError):
        ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]], required_ppe=["banana"])


def test_frame_response_serializes_all_parts():
    det = Detection("person", BBox(1, 2, 3, 4), 0.9, track_id=7)
    res = ComplianceResult(7, "z", frozenset({"helmet"}), frozenset(), frozenset({"helmet"}), False)
    evt = ViolationEvent(7, "z", frozenset({"helmet"}), 5.0, "cam-1")
    out = frame_response([det], FrameResult(results=[res], events=[evt]))
    assert out["detections"] == [{"cls": "person", "bbox": [1.0, 2.0, 3.0, 4.0], "confidence": 0.9, "track_id": 7}]
    assert out["results"][0] == {"track_id": 7, "zone": "z", "required": ["helmet"],
                                 "present": [], "missing": ["helmet"], "compliant": False}
    assert out["events"][0] == {"track_id": 7, "zone": "z", "missing": ["helmet"],
                                "timestamp": 5.0, "camera": "cam-1"}


def test_frame_message_parses():
    msg = FrameMessage(frame="abc", timestamp=1.5)
    assert msg.frame == "abc" and msg.timestamp == 1.5
