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


def lstm_model_dir() -> str | None:
    """Optional override for where trained LSTM models/scalers live, or
    `None` to use `backend/forecaster.py`'s repo-relative default.

    Needed because the trained `.keras`/`scalers.pkl` files are gitignored
    (too large/binary for version control) and, on a host that rebuilds the
    code checkout from git on every deploy (e.g. Render), the repo-relative
    default would point at a location that's wiped on every redeploy. Set
    this to an absolute path on a persistent volume/disk instead — e.g.
    `/var/data/lstm_models` — and the models survive redeploys without
    needing to be re-uploaded each time.
    """
    return os.environ.get("LSTM_MODEL_DIR") or None


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
    browser frontend."""
    return os.environ.get("GOOGLE_CLIENT_SECRET") or None


def google_redirect_uri() -> str | None:
    """Must exactly match a redirect URI registered on the Google Cloud
    OAuth client, and the one the React frontend used to build the
    authorize URL (both read this same value via `GET /auth/google/config`,
    so they can never drift from each other)."""
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
)


def cors_allowed_origins() -> list[str]:
    """Comma-separated `CORS_ALLOWED_ORIGINS` env var, or the dev defaults."""
    raw = os.environ.get("CORS_ALLOWED_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return list(_DEFAULT_CORS_ORIGINS)


def frontend_url() -> str:
    """Where the browser gets sent back to after `GET /auth/google/callback`
    finishes exchanging the code — the deployed React app's own origin, no
    trailing slash. Defaults to the Vite dev server."""
    return (os.environ.get("FRONTEND_URL") or "http://localhost:5173").rstrip("/")


# ---------------------------------------------------------------------------
#  Stripe billing (optional — Pricing/Billing pages report `stripe_configured:
#  false` and hide checkout/portal actions until all of these are set; see
#  backend/stripe_service.py)
# ---------------------------------------------------------------------------

def stripe_secret_key() -> str | None:
    """Never leaves `backend/stripe_service.py` — this is the key that
    authenticates every server-to-Stripe API call, never sent to the
    browser."""
    return os.environ.get("STRIPE_SECRET_KEY") or None


def stripe_webhook_secret() -> str | None:
    """Used only to verify the `Stripe-Signature` header on incoming
    webhooks — proves a request genuinely came from Stripe rather than an
    attacker POSTing a forged "subscription activated" event."""
    return os.environ.get("STRIPE_WEBHOOK_SECRET") or None


def stripe_price_id(plan: str) -> str | None:
    """The recurring Stripe Price id for "pro" or "premium" — configured
    per-deployment (test vs. live mode Stripe accounts use different ids for
    the same product)."""
    env_var = {"pro": "STRIPE_PRO_PRICE_ID", "premium": "STRIPE_PREMIUM_PRICE_ID"}.get(plan)
    if env_var is None:
        return None
    return os.environ.get(env_var) or None


def stripe_configured() -> bool:
    """Whether checkout can actually be started — the secret key plus both
    plan prices. `STRIPE_WEBHOOK_SECRET` is checked separately by the
    webhook route itself, since a deployment could theoretically accept
    checkouts before its webhook endpoint is registered with Stripe."""
    return bool(stripe_secret_key() and stripe_price_id("pro") and stripe_price_id("premium"))


def payment_mode() -> str:
    """"demo" or "stripe" — which checkout flow `/pricing` uses.

    Explicit `PAYMENT_MODE=demo`/`PAYMENT_MODE=stripe` always wins. Left
    unset, this infers the sensible default for whichever environment it's
    running in: "stripe" once real Stripe credentials are present, "demo"
    otherwise — so a fresh checkout (e.g. this account's Morocco-based
    Stripe access not being available yet for the PFE demo) never breaks
    the Pricing page just because Stripe isn't configured, and a real
    deployment that *does* set Stripe credentials doesn't need to also
    remember to flip this flag. The demo endpoint itself additionally
    refuses to run unless this resolves to "demo" (see
    backend/routers/billing.py), so the two modes can never be mixed
    per-request."""
    raw = (os.environ.get("PAYMENT_MODE") or "").strip().lower()
    if raw in ("demo", "stripe"):
        return raw
    return "stripe" if stripe_configured() else "demo"
