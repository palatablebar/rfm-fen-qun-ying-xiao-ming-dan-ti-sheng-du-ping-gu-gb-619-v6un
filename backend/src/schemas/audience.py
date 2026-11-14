from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AudienceIn(BaseModel):
    """生成名单：活动 + 预算（预算不传则用活动预算）。"""

    campaign_id: int = Field(gt=0)
    budget: float | None = Field(default=None, gt=0, le=5_000_000)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check_budget(self):
        if self.budget is not None and self.budget < 1:
            raise ValueError("预算至少 1 元")
        return self


class AudienceReviewIn(BaseModel):
    status: Literal["confirmed", "pushed"]
    note: str | None = Field(default=None, max_length=1000)


class AllocationQuery(BaseModel):
    budget: float | None = Field(default=None, gt=0, le=5_000_000)
