from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from app.domain.types import BBox, ComplianceResult, Detection, FrameResult, ViolationEvent
from app.evidence.snapshots import SnapshotStore
from app.ingest.frame_sink import ingest_frame
from app.notify.base import NotificationDispatcher
from app.persistence.journal import Journal


class _Spy:
    def __init__(self):
        self.events = []

    def notify(self, e):
        self.events.append(e)


def _result_with_event():
    return FrameResult(
        results=[ComplianceResult(1, "z", frozenset(), frozenset(), frozenset({"helmet"}), False)],
        events=[ViolationEvent(1, "z", frozenset({"helmet"}), 0.0, "cam")])


def _now():
    return datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def test_ingest_frame_persists_snapshot_and_notifies(tmp_path):
    j = Journal(":memory:")
    spy = _Spy()
    ingest_frame(j, SnapshotStore(str(tmp_path)), NotificationDispatcher([spy]),
                 np.zeros((100, 100, 3), np.uint8),
                 [Detection("person", BBox(10, 10, 90, 90), 0.9, 1)],
                 _result_with_event(), _now())
    ev = j.events()
    assert len(ev) == 1 and ev[0]["snapshot"] is not None
    assert (tmp_path / ev[0]["snapshot"]).exists()
    assert len(spy.events) == 1


def test_ingest_frame_tolerates_none_collaborators():
    j = Journal(":memory:")
    ingest_frame(j, None, None, "F", [], _result_with_event(), _now())
    assert len(j.events()) == 1 and j.events()[0]["snapshot"] is None
