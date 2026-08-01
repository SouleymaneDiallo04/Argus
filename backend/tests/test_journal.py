from __future__ import annotations

from datetime import datetime, timezone

from app.domain.types import ViolationEvent
from app.persistence.journal import Journal


def _ev(track_id, zone, missing, stream_ts=0.0, camera="cam-1"):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=stream_ts, camera=camera)


def _ts(minute):
    return datetime(2026, 7, 29, 14, minute, tzinfo=timezone.utc)


def test_record_and_query_events_newest_first():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Fonderie", ["helmet"]), _ts(30))
    j.record_event(_ev(2, "Bureau", ["mask"]), _ts(31))
    rows = j.events()
    assert [r["track_id"] for r in rows] == [2, 1]          # ts DESC
    assert rows[1]["zone"] == "Fonderie"
    assert rows[1]["missing"] == ["helmet"]                 # JSON -> liste triée


def test_events_filter_by_zone_ppe_and_time():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Fonderie", ["helmet", "shoes"]), _ts(30))
    j.record_event(_ev(2, "Bureau", ["mask"]), _ts(31))
    assert [r["track_id"] for r in j.events(zone="Fonderie")] == [1]
    assert [r["track_id"] for r in j.events(ppe="shoes")] == [1]
    assert [r["track_id"] for r in j.events(since="2026-07-29T14:31")] == [2]


def test_events_limit_and_offset():
    j = Journal(":memory:")
    for i in range(5):
        j.record_event(_ev(i, "Z", ["helmet"]), _ts(30 + i))
    assert len(j.events(limit=2)) == 2
    assert [r["track_id"] for r in j.events(limit=2, offset=2)] == [2, 1]
