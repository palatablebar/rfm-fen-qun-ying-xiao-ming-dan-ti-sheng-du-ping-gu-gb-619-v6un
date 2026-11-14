from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import AUDIENCE_CONFIRM_ROLES, AUDIENCE_GENERATE_ROLES
from src.controllers import audience_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.audience import AudienceIn, AudienceReviewIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/audiences", tags=["audiences"])


@router.get("")
def list_audiences(
    campaign_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None, max_length=16),
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return audience_controller.list_audiences(
        db, campaign_id=campaign_id, status=status, limit=page.limit, offset=page.offset
    )


@router.get("/{audience_id}")
def get_audience(
    audience_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return audience_controller.get_audience(db, audience_id)


@router.post("", status_code=201)
def generate_audience(
    payload: AudienceIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*AUDIENCE_GENERATE_ROLES)),
) -> dict:
    return audience_controller.generate(db, payload.model_dump(), principal, request)


@router.patch("/{audience_id}/review")
def review_audience(
    audience_id: int,
    payload: AudienceReviewIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*AUDIENCE_CONFIRM_ROLES)),
) -> dict:
    return audience_controller.review(db, audience_id, payload.model_dump(), principal, request)
