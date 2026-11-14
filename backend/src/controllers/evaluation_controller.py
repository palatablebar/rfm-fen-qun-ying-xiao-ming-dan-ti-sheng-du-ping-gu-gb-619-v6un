"""结算评估控制器：导入结算批次、发布评估；写操作都落审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.audience import Audience
from src.models.campaign import Campaign
from src.services import audit_service, evaluation_service
from src.utils.timeutil import parse_date


def list_for_campaign(db: Session, campaign_id: int) -> dict:
    campaign = evaluation_service.get_campaign(db, campaign_id)
    items = evaluation_service.list_for_campaign(db, campaign_id)
    published = sum(1 for item in items if item["status"] == "published")
    return {
        "campaign": {"id": campaign.id, "code": campaign.code, "name": campaign.name},
        "items": items,
        "total": len(items),
        "published": published,
        "in_progress": len(items) - published,
    }


def _detail(db: Session, evaluation_id: int) -> dict:
    evaluation = evaluation_service.get_evaluation(db, evaluation_id)
    audience = db.get(Audience, evaluation.audience_id)
    campaign = db.get(Campaign, evaluation.campaign_id)
    result = evaluation_service.serialize(evaluation, audience, campaign)
    result["fact_rows"] = evaluation_service.fact_rows(evaluation)
    return result


def detail(db: Session, evaluation_id: int) -> dict:
    return _detail(db, evaluation_id)


def import_settlement(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    campaign_id = payload["campaign_id"]
    result = evaluation_service.apply_import(
        db,
        campaign_id=campaign_id,
        batch_no=payload["batch_no"],
        as_of=parse_date(payload.get("as_of")),
        rows=payload["rows"],
        operator_email=principal["email"],
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="evaluation.import",
        entity="campaign",
        entity_id=campaign_id,
        detail={
            "batch_no": payload["batch_no"],
            "duplicate": result["duplicate"],
            "rows": len(payload["rows"]),
            "applied": result["applied"],
            "skipped": result["skipped"],
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def publish(db: Session, evaluation_id: int, payload: dict, principal: dict, request: Request) -> dict:
    evaluation = evaluation_service.get_evaluation(db, evaluation_id)
    already = evaluation.status == "published"
    evaluation_service.publish(db, evaluation, actor=principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="evaluation.publish",
        entity="evaluation",
        entity_id=evaluation.id,
        detail={
            "audience_id": evaluation.audience_id,
            "already_published": already,
            "treated_count": evaluation.treated_count,
            "control_count": evaluation.control_count,
            "incremental_rate": evaluation.incremental_rate,
            "roi": evaluation.roi,
            "note": payload.get("note"),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _detail(db, evaluation_id)
