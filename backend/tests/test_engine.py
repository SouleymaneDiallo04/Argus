from __future__ import annotations

from app.domain.types import BBox, Detection, Zone
from app.domain.engine import ComplianceEngine


def person(track_id: int) -> Detection:
    return Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=track_id)


def helmet() -> Detection:
    return Detection("helmet", BBox(120, 110, 180, 150), 0.8)


def vest() -> Detection:
    return Detection("safety-vest", BBox(110, 200, 190, 300), 0.8)


ZONE = Zone(
    name="chantier",
    polygon=[(0, 0), (300, 0), (300, 500), (0, 500)],
    required_ppe=frozenset({"helmet", "safety-vest"}),
)


def test_fully_equipped_person_is_compliant_no_event():
    engine = ComplianceEngine([ZONE])
    result = engine.process_frame([person(1), helmet(), vest()], timestamp=0.0)
    assert len(result.results) == 1
    assert result.results[0].compliant is True
    assert result.events == []


def test_missing_vest_is_non_compliant():
    engine = ComplianceEngine([ZONE])
    result = engine.process_frame([person(1), helmet()], timestamp=0.0)
    assert result.results[0].compliant is False
    assert result.results[0].missing == frozenset({"safety-vest"})


def test_violation_event_emitted_after_confirm_window():
    engine = ComplianceEngine([ZONE], confirm_seconds=2.0)
    # anomalie continue : casque seul, gilet manquant
    engine.process_frame([person(1), helmet()], timestamp=0.0)
    engine.process_frame([person(1), helmet()], timestamp=1.0)
    result = engine.process_frame([person(1), helmet()], timestamp=2.0)
    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.track_id == 1
    assert ev.zone == "chantier"
    assert ev.missing == frozenset({"safety-vest"})
    assert ev.camera == "cam-1"
    assert ev.timestamp == 2.0


def test_no_duplicate_event_while_violation_persists():
    engine = ComplianceEngine([ZONE], confirm_seconds=1.0)
    engine.process_frame([person(1), helmet()], timestamp=0.0)
    engine.process_frame([person(1), helmet()], timestamp=1.0)   # event ici
    later = engine.process_frame([person(1), helmet()], timestamp=2.0)
    assert later.events == []


def test_person_outside_zone_has_no_requirements():
    engine = ComplianceEngine([ZONE])
    outsider = Detection("person", BBox(1000, 100, 1100, 400), 0.9, track_id=9)
    result = engine.process_frame([outsider], timestamp=0.0)
    assert result.results[0].compliant is True
    assert result.results[0].zone is None
