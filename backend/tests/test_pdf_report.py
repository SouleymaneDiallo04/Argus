from __future__ import annotations

from app.reports.pdf_report import summary_pdf


def test_summary_pdf_returns_pdf_bytes():
    stats = {"global": {"rate": 0.9},
             "by_zone": [{"zone": "Fonderie", "rate": 0.9}],
             "over_time": [],
             "violations": {"total": 2, "by_zone": {"Fonderie": 2}}}
    events = [{"ts": "2026-08-04T12:00", "zone": "Fonderie", "track_id": 37,
               "missing": ["helmet"]}]
    pdf = summary_pdf(stats, events,
                      {"site": "Meknès-Nord", "since": None, "until": None,
                       "generated_at": "2026-08-04"})
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500


def test_summary_pdf_handles_empty():
    pdf = summary_pdf({"global": {}, "by_zone": [], "over_time": [],
                       "violations": {"total": 0, "by_zone": {}}}, [], {})
    assert pdf[:4] == b"%PDF"
