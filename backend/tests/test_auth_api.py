from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.auth.passwords import hash_password
from app.auth.users import UserStore
from app.persistence.journal import Journal


def _auth_client():
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b: b
    app.state.journal = Journal(":memory:")
    app.state.jwt_secret = "test-secret"
    app.state.user_store = UserStore({
        "admin": (hash_password("pw"), "admin"),
        "hse": (hash_password("pw"), "hse"),
    })
    return TestClient(app)


def _token(client, username):
    return client.post("/auth/login",
                       json={"username": username, "password": "pw"}).json()["access_token"]


def test_login_and_me():
    client = _auth_client()
    r = client.post("/auth/login", json={"username": "admin", "password": "pw"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["username"] == "admin"


def test_login_bad_credentials():
    assert _auth_client().post(
        "/auth/login", json={"username": "admin", "password": "no"}).status_code == 401


def test_me_requires_token():
    assert _auth_client().get("/auth/me").status_code == 401


def _zone_payload():
    return {"zones": [{"name": "z", "polygon": [[0, 0], [10, 0], [10, 10]],
                       "required_ppe": ["helmet"]}]}


def test_write_endpoints_enforce_roles():
    client = _auth_client()
    assert client.put("/zones", json=_zone_payload()).status_code == 401
    hse = {"Authorization": f"Bearer {_token(client, 'hse')}"}
    assert client.put("/zones", json=_zone_payload(), headers=hse).status_code == 403
    admin = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    assert client.put("/zones", json=_zone_payload(), headers=admin).status_code == 200


def test_ack_records_operator():
    from datetime import datetime, timezone
    from app.domain.types import ViolationEvent
    client = _auth_client()
    client.app.state.journal.record_event(
        ViolationEvent(1, "Z", frozenset({"helmet"}), 0.0, "cam-1"),
        datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc))
    eid = client.get("/events").json()["events"][0]["id"]
    hse = {"Authorization": f"Bearer {_token(client, 'hse')}"}
    r = client.post(f"/events/{eid}/status", json={"status": "ack"}, headers=hse)
    assert r.status_code == 200 and r.json()["acked_by"] == "hse"


def test_auth_disabled_leaves_endpoints_open():
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b: b
    client = TestClient(app)  # pas de user_store -> auth désactivée
    assert client.put("/zones", json=_zone_payload()).status_code == 200
