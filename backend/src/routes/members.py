from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import member_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.utils.pagination import page_params

router = APIRouter(tags=["members"])


@router.get("/members")
def list_members(
    q: str | None = Query(default=None, max_length=60),
    segment: str | None = Query(default=None, max_length=20),
    tier: str | None = Query(default=None, max_length=12),
    min_amount: float | None = Query(default=None, ge=0),
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return member_controller.list_members(
        db,
        principal,
        q=q,
        segment=segment,
        tier=tier,
        min_amount=min_amount,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/members/{member_id}")
def get_member(
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return member_controller.get_member(db, member_id, principal, request)


@router.get("/orders")
def list_orders(
    member_id: int | None = Query(default=None, ge=1),
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return member_controller.list_orders(db, member_id=member_id, limit=page.limit, offset=page.offset)
