"""算法 B（提升度与预算分配）单测：正常 / 边界 / 确定性。"""
from __future__ import annotations

import pytest

from src.services import lift_service
from src.utils.errors import AppError


def _segment(code, count, rate, coupon, ticket=30.0, share=0.6):
    return {
        "code": code,
        "name": code.upper(),
        "member_count": count,
        "purchase_rate": rate,
        "coupon_face": coupon,
        "core_share": share,
        "avg_ticket": ticket,
    }


THREE = [
    _segment("a", 1000, 0.060, 8.0),
    _segment("b", 1000, 0.045, 6.0),
    _segment("c", 1000, 0.033, 2.0),
]


def test_greedy_order_by_lift_over_cost():
    result = lift_service.allocate(THREE, budget=100000, global_rate=0.03)
    ranks = {row["segment_code"]: row["priority"] for row in result["segments"]}
    # 单人成本：a=0.63, b=0.42, c=0.216 → lift/成本 排序 c > b > a
    assert ranks == {"c": 1, "b": 2, "a": 3}
    assert all(row["status"] == "allocated" for row in result["segments"])


def test_budget_binding_defers_remaining_segments():
    result = lift_service.allocate(THREE, budget=200, global_rate=0.03)
    status = {row["segment_code"]: row["status"] for row in result["segments"]}
    assert status["c"] == "allocated"
    assert status["b"] == "deferred"
    assert status["a"] == "deferred"
    deferred = next(row for row in result["segments"] if row["segment_code"] == "b")
    assert "预算不足" in deferred["reason"]
    assert deferred["allocated"] == 0
    assert result["totals"]["spend"] <= 200


def test_tail_discount_halves_effect_math():
    single = [_segment("a", 1000, 0.060, 8.0)]
    result = lift_service.allocate(single, budget=630, global_rate=0.03, tail_factor=0.6, orders_per_converter=1.4)
    row = result["segments"][0]
    assert row["allocated"] == 1000
    assert row["core_allocated"] == 600
    assert row["tail_allocated"] == 400
    # 有效人数 = 600 + 400×0.6 = 840；Δp = 0.03 → 增量人数 25.2 → 单量 round(35.28)=35
    assert row["effective_people"] == pytest.approx(840.0)
    assert row["inc_converters"] == pytest.approx(25.2)
    assert row["inc_orders"] == 35
    assert row["budget"] == pytest.approx(630.0)
    assert row["inc_gmv"] == pytest.approx(1050.0)
    assert row["roi"] == pytest.approx(1.67)


def test_full_tail_factor_removes_discount():
    single = [_segment("a", 1000, 0.060, 8.0)]
    discounted = lift_service.allocate(single, budget=630, global_rate=0.03, tail_factor=0.6)
    plain = lift_service.allocate(single, budget=630, global_rate=0.03, tail_factor=1.0)
    assert plain["segments"][0]["inc_orders"] > discounted["segments"][0]["inc_orders"]


def test_lift_below_one_is_not_targeted():
    segments = [_segment("churn", 800, 0.021, 6.0), _segment("dead", 500, 0.010, 4.0)]
    result = lift_service.allocate(segments, budget=100000, global_rate=0.03)
    assert all(row["status"] == "ineligible" for row in result["segments"])
    assert result["totals"]["audience"] == 0
    assert result["totals"]["spend"] == 0.0
    assert result["totals"]["roi"] == 0.0


def test_totals_equal_sum_of_segments():
    result = lift_service.allocate(THREE, budget=900, global_rate=0.03)
    allocated = [row for row in result["segments"] if row["status"] == "allocated"]
    totals = result["totals"]
    assert totals["audience"] == sum(row["allocated"] for row in allocated)
    assert totals["spend"] == pytest.approx(sum(row["budget"] for row in allocated))
    assert totals["inc_orders"] == sum(row["inc_orders"] for row in allocated)
    assert totals["inc_gmv"] == pytest.approx(sum(row["inc_gmv"] for row in allocated))
    assert totals["spend"] <= 900
    assert totals["budget_remaining"] == pytest.approx(900 - totals["spend"])


def test_invalid_budget_and_params():
    with pytest.raises(AppError):
        lift_service.allocate(THREE, budget=0, global_rate=0.03)
    with pytest.raises(AppError):
        lift_service.allocate(THREE, budget=-10, global_rate=0.03)
    with pytest.raises(AppError):
        lift_service.allocate(THREE, budget=100, global_rate=0.03, tail_factor=0.0)
    with pytest.raises(AppError):
        lift_service.allocate(THREE, budget=100, global_rate=0.03, orders_per_converter=0)


def test_empty_segments_and_determinism():
    empty = lift_service.allocate([], budget=100, global_rate=0.03)
    assert empty["totals"]["audience"] == 0
    first = lift_service.allocate(THREE, budget=777, global_rate=0.03)
    second = lift_service.allocate(THREE, budget=777, global_rate=0.03)
    assert first == second
    assert first["log"] == second["log"]
