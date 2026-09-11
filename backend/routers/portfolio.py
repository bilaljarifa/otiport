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
from sqlalchemy.orm import Session

from backend import crud
from backend.db import get_db
from backend.deps import get_current_user
from backend.models import User
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
