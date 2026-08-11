"""策略基类 + 扫描上下文"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import math

from ..models import OptionChain, Signal, Leg, ScanContext
from ..config import MAX_SPREAD_PCT


class Strategy(ABC):
    """策略基类——所有扫描策略继承此基类"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    @abstractmethod
    def scan(self, chain: OptionChain, context: ScanContext) -> List[Signal]:
        """扫描单个品种 → 信号列表"""
        ...

    def scan_multi(self, chains: Dict[str, Optional[OptionChain]],
                   contexts: Dict[str, ScanContext]) -> Dict[str, List[Signal]]:
        """扫描多品种 → {vcode: [Signal, ...]}"""
        results = {}
        for vcode, chain in chains.items():
            if chain is None:
                results[vcode] = []
                continue
            ctx = contexts.get(vcode)
            if ctx is None:
                results[vcode] = []
                continue
            results[vcode] = self.scan(chain, ctx)
        return results

    @staticmethod
    def _liquidity_score(bid: float, ask: float, oi: int = 0) -> float:
        """统一流动性评分（0-100）。

        bid≤0 → 0 分；spread>20% → 0 分。
        """
        if bid <= 0 or ask <= 0 or ask < bid:
            return 0.0
        spread_pct = (ask - bid) / bid * 100
        if spread_pct > 20:
            return 0.0
        # 线性衰减：spread 0% → 100，spread 20% → 0
        score = max(0.0, 100.0 - spread_pct * 5.0)
        # OI 加分：>100 手 +10
        if oi > 100:
            score = min(100.0, score + 10.0)
        return round(score, 1)

    @staticmethod
    def _combine_greeks(sell_greeks: Dict[str, float],
                        buy_greeks: Dict[str, float]) -> Dict[str, float]:
        """组合 Greeks：卖腿 ×(-1) + 买腿 ×(+1)"""
        combined = {}
        all_keys = set(sell_greeks.keys()) | set(buy_greeks.keys())
        for k in all_keys:
            # 卖腿：short → greek 取反；买腿：long → greek 不变
            combined[k] = round(
                buy_greeks.get(k, 0.0) - sell_greeks.get(k, 0.0), 4)
        return combined

    @staticmethod
    def _make_signal(strategy: str, variety: str, name: str, contract: str,
                     legs: List[Leg], max_profit: float, max_loss: float,
                     rr_ratio: float, greeks: Dict = None,
                     tier: str = "PAPER", edge_score: float = 0.0,
                     liquidity_score: float = 0.0, **metadata) -> Signal:
        """统一信号工厂"""
        return Signal(
            strategy=strategy,
            variety=variety,
            name=name,
            contract=contract,
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            rr_ratio=rr_ratio,
            greeks=greeks or {},
            tier=tier,
            edge_score=edge_score,
            liquidity_score=liquidity_score,
            metadata=metadata,
        )
