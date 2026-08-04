from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, Detection
from app.notify.base import NotificationDispatcher
from app.persistence.journal import Journal


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets

    def reset(self):
        pass


class _Spy:
    def __init__(self):
        self.events = []

    def notify(self, event):
        self.events.append(event)


def test_ws_dispatche_une_notification_sur_infraction():
    spy = _Spy()
    app = create_app()
    app.state.detector = _StubDetector(
        [Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)])
    app.state.decode = lambda b64: b64
    app.state.journal = Journal(":memory:")
    app.state.notifier = NotificationDispatcher([spy])
    client = TestClient(app)
    client.put("/zones", json={"zones": [{"name": "z",
               "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
               "required_ppe": ["helmet"]}]})
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "F", "timestamp": 0.0}); ws.receive_json()
        ws.send_json({"frame": "F", "timestamp": 3.5}); ws.receive_json()  # >= confirm (3s)
    assert len(spy.events) == 1
    assert spy.events[0].zone == "z"
