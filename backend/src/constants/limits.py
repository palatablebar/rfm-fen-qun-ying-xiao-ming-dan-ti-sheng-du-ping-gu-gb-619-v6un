"""限额与算法口径常量。"""

RATE_WINDOW_SECONDS = 60
MAX_PAGE_SIZE = 200
MAX_IMPORT_ROWS = 5000
MAX_EXPORT_ROWS = 20000

# ---- RFM 算法 A ----
RFM_BUCKETS = 5                      # 分位切 5 档
RFM_WINDOW_DAYS = 365                # F/M 统计窗口默认一年（180 天会让「重要挽留」在定义上落空）
DEFAULT_RFM_WEIGHTS = (0.3, 0.3, 0.4)
MIN_RFM_WEIGHTS = 0.0
MAX_RFM_WEIGHTS = 1.0
WEIGHT_SUM_TOLERANCE = 0.001
NO_ORDER_RECENCY_DAYS = 9999         # 从未下单会员的 R 值哨兵
SCORE_SPLIT = 3                      # 八类规则的高低分界线

# ---- 提升度与预算算法 B ----
DEFAULT_REACH_COST = 0.15            # 人均触达成本（短信 / 小程序订阅消息，元）
DEFAULT_ORDERS_PER_CONVERTER = 1.4   # 每个增量转化会员在活动窗口内的增量单量
DEFAULT_CORE_SHARE = 0.6             # 分群内「高响应核心盘」占比
DEFAULT_TAIL_FACTOR = 0.6            # 超出核心盘部分的边际折减系数
LIFT_ELIGIBLE_MIN = 1.0              # lift ≤ 1 不投放
