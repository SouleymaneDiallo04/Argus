from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, ViolationEvent
from app.evidence.snapshots import SnapshotStore
from app.persistence.journal import Journal


def _client(journal, snapshots):
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    app.state.snapshots = snapshots
    return TestClient(app)


def _ev(track_id, zone, missing):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=0.0, camera="cam-1")


def test_get_event_snapshot_served_and_404(tmp_path):
    journal = Journal(":memory:")
    snapshots = SnapshotStore(str(tmp_path))
    name = snapshots.save(np.full((100, 100, 3), 127, dtype=np.uint8), [BBox(10, 10, 90, 90)])
    journal.record_event(_ev(1, "Z", ["helmet"]),
                         datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc), snapshot=name)
    client = _client(journal, snapshots)

    row = client.get("/events").json()["events"][0]
    assert row["snapshot"] == name

    ok = client.get(f"/events/{row['id']}/snapshot")
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/jpeg"

    assert client.get("/events/9999/snapshot").status_code == 404


def test_get_snapshot_404_when_event_has_none(tmp_path):
    journal = Journal(":memory:")
    journal.record_event(_ev(2, "Z", ["mask"]),
                         datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc))  # pas de snapshot
    client = _client(journal, SnapshotStore(str(tmp_path)))
    row = client.get("/events").json()["events"][0]
    assert client.get(f"/events/{row['id']}/snapshot").status_code == 404
