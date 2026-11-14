"""总览：会员规模、分群分布、券预算、预计增量与 ROI、近 7 天订单趋势。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import (
    AUDIENCE_STATUS_LABELS,
    CAMPAIGN_STATUS_LABELS,
    MEMBER_TIER_LABELS,
    SEGMENT_LABELS,
)
from src.models.audience import Audience
from src.models.campaign import Campaign
from src.models.member import Member
from src.models.order import Order
from src.models.segment import Segment
from src.utils.timeutil import iso_utc, local_now, utcnow


def worker_alive() -> bool:
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        value = client.get(f"{settings.app_name}:worker:heartbeat")
        return bool(value) and (time.time() - float(value)) < 120
    except Exception:
        return False


def overview(db: Session) -> dict:
    members_total = db.scalar(select(func.count()).select_from(Member)) or 0
    orders_total = db.scalar(select(func.count()).select_from(Order)) or 0
    gmv_total = db.scalar(select(func.sum(Order.amount))) or 0.0

    segment_rows = db.scalars(select(Segment).order_by(Segment.sort_order)).all()
    segments = [
        {
            "code": row.code,
            "name": row.name,
            "member_count": row.member_count,
            "share": round(row.share or 0.0, 4),
            "lift": round(row.lift or 0.0, 4),
            "purchase_rate": round(row.purchase_rate or 0.0, 6),
            "coupon_face": round(row.coupon_face or 0.0, 2),
        }
        for row in segment_rows
    ]
    as_of = None
    for row in segment_rows:
        if row.as_of:
            as_of = iso_utc(row.as_of)
            break
    snapshot = next((row.snapshot for row in segment_rows if row.snapshot), {})

    tier_rows = db.execute(
        select(Member.tier, func.count()).group_by(Member.tier)
    ).all()
    tiers = [
        {"key": key, "label": MEMBER_TIER_LABELS.get(key, key), "count": count}
        for key, count in sorted(tier_rows, key=lambda item: item[1], reverse=True)
    ]

    campaigns = db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()
    budget_total = round(sum(item.budget or 0.0 for item in campaigns if item.status == "active"), 2)
    latest_audience = db.scalar(select(Audience).order_by(Audience.id.desc()).limit(1))
    audiences_total = db.scalar(select(func.count()).select_from(Audience)) or 0
    pending_audiences = (
        db.scalar(select(func.count()).select_from(Audience).where(Audience.status == "pending")) or 0
    )

    today = local_now().date()
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        start = datetime.combine(day, datetime.min.time()) - timedelta(minutes=settings.app_timezone_offset_minutes)
        end = start + timedelta(days=1)
        count = db.scalar(
            select(func.count()).select_from(Order).where(Order.paid_at >= start).where(Order.paid_at < end)
        ) or 0
        amount = db.scalar(
            select(func.sum(Order.amount)).where(Order.paid_at >= start).where(Order.paid_at < end)
        ) or 0.0
        trend.append({"date": day.isoformat(), "orders": int(count), "gmv": round(float(amount), 2)})

    recent_30 = db.scalar(
        select(func.count()).select_from(Order).where(Order.paid_at >= utcnow() - timedelta(days=30))
    ) or 0

    return {
        "members_total": members_total,
        "orders_total": orders_total,
        "gmv_total": round(float(gmv_total), 2),
        "orders_30d": int(recent_30),
        "segments": segments,
        "tiers": tiers,
        "campaigns_total": len(campaigns),
        "campaigns": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "budget": round(item.budget or 0.0, 2),
                "status": item.status,
                "status_label": CAMPAIGN_STATUS_LABELS.get(item.status, item.status),
                "starts_on": item.starts_on.isoformat() if item.starts_on else None,
            }
            for item in campaigns
        ],
        "budget_total": budget_total,
        "audiences_total": audiences_total,
        "pending_audiences": pending_audiences,
        "latest_audience": (
            {
                "id": latest_audience.id,
                "audience_no": latest_audience.audience_no,
                "status": latest_audience.status,
                "status_label": AUDIENCE_STATUS_LABELS.get(latest_audience.status, latest_audience.status),
                "member_count": latest_audience.member_count,
                "spend": round(latest_audience.spend or 0.0, 2),
                "inc_orders": latest_audience.inc_orders,
                "inc_gmv": round(latest_audience.inc_gmv or 0.0, 2),
                "roi": round(latest_audience.roi or 0.0, 2),
                "created_at": iso_utc(latest_audience.created_at),
            }
            if latest_audience
            else None
        ),
        "snapshot": snapshot,
        "as_of": as_of,
        "trend": trend,
        "worker_alive": worker_alive(),
    }
