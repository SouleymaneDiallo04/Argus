# V2 — Auth + rôles (backend) — Design

**Date :** 2026-08-31
**Phase :** V2 — première brique (auth). Incrément **backend**.
**Dépend de :** tout V1/V1.5 mergé sur `main`.
**Statut :** validé

## 1. Objectif

Ajouter une authentification par **JWT** et deux **rôles** (`admin`, `hse`), et protéger les
endpoints d'écriture/config. L'acquittement enregistre désormais **qui** a acquitté. Le login UI
et le câblage côté front sont l'**incrément suivant**.

## 2. Décisions de conception (validées)

- **JWT via `pyjwt`** (HS256) — 2ᵉ nouvelle dépendance du projet (après reportlab).
- **Protection écriture/config seulement** : `PUT /zones`, `POST/DELETE /sources/rtsp` (**admin**),
  `POST /events/{id}/status` (**hse+admin**). Reads + WS restent ouverts (incrément suivant).
- **Auth opt-in** : active **uniquement si configurée** (`ARGUS_JWT_SECRET` + mots de passe).
  Sinon endpoints ouverts (comportement V1 préservé — rien ne casse, la démo tourne sans creds).
- **admin est super-utilisateur** (passe toutes les exigences de rôle).
- Mots de passe hachés **pbkdf2 (stdlib)** ; utilisateurs **seedés depuis l'env**, pas de table.

## 3. Périmètre

**Dans cet incrément (backend) :**
- Module `app/auth/` (mots de passe, tokens, store d'utilisateurs, dépendances FastAPI).
- `POST /auth/login`, `GET /auth/me`.
- Protection par rôle des endpoints d'écriture/config + `acked_by` sur l'ack.
- Dépendance `pyjwt` + config + `DECISIONS.md`.

**Hors périmètre (incrément suivant) :** login UI, contexte d'auth front, envoi du token, gating
des actions par rôle, protection des reads + du WS.

## 4. Module `app/auth/`

### `passwords.py` (stdlib)
```
hash_password(password: str) -> str            # "pbkdf2$<iter>$<salt_hex>$<hash_hex>"
verify_password(password: str, stored: str) -> bool   # hmac.compare_digest, tolère un format invalide -> False
```

### `tokens.py` (pyjwt)
```
encode_token(username: str, role: str, secret: str, ttl_seconds=28800) -> str  # HS256, claim exp
decode_token(token: str, secret: str) -> dict   # {sub, role} ; lève jwt.InvalidTokenError si invalide/expiré
```

### `users.py`
```
@dataclass(frozen=True) class User: username: str; role: str
class UserStore:
    def __init__(self, users: dict[str, tuple[str, str]])   # username -> (hash, role)
    def authenticate(self, username, password) -> User | None
    @classmethod def from_env(cls, env) -> "UserStore | None"
        # None si ARGUS_JWT_SECRET absent OU aucun mot de passe configuré.
        # sinon seed: admin=ARGUS_ADMIN_PASSWORD (role admin), hse=ARGUS_HSE_PASSWORD (role hse),
        # ceux présents seulement.
```

### `deps.py` (FastAPI)
```
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

def current_user(request, token=Depends(oauth2_scheme)) -> User:
    store = request.app.state.user_store
    if store is None:                       # auth désactivée -> super-admin implicite
        return User("system", "admin")
    if not token: raise HTTPException(401)
    try: data = decode_token(token, request.app.state.jwt_secret)
    except Exception: raise HTTPException(401)
    return User(data["sub"], data["role"])

def require_role(*roles):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise HTTPException(403)
        return user
    return dep
```

## 5. API

- **`POST /auth/login`** body `{username, password}` :
  - store `None` → 400 (« auth non configurée ») ;
  - `authenticate` échoue → 401 ;
  - sinon → `{"access_token": <jwt>, "token_type": "bearer", "role": <role>}`.
- **`GET /auth/me`** (`Depends(current_user)`) → `{"username", "role"}`.
- Protection (via `Depends(require_role(...))`) :
  - `PUT /zones` → `require_role("admin")` ;
  - `POST /sources/rtsp`, `DELETE /sources/rtsp` → `require_role("admin")` ;
  - `POST /events/{id}/status` → `require_role("hse")` (admin super-user OK) ; passe
    `user.username` en `acked_by`.

## 6. Journal — `acked_by`

- Colonne `acked_by TEXT` sur `events` (nullable) + migration défensive.
- `set_status(event_id, status, acked_by=None)` : `UPDATE ... SET status=?, acked_by=? ...`.
- `events()` / `event()` : incluent `acked_by`.

## 7. Câblage `create_app`

- `app.state.jwt_secret = os.environ.get("ARGUS_JWT_SECRET")`.
- `app.state.user_store = None` (défaut) ; au `lifespan`, `UserStore.from_env(os.environ)`
  (reste `None` si non configuré). **Injectable en test** (comme detector/journal).
- `POST /auth/login` lit `app.state.user_store` + `jwt_secret`.

## 8. Fichiers

```
backend/app/auth/__init__.py
backend/app/auth/passwords.py
backend/app/auth/tokens.py
backend/app/auth/users.py
backend/app/auth/deps.py
backend/app/api/app.py            # login/me ; require_role sur zones/rtsp/status ; state auth
backend/app/api/schemas.py        # LoginRequest
backend/app/persistence/journal.py # acked_by
backend/requirements.txt + requirements-dev.txt   # pyjwt
backend/tests/test_passwords.py test_tokens.py test_users.py test_auth_api.py
backend/tests/test_journal.py     # acked_by
docs/DECISIONS.md
```

## 9. Tests (TDD)

- **passwords** : hash≠pw ; verify vrai/faux ; format invalide → False.
- **tokens** : encode→decode `{sub,role}` ; secret erroné → lève ; ttl négatif (expiré) → lève.
- **users** : `authenticate` ok/mauvais mdp/inconnu ; `from_env` seed admin+hse ; `None` si non
  configuré.
- **auth_api** : login ok→token + role ; mauvais creds→401 ; `/auth/me`→user ; endpoint protégé
  sans token→401 ; rôle insuffisant→403 ; bon rôle→200 ; **auth désactivée (pas de store) →
  endpoints ouverts** (200 sans token) ; ack enregistre `acked_by`.
- **journal** : `set_status(..., acked_by="x")` → `event()["acked_by"]=="x"`.
- Suites existantes vertes (backend **112** — elles ne configurent pas d'auth → ouvertes).

## 10. Critères d'acceptation

1. Sans config d'auth : comportement V1 inchangé (endpoints ouverts, suites vertes).
2. Avec config : login renvoie un JWT ; `/auth/me` identifie l'utilisateur ; les endpoints
   d'écriture exigent le bon rôle (401 sans token, 403 rôle insuffisant, 200 sinon).
3. L'ack enregistre `acked_by`.
4. `pyjwt` ajouté aux deux requirements ; CI verte.
