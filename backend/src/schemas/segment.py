from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RecomputeIn(BaseModel):
    """算法 A 的可调参数：权重 + 统计窗口。"""

    weight_r: float = Field(default=0.3, ge=0.0, le=1.0)
    weight_f: float = Field(default=0.3, ge=0.0, le=1.0)
    weight_m: float = Field(default=0.4, ge=0.0, le=1.0)
    window_days: int = Field(default=365, ge=30, le=730)

    @field_validator("weight_m")
    @classmethod
    def _sum_to_one(cls, value: float, info) -> float:
        data = info.data or {}
        total = data.get("weight_r", 0.0) + data.get("weight_f", 0.0) + value
        if abs(total - 1.0) > 0.001:
            raise ValueError("三项权重之和必须等于 1.0")
        return value


class SegmentPatch(BaseModel):
    coupon_face: float | None = Field(default=None, ge=0.0, le=200.0)
    core_share: float | None = Field(default=None, ge=0.1, le=1.0)
    enabled: bool | None = None


class SegmentOut(BaseModel):
    id: int
    code: str
    name: str
    rule_text: str
    member_count: int
    share: float
    purchase_rate: float
    lift: float
    coupon_face: float
    core_share: float
    enabled: bool


class CampaignIn(BaseModel):
    code: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=80)
    budget: float = Field(gt=0, le=5_000_000)
    channel: str = Field(default="小程序订阅消息", max_length=20)
    status: Literal["draft", "active", "closed"] = "draft"
    starts_on: str | None = Field(default=None, max_length=10)
    ends_on: str | None = Field(default=None, max_length=10)
    note: str | None = Field(default=None, max_length=1000)
