"""算法 A（RFM 评分与八类分群）单测：正常 / 边界 / 确定性。"""
from __future__ import annotations

from datetime import date

import pytest

from src.constants.enums import SEGMENT_ORDER
from src.services import rfm_service
from src.utils.errors import AppError

AS_OF = date(2026, 11, 14)


def _member(index, days, orders, amount, rate=0.03, ticket=26.0):
    last = None if days is None else AS_OF.fromordinal(AS_OF.toordinal() - days)
    return {
        "id": index,
        "member_no": f"M{index:03d}",
        "last_order_on": last,
        "orders": orders,
        "amount": amount,
        "purchase_rate": rate,
        "avg_ticket": ticket,
    }


def test_percentile_thresholds_are_linear():
    assert rfm_service.percentiles([1, 2, 3, 4, 5], 5) == [1.8, 2.6, 3.4, 4.2]
    assert rfm_service.percentiles([], 5) == [0.0, 0.0, 0.0, 0.0]


def test_scores_span_one_to_five():
    members = [
        _member(1, 5, 1, 20),
        _member(2, 20, 2, 40),
        _member(3, 40, 3, 60),
        _member(4, 70, 4, 80),
        _member(5, 120, 5, 100),
    ]
    result = rfm_service.compute(members, as_of=AS_OF)
    by_no = {row["member_no"]: row for row in result["members"]}
    # R 越小越好：最近下单的人 R 分 5
    assert by_no["M001"]["r_score"] == 5
    assert by_no["M005"]["r_score"] == 1
    # F / M 越大越好
    assert [by_no[f"M{index:03d}"]["f_score"] for index in range(1, 6)] == [1, 2, 3, 4, 5]
    assert [by_no[f"M{index:03d}"]["m_score"] for index in range(1, 6)] == [1, 2, 3, 4, 5]
    assert result["thresholds"]["f"] == [1.8, 2.6, 3.4, 4.2]


def test_ties_share_the_same_bucket():
    members = [_member(index, 30, 4, 50) for index in range(1, 6)]
    result = rfm_service.compute(members, as_of=AS_OF)
    scores = {(row["r_score"], row["f_score"], row["m_score"]) for row in result["members"]}
    assert len(scores) == 1
    assert scores.pop() == (5, 1, 1)


def test_classify_covers_all_eight_segments():
    cases = {
        (5, 5, 5): "champion",
        (3, 4, 3): "loyal",
        (4, 3, 4): "potential",
        (2, 4, 4): "at_risk",
        (4, 2, 1): "new",
        (2, 2, 2): "churn_warn",
        (3, 2, 2): "ordinary",
        (1, 1, 1): "hibernating",
    }
    for scores, expected in cases.items():
        assert rfm_service.classify(*scores) == expected
    assert len({*cases.values()}) == len(SEGMENT_ORDER)


def test_member_without_orders_goes_hibernating():
    members = [_member(1, None, 0, 0), _member(2, 10, 6, 200), _member(3, 25, 2, 60)]
    result = rfm_service.compute(members, as_of=AS_OF)
    row = next(item for item in result["members"] if item["member_no"] == "M001")
    assert row["r_days"] == 9999
    assert row["r_score"] == 1
    assert row["segment_code"] == "hibernating"


def test_segment_lift_uses_rates_from_data():
    members = [
        _member(1, 5, 5, 200, rate=0.09),
        _member(2, 6, 5, 190, rate=0.09),
        _member(3, 200, 1, 30, rate=0.01),
        _member(4, 210, 1, 25, rate=0.01),
    ]
    result = rfm_service.compute(members, as_of=AS_OF)
    global_rate = result["global_purchase_rate"]
    assert global_rate == pytest.approx(0.05)
    top = max(result["segments"], key=lambda item: item["lift"])
    assert top["purchase_rate"] == pytest.approx(0.09)
    assert top["lift"] == pytest.approx(1.8)
    assert sum(item["member_count"] for item in result["segments"]) == 4
    assert sum(item["share"] for item in result["segments"]) == pytest.approx(1.0)


def test_weights_must_sum_to_one():
    members = [_member(1, 5, 2, 40)]
    with pytest.raises(AppError) as exc:
        rfm_service.compute(members, as_of=AS_OF, weights=(0.5, 0.5, 0.5))
    assert exc.value.status_code == 422
    with pytest.raises(AppError):
        rfm_service.compute(members, as_of=AS_OF, weights=(1.5, -0.5, 0.0))


def test_composite_score_follows_weights():
    members = [
        _member(1, 5, 1, 20),      # R 高 / F 低 / M 低
        _member(2, 200, 5, 200),   # R 低 / F 高 / M 高
        _member(3, 40, 3, 60),
        _member(4, 90, 2, 40),
    ]
    result = rfm_service.compute(members, as_of=AS_OF, weights=(0.3, 0.3, 0.4))
    alt = rfm_service.compute(members, as_of=AS_OF, weights=(0.6, 0.2, 0.2))
    base_scores = {item["member_no"]: item["composite_score"] for item in result["members"]}
    alt_scores = {item["member_no"]: item["composite_score"] for item in alt["members"]}
    assert base_scores != alt_scores
    row = next(item for item in result["members"] if item["member_no"] == "M001")
    assert row["composite_score"] == pytest.approx(
        0.3 * row["r_score"] + 0.3 * row["f_score"] + 0.4 * row["m_score"]
    )


def test_empty_input_is_partial_and_deterministic():
    empty = rfm_service.compute([], as_of=AS_OF)
    assert empty["status"] == "partial"
    assert empty["members"] == []
    assert len(empty["segments"]) == 8
    assert all(item["member_count"] == 0 for item in empty["segments"])

    members = [_member(1, 5, 3, 120), _member(2, 40, 1, 30), _member(3, 90, 2, 60)]
    first = rfm_service.compute(members, as_of=AS_OF)
    second = rfm_service.compute(members, as_of=AS_OF)
    assert first == second
