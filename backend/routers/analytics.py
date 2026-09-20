# -*- coding: utf-8 -*-
"""Model Evaluation + Backtesting — read-only quantitative analysis over the
app's existing LSTM forecaster and mean-variance optimizer.

Everything here is public *market* data and derived statistics (no user
account/portfolio data is read or written), but every route still sits
behind the same `get_current_user` dependency as the rest of the
authenticated app — this is analysis tooling for signed-in users, not a
public marketing feature like the Landing page ticker.
"""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.backtester import BacktestError, TRAINED_TICKERS as BACKTEST_TICKERS, run_backtest
from backend.backtest_jobs import get_job, start_backtest_job
from backend.market_regime import MarketRegimeError, classify_market_regime
from backend.model_comparison import compare_models
from backend.deps import get_current_user
from backend.forecaster import get_expected_returns
from backend.model_evaluation import TRAINED_TICKERS, evaluate_ticker, evaluate_universe
from backend.optimizer import portfolio_return
from backend.risk import RiskAnalysisError, compute_portfolio_risk
from backend.routers.risk import CorrelationMatrix, PositionRisk, RegionExposure, VarModel

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------------------
#  Model Evaluation
# ---------------------------------------------------------------------------

class PeriodInfo(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    rows: int = 0


class SplitMetrics(BaseModel):
    mae: float
    rmse: float
    mape: Optional[float] = None
    mape_observations: int = 0
    directional_accuracy: Optional[float] = None
    observations: int


class ActualPredictedSeries(BaseModel):
    dates: list[str] = []
    actual: list[float] = []
    predicted: list[float] = []


class TickerEvaluation(BaseModel):
    ticker: str
    status: str
    detail: Optional[str] = None
    train_period: Optional[PeriodInfo] = None
    validation_period: Optional[PeriodInfo] = None
    test_period: Optional[PeriodInfo] = None
    validation_metrics: Optional[SplitMetrics] = None
    test_metrics: Optional[SplitMetrics] = None
    validation_series: Optional[ActualPredictedSeries] = None
    test_series: Optional[ActualPredictedSeries] = None


_EVAL_METHODOLOGY_NOTES = [
    "Data source: the same Yahoo Finance daily-close history the live forecaster and "
    "portfolio optimizer use (backend/forecaster.py), fetched from 2010-01-01 through today.",
    "Train/validation/test split: chronological 70% / 15% / 15% by row (no shuffling, no "
    "leakage), recomputed at evaluation time against however much history is currently "
    "available — the split therefore drifts forward slightly as new trading days accumulate. "
    "The exact resulting date ranges are reported per ticker below, never hardcoded.",
    "Forecasting horizon: each model predicts a single ticker's 22-trading-day-forward return, "
    "using the same 9-feature, 10-day-sequence input the live /forecast endpoint uses.",
    "Evaluation metrics: MAE and RMSE on the model's raw 22-day-return prediction; MAPE only "
    "where the actual move is large enough for the ratio to be numerically meaningful; "
    "directional accuracy is the percentage of test rows where the predicted and actual "
    "returns had the same sign.",
    "Epoch-level training/validation loss curves are not available: the training script "
    "(train_model.py) does not persist per-epoch history to disk, only the final trained "
    "model and scaler. Only out-of-sample prediction metrics are shown here, computed by "
    "running the already-trained model forward — no model is retrained to produce this page.",
    "Limitation: an LSTM's historical accuracy on past data is not a guarantee of future "
    "forecast accuracy.",
]


class ModelEvaluationUniverseResponse(BaseModel):
    tickers: list[str]


class ModelEvaluationSummaryResponse(BaseModel):
    tickers: list[TickerEvaluation]
    methodology_notes: list[str]


class ModelEvaluationDetailResponse(BaseModel):
    evaluation: TickerEvaluation
    methodology_notes: list[str]


@router.get("/model-evaluation/universe", response_model=ModelEvaluationUniverseResponse)
def model_evaluation_universe() -> ModelEvaluationUniverseResponse:
    """The tickers this module can evaluate — the 12 ETFs shipped with a trained model."""
    return ModelEvaluationUniverseResponse(tickers=TRAINED_TICKERS)


@router.get("/model-evaluation/summary", response_model=ModelEvaluationSummaryResponse)
def model_evaluation_summary() -> ModelEvaluationSummaryResponse:
    """Headline metrics for every trained ticker — no actual-vs-predicted
    series (kept for the per-ticker detail route) so this stays a light,
    single-screen payload for the overview table."""
    try:
        results = evaluate_universe()
    except ValueError as exc:
        # e.g. the data provider returned an incomplete/empty response for
        # this batch — a transient upstream failure, not a bad request.
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {exc}")
    except Exception as exc:  # noqa: BLE001 - see backtest()'s identical guard
        raise HTTPException(status_code=500, detail=f"Model evaluation error: {exc}")

    tickers_out = []
    for ticker in TRAINED_TICKERS:
        row = dict(results.get(ticker, {"ticker": ticker, "status": "model_unavailable"}))
        row.pop("validation_series", None)
        row.pop("test_series", None)
        tickers_out.append(TickerEvaluation(**row))
    return ModelEvaluationSummaryResponse(tickers=tickers_out, methodology_notes=_EVAL_METHODOLOGY_NOTES)


@router.get("/model-evaluation/{ticker}", response_model=ModelEvaluationDetailResponse)
def model_evaluation_detail(ticker: str) -> ModelEvaluationDetailResponse:
    """One ticker with full train/validation/test periods, metrics, and the
    actual-vs-predicted series needed for a chart."""
    try:
        result = evaluate_ticker(ticker.strip().upper())
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {exc}")
    except Exception as exc:  # noqa: BLE001 - see backtest()'s identical guard
        raise HTTPException(status_code=500, detail=f"Model evaluation error: {exc}")
    return ModelEvaluationDetailResponse(
        evaluation=TickerEvaluation(**result),
        methodology_notes=_EVAL_METHODOLOGY_NOTES,
    )


# ---------------------------------------------------------------------------
#  Backtesting
# ---------------------------------------------------------------------------

BacktestStrategy = Literal["max_sharpe", "min_volatility", "risk_parity", "equal_weight"]


class BacktestRequest(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: list(BACKTEST_TICKERS), min_length=1, max_length=12)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    initial_capital: float = Field(default=100_000.0, gt=0)
    strategy: BacktestStrategy = "max_sharpe"
    risk_free_rate: float = Field(default=0.0, description="Annualized, e.g. 0.05 for 5%")
    benchmark_ticker: Optional[str] = Field(default="SPY", description="Set to null/empty to disable")


class EquityPoint(BaseModel):
    date: str
    strategy_equity: float
    benchmark_equity: Optional[float] = None


class TradeOut(BaseModel):
    date: str
    ticker: str
    side: str
    quantity: float
    price: float
    notional: float


class CurveStats(BaseModel):
    total_return_pct: float
    annualized_return_pct: float
    annualized_volatility_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    trading_days: int


class BacktestInputsOut(BaseModel):
    tickers: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    strategy: str
    risk_free_rate: float
    benchmark_ticker: Optional[str] = None


class BacktestResponse(BaseModel):
    inputs: BacktestInputsOut
    equity_curve: list[EquityPoint]
    rebalance_dates: list[str]
    trades: list[TradeOut]
    num_trades: int
    winning_periods: int
    losing_periods: int
    flat_periods: int
    win_rate_pct: Optional[float] = None
    strategy_metrics: CurveStats
    benchmark_metrics: Optional[CurveStats] = None
    methodology_notes: list[str]


@router.post("/backtest", response_model=BacktestResponse)
def backtest(req: BacktestRequest) -> BacktestResponse:
    try:
        result = run_backtest(
            tickers=req.tickers,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            strategy=req.strategy,
            risk_free_rate=req.risk_free_rate,
            benchmark_ticker=req.benchmark_ticker or None,
        )
    except BacktestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - always answer with a proper
        # response (and CORS headers) rather than letting the ASGI server
        # turn an unexpected exception into a bare connection failure.
        raise HTTPException(status_code=500, detail=f"Backtest error: {exc}")
    return BacktestResponse(**result)


class BacktestJobStartResponse(BaseModel):
    job_id: str


class BacktestProgress(BaseModel):
    phase: Literal[
        "starting", "loading_models", "fetching_data", "computing_features",
        "forecasting", "simulating", "done",
    ]
    completed: int
    total: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class BacktestJobStatusResponse(BaseModel):
    status: Literal["running", "done", "error"]
    progress: BacktestProgress
    result: Optional[BacktestResponse] = None
    error: Optional[str] = None


@router.post("/backtest/start", response_model=BacktestJobStartResponse)
def start_backtest(req: BacktestRequest) -> BacktestJobStartResponse:
    """Same computation as `POST /backtest`, but returns immediately with a
    job id — the walk-forward simulation runs on a background thread so the
    caller can poll `GET /backtest/status/{job_id}` for real progress
    instead of blocking on one long request."""
    job_id = start_backtest_job(
        tickers=req.tickers,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        strategy=req.strategy,
        risk_free_rate=req.risk_free_rate,
        benchmark_ticker=req.benchmark_ticker or None,
    )
    return BacktestJobStartResponse(job_id=job_id)


@router.get("/backtest/status/{job_id}", response_model=BacktestJobStatusResponse)
def backtest_status(job_id: str) -> BacktestJobStatusResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired backtest job.")
    return BacktestJobStatusResponse(
        status=job["status"],
        progress=BacktestProgress(**job["progress"]),
        result=BacktestResponse(**job["result"]) if job["result"] is not None else None,
        error=job["error"],
    )


# ---------------------------------------------------------------------------
#  Scenario / What-If Analysis
#
#  Stateless calculation only — no database read or write, so it can never
#  modify a real portfolio. The caller supplies a hypothetical set of
#  holdings (which the frontend builds either from the user's real current
#  positions unmodified, or with scenario edits applied); this endpoint just
#  evaluates that hypothetical portfolio through the exact same risk
#  pipeline `GET /risk/portfolio` uses (`compute_portfolio_risk`), plus the
#  same LSTM-forecast expected-return math `POST /smart-invest` uses
#  (`get_expected_returns` + `portfolio_return`). No new calculation logic.
# ---------------------------------------------------------------------------

class ScenarioHolding(BaseModel):
    ticker: str
    dollar_value: float = Field(ge=0)


class ScenarioRequest(BaseModel):
    holdings: list[ScenarioHolding] = Field(default_factory=list, max_length=20)
    cash: float = Field(ge=0)
    benchmark_ticker: Optional[str] = "SPY"
    risk_free_rate: float = Field(default=0.0)


class ScenarioResponse(BaseModel):
    status: str
    detail: Optional[str] = None
    invested_value: float
    cash: float
    cash_pct: float
    expected_return_pct: Optional[float] = None
    lookback_days: Optional[int] = None
    volatility_pct: Optional[float] = None
    annualized_return_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    var: Optional[VarModel] = None
    beta: Optional[float] = None
    benchmark_ticker: Optional[str] = None
    concentration_hhi: Optional[float] = None
    diversification_score: Optional[float] = None
    positions: list[PositionRisk] = []
    exposure_by_region: list[RegionExposure] = []
    correlation_matrix: Optional[CorrelationMatrix] = None
    methodology_notes: list[str] = []


@router.post("/scenario", response_model=ScenarioResponse)
def analyze_scenario(req: ScenarioRequest) -> ScenarioResponse:
    """Evaluate a hypothetical (never persisted) portfolio — used for both
    the "current" and "scenario" sides of the What-If comparison, so both
    are computed through the identical methodology."""
    holdings = [h for h in req.holdings if h.dollar_value > 0]
    tickers = [h.ticker.strip().upper() for h in holdings]
    dollar_values = [h.dollar_value for h in holdings]

    try:
        result = compute_portfolio_risk(
            tickers=tickers,
            dollar_values=dollar_values,
            cash=req.cash,
            benchmark_ticker=(req.benchmark_ticker.strip().upper() if req.benchmark_ticker else None),
            risk_free_rate=req.risk_free_rate,
        )
    except RiskAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - see backtest()'s identical guard
        raise HTTPException(status_code=500, detail=f"Scenario analysis error: {exc}")

    expected_return_pct = None
    if tickers:
        try:
            mu = get_expected_returns(tickers)
            weights = np.array(dollar_values) / sum(dollar_values)
            expected_return_pct = round(float(portfolio_return(weights, mu)) * 100, 2)
        except Exception:  # noqa: BLE001 - forecast is a bonus field, never blocks the risk result
            expected_return_pct = None

    result["expected_return_pct"] = expected_return_pct
    return ScenarioResponse(**result)


# ---------------------------------------------------------------------------
#  Market Regime — transparent statistical trend/volatility classification
# ---------------------------------------------------------------------------

class RegimeSnapshot(BaseModel):
    trend: Literal["POSITIVE_TREND", "NEGATIVE_TREND", "NEUTRAL"]
    volatility_regime: Literal["HIGH_VOLATILITY", "NORMAL_VOLATILITY"]
    cumulative_return_pct: float
    annualized_volatility_pct: float


class RegimeTimelinePoint(RegimeSnapshot):
    date: str


class RegimeMethodology(BaseModel):
    trend_window_days: int
    trend_threshold_pct: float
    volatility_window_days: int
    volatility_high_multiplier: float


class MarketRegimeResponse(BaseModel):
    ticker: str
    as_of: str
    current_regime: RegimeSnapshot
    max_drawdown_pct: float
    observations: int
    timeline: list[RegimeTimelinePoint]
    methodology: RegimeMethodology


@router.get("/market-regime", response_model=MarketRegimeResponse)
def market_regime(ticker: str = "SPY") -> MarketRegimeResponse:
    """Trend/volatility regime for `ticker` (defaults to SPY as a broad-market
    proxy) — a disclosed statistical read on already-observed price history,
    never a forecast of the next regime."""
    try:
        result = classify_market_regime(ticker)
    except MarketRegimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {exc}")
    except Exception as exc:  # noqa: BLE001 - see backtest()'s identical guard
        raise HTTPException(status_code=500, detail=f"Market regime error: {exc}")
    return MarketRegimeResponse(**result)


# ---------------------------------------------------------------------------
#  Model Comparison Lab — LSTM vs. transparent non-ML baselines
# ---------------------------------------------------------------------------

class ComparisonModelResult(BaseModel):
    model: Literal["naive", "moving_average", "linear_regression", "lstm"]
    label: str
    status: str
    detail: Optional[str] = None
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    mape_observations: int = 0
    directional_accuracy: Optional[float] = None
    observations: int = 0


class ComparisonTestPeriod(BaseModel):
    start: str
    end: str
    observations: int


class ComparisonMethodology(BaseModel):
    target: str
    forecast_horizon_days: int
    sequence_length: int
    train_fraction_pct: float
    validation_fraction_pct: float
    test_fraction_pct: float


class ModelComparisonResponse(BaseModel):
    ticker: str
    status: str
    detail: Optional[str] = None
    models: list[ComparisonModelResult] = []
    test_period: Optional[ComparisonTestPeriod] = None
    methodology: Optional[ComparisonMethodology] = None


@router.get("/model-comparison/{ticker}", response_model=ModelComparisonResponse)
def model_comparison(ticker: str) -> ModelComparisonResponse:
    """Naive / Moving Average / Linear Regression / LSTM, all benchmarked
    over the identical chronological test split `model_evaluation.py`
    already evaluates the LSTM against — never a second methodology."""
    try:
        result = compare_models(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {exc}")
    except Exception as exc:  # noqa: BLE001 - see backtest()'s identical guard
        raise HTTPException(status_code=500, detail=f"Model comparison error: {exc}")
    return ModelComparisonResponse(**result)
