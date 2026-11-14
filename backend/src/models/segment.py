"""RFM 分群快照：分群规则、规模、购买率与提升度。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(40))
    rule_text: Mapped[str] = mapped_column(String(120), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    member_count: Mapped[int] = mapped_column(Integer, default=0)
    share: Mapped[float] = mapped_column(Float, default=0.0)
    avg_r_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_f_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_m_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_r_days: Mapped[float] = mapped_column(Float, default=0.0)
    avg_amount_window: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_ticket: Mapped[float] = mapped_column(Float, default=0.0)
    lift: Mapped[float] = mapped_column(Float, default=0.0)

    # 运营可调的券口径（算法 B 的成本侧）
    coupon_face: Mapped[float] = mapped_column(Float, default=6.0)
    core_share: Mapped[float] = mapped_column(Float, default=0.6)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    as_of: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 最近一次重算的快照参数（权重 / 窗口 / 分位阈值 / 大盘购买率），8 行写同一份
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
