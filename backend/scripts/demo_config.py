"""牧野茶饮 · RFM 演示数据规格（seed 的唯一数据来源，确定性可重放）。

规模：8,000 会员 / 30,000 订单（32 万会员的 1/40 抽样）；8 个 RFM 分群；2 个活动；2 份名单。
所有随机数来自固定种子 random.Random(61926)，两次 seed 生成的数据逐字节一致。
"""
from __future__ import annotations

from datetime import date

DEMO_PASSWORD = "Demo@2026"

DEMO_USERS = [
    ("admin@rfmseg.io", "林可 · 会员运营管理员", "admin"),
    ("analyst@rfmseg.io", "周棠 · 会员数据专员", "analyst"),
    ("viewer@rfmseg.io", "陈默 · 门店业务只读", "viewer"),
]

ORG = "牧野茶饮 · 会员运营组"

# 数据快照基准日（演示数据的时间锚点，避免 seed 依赖系统时钟）
SEED_ANCHOR = date(2026, 11, 14)
MEMBER_TARGET = 8000
ORDER_TARGET = 30000
RANDOM_SEED = 61926

CITIES = ["上海", "杭州", "苏州", "南京", "宁波"]
STORES = ["MY-S01", "MY-S02", "MY-S03", "MY-S04", "MY-S05", "MY-S06", "MY-S07", "MY-S08"]
CHANNELS = [("miniapp", 0.46), ("store", 0.34), ("delivery", 0.20)]

SURNAMES = [
    "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
    "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧",
]
GIVEN = [
    "若溪", "亦航", "子墨", "书言", "嘉禾", "沐宸", "云舒", "知微", "清越", "南乔",
    "少卿", "念念", "青禾", "予安", "星野", "闻笛", "拾光", "慕白", "昭昭", "语初",
    "白露", "疏影", "行舟", "稚川", "望舒", "澜清", "宜安", "见山", "一诺", "嘉言",
]

# 会员画像：权重 / 订单量 / 最近下单区间（天）/ 客单价 / 历史券响应率 / 卡等级
ARCHETYPES: list[dict] = [
    {"key": "champion", "weight": 0.06, "orders": 11.0, "recent": (0, 150), "ticket": 34.0, "rate": 0.062, "tier": "black"},
    {"key": "loyal", "weight": 0.10, "orders": 8.0, "recent": (10, 190), "ticket": 29.0, "rate": 0.050, "tier": "gold"},
    {"key": "potential", "weight": 0.10, "orders": 5.0, "recent": (5, 220), "ticket": 26.0, "rate": 0.041, "tier": "gold"},
    {"key": "new", "weight": 0.12, "orders": 1.4, "recent": (0, 45), "ticket": 24.0, "rate": 0.034, "tier": "silver"},
    {"key": "at_risk", "weight": 0.08, "orders": 6.5, "recent": (150, 320), "ticket": 31.0, "rate": 0.032, "tier": "gold"},
    {"key": "churn_warn", "weight": 0.14, "orders": 3.5, "recent": (190, 390), "ticket": 25.0, "rate": 0.022, "tier": "silver"},
    {"key": "ordinary", "weight": 0.22, "orders": 2.6, "recent": (50, 300), "ticket": 22.0, "rate": 0.017, "tier": "normal"},
    {"key": "hibernating", "weight": 0.18, "orders": 0.8, "recent": (300, 460), "ticket": 20.0, "rate": 0.010, "tier": "normal"},
]

# 各分群的券口径（算法 B 的成本侧；管理员可在「RFM 分群」页调整）
SEGMENT_COUPON: dict[str, dict] = {
    "champion": {"coupon_face": 8.0, "core_share": 0.6},
    "loyal": {"coupon_face": 8.0, "core_share": 0.6},
    "potential": {"coupon_face": 7.0, "core_share": 0.6},
    "at_risk": {"coupon_face": 10.0, "core_share": 0.6},
    "new": {"coupon_face": 12.0, "core_share": 0.7},
    "churn_warn": {"coupon_face": 6.0, "core_share": 0.6},
    "ordinary": {"coupon_face": 5.0, "core_share": 0.6},
    "hibernating": {"coupon_face": 4.0, "core_share": 0.6},
}

# 2 个活动（预算按 1/40 抽样折算，真实全量约 40 万/季度）
CAMPAIGNS: list[dict] = [
    {
        "seed_key": "seed-campaign-autumn",
        "code": "autumn-member-day",
        "name": "秋日会员日券",
        "channel": "小程序订阅消息",
        "budget": 1400.0,
        "status": "active",
        "starts_on": "2026-11-18",
        "ends_on": "2026-11-24",
        "note": "季度预算有限，先发高提升度分群；预算内无法覆盖的分群进入待定池。",
    },
    {
        "seed_key": "seed-campaign-double11",
        "code": "double11-warmup",
        "name": "双十一预热券",
        "channel": "门店企微群 + 小程序",
        "budget": 2600.0,
        "status": "active",
        "starts_on": "2026-11-08",
        "ends_on": "2026-11-13",
        "note": "覆盖全部可投分群，用于对照「够预算」与「不够预算」两种分配的差异。",
    },
]

SEED_AUDIENCES = [
    ("seed-audience-autumn", "autumn-member-day", "init 抽样名单：预算受限，按 lift/成本 贪心选群"),
    ("seed-audience-double11", "double11-warmup", "init 抽样名单：预算充足，覆盖全部可投分群"),
]
