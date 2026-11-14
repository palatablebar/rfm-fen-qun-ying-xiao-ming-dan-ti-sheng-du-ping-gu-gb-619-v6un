"""名单结算评估：确认名单时冻结同口径对照组，结算后发布增量与 ROI。

自然复购与增量分开的口径：
- 处理组（treated）沿用名单实际投放的分群配额，确认名单时冻结会员 id；
- 对照组（control）用同一分群结构、按固定哈希规则抽取，同样冻结，之后不再重抽；
- 结算数据按批次回流，发布的评估锁定，不再被晚到的核销记录覆盖。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("audience_id", name="ux_evaluations_audience"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 一份名单只对应一份评估；删除名单时评估一并删除
    audience_id: Mapped[int] = mapped_column(
        ForeignKey("audiences.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="in_progress", index=True)
    control_ratio: Mapped[float] = mapped_column(Float, default=0.1)

    # 确认名单时冻结的两组规模与会员 id（冻结后不随分群重算变化）
    treated_count: Mapped[int] = mapped_column(Integer, default=0)
    control_count: Mapped[int] = mapped_column(Integer, default=0)
    treated_members: Mapped[list] = mapped_column(JSON, default=list)
    control_members: Mapped[list] = mapped_column(JSON, default=list)

    # 分批回流的结算事实（按最终批次累计，不含晚到批次的重复计数）
    treated_redeemers: Mapped[int] = mapped_column(Integer, default=0)  # 处理组券核销人数
    control_redeemers: Mapped[int] = mapped_column(Integer, default=0)  # 对照组恒为 0（没发券）
    treated_converters: Mapped[int] = mapped_column(Integer, default=0)  # 处理组下单人数
    control_converters: Mapped[int] = mapped_column(Integer, default=0)  # 对照组自然下单人数
    treated_gmv: Mapped[float] = mapped_column(Float, default=0.0)
    control_gmv: Mapped[float] = mapped_column(Float, default=0.0)

    # 分批回流的结算事实：member_id -> {redeemed, gmv, orders, as_of, batch}，同一会员晚到记录覆盖旧记录
    facts: Mapped[dict] = mapped_column(JSON, default=dict)

    # 派生口径（页面与导出共用这份数字）
    treated_rate: Mapped[float] = mapped_column(Float, default=0.0)
    control_rate: Mapped[float] = mapped_column(Float, default=0.0)
    incremental_rate: Mapped[float] = mapped_column(Float, default=0.0)
    inc_converters: Mapped[float] = mapped_column(Float, default=0.0)
    inc_orders: Mapped[int] = mapped_column(Integer, default=0)
    inc_gmv: Mapped[float] = mapped_column(Float, default=0.0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)

    # 已回流人数（区分「没回来」与「回来了但没核销」）；reached = 券真的送达
    treated_observed: Mapped[int] = mapped_column(Integer, default=0)
    control_observed: Mapped[int] = mapped_column(Integer, default=0)
    treated_reached: Mapped[int] = mapped_column(Integer, default=0)
    control_reached: Mapped[int] = mapped_column(Integer, default=0)

    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EvaluationImport(Base):
    """结算导入批次：同一活动 + 同批次号只落一条，重试导入不新增、不重复应用。"""

    __tablename__ = "evaluation_imports"
    __table_args__ = (UniqueConstraint("campaign_id", "batch_no", name="ux_evaluation_imports_batch"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    batch_no: Mapped[str] = mapped_column(String(64))
    checksum: Mapped[str] = mapped_column(String(64))
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    rows_count: Mapped[int] = mapped_column(Integer, default=0)
    applied: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    operator_email: Mapped[str] = mapped_column(String(160), default="system")
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
