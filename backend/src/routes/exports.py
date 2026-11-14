from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import EXPORT_ROLES
from src.controllers import export_controller
from src.middlewares.rbac import require_roles

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/members.csv")
def members_csv(
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_ROLES)),
):
    return export_controller.members_csv(db, principal, request)


@router.get("/segments.csv")
def segments_csv(
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_ROLES)),
):
    return export_controller.segments_csv(db, principal, request)


@router.get("/audiences.csv")
def audiences_csv(
    request: Request,
    audience_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_ROLES)),
):
    return export_controller.audiences_csv(db, audience_id, principal, request)
