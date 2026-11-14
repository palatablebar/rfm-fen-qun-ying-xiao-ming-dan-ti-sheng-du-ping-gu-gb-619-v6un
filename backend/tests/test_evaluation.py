"""结算评估：同口径对照组、分批回流、导入幂等、发布锁定。

覆盖需求里的四个关键行为：
1. 确定名单时冻结对照组，自然复购由对照组扣除；
2. 同一批次重试导入不新增、不重复应用；
3. 晚到批次更新「进行中」评估，但不覆盖「已发布」评估；
4. 发布后 in_progress → published，页面/导出共用处理人数、对照人数、增量率、ROI。
"""
from __future__ import annotations

from datetime import date

import pytest

from src.constants.enums import EvaluationStatus
from src.models.member import Member
from src.services import evaluation_service
from src.utils.errors import AppError
from tests.conftest import add_audience, add_campaign, add_members


def _confirm(db, audience):
    from src.services import audience_service

    audience_service.confirm(db, audience, status="confirmed", note=None, actor="test@rfmseg.io")
    return evaluation_service.get_by_audience(db, audience.id)


def _rows(members, *, redeemed=True, gmv=40.0, as_of="2026-10-08"):
    return [
        {"member_no": member.member_no, "redeemed": redeemed, "orders": 1, "gmv": gmv, "as_of": as_of}
        for member in members
    ]


def test_confirm_freezes_same_segment_holdout(db):
    campaign = add_campaign(db)
    members = add_members(db, 300, segment="champion", seed=1)
    audience = add_audience(db, campaign, allocated=100)
    evaluation = _confirm(db, audience)

    assert evaluation.status == EvaluationStatus.IN_PROGRESS.value
    # 处理组 = 名单人数 − 对照组留出；默认 10% 对照组
    assert evaluation.treated_count == 90
    assert evaluation.control_count == 10
    assert evaluation.treated_count + evaluation.control_count == 100
    treated = set(evaluation.treated_members)
    control = set(evaluation.control_members)
    assert treated.isdisjoint(control)
    assert all(member_id in {member.id for member in members} for member_id in treated | control)
    # 对照组才是没被触达的人，成本只按处理组折算
    assert evaluation.spend == pytest.approx(54.0)


def test_holdout_control_is_excluded_from_csv_export(db):
    from src.services import export_service

    campaign = add_campaign(db)
    members = add_members(db, 300, segment="champion", seed=11)
    audience = add_audience(db, campaign, allocated=100, audience_no="A-11")
    evaluation = _confirm(db, audience)
    control_ids = set(evaluation.control_members)
    content = export_service.audience_csv(db, audience.id).decode("utf-8-sig")
    member_nos = [member.member_no for member in members]
    imported_nos = [member_no for member_no in member_nos if member_no in content]
    # 名单明细行数 = 处理组人数，且冻结的对照组会员号一个都不在导出里
    lines = [line for line in content.splitlines() if line.strip()]
    assert len(lines) == evaluation.treated_count + 1
    for member_id in control_ids:
        assert db.get(Member, member_id).member_no not in content


def test_confirm_is_idempotent(db):
    campaign = add_campaign(db)
    add_members(db, 200, segment="champion", seed=2)
    audience = add_audience(db, campaign, allocated=80, audience_no="A-1")
    first = _confirm(db, audience)
    first_control = list(first.control_members)
    second = _confirm(db, audience)
    assert second.id == first.id
    assert second.control_members == first_control


def test_natural_repeat_purchase_is_subtracted(db):
    campaign = add_campaign(db, budget=100)
    members = add_members(db, 300, segment="champion", seed=3)
    audience = add_audience(db, campaign, allocated=100, spend=100.0)
    evaluation = _confirm(db, audience)

    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    control = [db.get(Member, member_id) for member_id in evaluation.control_members]
    # 处理组 90 人下单 27（30%），对照组自然下单 2（20%）→ 增量率 10%
    rows = _rows(treated[:27], gmv=50.0) + _rows(control[:2], gmv=50.0, redeemed=False)
    assert len(control) == 10
    result = evaluation_service.apply_import(
        db,
        campaign_id=campaign.id,
        batch_no="B1",
        as_of=date(2026, 10, 8),
        rows=rows,
        operator_email="test@rfmseg.io",
    )
    evaluation = evaluation_service.get_evaluation(db, evaluation.id)
    assert evaluation.treated_rate == pytest.approx(0.30)
    assert evaluation.control_rate == pytest.approx(0.20)
    assert evaluation.incremental_rate == pytest.approx(0.10)
    # 增量人数 = 90 × 10% = 9；增量单量 = 9 × 1；增量 GMV = 9 × 50，实花 90（100×90%）
    assert evaluation.inc_converters == pytest.approx(9.0)
    assert evaluation.inc_orders == 9
    assert evaluation.inc_gmv == pytest.approx(450.0)
    assert evaluation.roi == pytest.approx(5.0)
    assert result["applied"] == 29


def test_duplicate_import_does_not_add_or_reapply(db):
    campaign = add_campaign(db)
    add_members(db, 300, segment="champion", seed=4)
    audience = add_audience(db, campaign, allocated=100, audience_no="A-4")
    evaluation = _confirm(db, audience)
    from src.models.evaluation import EvaluationImport

    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    payload = {
        "campaign_id": campaign.id,
        "batch_no": "B1",
        "as_of": date(2026, 10, 8),
        "rows": _rows(treated[:10]),
        "operator_email": "test@rfmseg.io",
    }
    first = evaluation_service.apply_import(db, **payload)
    assert first["duplicate"] is False
    assert first["applied"] == 10
    evaluation = evaluation_service.get_evaluation(db, evaluation.id)
    inc_orders_after_first = evaluation.inc_orders

    second = evaluation_service.apply_import(db, **payload)
    assert second["duplicate"] is True
    assert second["applied"] == 0
    assert db.query(EvaluationImport).count() == 1
    evaluation = evaluation_service.get_evaluation(db, evaluation.id)
    assert evaluation.inc_orders == inc_orders_after_first


def test_same_batch_different_content_conflicts(db):
    campaign = add_campaign(db)
    add_members(db, 300, segment="champion", seed=5)
    audience = add_audience(db, campaign, allocated=100, audience_no="A-5")
    evaluation = _confirm(db, audience)
    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B1", as_of=date(2026, 10, 8),
        rows=_rows(treated[:10]), operator_email="test@rfmseg.io",
    )
    with pytest.raises(AppError) as exc:
        evaluation_service.apply_import(
            db, campaign_id=campaign.id, batch_no="B1", as_of=date(2026, 10, 8),
            rows=_rows(treated[:12]), operator_email="test@rfmseg.io",
        )
    assert exc.value.status_code == 409


def test_late_batch_updates_in_progress_evaluation(db):
    campaign = add_campaign(db)
    add_members(db, 300, segment="champion", seed=6)
    audience = add_audience(db, campaign, allocated=100, audience_no="A-6")
    evaluation = _confirm(db, audience)
    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    control = [db.get(Member, member_id) for member_id in evaluation.control_members]

    evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B1", as_of=date(2026, 9, 30),
        rows=_rows(treated[:9]) + _rows(control[:1], redeemed=False), operator_email="test@rfmseg.io",
    )
    early = evaluation_service.get_evaluation(db, evaluation.id)
    early_rate = early.incremental_rate

    # 晚到批次补齐了更多核销（数据截止更晚）
    evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B2", as_of=date(2026, 10, 8),
        rows=_rows(treated[:36]) + _rows(control[:2], redeemed=False), operator_email="test@rfmseg.io",
    )
    late = evaluation_service.get_evaluation(db, evaluation.id)
    assert late.incremental_rate > early_rate
    assert late.treated_rate == pytest.approx(0.40)


def test_published_evaluation_is_locked_against_late_batches(db):
    campaign = add_campaign(db)
    add_members(db, 300, segment="champion", seed=7)
    audience = add_audience(db, campaign, allocated=100, audience_no="A-7")
    evaluation = _confirm(db, audience)
    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    control = [db.get(Member, member_id) for member_id in evaluation.control_members]

    evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B1", as_of=date(2026, 10, 6),
        rows=_rows(treated[:20]) + _rows(control[:2], redeemed=False), operator_email="test@rfmseg.io",
    )
    published = evaluation_service.publish(db, evaluation, actor="admin@rfmseg.io")
    frozen = (published.incremental_rate, published.roi, published.treated_count, published.control_count)

    result = evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B2", as_of=date(2026, 10, 8),
        rows=_rows(treated[:50]) + _rows(control[:3], redeemed=False), operator_email="test@rfmseg.io",
    )
    assert result["applied"] == 0
    assert result["skipped"] == 53
    after = evaluation_service.get_evaluation(db, evaluation.id)
    assert (after.incremental_rate, after.roi, after.treated_count, after.control_count) == frozen
    assert after.status == EvaluationStatus.PUBLISHED.value


def test_publish_is_idempotent_and_transitions_status(db):
    campaign = add_campaign(db)
    add_members(db, 200, segment="champion", seed=8)
    audience = add_audience(db, campaign, allocated=50, audience_no="A-8")
    evaluation = _confirm(db, audience)
    assert evaluation.status == EvaluationStatus.IN_PROGRESS.value
    first = evaluation_service.publish(db, evaluation, actor="admin@rfmseg.io")
    assert first.status == EvaluationStatus.PUBLISHED.value
    published_at = first.published_at
    second = evaluation_service.publish(db, first, actor="admin@rfmseg.io")
    assert second.status == EvaluationStatus.PUBLISHED.value
    assert second.published_at == published_at


def test_no_control_data_yields_zero_increment(db):
    campaign = add_campaign(db)
    add_members(db, 300, segment="champion", seed=9)
    audience = add_audience(db, campaign, allocated=100, audience_no="A-9")
    evaluation = _confirm(db, audience)
    # 只回流处理组，没有对照组数据 → 不能把全部核销都算成增量
    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B1", as_of=date(2026, 10, 8),
        rows=_rows(treated[:22]), operator_email="test@rfmseg.io",
    )
    evaluation = evaluation_service.get_evaluation(db, evaluation.id)
    assert evaluation.treated_rate == pytest.approx(22 / 90, abs=1e-5)
    assert evaluation.control_rate == 0.0
    assert evaluation.incremental_rate == 0.0
    assert evaluation.inc_gmv == 0.0


def test_serialize_shares_four_numbers_for_page_and_export(db):
    campaign = add_campaign(db)
    add_members(db, 300, segment="champion", seed=10)
    audience = add_audience(db, campaign, allocated=100, spend=100.0, audience_no="A-10")
    evaluation = _confirm(db, audience)
    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    control = [db.get(Member, member_id) for member_id in evaluation.control_members]
    evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B1", as_of=date(2026, 10, 8),
        rows=_rows(treated[:27]) + _rows(control[:2], redeemed=False), operator_email="test@rfmseg.io",
    )
    evaluation_service.publish(db, evaluation, actor="admin@rfmseg.io")
    data = evaluation_service.serialize(evaluation, audience, campaign)
    assert set(["treated_count", "control_count", "incremental_rate", "roi"]) <= set(data)
    assert data["status"] == "published"
    assert data["status_label"] == "已发布"
    assert data["treated_count"] == 90
    assert data["control_count"] == 10
    assert data["incremental_rate"] == pytest.approx(0.10)
    # 每单 ¥40：处理组人均 27×40/90=12，对照组 2×40/10=8 → 增量 GMV 90×4=360，ROI 360/90
    assert data["inc_gmv"] == pytest.approx(360.0)
    assert data["roi"] == pytest.approx(4.0)


def test_unreached_members_are_excluded_from_conversion_denominator(db):
    """券投递失败的人不算「没转化」：从处理组转化率分母中剔除。"""
    campaign = add_campaign(db)
    add_members(db, 300, segment="champion", seed=12)
    audience = add_audience(db, campaign, allocated=100, audience_no="A-12", spend=90)
    evaluation = _confirm(db, audience)
    treated = [db.get(Member, member_id) for member_id in evaluation.treated_members]
    control = [db.get(Member, member_id) for member_id in evaluation.control_members]

    def row(member, *, reached, redeemed, orders):
        return {
            "member_no": member.member_no,
            "reached": reached,
            "redeemed": redeemed,
            "orders": orders,
            "gmv": 50.0 if orders else 0.0,
            "as_of": "2026-10-08",
        }

    rows = [row(member, reached=True, redeemed=True, orders=1) for member in treated[:18]]
    rows += [row(member, reached=False, redeemed=False, orders=0) for member in treated[18:28]]
    rows += [row(member, reached=True, redeemed=False, orders=1) for member in control[:2]]
    evaluation_service.apply_import(
        db, campaign_id=campaign.id, batch_no="B1", as_of=date(2026, 10, 8),
        rows=rows, operator_email="test@rfmseg.io",
    )
    evaluation = evaluation_service.get_evaluation(db, evaluation.id)
    # 分母 90 − 10 投递失败 = 80；转换 18/80 = 22.5%，对照组 2/10 = 20% → 增量率 2.5%
    assert evaluation.treated_reached == 80
    assert evaluation.treated_rate == pytest.approx(0.225)
    assert evaluation.control_rate == pytest.approx(0.20)
    assert evaluation.incremental_rate == pytest.approx(0.025)
