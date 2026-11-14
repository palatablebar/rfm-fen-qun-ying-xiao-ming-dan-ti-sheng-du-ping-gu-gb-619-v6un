"""会员与订单读取：分页、筛选、手机号脱敏、订单明细。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import MEMBER_TIER_LABELS, ORDER_CHANNEL_LABELS, SEGMENT_LABELS
from src.models.member import Member
from src.models.order import Order
from src.utils.errors import not_found
from src.utils.timeutil import iso_date, iso_utc


def mask_phone(phone: str) -> str:
    text = (phone or "").strip()
    if len(text) < 7:
        return "***"
    return f"{text[:3]}****{text[-4:]}"


def serialize_member(member: Member, *, mask: bool) -> dict:
    return {
        "id": member.id,
        "member_no": member.member_no,
        "name": member.name,
        "phone": mask_phone(member.phone) if mask else member.phone,
        "phone_masked": mask,
        "city": member.city,
        "tier": member.tier,
        "tier_label": MEMBER_TIER_LABELS.get(member.tier, member.tier),
        "joined_on": iso_date(member.joined_on),
        "last_order_at": iso_utc(member.last_order_at),
        "r_days": member.r_days,
        "orders_window": member.orders_window,
        "amount_window": round(member.amount_window or 0.0, 2),
        "r_score": member.r_score,
        "f_score": member.f_score,
        "m_score": member.m_score,
        "composite_score": member.composite_score,
        "segment_code": member.segment_code,
        "segment_label": SEGMENT_LABELS.get(member.segment_code or "", None),
        "purchase_rate": round(member.purchase_rate or 0.0, 6),
        "avg_ticket": round(member.avg_ticket or 0.0, 2),
    }


def serialize_order(order: Order, member_no: str | None = None) -> dict:
    return {
        "id": order.id,
        "order_no": order.order_no,
        "member_no": member_no,
        "store_code": order.store_code,
        "channel": order.channel,
        "channel_label": ORDER_CHANNEL_LABELS.get(order.channel, order.channel),
        "amount": round(order.amount or 0.0, 2),
        "items": order.items,
        "coupon_used": bool(order.coupon_used),
        "paid_at": iso_utc(order.paid_at),
    }


def list_members(
    db: Session,
    *,
    q: str | None = None,
    segment: str | None = None,
    tier: str | None = None,
    min_amount: float | None = None,
    limit: int = 20,
    offset: int = 0,
    mask: bool = False,
) -> dict:
    stmt = select(Member)
    count_stmt = select(func.count()).select_from(Member)
    if q:
        like = f"%{q.strip()}%"
        condition = Member.member_no.ilike(like) | Member.name.ilike(like) | Member.phone.ilike(like)
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if segment:
        stmt = stmt.where(Member.segment_code == segment)
        count_stmt = count_stmt.where(Member.segment_code == segment)
    if tier:
        stmt = stmt.where(Member.tier == tier)
        count_stmt = count_stmt.where(Member.tier == tier)
    if min_amount is not None:
        stmt = stmt.where(Member.amount_window >= min_amount)
        count_stmt = count_stmt.where(Member.amount_window >= min_amount)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(Member.composite_score.desc().nullslast(), Member.id).limit(limit).offset(offset)
    ).all()
    return {
        "items": [serialize_member(row, mask=mask) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_member(db: Session, member_id: int, *, mask: bool) -> dict:
    member = db.get(Member, member_id)
    if member is None:
        raise not_found("member", member_id)
    orders = db.scalars(
        select(Order).where(Order.member_id == member_id).order_by(Order.paid_at.desc()).limit(20)
    ).all()
    payload = serialize_member(member, mask=mask)
    payload["orders"] = [serialize_order(order, member.member_no) for order in orders]
    payload["orders_total"] = db.scalar(
        select(func.count()).select_from(Order).where(Order.member_id == member_id)
    ) or 0
    return payload


def list_orders(db: Session, *, member_id: int | None = None, limit: int = 20, offset: int = 0) -> dict:
    stmt = select(Order)
    count_stmt = select(func.count()).select_from(Order)
    if member_id:
        stmt = stmt.where(Order.member_id == member_id)
        count_stmt = count_stmt.where(Order.member_id == member_id)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Order.paid_at.desc()).limit(limit).offset(offset)).all()
    member_nos = {}
    if rows:
        ids = {row.member_id for row in rows}
        member_nos = {
            item.id: item.member_no for item in db.scalars(select(Member).where(Member.id.in_(ids))).all()
        }
    return {
        "items": [serialize_order(row, member_nos.get(row.member_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
