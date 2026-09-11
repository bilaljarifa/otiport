# -*- coding: utf-8 -*-
"""Admin-only user management and system stats.

Every route here depends on `require_admin`, which re-checks the caller's
role from the database on each request (see `backend/deps.py`) — a
frontend-only "is admin" flag is never trusted. Deliberately scoped to
*account* management: there is no endpoint for an admin to read another
user's portfolio/orders/watchlist/alerts (see README "Permissions par
défaut").
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend import crud
from backend.config import APP_VERSION
from backend.db import get_db
from backend.deps import require_admin
from backend.models import User
from backend.schemas import SystemStats, UpdateUserRoleRequest, UserOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in crud.list_users(db)]


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, req: UpdateUserRoleRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> UserOut:
    target = crud.get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    demoting_or_disabling = (
        (req.role is not None and req.role != "admin") or req.is_active is False
    )
    if target.id == admin.id and demoting_or_disabling:
        raise HTTPException(
            status_code=400,
            detail="Impossible de modifier votre propre rôle ou statut administrateur.",
        )

    updated = crud.update_user_role(db, target, role=req.role, is_active=req.is_active)
    return UserOut.model_validate(updated)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte.")
    target = crud.get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    crud.delete_user(db, target)
    return None


@router.get("/stats", response_model=SystemStats)
def stats(db: Session = Depends(get_db)) -> SystemStats:
    return SystemStats(**crud.system_stats(db), backend_version=APP_VERSION)
