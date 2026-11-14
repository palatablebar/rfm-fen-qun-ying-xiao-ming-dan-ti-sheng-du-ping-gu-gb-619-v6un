"""会员主档：RFM 评分与分群结果的载体。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        Index("ix_members_segment_tier", "segment_code", "tier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_no: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(40))
    phone: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(24), default="上海")
    tier: Mapped[str] = mapped_column(String(12), default="normal", index=True)
    joined_on: Mapped[date] = mapped_column(Date)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    orders_window: Mapped[int] = mapped_column(Integer, default=0)
    amount_window: Mapped[float] = mapped_column(Float, default=0.0)
    # 历史券响应率（近 3 次同类活动的人均核销口径），提升度算法 B 的购买率来源
    purchase_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_ticket: Mapped[float] = mapped_column(Float, default=0.0)

    # ---- 算法 A 写回 ----
    r_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    r_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    f_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    m_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    segment_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
