# -*- coding: utf-8 -*-
"""Historical backtesting engine for the app's own forecast + optimize
strategy: LSTM-forecasted 22-day returns (`backend/forecaster.py`) rebalanced
into a mean-variance-optimized allocation (`backend/optimizer.py`) every 22
trading days — the model's own forecast horizon, so the strategy trades on
its forecast exactly as often as that forecast is valid for.

This is a historical simulation, not a prediction of future performance.

No look-ahead: technical features (`compute_features`) use only backward
-looking rolling windows, computed once over the whole fetched window, then
at each rebalance date `t` only rows with `Date <= t` are read out of that
same dataset — mathematically identical to recomputing features on data
truncated at `t` (rolling windows never see rows after the row they're
computed for), but without recomputing the expensive feature pipeline once
per rebalance. `tests/test_backtester.py` verifies this directly: changing
prices *after* a given rebalance date does not change the weights chosen at
that date.

Execution assumption: a signal computed from data through date `t` is
assumed to fill at `t`'s own closing price — the same "fill at the
backend-fetched last/current price" assumption `backend/crud.py`'s paper
trading engine already uses for MARKET orders, extended here across
historical dates. No commissions, slippage, or bid/ask spread are modeled;
this is disclosed in `methodology_notes` on every response, not hidden.
"""

from __future__ import annotations

from typing import Callable, Literal, Optional

import numpy as np
import pandas as pd

from backend.forecaster import (
    DEFAULT_MODEL_DIR,
    REGION_MAPPING,
    compute_covariance_matrix,
    compute_features,
    create_sequences_for_prediction,
    ensure_positive_semidefinite,
    fetch_etf_data,
    load_model_with_weights,
    load_scalers,
    prepare_dataset,
    resolve_model_dir,
    annualize_22d_return,
)
from backend.optimizer import optimize_portfolio
from backend.performance_metrics import InsufficientHistoryError, curve_stats
from backend.ttl_cache import TTLCache
from train_model import SEQ_LENGTH

TRAINED_TICKERS = list(REGION_MAPPING.keys())
Strategy = Literal["max_sharpe", "min_volatility", "risk_parity", "equal_weight"]

# The model's own forecast horizon (`predict_returns` predicts a 22-trading
# -day return) — rebalancing on that same cadence is what makes this "the
# existing forecasting/portfolio logic" rather than an arbitrary schedule.
REBALANCE_EVERY_N_DAYS = 22

# Calendar-day lookback fetched *before* the requested start date so the
# first rebalance already has the >=252-trading-session history
# `compute_features`'s rolling windows need. ~252 trading days spans roughly
# 365 calendar days; padded further for holidays/weekends and the 10-day
# sequence window.
_HISTORY_BUFFER_DAYS = 450

# Skip a rebalance leg smaller than this notional — matches
# `backend/crud.py`'s own `_DUST` convention for ignoring rounding-level
# deltas, not a new threshold invented for this module.
_DUST_NOTIONAL = 1.0

_MAX_BACKTEST_YEARS = 20

# A full walk-forward run loads every ticker's model once and re-evaluates
# it at every rebalance — not something to redo on identical repeat
# requests (a page revisit, a chart re-render). Keyed on every input
# parameter, so any change produces a fresh run.
_CACHE_TTL_SECONDS = 600
_backtest_cache = TTLCache(ttl_seconds=_CACHE_TTL_SECONDS)


class BacktestError(ValueError):
    """Raised for invalid inputs or insufficient history — always a 400 at
    the API layer, never a fabricated result."""


def _load_models(tickers: list[str], model_dir) -> dict:
    models = {}
    for ticker in tickers:
        model_file = model_dir / f"{ticker}_model.keras"
        if not model_file.exists():
            continue
        try:
            models[ticker] = load_model_with_weights(str(model_file))
        except Exception:  # noqa: BLE001 - one bad model file must not sink the run
            continue
    return models


def _predict_mu_all_dates(
    dataset: pd.DataFrame, dates: list, tickers: list[str], models: dict, scalers: dict,
) -> dict:
    """Expected-return vector for *every* rebalance date, keyed by date.

    Profiling a 3Y/12-ETF backtest (`cProfile`, before this change) showed
    ~93s of a ~113s run — 77% of total wall time — inside `Model.predict()`,
    called once per (ticker, rebalance date) pair (420 calls). Each call's
    cost was almost entirely Keras's fixed per-call overhead (dataset-handler
    construction, tf.function retracing — TensorFlow explicitly warns about
    this exact pattern) rather than the LSTM computation itself, which is
    trivial for a (1, 10, 9) input. The fix batches every rebalance date's
    sequence for a given ticker into a single `model.predict()` call — one
    call per ticker for the *whole* backtest (12 total) instead of one per
    (ticker, date) pair (420) — while building each row from exactly the
    same `dataset[dataset["Date"] <= date]` truncation as before, so the
    no-lookahead guarantee and the predicted values themselves are
    unchanged; only how many times the model is invoked changes.
    """
    per_ticker_rows: dict[str, list[np.ndarray]] = {t: [] for t in tickers}
    per_ticker_row_dates: dict[str, list] = {t: [] for t in tickers}
    fallback_by_date: dict = {d: {} for d in dates}

    for date in dates:
        ds_upto_t = dataset[dataset["Date"] <= date]
        for ticker in tickers:
            scaler = scalers.get(ticker)
            model = models.get(ticker)
            X, _info = create_sequences_for_prediction(ds_upto_t, ticker, scaler, seq_length=SEQ_LENGTH)
            if X is None or model is None:
                ticker_rows = ds_upto_t[ds_upto_t["Ticker"] == ticker]
                hist = float(ticker_rows["return_22d"].values[-1]) if len(ticker_rows) else 0.0
                fallback_by_date[date][ticker] = annualize_22d_return(hist)
                continue
            per_ticker_rows[ticker].append(X[0])
            per_ticker_row_dates[ticker].append(date)

    raw_pred_by_ticker_date: dict[tuple, float] = {}
    for ticker in tickers:
        rows = per_ticker_rows[ticker]
        if not rows:
            continue
        batch = np.stack(rows, axis=0)
        preds = models[ticker].predict(batch, verbose=0).reshape(-1)
        for date, pred in zip(per_ticker_row_dates[ticker], preds):
            raw_pred_by_ticker_date[(ticker, date)] = float(pred)

    mu_by_date: dict = {}
    for date in dates:
        mu = []
        for ticker in tickers:
            if (ticker, date) in raw_pred_by_ticker_date:
                mu.append(annualize_22d_return(raw_pred_by_ticker_date[(ticker, date)]))
            else:
                mu.append(fallback_by_date[date][ticker])
        mu = np.clip(np.array(mu), -0.5, 2.0)
        mu_by_date[date] = np.nan_to_num(mu, nan=0.0)
    return mu_by_date


def _curve_stats(equity: np.ndarray, risk_free_rate: float) -> dict:
    try:
        return curve_stats(equity, risk_free_rate)
    except InsufficientHistoryError as exc:
        raise BacktestError(str(exc))


def run_backtest(
    tickers: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    strategy: Strategy = "max_sharpe",
    risk_free_rate: float = 0.0,
    benchmark_ticker: Optional[str] = "SPY",
    model_path: Optional[str] = None,
    on_progress: Optional[Callable[[str, int, int, Optional[str], Optional[str]], None]] = None,
) -> dict:
    """`on_progress(phase, completed, total, period_start, period_end)`, when
    given, is called once per real phase transition and once per real
    completed rebalance — never a fabricated/interpolated tick. Purely a
    reporting hook: it cannot influence the computation, so a caller that
    passes nothing behaves exactly as before."""

    def _report(phase: str, completed: int, total: int,
                period_start: Optional[str] = None, period_end: Optional[str] = None) -> None:
        if on_progress is not None:
            on_progress(phase, completed, total, period_start, period_end)

    tickers = sorted({t.strip().upper() for t in tickers if t.strip()})
    if not tickers:
        raise BacktestError("At least one ticker is required.")
    if initial_capital <= 0:
        raise BacktestError("Initial capital must be positive.")

    try:
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
    except (ValueError, TypeError) as exc:
        raise BacktestError(f"Invalid start/end date: {exc}")

    # A client-supplied ISO datetime can carry a timezone (e.g. a trailing
    # "Z") while the other doesn't — comparing a tz-aware and a tz-naive
    # Timestamp raises TypeError, and every date downstream (the fetched
    # price history's index, `dataset["Date"]`) is tz-naive, so tz-aware
    # inputs are normalized to tz-naive here rather than threaded through.
    if start_ts.tzinfo is not None:
        start_ts = start_ts.tz_localize(None)
    if end_ts.tzinfo is not None:
        end_ts = end_ts.tz_localize(None)

    if end_ts <= start_ts:
        raise BacktestError("End date must be after start date.")
    if end_ts - start_ts > pd.Timedelta(days=_MAX_BACKTEST_YEARS * 365):
        raise BacktestError(f"Backtest window cannot exceed {_MAX_BACKTEST_YEARS} years.")

    benchmark = benchmark_ticker.strip().upper() if benchmark_ticker else None
    cache_key = (
        f"{','.join(tickers)}|{start_date}|{end_date}|{initial_capital}|{strategy}|"
        f"{risk_free_rate}|{benchmark or ''}|{model_path or ''}"
    )
    cached = _backtest_cache.get(cache_key)
    if cached is not None:
        return cached

    _report("loading_models", 0, 1)
    model_dir = resolve_model_dir(model_path or DEFAULT_MODEL_DIR)
    scalers = load_scalers(str(model_dir))
    models = _load_models(tickers, model_dir)

    _report("fetching_data", 0, 1)
    fetch_universe = sorted(set(tickers) | ({benchmark} if benchmark else set()))
    fetch_start = (start_ts - pd.Timedelta(days=_HISTORY_BUFFER_DAYS)).strftime("%Y-%m-%d")
    close_prices = fetch_etf_data(fetch_universe, fetch_start)

    _report("computing_features", 0, 1)
    features = compute_features(close_prices[tickers])
    dataset = prepare_dataset(features, tickers).sort_values(["Ticker", "Date"])

    # Dates every requested ticker has a feature row for, restricted to the
    # requested window — the actual simulation calendar.
    per_ticker_dates = [set(dataset.loc[dataset["Ticker"] == t, "Date"]) for t in tickers]
    feasible_dates = sorted(set.intersection(*per_ticker_dates)) if per_ticker_dates else []
    sim_dates = [d for d in feasible_dates if start_ts <= pd.Timestamp(d) <= end_ts]

    if len(sim_dates) < REBALANCE_EVERY_N_DAYS:
        raise BacktestError(
            "Not enough trading history in the selected window to run even one rebalance "
            f"(need at least {REBALANCE_EVERY_N_DAYS} trading days with full feature history)."
        )

    rebalance_dates_list = sim_dates[::REBALANCE_EVERY_N_DAYS]
    rebalance_dates = set(rebalance_dates_list)
    total_rebalances = len(rebalance_dates_list)

    _report("forecasting", 0, total_rebalances)
    mu_by_date = _predict_mu_all_dates(dataset, rebalance_dates_list, tickers, models, scalers)

    positions: dict[str, float] = {t: 0.0 for t in tickers}
    cash = float(initial_capital)
    trades: list[dict] = []
    equity_curve: list[dict] = []
    rebalance_equity_points: list[tuple[str, float]] = []

    benchmark_start_price = float(close_prices.loc[sim_dates[0], benchmark]) if benchmark else None
    rebalances_done = 0

    for date in sim_dates:
        date_str = str(pd.Timestamp(date))[:10]
        prices_today = close_prices.loc[date, tickers]

        if date in rebalance_dates:
            mu = mu_by_date[date]
            cov, _ = compute_covariance_matrix(tickers, close_prices=close_prices.loc[:date, tickers])
            cov = ensure_positive_semidefinite(cov)
            weights, _ = optimize_portfolio(mu=mu, cov=cov, risk_free=risk_free_rate, strategy=strategy)

            equity_before = cash + sum(positions[t] * float(prices_today[t]) for t in tickers)
            for i, t in enumerate(tickers):
                price = float(prices_today[t])
                target_notional = float(weights[i]) * equity_before
                current_notional = positions[t] * price
                delta_notional = target_notional - current_notional
                if abs(delta_notional) < _DUST_NOTIONAL:
                    continue
                delta_qty = delta_notional / price
                positions[t] += delta_qty
                cash -= delta_notional
                trades.append({
                    "date": date_str,
                    "ticker": t,
                    "side": "BUY" if delta_qty > 0 else "SELL",
                    "quantity": round(abs(delta_qty), 6),
                    "price": round(price, 4),
                    "notional": round(abs(delta_notional), 2),
                })
            rebalance_equity_points.append((date_str, equity_before))
            rebalances_done += 1
            period_end_date = (
                rebalance_dates_list[rebalances_done] if rebalances_done < total_rebalances else sim_dates[-1]
            )
            _report(
                "simulating", rebalances_done, total_rebalances,
                date_str, str(pd.Timestamp(period_end_date))[:10],
            )

        equity_today = cash + sum(positions[t] * float(prices_today[t]) for t in tickers)
        point = {"date": date_str, "strategy_equity": round(equity_today, 2)}
        if benchmark:
            point["benchmark_equity"] = round(
                initial_capital * float(close_prices.loc[date, benchmark]) / benchmark_start_price, 2,
            )
        equity_curve.append(point)

    strategy_equity = np.array([p["strategy_equity"] for p in equity_curve])
    strategy_metrics = _curve_stats(strategy_equity, risk_free_rate)

    benchmark_metrics = None
    if benchmark:
        benchmark_equity = np.array([p["benchmark_equity"] for p in equity_curve])
        benchmark_metrics = _curve_stats(benchmark_equity, risk_free_rate)

    # Winning/losing *rebalance periods* — the only unambiguous "trade" unit
    # for a continuously-rebalanced multi-asset portfolio (see module
    # docstring's discussion in the API layer / frontend copy). Each period
    # runs from one rebalance's pre-trade equity to the next's (or to the
    # final day for the last period).
    period_marks = [e for _, e in rebalance_equity_points] + [strategy_equity[-1]]
    winning_periods = losing_periods = flat_periods = 0
    for before, after in zip(period_marks[:-1], period_marks[1:]):
        change = after - before
        if change > 1e-9:
            winning_periods += 1
        elif change < -1e-9:
            losing_periods += 1
        else:
            flat_periods += 1
    decided_periods = winning_periods + losing_periods
    win_rate_pct = (winning_periods / decided_periods * 100.0) if decided_periods else None

    result = {
        "inputs": {
            "tickers": tickers,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "strategy": strategy,
            "risk_free_rate": risk_free_rate,
            "benchmark_ticker": benchmark,
        },
        "equity_curve": equity_curve,
        "rebalance_dates": [d for d, _ in rebalance_equity_points],
        "trades": trades,
        "num_trades": len(trades),
        "winning_periods": winning_periods,
        "losing_periods": losing_periods,
        "flat_periods": flat_periods,
        "win_rate_pct": win_rate_pct,
        "strategy_metrics": strategy_metrics,
        "benchmark_metrics": benchmark_metrics,
        "methodology_notes": [
            "Historical simulation only — not a prediction of future performance.",
            f"Rebalanced every {REBALANCE_EVERY_N_DAYS} trading days, matching the LSTM "
            "model's own 22-day forecast horizon; each rebalance uses only price/feature "
            "data dated on or before that rebalance date.",
            "Signals computed from data through date t are assumed to fill at t's own "
            "closing price, the same fill-at-last-price assumption the paper-trading "
            "engine uses for market orders.",
            "No commissions, slippage, or bid/ask spread are modeled.",
            "Position sizes are fractional (no whole-share rounding), consistent with "
            "the app's existing simulated paper-trading account.",
        ],
    }
    _backtest_cache.set(cache_key, result)
    _report("done", total_rebalances, total_rebalances)
    return result
