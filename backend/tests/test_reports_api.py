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


def _seed(journal):
    journal.record_event(
        ViolationEvent(track_id=37, zone="Fonderie", missing=frozenset({"helmet"}),
                       timestamp=0.0, camera="cam-1"),
        datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc))


def test_events_csv_download():
    journal = Journal(":memory:")
    _seed(journal)
    r = _client(journal).get("/reports/events.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "#37" in r.text and "helmet" in r.text


def test_summary_pdf_download():
    journal = Journal(":memory:")
    _seed(journal)
    r = _client(journal).get("/reports/summary.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"
