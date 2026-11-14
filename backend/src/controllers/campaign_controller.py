"""活动控制器：创建活动、预览算法 B 的预算分配。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, audience_service


def list_campaigns(db: Session) -> dict:
    return audience_service.list_campaigns(db)


def create_campaign(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    campaign = audience_service.create_campaign(db, payload, principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="campaign.create",
        entity="campaign",
        entity_id=campaign.id,
        detail={"code": campaign.code, "budget": campaign.budget},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return audience_service.serialize_campaign(campaign)


def preview(db: Session, campaign_id: int, budget: float | None) -> dict:
    campaign = audience_service.get_campaign(db, campaign_id)
    return audience_service.preview_allocation(db, campaign, budget)
