from __future__ import annotations

from pydantic import BaseModel, Field


class MemberOut(BaseModel):
    id: int
    member_no: str
    name: str
    phone: str
    city: str
    tier: str
    tier_label: str
    joined_on: str
    last_order_at: str | None
    r_days: int | None
    orders_window: int
    amount_window: float
    r_score: int | None
    f_score: int | None
    m_score: int | None
    composite_score: float | None
    segment_code: str | None
    segment_label: str | None
    purchase_rate: float
    avg_ticket: float
    phone_masked: bool


class OrderOut(BaseModel):
    id: int
    order_no: str
    member_no: str | None
    store_code: str
    channel: str
    channel_label: str
    amount: float
    items: int
    coupon_used: bool
    paid_at: str


class MemberQuery(BaseModel):
    q: str | None = Field(default=None, max_length=60)
    segment: str | None = Field(default=None, max_length=20)
    tier: str | None = Field(default=None, max_length=12)
    min_amount: float | None = Field(default=None, ge=0)
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
