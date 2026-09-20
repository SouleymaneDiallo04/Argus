from __future__ import annotations

from dataclasses import dataclass

from app.auth.passwords import hash_password, verify_password


@dataclass(frozen=True)
class User:
    username: str
    role: str


class UserStore:
    def __init__(self, users: dict[str, tuple[str, str]]):
        self._users = users  # username -> (password_hash, role)

    def authenticate(self, username: str, password: str) -> User | None:
        entry = self._users.get(username)
        if entry is None:
            return None
        pw_hash, role = entry
        if not verify_password(password, pw_hash):
            return None
        return User(username, role)

    @classmethod
    def from_env(cls, env) -> "UserStore | None":
        if not env.get("ARGUS_JWT_SECRET"):
            return None
        users: dict[str, tuple[str, str]] = {}
        if env.get("ARGUS_ADMIN_PASSWORD"):
            users["admin"] = (hash_password(env["ARGUS_ADMIN_PASSWORD"]), "admin")
        if env.get("ARGUS_HSE_PASSWORD"):
            users["hse"] = (hash_password(env["ARGUS_HSE_PASSWORD"]), "hse")
        return cls(users) if users else None
