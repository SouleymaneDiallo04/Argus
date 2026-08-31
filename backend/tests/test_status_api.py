from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import ViolationEvent
from app.persistence.journal import Journal


def _client(journal):
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b: b
    app.state.journal = journal
    return TestClient(app)


def _ev(track_id, zone, missing):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=0.0, camera="cam-1")


def test_set_status_ok_invalid_and_missing():
    journal = Journal(":memory:")
    journal.record_event(_ev(1, "Z", ["helmet"]),
                         datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc))
    client = _client(journal)
    eid = client.get("/events").json()["events"][0]["id"]

    ok = client.post(f"/events/{eid}/status", json={"status": "ack"})
    assert ok.status_code == 200 and ok.json()["status"] == "ack"

    assert client.post(f"/events/{eid}/status", json={"status": "bogus"}).status_code == 422
    assert client.post("/events/9999/status", json={"status": "ack"}).status_code == 404


def test_get_events_filter_by_status():
    journal = Journal(":memory:")
    journal.record_event(_ev(1, "Z", ["helmet"]),
                         datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc))
    client = _client(journal)
    assert len(client.get("/events", params={"status": "active"}).json()["events"]) == 1
    assert client.get("/events", params={"status": "resolved"}).json()["events"] == []
