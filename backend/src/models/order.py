"""订单流水：会员 R/F/M 的原始事实来源。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    store_code: Mapped[str] = mapped_column(String(16), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="store")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    items: Mapped[int] = mapped_column(Integer, default=1)
    coupon_used: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
