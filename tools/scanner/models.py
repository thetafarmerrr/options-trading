"""核心数据模型 — 不可变语义，策略间传递只读。

注意：pd.DataFrame 内容是可变对象，frozen 只冻结引用。
约定：策略不得修改 OptionChain.puts / .calls 的内容。
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict
import pandas as pd


@dataclass
class Leg:
    """单条期权腿"""
    side: str              # "sell" | "buy"
    option_type: str        # "C" | "P"
    strike: float
    price: float            # bid（卖腿）或 ask（买腿）


@dataclass
class Signal:
    """统一信号结构——所有策略输出此格式"""
    strategy: str           # "credit_put" | "credit_call" | "otm_inversion" | ...
    variety: str            # vcode: "m", "c", "au", ...
    name: str               # 品种中文名
    contract: str           # "m2609"
    legs: List[Leg]
    max_profit: float       # 最大盈利（元/手）
    max_loss: float         # 最大亏损（元/手）
    rr_ratio: float         # 盈亏比
    greeks: Dict[str, float] = field(default_factory=dict)  # {"delta": 0.15, ...}
    tier: str = "PAPER"     # "EXEC" | "PAPER" | "OBSERVE"
    edge_score: float = 0.0  # 0-100 综合优势
    liquidity_score: float = 0.0  # 0-100
    metadata: Dict = field(default_factory=dict)  # 额外信息


@dataclass
class OptionChain:
    """单个品种的完整期权链——由 DataSource 产出，策略只读"""
    variety: str            # "m"
    name: str               # "豆粕"
    contract: str           # "m2609"
    futures_price: float
    multiplier: int
    expiry: date
    dte: int
    puts: pd.DataFrame      # 标准化列: strike, bid, ask, last, volume, oi
    calls: pd.DataFrame     # 同上
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """校验数据完整性"""
        for side, df in [("puts", self.puts), ("calls", self.calls)]:
            if df.empty:
                continue
            required = {"strike", "bid", "ask"}
            missing = required - set(df.columns)
            if missing:
                raise ValueError(f"{self.contract} {side} 缺列: {missing}")


@dataclass
class ScanContext:
    """策略扫描上下文——main.py 预计算，策略直接消费"""
    events: List[dict] = field(default_factory=list)
    iv_percentile: Optional[float] = None
    iv_percentile_days: int = 0
    change_5d: Optional[float] = None
    hv_20d: Optional[float] = None
    hv_60d: Optional[float] = None
    iv_est: Optional[float] = None
    weekly_scan_warnings: List[str] = field(default_factory=list)
    capital: float = 20000.0
    event_priced: bool = False  # IV>70%ile + 事件≤5d → 买方降级
