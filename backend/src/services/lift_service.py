"""算法 B｜分群提升度与券预算分配（纯 Python，确定性）。

口径（README §10 与「名单与提升度」页同步展示）：

1. 提升度：lift_s = 分群购买率 p_s / 大盘购买率 p0。
   p_s 取群内会员历史券响应率均值，p0 取全量会员均值（同一份数据算出来，不写死）。
2. 单人成本：unit_cost_s = 触达成本 + p_s × 券面额
   （券只在核销时产生成本，所以按期望核销率折算；触达成本按投放人数算）。
3. 贪心排序：eff_s = lift_s / unit_cost_s，降序；lift ≤ 1 的群不投（增量 ≤ 0）。
4. 预算分配：按序在剩余预算内取 A_s = min(群人数, ⌊剩余 / unit_cost_s⌋)。
5. 边际收益递减：群内前 core_share 比例视为「高响应核心盘」按全效计算，
   超出部分按 tail_factor（默认 0.6）折减 —— 同一批人反复触达的增量会衰减。
6. 增量：Δp_s = p_s − p0（每人增量转化概率）
   增量人数 = (核心盘人数 + 0.6 × 溢出人数) × Δp_s
   增量单量 = 增量人数 × orders_per_converter（人均增量单量）
   增量 GMV = 增量单量 × 分群客单价
7. ROI = 增量 GMV / 该群券预算（投放成本），页面与导出都展示这条推导。
"""
from __future__ import annotations

import math

from src.constants.limits import (
    DEFAULT_CORE_SHARE,
    DEFAULT_ORDERS_PER_CONVERTER,
    DEFAULT_REACH_COST,
    DEFAULT_TAIL_FACTOR,
    LIFT_ELIGIBLE_MIN,
)
from src.utils.errors import AppError


def _round(value: float, digits: int = 2) -> float:
    return round(float(value) + 0.0, digits)


def allocate(
    segments: list[dict],
    *,
    budget: float,
    global_rate: float | None = None,
    reach_cost: float = DEFAULT_REACH_COST,
    orders_per_converter: float = DEFAULT_ORDERS_PER_CONVERTER,
    tail_factor: float = DEFAULT_TAIL_FACTOR,
    eligible_min: float = LIFT_ELIGIBLE_MIN,
) -> dict:
    if budget is None or not math.isfinite(float(budget)) or float(budget) <= 0:
        raise AppError("VALIDATION", 422, {"reason": "预算必须大于 0"})
    if reach_cost < 0 or orders_per_converter <= 0:
        raise AppError("VALIDATION", 422, {"reason": "成本与人均增量单量参数不合法"})
    if not (0.0 < tail_factor <= 1.0):
        raise AppError("VALIDATION", 422, {"reason": "折减系数必须在 (0,1]"})
    budget = float(budget)

    usable = [item for item in segments if item.get("member_count", 0) > 0]
    total_members = sum(int(item.get("member_count") or 0) for item in usable)
    if global_rate is None:
        if total_members == 0:
            global_rate = 0.0
        else:
            global_rate = sum(
                float(item.get("purchase_rate") or 0.0) * int(item.get("member_count") or 0)
                for item in usable
            ) / total_members
    global_rate = float(global_rate or 0.0)

    rows: list[dict] = []
    for item in usable:
        rate = float(item.get("purchase_rate") or 0.0)
        coupon_face = float(item.get("coupon_face") or 0.0)
        lift = (rate / global_rate) if global_rate > 0 else 0.0
        unit_cost = reach_cost + rate * coupon_face
        efficiency = (lift / unit_cost) if unit_cost > 0 else 0.0
        rows.append(
            {
                "segment_code": item.get("code"),
                "segment_name": item.get("name"),
                "member_count": int(item.get("member_count") or 0),
                "purchase_rate": _round(rate, 6),
                "lift": _round(lift, 4),
                "coupon_face": _round(coupon_face, 2),
                "unit_cost": _round(unit_cost, 4),
                "efficiency": _round(efficiency, 4),
                "core_share": _round(float(item.get("core_share") or DEFAULT_CORE_SHARE), 4),
                "avg_ticket": _round(float(item.get("avg_ticket") or 0.0), 2),
                "_rate": rate,
                "_unit_cost": unit_cost,
                "_lift": lift,
            }
        )

    ordered = sorted(
        rows,
        key=lambda row: (-row["efficiency"], -row["lift"], row["segment_code"] or ""),
    )

    remaining = budget
    priority = 0
    for row in ordered:
        eligible = row["_lift"] > eligible_min
        if not eligible:
            row.update(
                {
                    "status": "ineligible",
                    "priority": None,
                    "allocated": 0,
                    "budget": 0.0,
                    "inc_orders": 0,
                    "inc_gmv": 0.0,
                    "roi": 0.0,
                    "core_allocated": 0,
                    "tail_allocated": 0,
                    "reason": f"lift {row['lift']:.2f} ≤ {eligible_min:.2f}，投券不产生增量",
                }
            )
            continue
        unit_cost = row["_unit_cost"]
        affordable = int(remaining / unit_cost) if unit_cost > 0 else row["member_count"]
        while unit_cost > 0 and (affordable + 1) * unit_cost <= remaining + 1e-6:
            affordable += 1
        while unit_cost > 0 and affordable > 0 and affordable * unit_cost > remaining + 1e-6:
            affordable -= 1
        allocated = min(row["member_count"], max(0, affordable))
        if allocated <= 0:
            need_full = _round(row["member_count"] * unit_cost, 2)
            row.update(
                {
                    "status": "deferred",
                    "priority": None,
                    "allocated": 0,
                    "budget": 0.0,
                    "inc_orders": 0,
                    "inc_gmv": 0.0,
                    "roi": 0.0,
                    "core_allocated": 0,
                    "tail_allocated": 0,
                    "reason": f"预算不足，覆盖该群全量还需 ¥{need_full:,.2f}",
                }
            )
            continue

        priority += 1
        spend = _round(allocated * unit_cost, 2)
        remaining = _round(remaining - spend, 2)
        core_cap = int(math.ceil(row["member_count"] * row["core_share"]))
        core_allocated = min(allocated, core_cap)
        tail_allocated = max(0, allocated - core_cap)
        effective_people = core_allocated + tail_allocated * tail_factor
        delta = max(0.0, row["_rate"] - global_rate)
        inc_converters = effective_people * delta
        inc_orders = int(round(inc_converters * orders_per_converter))
        inc_gmv = _round(inc_orders * row["avg_ticket"], 2)
        roi = _round(inc_gmv / spend, 2) if spend > 0 else 0.0
        row.update(
            {
                "status": "allocated",
                "priority": priority,
                "allocated": allocated,
                "budget": spend,
                "inc_orders": inc_orders,
                "inc_gmv": inc_gmv,
                "roi": roi,
                "core_allocated": core_allocated,
                "tail_allocated": tail_allocated,
                "effective_people": _round(effective_people, 2),
                "inc_converters": _round(inc_converters, 2),
                "reason": (
                    f"核心盘 {core_allocated} 人全效 + 溢出 {tail_allocated} 人 ×{tail_factor:.1f} 折减"
                    if tail_allocated
                    else f"核心盘 {core_allocated} 人全效（未触及折减）"
                ),
            }
        )

    allocated_rows = [row for row in ordered if row["status"] == "allocated"]
    audience_total = sum(row["allocated"] for row in allocated_rows)
    spend_total = _round(sum(row["budget"] for row in allocated_rows), 2)
    inc_orders_total = sum(row["inc_orders"] for row in allocated_rows)
    inc_gmv_total = _round(sum(row["inc_gmv"] for row in allocated_rows), 2)
    roi_total = _round(inc_gmv_total / spend_total, 2) if spend_total > 0 else 0.0

    result_rows = []
    for row in ordered:
        clean = {key: value for key, value in row.items() if not key.startswith("_")}
        result_rows.append(clean)

    tail_rows = [row for row in allocated_rows if row["tail_allocated"] > 0]
    deferred = [row for row in ordered if row["status"] == "deferred"]
    ineligible = [row for row in ordered if row["status"] == "ineligible"]
    log = (
        f"预算 ¥{budget:,.2f}：按 lift/成本 贪心分配 {len(allocated_rows)} 个分群，覆盖 {audience_total} 人，"
        f"花费 ¥{spend_total:,.2f}，预计增量 {inc_orders_total} 单 / GMV ¥{inc_gmv_total:,.2f}，整体 ROI {roi_total:.2f}；"
        f"{len(tail_rows)} 个分群触发 0.6 边际折减，{len(deferred)} 个群预算不足，{len(ineligible)} 个群 lift≤1 不投"
    )
    return {
        "budget": _round(budget, 2),
        "global_rate": _round(global_rate, 6),
        "basis": {
            "reach_cost": _round(reach_cost, 4),
            "orders_per_converter": _round(orders_per_converter, 4),
            "tail_factor": _round(tail_factor, 4),
            "core_share_default": DEFAULT_CORE_SHARE,
            "eligible_min": eligible_min,
        },
        "segments": result_rows,
        "totals": {
            "audience": audience_total,
            "spend": spend_total,
            "budget_remaining": _round(remaining, 2),
            "inc_orders": inc_orders_total,
            "inc_gmv": inc_gmv_total,
            "roi": roi_total,
            "segments_allocated": len(allocated_rows),
            "segments_deferred": len(deferred),
            "segments_ineligible": len(ineligible),
            "tail_discounted": len(tail_rows),
        },
        "log": log,
    }
