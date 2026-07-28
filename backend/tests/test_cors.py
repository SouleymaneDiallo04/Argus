from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app


def _client():
    app = create_app()
    app.state.detector = object()   # stub : évite le chargement du modèle au démarrage
    app.state.decode = lambda b64: b64
    return TestClient(app)


def test_zones_get_has_cors_header_for_allowed_origin():
    resp = _client().get("/zones", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_preflight_put_zones_allowed():
    resp = _client().options(
        "/zones",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
