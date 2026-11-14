from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CAMPAIGN_WRITE_ROLES
from src.controllers import campaign_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.segment import CampaignIn

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return campaign_controller.list_campaigns(db)


@router.post("", status_code=201)
def create_campaign(
    payload: CampaignIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CAMPAIGN_WRITE_ROLES)),
) -> dict:
    return campaign_controller.create_campaign(db, payload.model_dump(), principal, request)


@router.get("/{campaign_id}/allocation")
def preview_allocation(
    campaign_id: int,
    budget: float | None = Query(default=None, gt=0, le=5_000_000),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return campaign_controller.preview(db, campaign_id, budget)
