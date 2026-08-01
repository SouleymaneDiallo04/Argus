from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.persistence.journal import Journal


def _client(journal):
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    return TestClient(app)


def test_get_stats_computes_rate():
    journal = Journal(":memory:")
    journal.record_observations("2026-07-29T14:30", "Fonderie", 10, 7)
    journal.record_observations("2026-07-29T14:31", "Fonderie", 5, 5)
    s = _client(journal).get("/stats").json()
    assert s["global"] == {"person_frames": 15, "compliant_frames": 12, "rate": 12 / 15}
    assert len(s["over_time"]) == 2
    assert {z["zone"]: z["rate"] for z in s["by_zone"]}["Fonderie"] == 12 / 15


def test_get_stats_rate_null_when_empty():
    s = _client(Journal(":memory:")).get("/stats").json()
    assert s["global"]["rate"] is None
