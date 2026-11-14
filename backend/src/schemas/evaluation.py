from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from src.constants.limits import MAX_IMPORT_ROWS


class SettlementRowIn(BaseModel):
    """一条会员级结算记录：触达 + 券核销 + 订单回流（可以分批晚到）。

    每行视为该会员在 ``as_of`` 时点的一份快照：
    ``reached`` 表示券是否真的送达（送达失败的人会从处理组分母剔除），
    ``redeemed`` 表示是否用了券，``orders`` / ``gmv`` 是活动窗口内该会员的订单事实。
    """

    member_no: str = Field(min_length=1, max_length=24)
    reached: bool = True
    redeemed: bool = False
    orders: int | None = Field(default=None, ge=0, le=100)
    gmv: float | None = Field(default=None, ge=0, le=1_000_000)
    as_of: str | None = Field(default=None, max_length=10)

    @field_validator("as_of")
    @classmethod
    def _valid_date(cls, value: str | None) -> str | None:
        if value:
            try:
                date.fromisoformat(value[:10])
            except ValueError:
                raise ValueError("as_of 应为 YYYY-MM-DD") from None
        return value


class SettlementImportIn(BaseModel):
    campaign_id: int = Field(gt=0)
    batch_no: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    as_of: str | None = Field(default=None, max_length=10)
    rows: list[SettlementRowIn] = Field(default_factory=list)

    @field_validator("as_of")
    @classmethod
    def _valid_date(cls, value: str | None) -> str | None:
        if value:
            try:
                date.fromisoformat(value[:10])
            except ValueError:
                raise ValueError("as_of 应为 YYYY-MM-DD") from None
        return value

    @model_validator(mode="after")
    def _size(self):
        if len(self.rows) > MAX_IMPORT_ROWS:
            raise ValueError(f"单批次最多 {MAX_IMPORT_ROWS} 行")
        return self


class EvaluationPublishIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
