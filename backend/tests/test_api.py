from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, Detection


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets

    def reset(self):
        pass


class _RaisingDetector:
    def detect(self, frame):
        raise RuntimeError("boom")

    def reset(self):
        pass


def _client(detector):
    app = create_app()
    app.state.detector = detector           # évite le chargement du vrai modèle au démarrage
    app.state.decode = lambda b64: b64      # bypass OpenCV : la frame "décodée" = la chaîne
    return TestClient(app)


def test_health_reports_model_loaded():
    resp = _client(_StubDetector([])).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "model_loaded": True}


def test_put_then_get_zones_roundtrip():
    client = _client(_StubDetector([]))
    payload = {"zones": [{"name": "z", "polygon": [[0, 0], [10, 0], [10, 10]],
                          "required_ppe": ["helmet"]}]}
    assert client.put("/zones", json=payload).status_code == 200
    got = client.get("/zones").json()
    assert got["zones"][0]["name"] == "z"
    assert got["zones"][0]["required_ppe"] == ["helmet"]


def test_put_zones_rejects_bad_polygon():
    client = _client(_StubDetector([]))
    payload = {"zones": [{"name": "z", "polygon": [[0, 0], [10, 0]], "required_ppe": ["helmet"]}]}
    assert client.put("/zones", json=payload).status_code == 422


def test_ws_stream_returns_compliance():
    person = Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)
    client = _client(_StubDetector([person]))
    client.put("/zones", json={"zones": [{"name": "z", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
                                          "required_ppe": ["helmet"]}]})
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "FAKE", "timestamp": 0.0})
        msg = ws.receive_json()
    assert msg["detections"][0]["cls"] == "person"
    assert msg["results"][0]["compliant"] is False
    assert msg["results"][0]["missing"] == ["helmet"]


def test_ws_invalid_frame_returns_error_without_closing():
    person = Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)
    client = _client(_StubDetector([person]))
    client.put("/zones", json={"zones": [{"name": "z", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
                                          "required_ppe": ["helmet"]}]})
    app = client.app

    def _bad_decode(b64):
        raise ValueError("frame illisible")

    with client.websocket_connect("/ws/stream") as ws:
        app.state.decode = _bad_decode
        ws.send_json({"frame": "BAD", "timestamp": 0.0})
        assert "error" in ws.receive_json()
        # la connexion reste ouverte : une frame valide ensuite est traitée normalement
        app.state.decode = lambda b64: b64
        ws.send_json({"frame": "OK", "timestamp": 1.0})
        msg = ws.receive_json()
    assert msg["detections"][0]["cls"] == "person"


def test_ws_malformed_json_returns_error_without_closing():
    client = _client(_StubDetector([]))
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_text("this is not json")          # receive_json -> JSONDecodeError (ValueError)
        assert "error" in ws.receive_json()
        # la connexion reste ouverte : un message JSON valide ensuite reçoit une réponse normale
        ws.send_json({"frame": "OK", "timestamp": 0.0})
        msg = ws.receive_json()
    assert "detections" in msg


def test_ws_pipeline_error_returns_error_without_closing():
    client = _client(_RaisingDetector())
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "OK", "timestamp": 0.0})
        assert "error" in ws.receive_json()
        # la connexion reste ouverte : un message suivant reçoit encore une réponse
        ws.send_json({"frame": "OK", "timestamp": 1.0})
        assert "error" in ws.receive_json()
