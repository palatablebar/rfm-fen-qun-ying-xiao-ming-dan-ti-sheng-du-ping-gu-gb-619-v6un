"""结算评估：确认名单时冻结同口径对照组，分批回流结算后发布增量与 ROI。

和「算法 B 的 lift」的区别（README §10 算法 C）：

- lift 是投放前的**历史券响应率 / 大盘**，只能回答「这个群本来就更爱买吗」；
- 评估是投放后的**处理组 vs 同口径对照组**，用实际回流数据扣掉自然复购，
  回答「这份名单本身多带来了多少」。

对齐口径：
1. 确认名单时，把名单按分群切成处理组与**对照组（holdout，不触达）**：
   每个分群内按固定哈希抽取 ``control_ratio``（默认 10%）的名单会员作对照，
   与处理组同分群、同名单来源，因此同口径；冻结后不再重抽；
2. 对照组会从券平台名单导出中剔除，确保他们真的没收到券；
3. 结算事实按 ``(campaign_id, batch_no)`` 分批导入，同一会员以 ``as_of`` 最新的记录为准；
   晚到批次会更新「进行中」评估，但不会覆盖「已发布」评估；
4. 增量率 = 处理组转化率 − 对照组自然转化率；增量单量 / GMV 同样按两组人均差 × 处理人数扣除自然复购；
   处理组里券没送达（``reached=False``）的人从分母剔除；对照组的「下单」就是自然复购；
5. 发布后 ``in_progress → published``，数字锁定，页面与导出读同一份 ``serialize`` 结果。
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import EVALUATION_STATUS_LABELS, EvaluationStatus
from src.constants.limits import DEFAULT_CONTROL_RATIO
from src.models.audience import Audience
from src.models.campaign import Campaign
from src.models.evaluation import Evaluation, EvaluationImport
from src.models.member import Member
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_date, iso_utc, parse_date, utcnow


def _round(value: float, digits: int = 2) -> float:
    return round(float(value) + 0.0, digits)


def _hash_key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _control_ratio(value: float | None) -> float:
    ratio = DEFAULT_CONTROL_RATIO if value is None else float(value)
    if not (0.0 < ratio <= 1.0):
        raise AppError("VALIDATION", 422, {"reason": "对照组比例必须在 (0,1] 之间"})
    return ratio


# --------------------------------------------------------------------------- #
# 冻结：处理组 + 同口径对照组
# --------------------------------------------------------------------------- #
def _listed_members(db: Session, audience: Audience) -> list[tuple[str, int]]:
    """按分群顺序取名单实际分配的会员（与导出名单明细同一排序）。

    返回 [(segment_code, member_id), ...]；会员已不存在的会被跳过。
    """
    picked: list[tuple[str, int]] = []
    seen: set[int] = set()
    for row in audience.allocation or []:
        if row.get("status") != "allocated" or not row.get("allocated"):
            continue
        code = row.get("segment_code")
        members = db.scalars(
            select(Member)
            .where(Member.segment_code == code)
            .order_by(Member.composite_score.desc().nullslast(), Member.id)
            .limit(int(row["allocated"]))
        ).all()
        for member in members:
            if member.id in seen:
                continue
            seen.add(member.id)
            picked.append((code or "", member.id))
    return picked


def _split_listed(
    audience: Audience, listed: list[tuple[str, int]], ratio: float
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """把已确认名单按分群切成「处理组」与「对照组（留出、不触达）」。

    对照组 = 每个分群内按固定哈希抽取 ``ratio`` 比例的名单会员，与处理组同分群、同名单来源，
    因而同口径；这部分会员不会进入券平台名单（导出时剔除），用于估计自然复购。
    每个分群至少留 1 人对照、至少留 1 人处理，保证两边都有样本。
    """
    per_segment: dict[str, list[int]] = {}
    for code, member_id in listed:
        per_segment.setdefault(code, []).append(member_id)

    control: list[tuple[str, int]] = []
    control_ids: set[int] = set()
    for code in sorted(per_segment):
        ids = per_segment[code]
        window = int(round(len(ids) * ratio))
        window = min(window, len(ids) - 1)
        if window <= 0:
            continue
        ranked = sorted(
            ids,
            key=lambda member_id: _hash_key(audience.audience_no, "control", member_id),
        )
        for member_id in ranked[:window]:
            control.append((code, member_id))
            control_ids.add(member_id)

    treated = [(code, member_id) for code, member_id in listed if member_id not in control_ids]
    return treated, control


def freeze_for_audience(
    db: Session,
    audience: Audience,
    *,
    control_ratio: float | None = None,
    seed_key: str | None = None,
) -> Evaluation:
    """确认名单时调用：若尚未冻结则生成处理组 / 对照组；已冻结则原样返回（幂等）。"""
    existing = db.scalar(select(Evaluation).where(Evaluation.audience_id == audience.id))
    if existing is not None:
        return existing

    ratio = _control_ratio(control_ratio)
    listed = _listed_members(db, audience)
    if not listed:
        raise AppError("VALIDATION", 409, {"reason": "名单没有可冻结的投放会员，无法建立对照组"})
    treated, control = _split_listed(audience, listed, ratio)
    treated_share = len(treated) / len(listed)
    # 对照组不触达，投放成本按处理组占名单的比例折算（券成本跟人走）
    spend = _round((audience.spend or 0.0) * treated_share, 2)

    evaluation = Evaluation(
        audience_id=audience.id,
        campaign_id=audience.campaign_id,
        status=EvaluationStatus.IN_PROGRESS.value,
        control_ratio=ratio,
        treated_count=len(treated),
        control_count=len(control),
        treated_members=[member_id for _, member_id in treated],
        control_members=[member_id for _, member_id in control],
        facts={},
        spend=spend,
        seed_key=seed_key or (f"{audience.seed_key}:evaluation" if audience.seed_key else None),
    )
    db.add(evaluation)
    db.flush()
    recompute_metrics(evaluation)
    db.flush()
    return evaluation


def frozen_control_ids(db: Session, audience_id: int) -> set[int]:
    """已被冻结为对照组的会员：券平台名单导出时剔除，确保他们真的没被触达。"""
    evaluation = db.scalar(select(Evaluation).where(Evaluation.audience_id == audience_id))
    if evaluation is None:
        return set()
    return {int(member_id) for member_id in (evaluation.control_members or [])}


# --------------------------------------------------------------------------- #
# 结算事实：分批导入（幂等）+ 指标重算
# --------------------------------------------------------------------------- #
def _normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    for item in rows:
        member_no = str(item.get("member_no") or "").strip()
        if not member_no:
            continue
        redeemed = bool(item.get("redeemed"))
        orders = item.get("orders")
        if orders is None:
            # 没有显式单量时：核销或有 GMV 都视为 1 单（对照组没有券，下单即自然购买）
            orders = 1 if (redeemed or float(item.get("gmv") or 0.0) > 0) else 0
        orders = int(orders)
        if orders < 0:
            raise AppError("VALIDATION", 422, {"reason": "订单数不能为负", "member_no": member_no})
        gmv = item.get("gmv")
        gmv = 0.0 if gmv is None else float(gmv)
        if gmv < 0:
            raise AppError("VALIDATION", 422, {"reason": "GMV 不能为负", "member_no": member_no})
        normalized.append(
            {
                "member_no": member_no,
                "reached": bool(item.get("reached", True)),
                "redeemed": redeemed,
                "orders": orders,
                "gmv": _round(gmv, 2),
            }
        )
    return normalized


def _checksum(rows: list[dict], as_of: date | None) -> str:
    payload = json.dumps(
        {"as_of": as_of.isoformat() if as_of else None, "rows": sorted(rows, key=lambda item: item["member_no"])},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _facts_of(evaluation: Evaluation) -> dict[str, dict]:
    return {str(key): value for key, value in (evaluation.facts or {}).items()}


def _batch_as_of(item: dict, fallback: date | None) -> date | None:
    text = item.get("as_of")
    return parse_date(text) if text else fallback


def apply_import(
    db: Session,
    *,
    campaign_id: int,
    batch_no: str,
    as_of: date | None,
    rows: list[dict],
    operator_email: str,
    seed_key: str | None = None,
) -> dict:
    """导入一个结算批次。

    - 同一活动 + 同一批次号：校验内容一致后直接返回原批次（不新增、不重复应用）；
    - 批次号相同但内容不同：409，避免误覆盖；
    - 已发布评估：该批次对其只计 skipped，不改任何数字。
    """
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise not_found("campaign", campaign_id)

    normalized = _normalize_rows(rows)
    checksum = _checksum(normalized, as_of)
    existing_batch = db.scalar(
        select(EvaluationImport).where(
            EvaluationImport.campaign_id == campaign_id, EvaluationImport.batch_no == batch_no
        )
    )
    if existing_batch is not None:
        if existing_batch.checksum != checksum:
            raise AppError(
                "CONFLICT",
                409,
                {"reason": "同一批次号的内容与首次导入不一致", "batch_no": batch_no},
            )
        return {
            "duplicate": True,
            "batch": serialize_batch(existing_batch),
            "applied": 0,
            "skipped": existing_batch.skipped,
            "evaluations": _campaign_evaluations(db, campaign_id),
        }

    evaluations = db.scalars(select(Evaluation).where(Evaluation.campaign_id == campaign_id)).all()
    # member_no -> Member（只解析本批出现的会员号）
    member_nos = [item["member_no"] for item in normalized]
    member_rows = db.scalars(select(Member).where(Member.member_no.in_(member_nos))).all()
    member_id_by_no = {member.member_no: member.id for member in member_rows}

    applied = 0
    skipped = 0
    for evaluation in evaluations:
        treated = {int(member_id) for member_id in (evaluation.treated_members or [])}
        control = {int(member_id) for member_id in (evaluation.control_members or [])}
        if evaluation.status == EvaluationStatus.PUBLISHED.value:
            skipped += sum(1 for item in normalized if member_id_by_no.get(item["member_no"]) in treated | control)
            continue
        facts = _facts_of(evaluation)
        for item in normalized:
            member_id = member_id_by_no.get(item["member_no"])
            if member_id is None or member_id not in treated | control:
                continue
            incoming = _batch_as_of(item, as_of)
            current = facts.get(str(member_id))
            if current is not None:
                current_as_of = parse_date(current.get("as_of"))
                if incoming is not None and current_as_of is not None and incoming < current_as_of:
                    # 数据口径更早的补录不覆盖更新的事实
                    skipped += 1
                    continue
            facts[str(member_id)] = {
                "reached": bool(item.get("reached", True)),
                "redeemed": bool(item["redeemed"]),
                "orders": int(item["orders"]),
                "gmv": _round(item["gmv"], 2),
                "as_of": (incoming or as_of).isoformat() if (incoming or as_of) else None,
                "batch_no": batch_no,
            }
            applied += 1
        evaluation.facts = facts
        evaluation.batch_no = batch_no
        if as_of is not None and (evaluation.data_as_of is None or as_of > evaluation.data_as_of):
            evaluation.data_as_of = as_of
        recompute_metrics(evaluation)

    batch = EvaluationImport(
        campaign_id=campaign_id,
        batch_no=batch_no,
        checksum=checksum,
        as_of=as_of,
        rows_count=len(normalized),
        applied=applied,
        skipped=skipped,
        operator_email=operator_email,
        seed_key=seed_key,
    )
    db.add(batch)
    db.flush()
    return {
        "duplicate": False,
        "batch": serialize_batch(batch),
        "applied": applied,
        "skipped": skipped,
        "evaluations": _campaign_evaluations(db, campaign_id),
    }


def _campaign_evaluations(db: Session, campaign_id: int) -> list[dict]:
    rows = db.scalars(select(Evaluation).where(Evaluation.campaign_id == campaign_id).order_by(Evaluation.id)).all()
    audiences = {
        item.id: item
        for item in db.scalars(select(Audience).where(Audience.id.in_([row.audience_id for row in rows]))).all()
    }
    campaign = db.get(Campaign, campaign_id)
    return [serialize(row, audiences.get(row.audience_id), campaign) for row in rows]


def list_for_campaign(db: Session, campaign_id: int) -> list[dict]:
    return _campaign_evaluations(db, campaign_id)


def get_campaign(db: Session, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise not_found("campaign", campaign_id)
    return campaign


def fact_rows(evaluation: Evaluation) -> list[dict]:
    """把冻结的两组与结算事实摊平成行（页面抽屉 / CSV 复查用），顺序确定。"""
    treated = [int(member_id) for member_id in (evaluation.treated_members or [])]
    control = [int(member_id) for member_id in (evaluation.control_members or [])]
    facts = _facts_of(evaluation)
    rows: list[dict] = []
    for group, ids in (("treated", treated), ("control", control)):
        for member_id in ids:
            fact = facts.get(str(member_id)) or {}
            rows.append(
                {
                    "group": group,
                    "member_id": member_id,
                    "reached": bool(fact.get("reached", True)),
                    "redeemed": bool(fact.get("redeemed")),
                    "orders": int(fact.get("orders") or 0),
                    "gmv": _round(fact.get("gmv") or 0.0, 2),
                    "fact_as_of": fact.get("as_of"),
                }
            )
    return rows


def recompute_metrics(evaluation: Evaluation) -> Evaluation:
    """由冻结的两组名单 + 结算事实重算四个共享数字与其他派生口径。

    增量 = 处理组人均 − 对照组人均，按处理组人数放大；自然复购被对照组扣掉。
    没有对照数据时退化为 0 增量（而不是把处理组全部算成增量）。
    """
    facts = _facts_of(evaluation)
    treated_ids = [str(member_id) for member_id in (evaluation.treated_members or [])]
    control_ids = [str(member_id) for member_id in (evaluation.control_members or [])]

    def totals(ids: list[str], *, require_reached: bool) -> tuple[int, int, int, float, int, int]:
        """返回 (券核销人数, 下单人数, 下单总单量, GMV, 已回流人数, 无效触达人数)。

        下单人数 = 活动窗口内有订单的会员（用券核销必然伴随下单，但下单不一定用券）。
        对照组没有券，「下单」就是自然复购。
        处理组里明确标记 ``reached=False`` 的人（券没送达）从转化率分母中剔除；
        还没回流任何记录的人仍在分母里（属于「暂无数据」而不是「投递失败」）。
        """
        redeemers = converters = orders = observed = unreached = 0
        gmv = 0.0
        for member_id in ids:
            fact = facts.get(member_id)
            if not fact:
                continue
            observed += 1
            if require_reached and not fact.get("reached", True):
                unreached += 1
                continue
            if fact.get("redeemed"):
                redeemers += 1
            if fact.get("redeemed") or int(fact.get("orders") or 0) > 0:
                converters += 1
            orders += int(fact.get("orders") or 0)
            gmv += float(fact.get("gmv") or 0.0)
        return redeemers, converters, orders, gmv, observed, unreached

    (
        treated_redeemers,
        treated_converters,
        treated_orders,
        treated_gmv,
        treated_observed,
        treated_unreached,
    ) = totals(treated_ids, require_reached=True)
    (
        control_redeemers,
        control_converters,
        control_orders,
        control_gmv,
        control_observed,
        control_unreached,
    ) = totals(control_ids, require_reached=False)

    # 转化率分母 = 冻结人数 − 明确投递失败人数；没回流数据的人仍算分母
    treated_size = len(treated_ids) - treated_unreached
    control_size = len(control_ids) - control_unreached
    treated_reached = treated_size
    control_reached = control_size
    # 转化率口径：处理组「下单」vs 对照组「自然下单」，增量 = 两者之差
    treated_rate = treated_converters / treated_size if treated_size else 0.0
    control_rate = control_converters / control_size if control_size else 0.0
    # 对照组一条回流都没有时不能把处理组全部当增量：增量口径未成立，先记 0
    incremental_rate = treated_rate - control_rate if control_observed else 0.0

    treated_orders_avg = treated_orders / treated_size if treated_size else 0.0
    control_orders_avg = control_orders / control_size if control_size else 0.0
    treated_gmv_avg = treated_gmv / treated_size if treated_size else 0.0
    control_gmv_avg = control_gmv / control_size if control_size else 0.0

    inc_converters = treated_size * incremental_rate
    inc_orders = (
        int(round(treated_size * (treated_orders_avg - control_orders_avg))) if control_observed else 0
    )
    inc_gmv = _round(treated_size * (treated_gmv_avg - control_gmv_avg), 2) if control_observed else 0.0
    spend = _round(evaluation.spend or 0.0, 2)
    roi = _round(inc_gmv / spend, 2) if spend > 0 else 0.0

    evaluation.treated_count = len(treated_ids)
    evaluation.control_count = len(control_ids)
    evaluation.treated_reached = treated_reached
    evaluation.control_reached = control_reached
    evaluation.treated_observed = treated_observed
    evaluation.control_observed = control_observed
    evaluation.treated_redeemers = treated_redeemers
    evaluation.control_redeemers = control_redeemers
    evaluation.treated_converters = treated_converters
    evaluation.control_converters = control_converters
    evaluation.treated_gmv = _round(treated_gmv, 2)
    evaluation.control_gmv = _round(control_gmv, 2)
    evaluation.treated_rate = _round(treated_rate, 6)
    evaluation.control_rate = _round(control_rate, 6)
    evaluation.incremental_rate = _round(incremental_rate, 6)
    evaluation.inc_converters = _round(inc_converters, 2)
    evaluation.inc_orders = inc_orders
    evaluation.inc_gmv = inc_gmv
    evaluation.roi = roi
    return evaluation


def publish(db: Session, evaluation: Evaluation, *, actor: str) -> Evaluation:
    """结算发布：进行中 → 已发布；已发布时幂等返回，不覆盖数字。"""
    if evaluation.status == EvaluationStatus.PUBLISHED.value:
        return evaluation
    recompute_metrics(evaluation)
    evaluation.status = EvaluationStatus.PUBLISHED.value
    evaluation.published_at = utcnow()
    evaluation.published_by = actor
    db.flush()
    return evaluation


# --------------------------------------------------------------------------- #
# 读取与序列化（页面与导出共用）
# --------------------------------------------------------------------------- #
def get_evaluation(db: Session, evaluation_id: int) -> Evaluation:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise not_found("evaluation", evaluation_id)
    return evaluation


def get_by_audience(db: Session, audience_id: int) -> Evaluation | None:
    return db.scalar(select(Evaluation).where(Evaluation.audience_id == audience_id))


def evaluations_by_audience(db: Session, audience_ids: list[int]) -> dict[int, Evaluation]:
    if not audience_ids:
        return {}
    rows = db.scalars(select(Evaluation).where(Evaluation.audience_id.in_(audience_ids))).all()
    return {row.audience_id: row for row in rows}


def serialize(
    evaluation: Evaluation,
    audience: Audience | None = None,
    campaign: Campaign | None = None,
) -> dict:
    """页面与 CSV 导出共用：四个核心数字只从这里出，避免两端口径漂移。"""
    return {
        "id": evaluation.id,
        "audience_id": evaluation.audience_id,
        "audience_no": audience.audience_no if audience else None,
        "campaign_id": evaluation.campaign_id,
        "campaign_name": campaign.name if campaign else None,
        "campaign_code": campaign.code if campaign else None,
        "status": evaluation.status,
        "status_label": EVALUATION_STATUS_LABELS.get(evaluation.status, evaluation.status),
        "control_ratio": _round(evaluation.control_ratio or 0.0, 4),
        # 页面和导出共用的四个数字
        "treated_count": int(evaluation.treated_count or 0),
        "control_count": int(evaluation.control_count or 0),
        "incremental_rate": _round(evaluation.incremental_rate or 0.0, 6),
        "roi": _round(evaluation.roi or 0.0, 2),
        # 明细
        "treated_redeemers": int(evaluation.treated_redeemers or 0),
        "control_redeemers": int(evaluation.control_redeemers or 0),
        "treated_converters": int(evaluation.treated_converters or 0),
        "control_converters": int(evaluation.control_converters or 0),
        "treated_observed": int(evaluation.treated_observed or 0),
        "control_observed": int(evaluation.control_observed or 0),
        "treated_reached": int(evaluation.treated_reached or 0),
        "control_reached": int(evaluation.control_reached or 0),
        "treated_rate": _round(evaluation.treated_rate or 0.0, 6),
        "control_rate": _round(evaluation.control_rate or 0.0, 6),
        "treated_gmv": _round(evaluation.treated_gmv or 0.0, 2),
        "control_gmv": _round(evaluation.control_gmv or 0.0, 2),
        "inc_converters": _round(evaluation.inc_converters or 0.0, 2),
        "inc_orders": int(evaluation.inc_orders or 0),
        "inc_gmv": _round(evaluation.inc_gmv or 0.0, 2),
        "spend": _round(evaluation.spend or 0.0, 2),
        "batch_no": evaluation.batch_no,
        "data_as_of": iso_date(evaluation.data_as_of),
        "published_at": iso_utc(evaluation.published_at),
        "published_by": evaluation.published_by,
        "created_at": iso_utc(evaluation.created_at),
    }


def serialize_batch(batch: EvaluationImport) -> dict:
    return {
        "id": batch.id,
        "campaign_id": batch.campaign_id,
        "batch_no": batch.batch_no,
        "checksum": batch.checksum,
        "as_of": iso_date(batch.as_of),
        "rows_count": batch.rows_count,
        "applied": batch.applied,
        "skipped": batch.skipped,
        "operator_email": batch.operator_email,
        "created_at": iso_utc(batch.created_at),
    }
