# V2 — Auth + rôles (backend) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auth JWT + rôles (admin/hse), opt-in, protégeant les endpoints d'écriture ; l'ack enregistre `acked_by`.

**Architecture:** Module `app/auth/` (mots de passe pbkdf2, tokens pyjwt, `UserStore` seedé env, deps FastAPI) ; endpoints `/auth/*` ; `require_role` sur zones/rtsp/status. Auth active seulement si configurée.

**Tech Stack:** Python 3.13, FastAPI, **pyjwt** (nouvelle dép), `hashlib`/`hmac` (stdlib), pytest.

## Global Constraints

- **Auth opt-in** : `app.state.user_store is None` ⇒ auth désactivée ⇒ endpoints ouverts
  (comportement V1, suites existantes vertes). Active si `UserStore.from_env` renvoie un store.
- **admin = super-utilisateur** (`require_role` : passe si `role == "admin"` ou `role in roles`).
- Rôles : `admin` (écriture/config), `hse` (ack/résolution). `pyjwt` dans **les deux** requirements.
- Interpréteur test : **`py -3`**. Suite backend existante (**112**) verte. Commits conventionnels,
  anglais, **sans `Co-Authored-By`**. Branche : `feat/auth-backend`.

---

### Task 1: Primitives — mots de passe (pbkdf2) + tokens (pyjwt)

**Files:**
- Create: `backend/app/auth/__init__.py` (vide), `backend/app/auth/passwords.py`, `backend/app/auth/tokens.py`
- Modify: `backend/requirements.txt`, `backend/requirements-dev.txt`
- Test: `backend/tests/test_passwords.py`, `backend/tests/test_tokens.py`

- [ ] **Step 1: Ajouter la dépendance + installer** — ajouter `pyjwt` en fin de
  `backend/requirements.txt` et `backend/requirements-dev.txt`, puis
  `cd backend && py -3 -m pip install pyjwt`.

- [ ] **Step 2: Écrire les tests qui échouent**

`backend/tests/test_passwords.py` :
```python
from app.auth.passwords import hash_password, verify_password


def test_hash_and_verify():
    h = hash_password("s3cret")
    assert h != "s3cret" and h.startswith("pbkdf2$")
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_verify_bad_format():
    assert verify_password("x", "not-a-hash") is False
```

`backend/tests/test_tokens.py` :
```python
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
```

- [ ] **Step 3: Lancer** — `cd backend && py -3 -m pytest tests/test_passwords.py tests/test_tokens.py -q` → FAIL.

- [ ] **Step 4: Écrire l'implémentation**

`backend/app/auth/__init__.py` : vide.

`backend/app/auth/passwords.py` :
```python
from __future__ import annotations

import hashlib
import hmac
import os

_ITER = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iter_s, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iter_s))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False
```

`backend/app/auth/tokens.py` :
```python
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
```

- [ ] **Step 5: Lancer** — PASS (5).

- [ ] **Step 6: Commit**
```bash
git add backend/app/auth/__init__.py backend/app/auth/passwords.py backend/app/auth/tokens.py backend/requirements.txt backend/requirements-dev.txt backend/tests/test_passwords.py backend/tests/test_tokens.py
git commit -m "feat(backend): auth primitives — pbkdf2 passwords + JWT tokens"
```

---

### Task 2: `UserStore` (seed env)

**Files:**
- Create: `backend/app/auth/users.py`
- Test: `backend/tests/test_users.py`

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_users.py`
```python
from app.auth.passwords import hash_password
from app.auth.users import User, UserStore


def test_authenticate():
    s = UserStore({"admin": (hash_password("pw"), "admin")})
    assert s.authenticate("admin", "pw") == User("admin", "admin")
    assert s.authenticate("admin", "bad") is None
    assert s.authenticate("ghost", "pw") is None


def test_from_env():
    assert UserStore.from_env({}) is None
    assert UserStore.from_env({"ARGUS_JWT_SECRET": "x"}) is None  # aucun mot de passe
    s = UserStore.from_env({"ARGUS_JWT_SECRET": "x",
                            "ARGUS_ADMIN_PASSWORD": "pw", "ARGUS_HSE_PASSWORD": "pw2"})
    assert s.authenticate("admin", "pw").role == "admin"
    assert s.authenticate("hse", "pw2").role == "hse"
```

- [ ] **Step 2: Lancer** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/auth/users.py`
```python
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
```

- [ ] **Step 4: Lancer** — PASS (2).

- [ ] **Step 5: Commit**
```bash
git add backend/app/auth/users.py backend/tests/test_users.py
git commit -m "feat(backend): UserStore seeded from environment"
```

---

### Task 3: Journal — `acked_by`

**Files:**
- Modify: `backend/app/persistence/journal.py`
- Test: `backend/tests/test_journal.py` (ajout)

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `backend/tests/test_journal.py`
```python
def test_set_status_records_acked_by():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30))
    row_id = j.events()[0]["id"]
    j.set_status(row_id, "ack", acked_by="alice")
    assert j.event(row_id)["acked_by"] == "alice"
    assert j.events()[0]["acked_by"] == "alice"
```

- [ ] **Step 2: Lancer** — `cd backend && py -3 -m pytest tests/test_journal.py -q` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/persistence/journal.py`

(a) `_SCHEMA` events — remplacer :
```python
    snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);
```
par :
```python
    snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    acked_by TEXT
);
```

(b) Migration défensive dans `__init__` — après le `try/except` du `status`, ajouter :
```python
        try:
            self._conn.execute("ALTER TABLE events ADD COLUMN acked_by TEXT")
        except sqlite3.OperationalError:
            pass  # colonne déjà présente
```

(c) `set_status` — remplacer par :
```python
    def set_status(self, event_id: int, status: str, acked_by: str | None = None) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE events SET status = ?, acked_by = ? WHERE id = ?",
                (status, acked_by, event_id))
            self._conn.commit()
            return cur.rowcount > 0
```

(d) `events()` — SELECT : `... snapshot, status, acked_by FROM events` ; dict : ajouter
`"acked_by": r["acked_by"]`.

(e) `event()` — SELECT : `... snapshot, status, acked_by FROM events` ; dict : ajouter
`"acked_by": r["acked_by"]`.

- [ ] **Step 4: Lancer** — `cd backend && py -3 -m pytest tests/test_journal.py -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/persistence/journal.py backend/tests/test_journal.py
git commit -m "feat(backend): journal records acked_by on status change"
```

---

### Task 4: Dépendances FastAPI + `/auth/login` + `/auth/me`

**Files:**
- Create: `backend/app/auth/deps.py`
- Modify: `backend/app/api/app.py`, `backend/app/api/schemas.py`
- Test: `backend/tests/test_auth_api.py`

**Interfaces:**
- Produces: `current_user`, `require_role(*roles)` ; `POST /auth/login` ; `GET /auth/me` ;
  `app.state.user_store` / `app.state.jwt_secret`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_auth_api.py`
```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.auth.passwords import hash_password
from app.auth.users import UserStore


def _auth_client():
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b: b
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
```

- [ ] **Step 2: Lancer** — `cd backend && py -3 -m pytest tests/test_auth_api.py -q` → FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`backend/app/auth/deps.py` :
```python
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer

from app.auth.tokens import decode_token
from app.auth.users import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> User:
    store = request.app.state.user_store
    if store is None:                       # auth désactivée -> super-admin implicite
        return User("system", "admin")
    if not token:
        raise HTTPException(status_code=401, detail="authentification requise")
    try:
        data = decode_token(token, request.app.state.jwt_secret)
    except Exception:
        raise HTTPException(status_code=401, detail="token invalide")
    return User(data["sub"], data["role"])


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise HTTPException(status_code=403, detail="rôle insuffisant")
        return user
    return dep
```

`backend/app/api/schemas.py` — ajouter :
```python
class LoginRequest(BaseModel):
    username: str
    password: str
```

`backend/app/api/app.py` :
- imports :
```python
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
```
```python
from app.api.schemas import FrameMessage, LoginRequest, RtspSource, StatusUpdate, ZonesConfig, frame_response
from app.auth.deps import current_user, require_role
from app.auth.tokens import encode_token
from app.auth.users import User, UserStore
```
- état (après `app.state.notifier = None`) :
```python
    app.state.jwt_secret = os.environ.get("ARGUS_JWT_SECRET")
    app.state.user_store = None          # UserStore.from_env au lifespan ; injecté en test
```
- dans `lifespan`, après le bloc `notifier` :
```python
        if app.state.user_store is None:
            app.state.user_store = UserStore.from_env(os.environ)
```
- endpoints (après `health`, avant `/zones`) :
```python
    @app.post("/auth/login")
    def login(body: LoginRequest) -> dict:
        store = app.state.user_store
        if store is None:
            raise HTTPException(status_code=400, detail="auth non configurée")
        user = store.authenticate(body.username, body.password)
        if user is None:
            raise HTTPException(status_code=401, detail="identifiants invalides")
        token = encode_token(user.username, user.role, app.state.jwt_secret)
        return {"access_token": token, "token_type": "bearer", "role": user.role}

    @app.get("/auth/me")
    def auth_me(user: User = Depends(current_user)) -> dict:
        return {"username": user.username, "role": user.role}
```

- [ ] **Step 4: Lancer** — `cd backend && py -3 -m pytest tests/test_auth_api.py tests/test_api.py -q` → PASS (auth + API existante).

- [ ] **Step 5: Commit**
```bash
git add backend/app/auth/deps.py backend/app/api/app.py backend/app/api/schemas.py backend/tests/test_auth_api.py
git commit -m "feat(backend): /auth/login + /auth/me + role dependencies"
```

---

### Task 5: Protéger les endpoints d'écriture + `acked_by`

**Files:**
- Modify: `backend/app/api/app.py`
- Test: `backend/tests/test_auth_api.py` (ajouts)

- [ ] **Step 1: Écrire les tests qui échouent** — ajouter à `backend/tests/test_auth_api.py`
```python
def _zone_payload():
    return {"zones": [{"name": "z", "polygon": [[0, 0], [10, 0], [10, 10]],
                       "required_ppe": ["helmet"]}]}


def test_write_endpoints_enforce_roles():
    client = _auth_client()
    # sans token -> 401
    assert client.put("/zones", json=_zone_payload()).status_code == 401
    # hse ne peut pas éditer les zones -> 403
    hse = {"Authorization": f"Bearer {_token(client, 'hse')}"}
    assert client.put("/zones", json=_zone_payload(), headers=hse).status_code == 403
    # admin peut -> 200
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
    # pas de user_store configuré -> auth désactivée
    client = TestClient(app)
    assert client.put("/zones", json=_zone_payload()).status_code == 200
```
*(le `_auth_client` doit exposer un journal `:memory:` : ajouter `app.state.journal = Journal(":memory:")` dans `_auth_client` et l'import `from app.persistence.journal import Journal`.)*

- [ ] **Step 2: Lancer** — `cd backend && py -3 -m pytest tests/test_auth_api.py -q` → FAIL (endpoints pas encore protégés).

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/api/app.py`

- `put_zones` — ajouter le paramètre de dépendance :
```python
    @app.put("/zones")
    def put_zones(config: ZonesConfig,
                  user: User = Depends(require_role("admin"))) -> ZonesConfig:
```
- `start_rtsp` et `stop_rtsp` — ajouter `, user: User = Depends(require_role("admin"))` à leur
  signature.
- `set_event_status` — protéger + enregistrer l'opérateur :
```python
    @app.post("/events/{event_id}/status")
    def set_event_status(event_id: int, body: StatusUpdate,
                         user: User = Depends(require_role("hse"))) -> dict:
        if body.status not in {"active", "ack", "resolved"}:
            raise HTTPException(status_code=422, detail="statut invalide")
        if not app.state.journal.set_status(event_id, body.status, acked_by=user.username):
            raise HTTPException(status_code=404, detail="event introuvable")
        return app.state.journal.event(event_id)
```

- [ ] **Step 4: Lancer** — `cd backend && py -3 -m pytest tests/test_auth_api.py tests/test_status_api.py tests/test_rtsp_api.py tests/test_api.py -q` → PASS
  (les tests existants ne configurent pas d'auth → `require_role` renvoie l'admin implicite → 200).

- [ ] **Step 5: Commit**
```bash
git add backend/app/api/app.py backend/tests/test_auth_api.py
git commit -m "feat(backend): role-protect write endpoints + record acked_by"
```

---

### Task 6: Journal de décisions

**Files:**
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Ajouter l'entrée** (en haut, après l'intro)
```markdown
## 2026-08-31 — V2 : auth opt-in (JWT pyjwt, rôles admin/hse, protection écriture)
**Contexte.** Passage d'un POC ouvert à un outil multi-utilisateur, sans casser la démo.
**Décision.** Auth **opt-in** : active seulement si `ARGUS_JWT_SECRET` + mots de passe
configurés (sinon endpoints ouverts). JWT HS256 via **pyjwt** ; mots de passe **pbkdf2**
(stdlib) ; utilisateurs seedés depuis l'env (pas de table). `admin` super-utilisateur ;
`hse` = voir + acquitter. Cet incrément protège l'**écriture/config** ; reads + WS restent
ouverts (auth des reads/WS + login UI = incréments suivants). L'ack enregistre `acked_by`.
**Conséquence.** Compat V1 préservée ; comble la note « ack anonyme » de V1.5.
```

- [ ] **Step 2: Commit**
```bash
git add docs/DECISIONS.md
git commit -m "docs: decision log (opt-in JWT auth + roles)"
```

---

## Self-Review

**1. Couverture spec :** primitives pbkdf2 + JWT ✅ (T1) ; `UserStore.from_env` ✅ (T2) ;
`acked_by` journal ✅ (T3) ; deps + login/me + state ✅ (T4) ; protection écriture + acked_by ✅
(T5) ; décision ✅ (T6). Opt-in (endpoints ouverts sans config) testé (T5). `pyjwt` dans les deux
requirements ✅ (T1).

**2. Placeholders :** aucun — modules, endpoints, migration, tests complets. Éditions `app.py`
ancrées (imports, état, lifespan, endpoints existants).

**3. Cohérence des types :** `hash_password/verify_password` (T1) ← `UserStore` (T2) ;
`encode_token/decode_token` (T1) ← `deps.current_user` (T4) ; `User`/`UserStore` (T2) ←
`app.state.user_store` + endpoints (T4, T5) ; `require_role` (T4) ← zones/rtsp/status (T5) ;
`set_status(acked_by=)` (T3) ← `set_event_status` (T5). Auth désactivée ⇒ `current_user` renvoie
`User("system","admin")` ⇒ toutes les suites existantes restent ouvertes/vertes.
```
