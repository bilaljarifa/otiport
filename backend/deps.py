# -*- coding: utf-8 -*-
"""Auth dependencies shared by every protected endpoint.

`get_current_user` re-reads `role`/`is_active` from the database on every
call — it never trusts those fields from the JWT payload itself. That means
disabling a user or changing their role takes effect immediately on their
next request, even with an unexpired token, and a logged-out token (its
`jti` in `token_blocklist`) is rejected outright.
"""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import TokenBlocklist, User
from backend.security import decode_access_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Identifiants invalides ou expirés.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise _CREDENTIALS_ERROR
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise _CREDENTIALS_ERROR from None

    jti = payload.get("jti")
    if jti and db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).first():
        raise _CREDENTIALS_ERROR

    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        raise _CREDENTIALS_ERROR from None

    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    if not user.is_active:
        # 401, not 403: a disabled account should force the client to sign
        # out and show the login screen, not surface as "forbidden" on an
        # otherwise-valid session (that's reserved for role checks, e.g.
        # require_admin).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ce compte a été désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux administrateurs.",
        )
    return user
