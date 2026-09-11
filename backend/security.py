# -*- coding: utf-8 -*-
"""Password hashing and JWT issuance/verification.

Passwords are hashed with bcrypt directly (no passlib — recent bcrypt
releases dropped the `__about__` attribute passlib's version probe relies
on). Tokens are short-lived JWTs whose payload carries only identity
(`sub`, `jti`, `exp`) — role and active-status are never trusted from the
token itself; `backend/deps.py` re-reads them from the database on every
request.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from backend.config import secret_key, token_expire_minutes

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:  # malformed hash
        return False


def create_access_token(user_id: int) -> tuple[str, str, datetime]:
    """Returns `(token, jti, expires_at)`."""
    jti = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=token_expire_minutes())
    payload: dict[str, Any] = {"sub": str(user_id), "jti": jti, "exp": expires_at}
    token = jwt.encode(payload, secret_key(), algorithm=_ALGORITHM)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises `jwt.PyJWTError` on an invalid/expired token."""
    return jwt.decode(token, secret_key(), algorithms=[_ALGORITHM])
