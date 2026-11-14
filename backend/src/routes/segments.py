from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import SEGMENT_ADMIN_ROLES
from src.controllers import segment_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.segment import RecomputeIn, SegmentPatch

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("")
def list_segments(
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return segment_controller.list_segments(db)


@router.post("/recompute")
def recompute(
    payload: RecomputeIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SEGMENT_ADMIN_ROLES)),
) -> dict:
    return segment_controller.recompute(db, payload.model_dump(), principal, request)


@router.patch("/{segment_id}")
def update_segment(
    segment_id: int,
    payload: SegmentPatch,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SEGMENT_ADMIN_ROLES)),
) -> dict:
    return segment_controller.update_segment(db, segment_id, payload.model_dump(exclude_unset=True), principal, request)
