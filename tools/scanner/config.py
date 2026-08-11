"""集中配置——改阈值只改这里"""

# ── 品种配置 ──
VARIETIES: dict = {
    "au": {"futures": 870,  "name": "沪金",   "multiplier": 1000},
    "m":  {"futures": 2800, "name": "豆粕",   "multiplier": 10},
    "c":  {"futures": 2300, "name": "玉米",   "multiplier": 10},
    "cf": {"futures": 13500,"name": "棉花",   "multiplier": 5},
    "sr": {"futures": 5600, "name": "白糖",   "multiplier": 10},
    "ta": {"futures": 4800, "name": "PTA",    "multiplier": 5},
    "i":  {"futures": 780,  "name": "铁矿石", "multiplier": 100},
    "ru": {"futures": 17000,"name": "橡胶",   "multiplier": 10},
    "ma": {"futures": 2450, "name": "甲醇",   "multiplier": 10},
    "rm": {"futures": 2500, "name": "菜籽粕", "multiplier": 10},
}

# ── 卖方阈值 ──
MAX_PREMIUM = 5.0           # 虚值倒挂最高权利金
MAX_SPREAD_PCT = 10         # 卖方价差上限（%）
SELLER_CAPITAL_PCT = 0.05   # 卖方单笔最大亏损占本金比
DELTA_MAX = 0.30            # 卖方 Delta 上限（绝对值）
RR_MIN = 0.15               # 最低盈亏比
EXEC_RR_MIN = 0.25          # EXEC 显示门槛
STRIKE_WIDTH_MAX = 0.05     # 行权价宽度上限（占期货价比）
OTM_MIN_PCT = 2.0           # 卖方最低 OTM%

# ── 买方阈值 ──
BUYER_SPREAD_CAP = 0.05      # 买方价差单笔上限
BUYER_SINGLE_EVENT_CAP = 0.05  # 单腿·事件单笔上限
BUYER_SINGLE_TREND_CAP = 0.02  # 单腿·趋势单笔上限
BUYER_IV_THRESHOLD = 25      # 买方价差/跨式 IV 分位阈值（ScP≤25）
BUYER_SINGLE_IV_THRESHOLD = 30  # 单腿买方 IV 阈值（更宽松：本金小+无限上行的彩票逻辑）
BUYER_COLOR_ENABLED = False  # Data≥30 后改为 True
TREND_CHG_MIN = 2.0          # 趋势触发最低涨跌幅%
TREND_SPREAD_MAX = 15        # 趋势单腿价差上限
EVENT_SPREAD_MAX = 10        # 事件单腿价差上限

# ── 通用 ──
OTM_PCT = 0.08               # 虚值倒挂边界（8%）
MAX_STRIKE_GAP = 3           # 双循环最大跨档数
RISK_FREE_RATE = 0.03        # 无风险利率（BS 用）
BSM_DEFAULT_IV = 0.20        # IV 估算 fallback

# ── 组合风控 ──
MAX_SAME_DIRECTION = 2       # 同方向信号上限
MAX_PORTFOLIO_DELTA_ABS = 0.5  # 组合 Delta 绝对值上限

# ── 事件定价 shortcut ──
EVENT_PRICED_IV_PCT = 70     # IV 分位 >70% + 事件 ≤5d → 买方降级
EVENT_PRICED_DAYS = 5

# ── Tier 宽度/OTM 门槛 ──
TIER_GREEN_WIDTH = 3.0       # width% ≤ 3% 且 OTM ≥ 2% → green
TIER_YELLOW_WIDTH = 4.0
TIER_GREEN_OTM = 2.0

# ── IV-HV 分层 ──
IV_HV_HEAVY = 0.05           # ≥5% → 重仓
IV_HV_NORMAL = 0.03          # ≥3% → 正常
IV_HV_HALF = 0.01            # ≥1% → 减半
