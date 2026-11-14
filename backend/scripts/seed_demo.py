"""幂等 seed：3 账号 / 8,000 会员 / 30,000 订单 / 8 分群 / 4 活动 / 4 份名单 / 2 份结算评估。

自然键 upsert：
  users.email / members.member_no / orders.order_no
  segments.code（只更新快照字段，不动运营改过的券面额）
  campaigns.code / audiences.seed_key
  audit_logs.seed_key
  结算评估走 audiences.seed_key → evaluations.audience_id 唯一约束；导入批次按 (campaign_id, batch_no)
  幂等，重试导入不新增、不重复应用；已发布评估不会被 seed 改动。

重复执行不新增、不覆盖已确认名单；SEED_SUMMARY 两次逐字一致。
数量口径（与 batch-plan 的 seed 段对应）：
  sources = 会员数、runs = 订单数、findings = 分群数、pending = 待确认名单数。
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, insert, select

from src.config.database import session_scope
from src.models.audit import AuditLog
from src.models.campaign import Campaign
from src.models.member import Member
from src.models.order import Order
from src.models.segment import Segment
from src.models.user import User
from src.services import audience_service, evaluation_service, segment_service
from src.constants.limits import RFM_WINDOW_DAYS
from src.utils.security import hash_password
from src.utils.timeutil import parse_date

from scripts.demo_config import (
    ARCHETYPES,
    CAMPAIGNS,
    CHANNELS,
    CITIES,
    DEMO_PASSWORD,
    DEMO_USERS,
    GIVEN,
    MEMBER_TARGET,
    ORDER_TARGET,
    ORG,
    RANDOM_SEED,
    SEED_ANCHOR,
    SEED_AUDIENCES,
    SEED_EVALUATIONS,
    SEGMENT_COUPON,
    STORES,
    SURNAMES,
)


def _pick_weighted(rng: random.Random, items: list[tuple[str, float]]) -> str:
    point = rng.random()
    cumulative = 0.0
    for key, weight in items:
        cumulative += weight
        if point <= cumulative:
            return key
    return items[-1][0]


def _build_dataset() -> tuple[list[dict], list[dict], dict[str, dict]]:
    """生成会员与订单（纯内存、纯确定性），返回 (member_rows, order_rows, stats)。"""
    rng = random.Random(RANDOM_SEED)
    archetype_by_key = {item["key"]: item for item in ARCHETYPES}
    weights = [(item["key"], item["weight"]) for item in ARCHETYPES]

    plans: list[dict] = []
    for index in range(MEMBER_TARGET):
        key = _pick_weighted(rng, weights)
        profile = archetype_by_key[key]
        base = profile["orders"]
        count = int(round(base + rng.uniform(-1.2, 1.2)))
        if key == "hibernating":
            count = max(0, count)
        else:
            count = max(1, count)
        plans.append({"index": index, "archetype": key, "profile": profile, "orders": count})

    total = sum(item["orders"] for item in plans)
    # 调整到精确 30,000 单：先削多、再补少（顺序由固定 rng 决定，可重放）
    rng.shuffle(plans)
    while total > ORDER_TARGET:
        for item in plans:
            if total <= ORDER_TARGET:
                break
            if item["orders"] > 0:
                item["orders"] -= 1
                total -= 1
    if total < ORDER_TARGET:
        candidates = [item for item in plans if item["archetype"] != "new"]
        cursor = 0
        while total < ORDER_TARGET and candidates:
            item = candidates[cursor % len(candidates)]
            item["orders"] += 1
            total += 1
            cursor += 1
    plans.sort(key=lambda item: item["index"])

    member_rows: list[dict] = []
    order_rows: list[dict] = []
    order_seq = 0
    for plan in plans:
        index = plan["index"]
        profile = plan["profile"]
        member_no = f"MY{index + 1:05d}"
        low, high = profile["recent"]
        joined_on = SEED_ANCHOR - timedelta(days=rng.randint(420, 1500))
        paid_days: list[int] = []
        for _ in range(plan["orders"]):
            span = rng.randint(low, high)
            paid_days.append(max(0, min(520, span + rng.randint(-18, 18))))
        paid_days.sort(reverse=True)
        amounts: list[float] = []
        last_paid: datetime | None = None
        for order_index, days in enumerate(paid_days):
            order_seq += 1
            items = rng.choice([1, 1, 1, 2, 2, 3])
            ticket = profile["ticket"] * rng.uniform(0.78, 1.32)
            amount = round(ticket * (1 + (items - 1) * 0.42), 2)
            amounts.append(amount)
            paid_at = datetime.combine(SEED_ANCHOR - timedelta(days=days), time(hour=rng.randint(8, 21), minute=rng.randint(0, 59)))
            if last_paid is None or paid_at > last_paid:
                last_paid = paid_at
            channel = _pick_weighted(rng, CHANNELS)
            order_rows.append(
                {
                    "order_no": f"MYO{order_seq:06d}",
                    "member_no": member_no,
                    "store_code": rng.choice(STORES),
                    "channel": channel,
                    "amount": amount,
                    "items": items,
                    "coupon_used": rng.random() < profile["rate"],
                    "paid_at": paid_at,
                    "created_at": paid_at,
                }
            )
        in_window = [amount for days, amount in zip(paid_days, amounts) if days <= RFM_WINDOW_DAYS]
        orders_window = len(in_window)
        amount_window = round(sum(in_window), 2)
        avg_ticket = round(sum(amounts) / len(amounts), 2) if amounts else 0.0
        rate = round(profile["rate"] * rng.uniform(0.82, 1.18), 6)
        tier = profile["tier"]
        if tier == "silver" and rng.random() < 0.18:
            tier = "gold"
        elif tier == "gold" and rng.random() < 0.12:
            tier = "black"
        member_rows.append(
            {
                "member_no": member_no,
                "name": rng.choice(SURNAMES) + rng.choice(GIVEN),
                "phone": "1" + rng.choice("35789") + "".join(str(rng.randint(0, 9)) for _ in range(9)),
                "city": rng.choice(CITIES),
                "tier": tier,
                "joined_on": joined_on,
                "last_order_at": last_paid,
                "orders_window": orders_window,
                "amount_window": amount_window,
                "purchase_rate": rate,
                "avg_ticket": avg_ticket,
            }
        )
    return member_rows, order_rows, {"members": len(member_rows), "orders": len(order_rows)}


def ensure_users(db) -> int:
    for email, display_name, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    display_name=display_name,
                    role=role,
                    org=ORG,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(User)) or 0


def ensure_members_and_orders(db) -> tuple[int, int]:
    members_total = db.scalar(select(func.count()).select_from(Member)) or 0
    orders_total = db.scalar(select(func.count()).select_from(Order)) or 0
    if members_total and orders_total:
        return members_total, orders_total

    member_rows, order_rows, _stats = _build_dataset()
    exist_members = {row for (row,) in db.execute(select(Member.member_no)).all()}
    new_members = [row for row in member_rows if row["member_no"] not in exist_members]
    for offset in range(0, len(new_members), 1000):
        db.execute(insert(Member), new_members[offset : offset + 1000])
    db.flush()

    id_by_no = {no: pk for no, pk in db.execute(select(Member.member_no, Member.id)).all()}
    exist_orders = {row for (row,) in db.execute(select(Order.order_no)).all()}
    payload = []
    for row in order_rows:
        if row["order_no"] in exist_orders:
            continue
        payload.append(
            {
                "order_no": row["order_no"],
                "member_id": id_by_no[row["member_no"]],
                "store_code": row["store_code"],
                "channel": row["channel"],
                "amount": row["amount"],
                "items": row["items"],
                "coupon_used": row["coupon_used"],
                "paid_at": row["paid_at"],
                "created_at": row["created_at"],
            }
        )
    for offset in range(0, len(payload), 2000):
        db.execute(insert(Order), payload[offset : offset + 2000])
    db.flush()
    members_total = db.scalar(select(func.count()).select_from(Member)) or 0
    orders_total = db.scalar(select(func.count()).select_from(Order)) or 0
    return members_total, orders_total


def ensure_segments(db) -> int:
    if db.scalar(select(func.count()).select_from(Segment)) == 0:
        segment_service.recompute(db)
        for code, config in SEGMENT_COUPON.items():
            segment = db.scalar(select(Segment).where(Segment.code == code))
            if segment is not None:
                segment.coupon_face = config["coupon_face"]
                segment.core_share = config["core_share"]
        db.flush()
    return db.scalar(select(func.count()).select_from(Segment)) or 0


def ensure_campaigns(db) -> int:
    for spec in CAMPAIGNS:
        exists = db.scalar(select(Campaign).where(Campaign.code == spec["code"]))
        if exists is not None:
            continue
        audience_service.create_campaign(
            db,
            {
                "code": spec["code"],
                "name": spec["name"],
                "channel": spec["channel"],
                "budget": spec["budget"],
                "status": spec["status"],
                "starts_on": spec["starts_on"],
                "ends_on": spec["ends_on"],
                "note": spec["note"],
            },
            operator_email="seed@rfmseg.io",
            seed_key=spec["seed_key"],
        )
        db.flush()
    return db.scalar(select(func.count()).select_from(Campaign)) or 0


def ensure_audiences(db) -> int:
    from src.models.audience import Audience

    campaigns = {item.code: item for item in db.scalars(select(Campaign)).all()}
    for seed_key, campaign_code, note in SEED_AUDIENCES:
        campaign = campaigns.get(campaign_code)
        if campaign is None:
            continue
        audience_service.generate(
            db,
            campaign=campaign,
            budget=None,
            operator_email="seed@rfmseg.io",
            note=note,
            seed_key=seed_key,
        )
    db.flush()
    return db.scalar(select(func.count()).select_from(Audience)) or 0


def _unit(*parts: object) -> float:
    """确定性 uniform(0,1)：不依赖 PYTHONHASHSEED，两次 seed 结果一致。"""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / 0x1000000000000


TREATED_REDEEM_MULT = 2.4
CONTROL_REDEEM_MULT = 1.2


def _settlement_rows(db, evaluation, batch_no: str, as_of: str, quality: float) -> list[dict]:
    """按冻结的两组生成会员级结算事实。

    处理组：有券，核销概率 = purchase_rate × 2.4；
    对照组：没有券，只有自然购买，概率 = purchase_rate × 1.2（低于处理组，体现券的增量）。
    `quality` 是这一批次已回流的比例（晚到批次会补齐剩余部分）。
    """
    from src.models.member import Member

    treated = set(int(member_id) for member_id in (evaluation.treated_members or []))
    control = set(int(member_id) for member_id in (evaluation.control_members or []))
    members = db.scalars(select(Member).where(Member.id.in_(treated | control))).all()
    rows = []
    for member in members:
        group = "treated" if member.id in treated else "control"
        base = (member.purchase_rate or 0.0) * (2.4 if group == "treated" else 1.2)
        probability = min(0.95, base)
        if _unit("redeem", group, member.member_no, evaluation.campaign_id) >= probability:
            continue
        # 这一批是否已回流：同一会员可能在后一批才补齐
        if _unit("batch", batch_no, member.member_no) >= quality:
            continue
        gmv = round((member.avg_ticket or 20.0) * (1.1 + _unit("gmv", batch_no, member.member_no) * 0.5), 2)
        rows.append(
            {
                "member_no": member.member_no,
                "redeemed": group == "treated",
                "orders": 1,
                "gmv": gmv,
                "as_of": as_of,
            }
        )
    return rows


def ensure_evaluations(db) -> dict:
    """确认两份历史名单 → 冻结对照组 → 导入分批结算 → 一份发布、一份进行中。"""
    from src.models.audience import Audience
    from src.models.evaluation import Evaluation

    audiences = {
        item.seed_key: item for item in db.scalars(select(Audience)).all() if item.seed_key
    }
    campaigns = {item.code: item for item in db.scalars(select(Campaign)).all()}
    for spec in SEED_EVALUATIONS:
        campaign = campaigns.get(spec["campaign_code"])
        audience = audiences.get(spec["audience_seed_key"])
        if campaign is None or audience is None:
            continue
        if audience.status == "pending":
            audience_service.confirm(
                db, audience, status="confirmed", note="seed：历史活动已结算，冻结同口径对照组", actor="seed@rfmseg.io"
            )
        evaluation = evaluation_service.freeze_for_audience(db, audience)
        for batch_no, as_of, quality in spec["batches"]:
            evaluation_service.apply_import(
                db,
                campaign_id=campaign.id,
                batch_no=batch_no,
                as_of=parse_date(as_of),
                rows=_settlement_rows(db, evaluation, batch_no, as_of, quality),
                operator_email="seed@rfmseg.io",
                seed_key=f"seed-import-{batch_no}",
            )
            db.flush()
        if spec["publish"] and evaluation.status != "published":
            evaluation_service.publish(db, evaluation, actor="seed@rfmseg.io")
    db.flush()
    evaluations = db.scalars(select(Evaluation)).all()
    return {
        "total": len(evaluations),
        "published": sum(1 for item in evaluations if item.status == "published"),
    }


def ensure_audit(db) -> None:
    seeds = [
        ("seed-audit-1", "admin@rfmseg.io", "admin", "segment.recompute", "segment", {"weights": [0.3, 0.3, 0.4]}),
        ("seed-audit-2", "analyst@rfmseg.io", "analyst", "export.members", "member", {"rows": 8000}),
    ]
    for seed_key, email, role, action, entity, detail in seeds:
        exists = db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key))
        if exists is None:
            db.add(
                AuditLog(
                    actor_email=email,
                    actor_role=role,
                    action=action,
                    entity=entity,
                    detail=detail,
                    layer="seed",
                    seed_key=seed_key,
                )
            )
    db.flush()


def seed_all() -> dict:
    from src.models.audience import Audience

    with session_scope() as db:
        users = ensure_users(db)
        members, orders = ensure_members_and_orders(db)
        segments = ensure_segments(db)
        ensure_campaigns(db)
        ensure_audiences(db)
        ensure_evaluations(db)
        ensure_audit(db)
        audiences = db.scalar(select(func.count()).select_from(Audience)) or 0
        pending = db.scalar(select(func.count()).select_from(Audience).where(Audience.status == "pending")) or 0
        summary = (
            f"SEED_SUMMARY brand=rfmseg users={users} sources={members} "
            f"runs={orders} findings={segments} pending={pending}"
        )
        print(summary, flush=True)
        return {
            "users": users,
            "members": members,
            "orders": orders,
            "segments": segments,
            "audiences": audiences,
            "pending": pending,
        }


if __name__ == "__main__":
    seed_all()
