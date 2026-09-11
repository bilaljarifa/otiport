# -*- coding: utf-8 -*-
"""Client for the Optiport FastAPI backend.

The backend owns the business logic (LSTM forecasting + Markowitz
optimisation). This module is a thin, typed transport layer: it never
recomputes anything, it only calls endpoints, caches read-only responses and
turns failures into a single `ApiError` the views can render as an error state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import requests
import streamlit as st

DEFAULT_BASE_URL = "http://localhost:8000"

# One reused connection pool for the whole process instead of a fresh TCP (+TLS,
# for https backends) handshake per call — `requests.request(...)` implicitly
# opens and tears down a new connection every time. Safe to share across
# Streamlit's per-session threads: urllib3's pool underneath is thread-safe,
# and no per-call state (cookies, auth) is stored on the session itself —
# every call still passes its own headers explicitly.
_session = requests.Session()

# Path to the per-ticker LSTM models, as expected by `backend.forecaster`.
DEFAULT_MODEL_PATH = "trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs"

Strategy = Literal["max_sharpe", "min_volatility", "risk_parity", "equal_weight"]


@dataclass
class ApiError(Exception):
    """A backend failure translated into something displayable."""

    kind: Literal["offline", "timeout", "http", "invalid"]
    message: str
    detail: str | None = None

    def __str__(self) -> str:  # pragma: no cover - display helper
        return self.message

    @property
    def title(self) -> str:
        return {
            "offline": "Backend injoignable",
            "timeout": "Délai dépassé",
            "http": "Erreur du service d'optimisation",
            "invalid": "Réponse invalide",
        }[self.kind]

    @property
    def hint(self) -> str:
        if self.kind == "offline":
            return (
                "Démarrez l'API : `uvicorn api:app --reload --port 8000` "
                "depuis le dossier Optiport."
            )
        if self.kind == "timeout":
            return (
                "Le forecast LSTM et le téléchargement des historiques peuvent "
                "dépasser deux minutes au premier appel. Réessayez avec moins d'ETF."
            )
        return self.detail or ""


def base_url() -> str:
    """Backend URL, overridable from the Settings page."""
    return st.session_state.get("prefs", {}).get("api_url", DEFAULT_BASE_URL).rstrip("/")


@dataclass
class AuthError(Exception):
    """Raised when the backend rejects the current token (expired, revoked,
    or the account was disabled). The app layer catches this to force a
    sign-out instead of showing a generic error state."""

    message: str

    def __str__(self) -> str:  # pragma: no cover - display helper
        return self.message


def _auth_headers() -> dict[str, str]:
    token = st.session_state.get("auth_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _request(method: str, path: str, *, json: dict[str, Any] | None = None,
             timeout: int = 30, auth: bool = True) -> Any:
    url = f"{base_url()}{path}"
    headers = _auth_headers() if auth else {}
    try:
        response = _session.request(method, url, json=json, headers=headers, timeout=timeout)
    except requests.exceptions.ConnectionError:
        raise ApiError("offline", f"Impossible de joindre {url}.") from None
    except requests.exceptions.Timeout:
        raise ApiError("timeout", f"{path} n'a pas répondu en {timeout}s.") from None
    except requests.exceptions.RequestException as exc:
        raise ApiError("offline", f"Échec de la requête vers {url}.", str(exc)) from exc

    if response.status_code in (401, 403) and auth:
        detail = None
        try:
            detail = response.json().get("detail")
        except ValueError:
            pass
        if response.status_code == 401:
            raise AuthError(detail or "Session expirée — veuillez vous reconnecter.")
        # 403 with a valid-but-insufficient token (e.g. non-admin hitting an
        # admin route) is a normal authorization failure, not a dead session.
        raise ApiError("http", f"{path} a renvoyé HTTP 403.", detail)

    if response.status_code >= 400:
        detail = None
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text[:500] or None
        raise ApiError("http", f"{path} a renvoyé HTTP {response.status_code}.", detail)

    if response.status_code == 204 or not response.content:
        return None

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("invalid", f"{path} n'a pas renvoyé du JSON.", str(exc)) from exc


# ---------------------------------------------------------------------------
#  Endpoints
# ---------------------------------------------------------------------------

@st.cache_data(ttl=20, show_spinner=False)
def health(_url: str) -> dict[str, Any] | None:
    """Backend health. `_url` is part of the cache key so the Settings page can
    point the app at another host and get a fresh probe."""
    try:
        return _request("GET", "/health", timeout=3)
    except ApiError:
        return None


def is_online() -> bool:
    return health(base_url()) is not None


def smart_invest(
    tickers: Sequence[str],
    *,
    strategy: Strategy = "max_sharpe",
    risk_free_rate: float = 0.05,
    investment_amount: float | None = None,
    include_charts: bool = True,
    model_path: str = DEFAULT_MODEL_PATH,
    timeout: int = 180,
) -> dict[str, Any]:
    """Forecast + optimise in one call (`POST /smart-invest`).

    This is the core action of the application; it is deliberately not cached so
    the user always gets a fresh run, and the result is persisted in session
    state by the caller.
    """
    payload = {
        "tickers": list(tickers),
        "model_path": model_path,
        "risk_free_rate": risk_free_rate,
        "strategy": strategy,
        "investment_amount": investment_amount,
        "include_charts": include_charts,
    }
    return _request("POST", "/smart-invest", json=payload, timeout=timeout)


@st.cache_data(ttl=900, show_spinner=False)
def forecast(tickers: tuple[str, ...], *, model_path: str = DEFAULT_MODEL_PATH,
             timeout: int = 180) -> dict[str, Any]:
    """22-day return forecasts per ticker (`POST /forecast`)."""
    return _request(
        "POST", "/forecast",
        json={"tickers": list(tickers), "model_path": model_path},
        timeout=timeout,
    )


@st.cache_data(ttl=300, show_spinner=False)
def chart_data(tickers: tuple[str, ...], *, period: str = "6mo",
               normalize: bool = True, timeout: int = 90) -> dict[str, Any]:
    """Price series and YTD returns (`POST /chart-data`)."""
    return _request(
        "POST", "/chart-data",
        json={"tickers": list(tickers), "period": period, "normalize": normalize},
        timeout=timeout,
    )


@st.cache_data(ttl=900, show_spinner=False)
def efficient_frontier(tickers: tuple[str, ...], *, risk_free_rate: float = 0.05,
                       n_points: int = 40, model_path: str = DEFAULT_MODEL_PATH,
                       timeout: int = 240) -> dict[str, Any]:
    """Efficient frontier points (`POST /efficient-frontier`)."""
    return _request(
        "POST", "/efficient-frontier",
        json={
            "tickers": list(tickers),
            "model_path": model_path,
            "risk_free_rate": risk_free_rate,
            "n_points": n_points,
        },
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
#  News, sentiment & market impact
#
#  NEWS_API_KEY never reaches this module or the browser: every call below
#  goes through the FastAPI backend, which is the only thing that talks to
#  NewsAPI (see backend/news_service.py).
# ---------------------------------------------------------------------------

def analyze_news(ticker: str, headline: str, *, description: str = "",
                 content: str = "", timeout: int = 20) -> dict[str, Any]:
    """Sentiment + market impact for a manually entered headline/article
    (`POST /news/analyze`). Not cached: each submission is a fresh request."""
    return _request(
        "POST", "/news/analyze",
        json={
            "ticker": ticker, "headline": headline,
            "description": description, "content": content,
        },
        timeout=timeout,
    )


@st.cache_data(ttl=900, show_spinner=False)
def ticker_news(ticker: str, timeout: int = 30) -> dict[str, Any]:
    """Recent, scored news for a ticker (`GET /news/{ticker}`)."""
    return _request("GET", f"/news/{ticker}", timeout=timeout)


@st.cache_data(ttl=900, show_spinner=False)
def ticker_news_summary(ticker: str, timeout: int = 30) -> dict[str, Any]:
    """Aggregated sentiment/impact for today's news (`GET /news/{ticker}/summary`)."""
    return _request("GET", f"/news/{ticker}/summary", timeout=timeout)


@st.cache_data(ttl=900, show_spinner=False)
def market_news_impact(tickers: tuple[str, ...], timeout: int = 120) -> dict[str, Any]:
    """News-driven sentiment/impact across a universe of tickers
    (`POST /news/market-impact`). One request instead of one per ticker."""
    return _request(
        "POST", "/news/market-impact",
        json={"tickers": list(tickers)},
        timeout=timeout,
    )


@st.cache_data(ttl=900, show_spinner=False)
def forecast_context(ticker: str, *, current_price: float | None = None,
                     model_path: str = DEFAULT_MODEL_PATH,
                     timeout: int = 180) -> dict[str, Any]:
    """Base forecast vs. news-context forecast (`POST /forecast/context`)."""
    return _request(
        "POST", "/forecast/context",
        json={"ticker": ticker, "model_path": model_path, "current_price": current_price},
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
#  Auth
#
#  register/login are unauthenticated by construction (no token exists yet);
#  everything else attaches whatever token is currently in session state.
# ---------------------------------------------------------------------------

def register(username: str, email: str, password: str, full_name: str,
             *, timeout: int = 20) -> dict[str, Any]:
    return _request(
        "POST", "/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": full_name},
        timeout=timeout, auth=False,
    )


def login(username: str, password: str, *, timeout: int = 20) -> dict[str, Any]:
    return _request(
        "POST", "/auth/login",
        json={"username": username, "password": password},
        timeout=timeout, auth=False,
    )


def logout(*, timeout: int = 10) -> None:
    """Revokes the current token server-side. Best-effort: a network failure
    here must never block the client from clearing its own session state."""
    try:
        _request("POST", "/auth/logout", timeout=timeout)
    except (ApiError, AuthError):
        pass


@st.cache_data(ttl=30, show_spinner=False)
def google_config(*, timeout: int = 5) -> dict[str, Any]:
    """Whether "Continue with Google" should be shown, and the (non-secret)
    client id needed to build the authorize URL. Cached briefly so the
    login screen doesn't re-check on every keystroke; never raises — an
    offline/misconfigured backend just means the button stays hidden."""
    try:
        return _request("GET", "/auth/google/config", timeout=timeout, auth=False)
    except ApiError:
        return {"enabled": False, "client_id": None}


def google_login(code: str, redirect_uri: str, *, timeout: int = 20) -> dict[str, Any]:
    return _request(
        "POST", "/auth/google",
        json={"code": code, "redirect_uri": redirect_uri},
        timeout=timeout, auth=False,
    )


def me(*, timeout: int = 20) -> dict[str, Any]:
    return _request("GET", "/auth/me", timeout=timeout)


def update_profile(*, full_name: str | None = None, job_title: str | None = None,
                    desk: str | None = None, timeout: int = 20) -> dict[str, Any]:
    payload = {k: v for k, v in {
        "full_name": full_name, "job_title": job_title, "desk": desk,
    }.items() if v is not None}
    return _request("PATCH", "/auth/me", json=payload, timeout=timeout)


# ---------------------------------------------------------------------------
#  Portfolio — the caller's own simulated account
#
#  Not cached: this is mutated by trading actions almost every run, and each
#  view needs a fresh read after a mutation.
# ---------------------------------------------------------------------------

def get_portfolio_summary(*, timeout: int = 20) -> dict[str, Any]:
    """Account + positions + orders + transactions + watchlist + alerts in
    one call (`GET /portfolio/summary`) — what `services.store.sync_portfolio()`
    uses instead of six separate requests."""
    return _request("GET", "/portfolio/summary", timeout=timeout)


def get_account(*, timeout: int = 20) -> dict[str, Any]:
    return _request("GET", "/portfolio/account", timeout=timeout)


def get_positions(*, timeout: int = 20) -> list[dict[str, Any]]:
    return _request("GET", "/portfolio/positions", timeout=timeout)


def get_orders(*, timeout: int = 20) -> list[dict[str, Any]]:
    return _request("GET", "/portfolio/orders", timeout=timeout)


def place_order(ticker: str, side: str, quantity: float, *, order_type: str = "MARKET",
                 limit_price: float | None = None, timeout: int = 30) -> dict[str, Any]:
    return _request(
        "POST", "/portfolio/orders",
        json={
            "ticker": ticker, "side": side, "quantity": quantity,
            "order_type": order_type, "limit_price": limit_price,
        },
        timeout=timeout,
    )


def cancel_order(order_id: int, *, timeout: int = 20) -> dict[str, Any]:
    return _request("POST", f"/portfolio/orders/{order_id}/cancel", timeout=timeout)


def get_transactions(*, timeout: int = 20) -> list[dict[str, Any]]:
    return _request("GET", "/portfolio/transactions", timeout=timeout)


def get_watchlist(*, timeout: int = 20) -> list[str]:
    return _request("GET", "/portfolio/watchlist", timeout=timeout)["tickers"]


def add_watch(ticker: str, *, timeout: int = 20) -> list[str]:
    return _request("POST", f"/portfolio/watchlist/{ticker}", timeout=timeout)["tickers"]


def remove_watch(ticker: str, *, timeout: int = 20) -> list[str]:
    return _request("DELETE", f"/portfolio/watchlist/{ticker}", timeout=timeout)["tickers"]


def get_alerts(*, timeout: int = 20) -> list[dict[str, Any]]:
    return _request("GET", "/portfolio/alerts", timeout=timeout)


def add_alert(ticker: str, direction: str, threshold: float, note: str = "",
              *, timeout: int = 20) -> dict[str, Any]:
    return _request(
        "POST", "/portfolio/alerts",
        json={"ticker": ticker, "direction": direction, "threshold": threshold, "note": note},
        timeout=timeout,
    )


def remove_alert(alert_id: int, *, timeout: int = 20) -> None:
    _request("DELETE", f"/portfolio/alerts/{alert_id}", timeout=timeout)


def reset_alert_api(alert_id: int, *, timeout: int = 20) -> dict[str, Any]:
    return _request("POST", f"/portfolio/alerts/{alert_id}/reset", timeout=timeout)


def settle(*, timeout: int = 30) -> None:
    """Match open limit orders / active alerts against fresh prices. Called
    once per Streamlit run."""
    _request("POST", "/portfolio/settle", timeout=timeout)


def reset_account(*, timeout: int = 20) -> None:
    _request("POST", "/portfolio/reset", timeout=timeout)


# ---------------------------------------------------------------------------
#  Admin
# ---------------------------------------------------------------------------

def admin_list_users(*, timeout: int = 20) -> list[dict[str, Any]]:
    return _request("GET", "/admin/users", timeout=timeout)


def admin_update_user(user_id: int, *, role: str | None = None,
                       is_active: bool | None = None, timeout: int = 20) -> dict[str, Any]:
    payload = {k: v for k, v in {"role": role, "is_active": is_active}.items() if v is not None}
    return _request("PATCH", f"/admin/users/{user_id}", json=payload, timeout=timeout)


def admin_delete_user(user_id: int, *, timeout: int = 20) -> None:
    _request("DELETE", f"/admin/users/{user_id}", timeout=timeout)


def admin_stats(*, timeout: int = 20) -> dict[str, Any]:
    return _request("GET", "/admin/stats", timeout=timeout)
