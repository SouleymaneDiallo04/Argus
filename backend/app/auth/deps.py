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
