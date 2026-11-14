"""营销活动：预算与券口径的载体。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    channel: Mapped[str] = mapped_column(String(20), default="小程序订阅消息")
    budget: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    reach_cost: Mapped[float] = mapped_column(Float, default=0.15)
    orders_per_converter: Mapped[float] = mapped_column(Float, default=1.4)
    tail_factor: Mapped[float] = mapped_column(Float, default=0.6)
    target_segments: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_email: Mapped[str] = mapped_column(String(160), default="system")
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
