from __future__ import annotations

import time

import numpy as np
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, Detection
from app.persistence.journal import Journal


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets

    def reset(self):
        pass


class _FakeCap:
    def __init__(self, n):
        self._n = n

    def read(self):
        if self._n > 0:
            self._n -= 1
            return True, np.zeros((480, 640, 3), np.uint8)
        return False, None

    def release(self):
        pass


def _client(journal, frames):
    app = create_app()
    app.state.detector = _StubDetector(
        [Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)])
    app.state.decode = lambda b: b
    app.state.journal = journal
    app.state.rtsp_capture_factory = lambda url: _FakeCap(frames)
    return TestClient(app)


def test_rtsp_start_ingests_then_stop():
    journal = Journal(":memory:")
    client = _client(journal, frames=8)
    client.put("/zones", json={"zones": [{"name": "z",
               "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
               "required_ppe": ["helmet"]}]})

    r = client.post("/sources/rtsp", json={"url": "rtsp://x"})
    assert r.status_code == 200 and r.json()["running"] is True

    for _ in range(60):                          # attendre l'ingestion de quelques frames
        if journal.stats()["global"]["person_frames"] >= 1:
            break
        time.sleep(0.05)
    assert journal.stats()["global"]["person_frames"] >= 1

    assert client.delete("/sources/rtsp").json()["stopped"] is True
    assert client.get("/sources/rtsp").json()["running"] is False
