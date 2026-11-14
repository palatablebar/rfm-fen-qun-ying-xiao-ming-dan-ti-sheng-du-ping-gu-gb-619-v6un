"""活动与名单：算法 B 的编排层（预览不落库，生成才落库）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import AUDIENCE_STATUS_LABELS, CAMPAIGN_STATUS_LABELS
from src.models.audience import Audience
from src.models.campaign import Campaign
from src.services import lift_service, segment_service
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_date, iso_utc, local_now, utcnow


def serialize_campaign(campaign: Campaign) -> dict:
    return {
        "id": campaign.id,
        "code": campaign.code,
        "name": campaign.name,
        "channel": campaign.channel,
        "budget": round(campaign.budget or 0.0, 2),
        "status": campaign.status,
        "status_label": CAMPAIGN_STATUS_LABELS.get(campaign.status, campaign.status),
        "starts_on": iso_date(campaign.starts_on),
        "ends_on": iso_date(campaign.ends_on),
        "reach_cost": round(campaign.reach_cost or 0.0, 4),
        "orders_per_converter": round(campaign.orders_per_converter or 0.0, 4),
        "tail_factor": round(campaign.tail_factor or 0.0, 4),
        "target_segments": campaign.target_segments or [],
        "note": campaign.note,
        "operator_email": campaign.operator_email,
        "created_at": iso_utc(campaign.created_at),
    }


def list_campaigns(db: Session) -> dict:
    rows = db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()
    return {"items": [serialize_campaign(row) for row in rows], "total": len(rows)}


def get_campaign(db: Session, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise not_found("campaign", campaign_id)
    return campaign


def create_campaign(db: Session, payload: dict, operator_email: str, seed_key: str | None = None) -> Campaign:
    exists = db.scalar(select(Campaign).where(Campaign.code == payload["code"]))
    if exists is not None:
        raise AppError("CONFLICT", 409, {"code": payload["code"]})
    campaign = Campaign(
        code=payload["code"],
        name=payload["name"],
        channel=payload.get("channel") or "小程序订阅消息",
        budget=round(float(payload["budget"]), 2),
        status=payload.get("status") or "draft",
        starts_on=_parse_date(payload.get("starts_on")),
        ends_on=_parse_date(payload.get("ends_on")),
        note=payload.get("note"),
        operator_email=operator_email,
        seed_key=seed_key,
    )
    db.add(campaign)
    db.flush()
    return campaign


def _parse_date(text: str | None):
    if not text:
        return None
    from datetime import date

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        raise AppError("VALIDATION", 422, {"reason": "日期格式应为 YYYY-MM-DD", "value": text}) from None


def preview_allocation(db: Session, campaign: Campaign, budget: float | None = None) -> dict:
    """算法 B 预览：读当前分群快照 + 活动参数，算出预算分配（不落库）。"""
    segments = segment_service.segments_for_allocation(db)
    if not segments:
        raise AppError("VALIDATION", 409, {"reason": "还没有分群快照，请先重算 RFM"})
    meta = segment_service.list_segments(db)
    result = lift_service.allocate(
        segments,
        budget=float(budget if budget is not None else campaign.budget),
        global_rate=meta.get("global_purchase_rate") or None,
        reach_cost=campaign.reach_cost,
        orders_per_converter=campaign.orders_per_converter,
        tail_factor=campaign.tail_factor,
    )
    result["campaign"] = serialize_campaign(campaign)
    result["as_of"] = meta.get("as_of")
    result["segments_basis"] = [
        {
            "code": item["code"],
            "name": item["name"],
            "rule_text": item.get("rule_text"),
            "share": item.get("share"),
            "avg_r_days": item.get("avg_r_days"),
        }
        for item in meta["items"]
    ]
    return result


def _next_audience_no(db: Session) -> str:
    prefix = f"A{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(Audience).where(Audience.audience_no.like(f"{prefix}%"))) or 0
    return f"{prefix}{count + 1:02d}"


def generate(
    db: Session,
    *,
    campaign: Campaign,
    budget: float | None,
    operator_email: str,
    note: str | None = None,
    seed_key: str | None = None,
) -> Audience:
    if seed_key:
        existing = db.scalar(select(Audience).where(Audience.seed_key == seed_key))
        if existing is not None:
            return existing
    allocation = preview_allocation(db, campaign, budget)
    if not allocation["totals"]["audience"]:
        raise AppError("VALIDATION", 409, {"reason": "当前预算下没有可分群可投，请提高预算或调整券面额"})
    audience = Audience(
        audience_no=_next_audience_no(db),
        campaign_id=campaign.id,
        status="pending",
        budget=allocation["budget"],
        member_count=allocation["totals"]["audience"],
        spend=allocation["totals"]["spend"],
        inc_orders=allocation["totals"]["inc_orders"],
        inc_gmv=allocation["totals"]["inc_gmv"],
        roi=allocation["totals"]["roi"],
        global_rate=allocation["global_rate"],
        allocation=allocation["segments"],
        note=note or allocation["log"],
        operator_email=operator_email,
        seed_key=seed_key,
    )
    db.add(audience)
    db.flush()
    return audience


def serialize_audience(audience: Audience, campaign: Campaign | None = None) -> dict:
    return {
        "id": audience.id,
        "audience_no": audience.audience_no,
        "campaign_id": audience.campaign_id,
        "campaign_name": campaign.name if campaign else None,
        "campaign_code": campaign.code if campaign else None,
        "status": audience.status,
        "status_label": AUDIENCE_STATUS_LABELS.get(audience.status, audience.status),
        "budget": round(audience.budget or 0.0, 2),
        "budget_remaining": round((audience.budget or 0.0) - (audience.spend or 0.0), 2),
        "member_count": audience.member_count,
        "spend": round(audience.spend or 0.0, 2),
        "inc_orders": audience.inc_orders,
        "inc_gmv": round(audience.inc_gmv or 0.0, 2),
        "roi": round(audience.roi or 0.0, 2),
        "global_rate": round(audience.global_rate or 0.0, 6),
        "allocation": audience.allocation or [],
        "note": audience.note,
        "operator_email": audience.operator_email,
        "confirmed_by": audience.confirmed_by,
        "confirmed_at": iso_utc(audience.confirmed_at),
        "created_at": iso_utc(audience.created_at),
    }


def list_audiences(
    db: Session,
    *,
    campaign_id: int | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(Audience)
    count_stmt = select(func.count()).select_from(Audience)
    if campaign_id:
        stmt = stmt.where(Audience.campaign_id == campaign_id)
        count_stmt = count_stmt.where(Audience.campaign_id == campaign_id)
    if status:
        stmt = stmt.where(Audience.status == status)
        count_stmt = count_stmt.where(Audience.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Audience.id.desc()).limit(limit).offset(offset)).all()
    campaigns = {item.id: item for item in db.scalars(select(Campaign)).all()}
    return {
        "items": [serialize_audience(row, campaigns.get(row.campaign_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_audience(db: Session, audience_id: int) -> Audience:
    audience = db.get(Audience, audience_id)
    if audience is None:
        raise not_found("audience", audience_id)
    return audience


def confirm(db: Session, audience: Audience, *, status: str, note: str | None, actor: str) -> Audience:
    if status not in {"confirmed", "pushed"}:
        raise AppError("VALIDATION", 422, {"reason": "只能确认或推送名单"})
    audience.status = status
    audience.confirmed_by = actor
    audience.confirmed_at = utcnow()
    if note:
        audience.note = note
    db.flush()
    return audience
