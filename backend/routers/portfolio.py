# -*- coding: utf-8 -*-
"""The caller's own paper-trading account: positions, orders, transactions,
watchlist and alerts.

Every query is filtered by the current user's own `account_id`/`user_id`, so
another user's records are simply not reachable — a mismatched id returns
404, not 403, so existence isn't leaked either. Order fills happen
server-side against backend-fetched prices (`backend/pricing.py`); nothing
here trusts a client-supplied price.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import crud, pricing
from backend.db import get_db
from backend.deps import get_current_user
from backend.models import User
from backend.performance_attribution import compute_attribution
from backend.portfolio_history import compute_account_equity_curve
from backend.schemas import (
    AccountOut,
    AddAlertRequest,
    AlertOut,
    OrderOut,
    PlaceOrderRequest,
    PortfolioSummaryOut,
    PositionOut,
    TransactionOut,
    WatchlistOut,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(get_current_user)])


class EquityCurveResponse(BaseModel):
    dates: list[str]
    equity: list[float]
    note: str | None = None


@router.get("/summary", response_model=PortfolioSummaryOut)
def get_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioSummaryOut:
    """Account + positions + orders + transactions + watchlist + alerts in
    one round trip — what `services.store.sync_portfolio()` calls once per
    Streamlit run instead of six separate requests. Not cached: every field
    is computed fresh from the database, scoped to `user` exactly like the
    individual endpoints below."""
    account_id = user.account.id
    return PortfolioSummaryOut(
        account=AccountOut.model_validate(user.account),
        positions=[PositionOut.model_validate(p) for p in crud.list_positions(db, account_id)],
        orders=[OrderOut.model_validate(o) for o in crud.list_orders(db, account_id)],
        transactions=[TransactionOut.model_validate(t) for t in crud.list_transactions(db, account_id)],
        watchlist=crud.list_watchlist(db, user.id),
        alerts=[AlertOut.model_validate(a) for a in crud.list_alerts(db, user.id)],
    )


@router.get("/account", response_model=AccountOut)
def get_account(user: User = Depends(get_current_user)) -> AccountOut:
    return AccountOut.model_validate(user.account)


@router.get("/positions", response_model=list[PositionOut])
def get_positions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[PositionOut]:
    return [PositionOut.model_validate(p) for p in crud.list_positions(db, user.account.id)]


@router.get("/orders", response_model=list[OrderOut])
def get_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[OrderOut]:
    return [OrderOut.model_validate(o) for o in crud.list_orders(db, user.account.id)]


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    req: PlaceOrderRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> OrderOut:
    order = crud.place_order(
        db, user.account, ticker=req.ticker, side=req.side, quantity=req.quantity,
        order_type=req.order_type, limit_price=req.limit_price,
    )
    return OrderOut.model_validate(order)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> OrderOut:
    order = crud.cancel_order(db, user.account.id, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Ordre introuvable ou déjà clôturé.")
    return OrderOut.model_validate(order)


@router.get("/transactions", response_model=list[TransactionOut])
def get_transactions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[TransactionOut]:
    return [TransactionOut.model_validate(t) for t in crud.list_transactions(db, user.account.id)]


@router.get("/equity-curve", response_model=EquityCurveResponse)
def get_equity_curve(
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> EquityCurveResponse:
    """Real historical account value since this account's first deposit,
    reconstructed from its own transaction ledger — see
    `backend/portfolio_history.py`. The full history is returned in one call;
    the frontend slices it into 1D/1W/1M/... ranges locally rather than
    re-fetching per range."""
    transactions = crud.list_transactions(db, user.account.id)
    tx_dicts = [
        {"type": t.type, "ticker": t.ticker, "quantity": t.quantity, "amount": t.amount, "created_at": t.created_at}
        for t in sorted(transactions, key=lambda t: t.created_at)
    ]
    positions = {p.ticker: p.quantity for p in crud.list_positions(db, user.account.id)}
    try:
        result = compute_account_equity_curve(tx_dicts, positions)
    except Exception as exc:  # noqa: BLE001 - always answer with a proper response
        raise HTTPException(status_code=500, detail=f"Equity curve error: {exc}")
    return EquityCurveResponse(**result)


class HoldingContribution(BaseModel):
    ticker: str
    contribution: float
    contribution_pct: float | None = None
    market_value: float
    is_open_position: bool


class RegionContribution(BaseModel):
    region: str
    contribution: float


class AttributionMethodology(BaseModel):
    method: str
    description: str
    period: str
    contribution_pct_minimum_total_return: float


class AttributionResponse(BaseModel):
    status: str
    detail: str | None = None
    total_return: float | None = None
    holdings: list[HoldingContribution] = []
    region_contributions: list[RegionContribution] = []
    largest_contributor: HoldingContribution | None = None
    largest_detractor: HoldingContribution | None = None
    methodology: AttributionMethodology | None = None


@router.get("/attribution", response_model=AttributionResponse)
def get_attribution(
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> AttributionResponse:
    """Which of the caller's own real holdings contributed to their real
    portfolio return, since account inception — built from the same
    transaction ledger and live prices as everything else (see
    `backend/performance_attribution.py`), never a second accounting model."""
    account_id = user.account.id
    transactions = [
        {"type": t.type, "ticker": t.ticker, "amount": t.amount}
        for t in crud.list_transactions(db, account_id)
    ]
    positions = crud.list_positions(db, account_id)
    tickers = [p.ticker for p in positions]
    prices = pricing.get_last_prices(tickers) if tickers else {}
    current_market_values = {
        p.ticker: p.quantity * prices[p.ticker] for p in positions if p.ticker in prices
    }

    try:
        result = compute_attribution(transactions, current_market_values)
    except Exception as exc:  # noqa: BLE001 - always answer with a proper response
        raise HTTPException(status_code=500, detail=f"Performance attribution error: {exc}")
    return AttributionResponse(**result)


@router.get("/watchlist", response_model=WatchlistOut)
def get_watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchlistOut:
    return WatchlistOut(tickers=crud.list_watchlist(db, user.id))


@router.post("/watchlist/{ticker}", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def add_watch(
    ticker: str, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> WatchlistOut:
    crud.add_watch(db, user.id, ticker.upper())
    return WatchlistOut(tickers=crud.list_watchlist(db, user.id))


@router.delete("/watchlist/{ticker}", response_model=WatchlistOut)
def remove_watch(
    ticker: str, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> WatchlistOut:
    crud.remove_watch(db, user.id, ticker.upper())
    return WatchlistOut(tickers=crud.list_watchlist(db, user.id))


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AlertOut]:
    return [AlertOut.model_validate(a) for a in crud.list_alerts(db, user.id)]


@router.post("/alerts", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
def create_alert(
    req: AddAlertRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> AlertOut:
    alert = crud.add_alert(
        db, user.id, ticker=req.ticker, direction=req.direction,
        threshold=req.threshold, note=req.note,
    )
    return AlertOut.model_validate(alert)


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> None:
    removed = crud.remove_alert(db, user.id, alert_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Alerte introuvable.")
    return None


@router.post("/alerts/{alert_id}/reset", response_model=AlertOut)
def reset_alert(
    alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> AlertOut:
    alert = crud.reset_alert(db, user.id, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerte introuvable.")
    return AlertOut.model_validate(alert)


@router.post("/settle", status_code=status.HTTP_204_NO_CONTENT)
def settle(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    """Match open limit orders and active alerts against fresh prices. Called
    once per Streamlit run, mirroring the previous client-side `store.settle`."""
    crud.settle(db, user)
    return None


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    crud.reset_account(db, user)
    return None
