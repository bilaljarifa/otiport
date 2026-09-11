# -*- coding: utf-8 -*-
"""Environment configuration for the FastAPI backend.

Secrets (`NEWS_API_KEY`, `AUTH_SECRET_KEY`) are read from `.env` (via
`python-dotenv`) or the process environment and never leave this module as a
bare string outside of the functions that hand them to the code that needs
them. Nothing here logs, prints, or returns a secret — `api.py` must never
place one in a response body.
"""

from __future__ import annotations

import os
import secrets
import warnings
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is in requirements.txt
    load_dotenv = None

_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _ROOT / ".env"

# Single source of truth for the version reported by `/health` and the admin
# system-stats endpoint — keep in sync with the `FastAPI(version=...)` in api.py.
APP_VERSION = "2.1.0"

if load_dotenv is not None:
    load_dotenv(_ENV_PATH)


def news_api_key() -> str | None:
    """The NewsAPI key, or `None` when unset.

    Never log or serialize the return value.
    """
    return os.environ.get("NEWS_API_KEY") or None


def has_news_api_key() -> bool:
    return bool(news_api_key())


def openai_api_key() -> str | None:
    """The OpenAI API key, or `None` when unset.

    Never log or serialize the return value.
    """
    return os.environ.get("OPENAI_API_KEY") or None


def has_openai_key() -> bool:
    return bool(openai_api_key())


def openai_model() -> str:
    return os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"


def groq_api_key() -> str | None:
    """The Groq API key, or `None` when unset.

    Never log or serialize the return value.
    """
    return os.environ.get("GROQ_API_KEY") or None


def has_groq_key() -> bool:
    return bool(groq_api_key())


def groq_base_url() -> str:
    return (os.environ.get("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")


def groq_model() -> str:
    return os.environ.get("GROQ_MODEL") or "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
#  AI Assistant provider — "groq" (default: free tier, hosted, no local
#  compute needed, requires GROQ_API_KEY) or "openai" (paid, requires
#  OPENAI_API_KEY above). Never a secret itself.
# ---------------------------------------------------------------------------

def ai_provider() -> str:
    return (os.environ.get("AI_PROVIDER") or "groq").strip().lower()


# ---------------------------------------------------------------------------
#  Auth
# ---------------------------------------------------------------------------

# Generated once per process when AUTH_SECRET_KEY is unset, so a bare dev
# checkout still works. This means tokens stop validating across restarts —
# fine for local development, not acceptable in production. Set
# AUTH_SECRET_KEY explicitly (a long random string) anywhere the backend
# needs to keep issuing valid tokens across restarts.
_FALLBACK_SECRET_KEY = secrets.token_hex(32)
_warned_fallback_secret = False


def secret_key() -> str:
    """The JWT signing secret. Never log or serialize the return value."""
    global _warned_fallback_secret
    key = os.environ.get("AUTH_SECRET_KEY")
    if key:
        return key
    if not _warned_fallback_secret:
        warnings.warn(
            "AUTH_SECRET_KEY is not set — using a random per-process secret. "
            "All issued tokens will be invalidated on restart. Set "
            "AUTH_SECRET_KEY in .env for any persistent deployment.",
            RuntimeWarning,
            stacklevel=2,
        )
        _warned_fallback_secret = True
    return _FALLBACK_SECRET_KEY


def token_expire_minutes() -> int:
    """Access token lifetime, in minutes. Defaults to 8 working hours."""
    raw = os.environ.get("AUTH_TOKEN_EXPIRE_MINUTES")
    try:
        return int(raw) if raw else 480
    except ValueError:
        return 480


def database_url() -> str:
    """SQLAlchemy database URL. Defaults to a SQLite file at the repo root."""
    return os.environ.get("DATABASE_URL") or f"sqlite:///{_ROOT / 'optiport.db'}"


# ---------------------------------------------------------------------------
#  Google OAuth (optional — "Continue with Google" is hidden/disabled on the
#  frontend until all three of these are set; see `backend/google_oauth.py`)
# ---------------------------------------------------------------------------

def google_client_id() -> str | None:
    """Not a secret — also used by the frontend to build the Google
    authorize URL, so it's fine for it to reach the browser."""
    return os.environ.get("GOOGLE_CLIENT_ID") or None


def google_client_secret() -> str | None:
    """Never leaves `backend/google_oauth.py` — the authorization-code
    exchange happens server-side specifically so this never reaches the
    browser/Streamlit frontend."""
    return os.environ.get("GOOGLE_CLIENT_SECRET") or None


def google_redirect_uri() -> str | None:
    """Must exactly match a redirect URI registered on the Google Cloud
    OAuth client — typically the Streamlit app's own URL
    (e.g. http://localhost:8501)."""
    return os.environ.get("GOOGLE_REDIRECT_URI") or None


def google_oauth_configured() -> bool:
    return bool(google_client_id() and google_client_secret() and google_redirect_uri())


# ---------------------------------------------------------------------------
#  CORS — only needed once a browser-based frontend (React) calls this API
#  directly from a different origin. Streamlit never needed this: it made
#  the same-process/server-side Python calls, never a browser fetch.
# ---------------------------------------------------------------------------

_DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173", "http://127.0.0.1:5173",  # Vite dev server
    "http://localhost:8501", "http://127.0.0.1:8501",  # Streamlit, kept during migration
)


def cors_allowed_origins() -> list[str]:
    """Comma-separated `CORS_ALLOWED_ORIGINS` env var, or the dev defaults."""
    raw = os.environ.get("CORS_ALLOWED_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return list(_DEFAULT_CORS_ORIGINS)
