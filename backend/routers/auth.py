# -*- coding: utf-8 -*-
"""Registration, login, logout and the current user's own profile."""

from __future__ import annotations

from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import crud
from backend.config import (
    frontend_url,
    google_client_id,
    google_oauth_configured,
    google_redirect_uri,
)
from backend.db import get_db
from backend.deps import get_current_user
from backend.google_oauth import GoogleOAuthError, exchange_code_for_profile
from backend.models import TokenBlocklist, User
from backend.schemas import (
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)
from backend.security import create_access_token, decode_access_token
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/auth", tags=["auth"])

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if crud.get_user_by_username(db, req.username) is not None:
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur est déjà pris.")
    if crud.get_user_by_email(db, req.email) is not None:
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est déjà utilisée.")

    try:
        user = crud.create_user(
            db, username=req.username, email=req.email,
            password=req.password, full_name=req.full_name,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Nom d'utilisateur ou e-mail déjà utilisé.") from None

    token, _jti, _exp = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = crud.authenticate_user(db, req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Nom d'utilisateur ou mot de passe incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Ce compte est désactivé.")

    token, _jti, _exp = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str | None = Depends(_oauth2_scheme), db: Session = Depends(get_db)) -> None:
    """Revokes the presented token by blocklisting its `jti`, so it cannot be
    replayed even though JWTs are otherwise stateless."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return None
    jti = payload.get("jti")
    if jti and not db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).first():
        db.add(TokenBlocklist(jti=jti))
        db.commit()
    return None


@router.get("/google/config")
def google_config() -> dict:
    """Whether "Continue with Google" should be shown at all, and the
    (non-secret) client id + redirect URI the frontend needs to build the
    Google authorize URL itself — one source of truth for the redirect URI
    so it can't drift from what the token-exchange step below expects. The
    client secret never leaves this backend."""
    if not google_oauth_configured():
        return {"enabled": False, "client_id": None, "redirect_uri": None}
    return {
        "enabled": True,
        "client_id": google_client_id(),
        "redirect_uri": google_redirect_uri(),
    }


def _complete_google_login(db: Session, code: str, redirect_uri: str | None) -> User:
    """Shared by both Google entry points below — the JSON API
    (`POST /auth/google`, a code-exchange the *caller* already has, e.g. a
    non-browser client) and the browser redirect handler
    (`GET /auth/google/callback`, the one this app's own Login page uses).
    Raises `GoogleOAuthError`/`crud.EmailAlreadyRegistered`/`ValueError`
    (disabled account) — each entry point maps these to its own appropriate
    response shape (a JSON error vs. a redirect back to the frontend)."""
    profile = exchange_code_for_profile(code, redirect_uri)
    user = crud.get_or_create_google_user(db, profile)
    if not user.is_active:
        raise ValueError("Ce compte est désactivé.")
    return user


@router.post("/google", response_model=TokenResponse)
def google_login(req: GoogleAuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = _complete_google_login(db, req.code, req.redirect_uri)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except crud.EmailAlreadyRegistered as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None

    token, _jti, _exp = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/google/callback")
def google_callback(code: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    """Where Google's own redirect actually lands — registered as the
    Authorized redirect URI on the Google Cloud OAuth client, so it must be
    a real, GET-able backend route rather than something only the React app
    serves. Never renders a raw JSON error to the browser here: this whole
    request is a top-level navigation Google initiated, not a fetch the
    frontend can catch, so every outcome ends in a redirect back to the
    frontend's own callback page — success puts the Optiport JWT in the URL
    *fragment* (`#access_token=...`), which browsers never send to any
    server (ours included) and which never appears in server access logs,
    unlike a query parameter would."""
    callback_page = f"{frontend_url()}/auth/google/callback"

    if error:
        return RedirectResponse(f"{callback_page}?{urlencode({'error': error})}")
    if not code:
        return RedirectResponse(f"{callback_page}?{urlencode({'error': 'missing_code'})}")

    try:
        user = _complete_google_login(db, code, google_redirect_uri())
    except (GoogleOAuthError, crud.EmailAlreadyRegistered, ValueError) as exc:
        return RedirectResponse(f"{callback_page}?{urlencode({'error': str(exc)})}")

    token, _jti, _exp = create_access_token(user.id)
    return RedirectResponse(f"{callback_page}#access_token={token}")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    req: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> UserOut:
    updated = crud.update_profile(
        db, user, full_name=req.full_name, job_title=req.job_title, desk=req.desk,
    )
    return UserOut.model_validate(updated)
