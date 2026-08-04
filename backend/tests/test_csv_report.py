from __future__ import annotations

from app.reports.csv_report import events_csv


def test_events_csv_header_and_rows():
    out = events_csv([
        {"ts": "2026-08-04T12:00", "zone": "Fonderie", "track_id": 37,
         "missing": ["helmet", "shoes"], "camera": "cam-1", "snapshot": "a.jpg"},
        {"ts": "2026-08-04T12:01", "zone": None, "track_id": 8,
         "missing": ["mask"], "camera": "cam-1", "snapshot": None},
    ])
    lines = out.strip().splitlines()
    assert lines[0] == "Heure,Zone,Personne,EPI manquants,Caméra,Preuve"
    assert "#37" in lines[1] and '"helmet, shoes"' in lines[1] and "a.jpg" in lines[1]
    assert "#8" in lines[2] and "mask" in lines[2]


def test_events_csv_empty_has_only_header():
    assert events_csv([]).strip() == "Heure,Zone,Personne,EPI manquants,Caméra,Preuve"
