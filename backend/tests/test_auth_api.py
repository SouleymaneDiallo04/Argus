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
