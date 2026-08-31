from __future__ import annotations

from datetime import datetime, timezone

from app.domain.types import ComplianceResult, FrameResult, ViolationEvent
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


def test_record_observations_upsert_is_additive():
    j = Journal(":memory:")
    j.record_observations("2026-07-29T14:30", "Fonderie", 4, 3)
    j.record_observations("2026-07-29T14:30", "Fonderie", 6, 2)   # même clé -> somme
    g = j.stats()["global"]
    assert g == {"person_frames": 10, "compliant_frames": 5, "rate": 0.5}


def test_stats_global_by_zone_over_time_excludes_no_zone():
    j = Journal(":memory:")
    j.record_observations("2026-07-29T14:30", "Fonderie", 10, 7)
    j.record_observations("2026-07-29T14:31", "Fonderie", 5, 5)
    j.record_observations("2026-07-29T14:30", "", 3, 3)           # hors zone -> exclu
    s = j.stats()
    assert s["global"] == {"person_frames": 15, "compliant_frames": 12, "rate": 12 / 15}
    by_zone = {z["zone"]: z for z in s["by_zone"]}
    assert set(by_zone) == {"Fonderie"}                           # "" exclu
    assert by_zone["Fonderie"]["rate"] == 12 / 15
    assert [o["bucket"] for o in s["over_time"]] == ["2026-07-29T14:30", "2026-07-29T14:31"]


def test_stats_rate_null_when_no_observation():
    assert Journal(":memory:").stats()["global"]["rate"] is None


def test_stats_violations_count_from_events():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Fonderie", ["helmet"]), _ts(30))
    j.record_event(_ev(2, "Fonderie", ["mask"]), _ts(31))
    v = j.stats()["violations"]
    assert v["total"] == 2
    assert v["by_zone"]["Fonderie"] == 2


def _cr(track_id, zone, compliant, missing=()):
    return ComplianceResult(track_id=track_id, zone=zone, required=frozenset(),
                            present=frozenset(), missing=frozenset(missing),
                            compliant=compliant)


def test_record_frame_persists_events_and_observations():
    j = Journal(":memory:")
    result = FrameResult(
        results=[_cr(1, "Fonderie", False, ["helmet"]),
                 _cr(2, "Fonderie", True),
                 _cr(3, None, True)],                 # hors zone
        events=[_ev(1, "Fonderie", ["helmet"])],
    )
    j.record_frame(result, _ts(30))
    assert len(j.events()) == 1                        # l'event est journalisé
    fonderie = {z["zone"]: z for z in j.stats()["by_zone"]}["Fonderie"]
    assert fonderie["person_frames"] == 2              # persons 1 & 2 (zone nommée)
    assert fonderie["compliant_frames"] == 1           # seul le 2 est conforme
    # la personne hors zone est agrégée sous "" (exclue du global/by_zone)
    assert j.stats()["global"]["person_frames"] == 2


def test_record_event_stores_snapshot():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30), snapshot="abc.jpg")
    assert j.events()[0]["snapshot"] == "abc.jpg"


def test_event_lookup_by_id():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30), snapshot="abc.jpg")
    row_id = j.events()[0]["id"]
    assert j.event(row_id)["snapshot"] == "abc.jpg"
    assert j.event(9999) is None


def test_record_frame_attaches_snapshot():
    j = Journal(":memory:")
    result = FrameResult(results=[_cr(1, "Z", False, ["helmet"])],
                         events=[_ev(1, "Z", ["helmet"])])
    j.record_frame(result, _ts(30), snapshot="snap.jpg")
    assert j.events()[0]["snapshot"] == "snap.jpg"


def test_event_status_defaults_active_and_set_status():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30))
    row_id = j.events()[0]["id"]
    assert j.events()[0]["status"] == "active"
    assert j.set_status(row_id, "ack") is True
    assert j.event(row_id)["status"] == "ack"
    assert j.set_status(9999, "resolved") is False


def test_events_filter_by_status():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30))
    j.record_event(_ev(2, "Z", ["mask"]), _ts(31))
    second = j.events()[0]["id"]
    j.set_status(second, "resolved")
    assert [e["status"] for e in j.events(status="active")] == ["active"]
    assert [e["status"] for e in j.events(status="resolved")] == ["resolved"]
