from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt


def encode_token(username: str, role: str, secret: str, ttl_seconds: int = 28800) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "role": role,
               "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])
