"""共享枚举（后端唯一定义处）。前端副本见 frontend/site/js/config.js。

README「共享枚举出现位置」一节列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class MemberTier(StrEnum):
    """会员卡等级。"""

    NORMAL = "normal"
    SILVER = "silver"
    GOLD = "gold"
    BLACK = "black"


MEMBER_TIER_LABELS: dict[str, str] = {
    MemberTier.NORMAL.value: "普通会员",
    MemberTier.SILVER.value: "银卡",
    MemberTier.GOLD.value: "金卡",
    MemberTier.BLACK.value: "黑金卡",
}

MEMBER_TIER_ORDER: list[str] = [
    MemberTier.NORMAL.value,
    MemberTier.SILVER.value,
    MemberTier.GOLD.value,
    MemberTier.BLACK.value,
]


class SegmentCode(StrEnum):
    """RFM 八类规则分群（顺序即展示顺序与规则命中顺序）。"""

    CHAMPION = "champion"
    LOYAL = "loyal"
    POTENTIAL = "potential"
    AT_RISK = "at_risk"
    NEW = "new"
    CHURN_WARN = "churn_warn"
    ORDINARY = "ordinary"
    HIBERNATING = "hibernating"


SEGMENT_LABELS: dict[str, str] = {
    SegmentCode.CHAMPION.value: "重要价值",
    SegmentCode.LOYAL.value: "重要保持",
    SegmentCode.POTENTIAL.value: "重要发展",
    SegmentCode.AT_RISK.value: "重要挽留",
    SegmentCode.NEW.value: "新客养成",
    SegmentCode.CHURN_WARN.value: "流失预警",
    SegmentCode.ORDINARY.value: "一般价值",
    SegmentCode.HIBERNATING.value: "沉睡会员",
}

SEGMENT_RULES: dict[str, str] = {
    SegmentCode.CHAMPION.value: "R≥4 且 F≥4 且 M≥4",
    SegmentCode.LOYAL.value: "R≥3 且 F≥4 且 M≥3",
    SegmentCode.POTENTIAL.value: "R≥4 且 F≥3 且 M≥4",
    SegmentCode.AT_RISK.value: "R≤2 且 F≥4 且 M≥4",
    SegmentCode.NEW.value: "R≥4 且 F≤2（近期首购、单量少）",
    SegmentCode.CHURN_WARN.value: "R≤2 且 F≥2 且 M≥2",
    SegmentCode.ORDINARY.value: "R≥3 且 M≤3（常来但客单低）",
    SegmentCode.HIBERNATING.value: "其余（低 R / 低 F / 低 M）",
}

SEGMENT_ORDER: list[str] = [code.value for code in SegmentCode]


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


CAMPAIGN_STATUS_LABELS: dict[str, str] = {
    CampaignStatus.DRAFT.value: "草稿",
    CampaignStatus.ACTIVE.value: "进行中",
    CampaignStatus.CLOSED.value: "已结束",
}


class AudienceStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PUSHED = "pushed"


AUDIENCE_STATUS_LABELS: dict[str, str] = {
    AudienceStatus.PENDING.value: "待确认",
    AudienceStatus.CONFIRMED.value: "已确认",
    AudienceStatus.PUSHED.value: "已推送券平台",
}

AUDIENCE_STATUS_ORDER: list[str] = [
    AudienceStatus.PENDING.value,
    AudienceStatus.CONFIRMED.value,
    AudienceStatus.PUSHED.value,
]


class OrderChannel(StrEnum):
    MINIAPP = "miniapp"
    STORE = "store"
    DELIVERY = "delivery"


ORDER_CHANNEL_LABELS: dict[str, str] = {
    OrderChannel.MINIAPP.value: "小程序自提",
    OrderChannel.STORE.value: "门店收银",
    OrderChannel.DELIVERY.value: "外卖平台",
}


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    SEED = "seed"


TRIGGER_LABELS: dict[str, str] = {
    TriggerKind.MANUAL.value: "手动重算",
    TriggerKind.SCHEDULE.value: "每日定时",
    TriggerKind.SEED.value: "初始化",
}
