import jwt
import pytest

from app.auth.tokens import encode_token, decode_token


def test_encode_decode_roundtrip():
    data = decode_token(encode_token("alice", "admin", "secret"), "secret")
    assert data["sub"] == "alice" and data["role"] == "admin"


def test_wrong_secret_raises():
    t = encode_token("alice", "admin", "secret")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(t, "other")


def test_expired_raises():
    t = encode_token("alice", "admin", "secret", ttl_seconds=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(t, "secret")
