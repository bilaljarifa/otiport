# -*- coding: utf-8 -*-
"""Risk Center — risk metrics for the caller's own current holdings only.

Positions and cash are always read from the database scoped to
`user.account.id` (same pattern as `backend/routers/portfolio.py`) — a
client cannot request another user's risk profile, and cannot influence the
holdings/prices the calculation uses (prices come from `backend.pricing`,
never from the request).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import crud, pricing
from backend.db import get_db
from backend.deps import get_current_user
from backend.models import User
from backend.risk import RiskAnalysisError, compute_portfolio_risk

router = APIRouter(prefix="/risk", tags=["risk"], dependencies=[Depends(get_current_user)])


class PositionRisk(BaseModel):
    ticker: str
    weight_pct: float
    market_value: float
    risk_contribution_pct: float


class VarModel(BaseModel):
    confidence: float
    var_pct: float
    cvar_pct: float
    observations: int
    var_dollar: float
    cvar_dollar: float


class RegionExposure(BaseModel):
    region: str
    weight_pct: float


class CorrelationMatrix(BaseModel):
    tickers: list[str]
    values: list[list[float]]


class PortfolioRiskResponse(BaseModel):
    status: str
    detail: Optional[str] = None
    invested_value: float
    cash: float
    cash_pct: float
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


@router.get("/portfolio", response_model=PortfolioRiskResponse)
def portfolio_risk(
    benchmark: str = Query(default="SPY"),
    risk_free_rate: float = Query(default=0.0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioRiskResponse:
    positions = crud.list_positions(db, user.account.id)
    tickers = [p.ticker for p in positions]

    dollar_values: list[float] = []
    if tickers:
        prices = pricing.get_last_prices(tickers)
        # A ticker whose live price is momentarily unavailable is valued at
        # its average cost rather than dropped — dropping it would silently
        # understate both invested value and that position's real risk.
        for p in positions:
            price = prices.get(p.ticker, p.avg_price)
            dollar_values.append(p.quantity * price)

    try:
        result = compute_portfolio_risk(
            tickers=tickers,
            dollar_values=dollar_values,
            cash=user.account.cash,
            benchmark_ticker=benchmark.strip().upper() if benchmark else None,
            risk_free_rate=risk_free_rate,
        )
    except RiskAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - always answer with a proper response
        raise HTTPException(status_code=500, detail=f"Risk analysis error: {exc}")

    return PortfolioRiskResponse(**result)
