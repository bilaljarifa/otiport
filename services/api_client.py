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


def _request(method: str, path: str, *, json: dict[str, Any] | None = None,
             timeout: int = 30) -> Any:
    url = f"{base_url()}{path}"
    try:
        response = requests.request(method, url, json=json, timeout=timeout)
    except requests.exceptions.ConnectionError:
        raise ApiError("offline", f"Impossible de joindre {url}.") from None
    except requests.exceptions.Timeout:
        raise ApiError("timeout", f"{path} n'a pas répondu en {timeout}s.") from None
    except requests.exceptions.RequestException as exc:
        raise ApiError("offline", f"Échec de la requête vers {url}.", str(exc)) from exc

    if response.status_code >= 400:
        detail: str | None = None
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text[:500] or None
        raise ApiError("http", f"{path} a renvoyé HTTP {response.status_code}.", detail)

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
