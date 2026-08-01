from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import ViolationEvent
from app.persistence.journal import Journal


def _client(journal):
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    return TestClient(app)


def _ev(track_id, zone, missing):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=0.0, camera="cam-1")


def test_get_events_orders_and_filters():
    journal = Journal(":memory:")
    journal.record_event(_ev(1, "Fonderie", ["helmet"]),
                         datetime(2026, 7, 29, 14, 30, tzinfo=timezone.utc))
    journal.record_event(_ev(2, "Bureau", ["mask"]),
                         datetime(2026, 7, 29, 14, 31, tzinfo=timezone.utc))
    client = _client(journal)

    allev = client.get("/events").json()["events"]
    assert [e["track_id"] for e in allev] == [2, 1]           # plus récent d'abord

    fonderie = client.get("/events", params={"zone": "Fonderie"}).json()["events"]
    assert len(fonderie) == 1 and fonderie[0]["missing"] == ["helmet"]

    helmet = client.get("/events", params={"ppe": "helmet"}).json()["events"]
    assert [e["track_id"] for e in helmet] == [1]
