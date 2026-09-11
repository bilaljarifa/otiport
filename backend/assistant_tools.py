# -*- coding: utf-8 -*-
"""Real data functions the AI Assistant can call (OpenAI tool/function
calling) — every one of these wraps an existing Optiport data source
(the database, `backend/pricing.py`, `backend/news_*`, `backend/forecaster.py`,
`backend/optimizer.py`). None of them compute or invent anything new; they
only shape existing results into compact JSON for the model to read.

Deliberately imports from `backend.*` only, never from `api.py` — `api.py`
registers the assistant router, so importing back from it would be circular.
Where `api.py` already has the same shape (e.g. `_get_analyzed_news`), the
handful of lines are mirrored here rather than shared, to keep the two
call paths (one HTTP-request-scoped, one tool-call-scoped) independent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend import crud, pricing
from backend.etf_metadata import ETF_METADATA
from backend.forecaster import get_portfolio_data, predict_returns
from backend.models import User
from backend.news_aggregator import aggregate as aggregate_news
from backend.news_cache import analyzed_news_cache
from backend.news_pipeline import analyze_articles
from backend.news_service import NewsServiceError, fetch_news_for_ticker
from backend.optimizer import optimize_portfolio

DEFAULT_TICKERS: list[str] = list(ETF_METADATA.keys())


def get_portfolio(db: Session, user: User) -> dict[str, Any]:
    """The caller's real simulated account: cash plus every open position
    marked to the latest known price."""
    account = user.account
    positions = crud.list_positions(db, account.id)
    tickers = [p.ticker for p in positions]
    prices = pricing.get_last_prices(tickers) if tickers else {}

    holdings = []
    market_value = 0.0
    for p in positions:
        price = prices.get(p.ticker)
        value = price * p.quantity if price is not None else None
        if value is not None:
            market_value += value
        holdings.append({
            "ticker": p.ticker,
            "quantity": p.quantity,
            "avg_cost": round(p.avg_price, 4),
            "last_price": round(price, 4) if price is not None else None,
            "market_value": round(value, 2) if value is not None else None,
            "unrealized_pnl": round(value - p.quantity * p.avg_price, 2) if value is not None else None,
        })

    return {
        "cash": round(account.cash, 2),
        "positions": holdings,
        "total_market_value": round(market_value, 2),
        "equity": round(account.cash + market_value, 2),
    }


def get_market_quotes(tickers: list[str]) -> dict[str, Any]:
    """Live price + previous close + day change for arbitrary tickers —
    same data source as `GET /market/quotes`."""
    tickers = [t.upper() for t in tickers][:20]
    quotes = pricing.get_quotes(tickers)
    missing = [t for t in tickers if t not in quotes]
    return {"quotes": quotes, "missing": missing}


def get_ticker_news(ticker: str) -> dict[str, Any]:
    """Recent news + aggregated sentiment for one ticker — same pipeline as
    `GET /news/{ticker}` and `GET /news/{ticker}/summary`, independently
    cached here (see module docstring)."""
    ticker = ticker.upper()
    cached = analyzed_news_cache.get(ticker)
    if cached is None:
        company_name = ETF_METADATA.get(ticker, {}).get("name")
        query_name = f"{company_name} ETF" if company_name else None
        try:
            raw_articles = fetch_news_for_ticker(ticker, company_name=query_name)
        except NewsServiceError as exc:
            return {"error": f"News service unavailable ({exc.kind})."}
        cached = analyze_articles(raw_articles)
        cached.sort(key=lambda a: a.get("publishedAt") or "", reverse=True)
        analyzed_news_cache.set(ticker, cached)

    summary = aggregate_news(cached)
    headlines = [
        {
            "title": a["title"],
            "sentiment": a["sentiment"]["label"],
            "publishedAt": a["publishedAt"],
        }
        for a in cached[:8]
    ]
    return {"ticker": ticker, "summary": summary, "recent_headlines": headlines}


def get_return_forecast(tickers: list[str] | None = None) -> dict[str, Any]:
    """22-day forward return forecast per ticker from the existing per-ticker
    LSTM pipeline, with the same honest per-ticker fallback note used
    elsewhere in the app when a trained model isn't available."""
    tickers = [t.upper() for t in tickers] if tickers else DEFAULT_TICKERS
    try:
        predictions = predict_returns(tickers=tickers)
    except Exception as exc:
        return {"error": f"Forecast failed: {exc}"}
    return {
        ticker: {
            "predicted_return_22d": pred.get("predicted_return_22d"),
            "last_actual_return_22d": pred.get("last_actual_return_22d"),
            "note": pred.get("note"),
        }
        for ticker, pred in predictions.items()
    }


def get_portfolio_optimization(
    tickers: list[str] | None = None,
    strategy: str = "max_sharpe",
    risk_free_rate: float = 0.05,
) -> dict[str, Any]:
    """Optimized allocation over real forecasted returns + historical
    covariance — the same engine behind `POST /optimize` / `/smart-invest`.
    Slow (fetches fresh historical data for every ticker); only call this
    when the user actually asks for an allocation/optimization."""
    tickers = [t.upper() for t in tickers] if tickers else DEFAULT_TICKERS
    if strategy not in {"max_sharpe", "min_volatility", "risk_parity", "equal_weight"}:
        strategy = "max_sharpe"

    try:
        data = get_portfolio_data(tickers=tickers)
        weights, metrics = optimize_portfolio(
            mu=data["expected_returns"], cov=data["covariance_matrix"],
            risk_free=risk_free_rate, strategy=strategy,
        )
    except Exception as exc:
        return {"error": f"Optimization failed: {exc}"}

    allocations = [
        {
            "ticker": t,
            "name": ETF_METADATA.get(t, {}).get("name", t),
            "weight_percent": round(float(w) * 100, 2),
        }
        for t, w in zip(tickers, weights)
    ]
    allocations.sort(key=lambda a: -a["weight_percent"])

    return {
        "strategy": strategy,
        "allocations": allocations,
        "expected_annual_return_percent": round(metrics["expected_return"] * 100, 2),
        "annual_volatility_percent": round(metrics["volatility"] * 100, 2),
        "sharpe_ratio": round(metrics["sharpe"], 2),
    }
