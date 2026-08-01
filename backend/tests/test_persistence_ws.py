from __future__ import annotations

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


def _client(journal):
    app = create_app()
    app.state.detector = _StubDetector(
        [Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)])
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    return TestClient(app)


def test_ws_flux_persists_event_and_observations():
    journal = Journal(":memory:")
    client = _client(journal)
    client.put("/zones", json={"zones": [{"name": "z",
               "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
               "required_ppe": ["helmet"]}]})
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "F", "timestamp": 0.0}); ws.receive_json()
        ws.send_json({"frame": "F", "timestamp": 3.5}); ws.receive_json()  # >= confirm (3s)
    events = journal.events()
    assert len(events) == 1                       # une infraction confirmée
    assert events[0]["zone"] == "z"
    assert events[0]["missing"] == ["helmet"]
    g = journal.stats()["global"]
    assert g["person_frames"] == 2                # 2 frames, 1 personne chacune
    assert g["compliant_frames"] == 0
    assert g["rate"] == 0.0
