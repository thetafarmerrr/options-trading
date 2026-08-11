"""虚值倒挂扫描（Put 区套利）

修正：
- _ref_spread_ok 卖腿收紧（比买腿 MAX_SPREAD_PCT=10 更严）
- profit_pct 分母用期货价格（不用低价腿 → 不再夸大收益率）
"""

from typing import List, Dict

from ..models import OptionChain, Signal, Leg, ScanContext
from ..config import (
    MAX_PREMIUM, OTM_PCT, MAX_SPREAD_PCT, SELLER_CAPITAL_PCT, MAX_STRIKE_GAP,
)
from .base import Strategy


def _spread(bid: float, ask: float) -> float:
    if bid > 0 and ask > 0:
        return round((ask - bid) / bid * 100, 1)
    return 999.0


def _ref_spread_ok(price: float, bid: float, ask: float) -> bool:
    """参考腿（卖腿）流动性检查——比买腿更严。

    修正旧方案不对称问题：卖腿 ≤8%（< 买腿 MAX_SPREAD_PCT=10）。
    """
    if bid <= 0:
        return False
    sp = (ask - bid) / bid * 100
    if price < 10:
        return sp < 15
    elif price < 30:
        return sp < 10
    else:
        return sp < 8


class OTMInversionStrategy(Strategy):
    """虚值 Put 倒挂扫描"""

    def scan(self, chain: OptionChain, context: ScanContext) -> List[Signal]:
        results = []
        mult = chain.multiplier

        otm_boundary = int(chain.futures_price * (1 - OTM_PCT))
        otm_puts = chain.puts[chain.puts["strike"] < otm_boundary].copy()

        if otm_puts.empty:
            return results

        # 构建行列表
        rows = []
        for _, row in otm_puts.iterrows():
            p_last = float(row.get("last", 0))
            p_bid = float(row.get("bid", 0))
            p_ask = float(row.get("ask", 0))
            if p_last <= 0 or p_last > MAX_PREMIUM:
                continue
            if p_bid <= 0:
                continue
            rows.append({
                "strike": int(row["strike"]),
                "price": p_last,
                "bid": p_bid,
                "ask": p_ask,
                "oi": int(row.get("oi", 0)),
            })

        max_gap_value = chain.futures_price * 0.05  # 5% 期货价格

        for i in range(len(rows)):
            for j in range(i + 1, min(i + 1 + MAX_STRIKE_GAP, len(rows))):
                cur = rows[i]   # 低 strike（应为便宜）
                nxt = rows[j]   # 高 strike（应为贵）
                # cur=低strike应该便宜, nxt=高strike应该贵
                # 倒挂：cur price > nxt price（低strike反而更贵）

                # 跨度检查
                if nxt["strike"] - cur["strike"] > max_gap_value:
                    continue

                # 中间档阻断检查
                middle_blocks = False
                for k in range(i + 1, j):
                    mid = rows[k]
                    mid_sp = _spread(mid["bid"], mid["ask"])
                    if mid["bid"] > 0 and mid_sp <= 50:
                        middle_blocks = True
                        break
                if middle_blocks:
                    continue

                # 价格倒挂检查
                if cur["price"] <= nxt["price"]:
                    continue

                # 参考腿（高价=低 strike，卖腿）流动性 — 更严
                if not _ref_spread_ok(cur["price"], cur["bid"], cur["ask"]):
                    continue

                # 买入腿（低价=高 strike）流动性
                buy_sp = _spread(nxt["bid"], nxt["ask"])
                if buy_sp > MAX_SPREAD_PCT or nxt["bid"] <= 0:
                    continue

                # profit_pct 用期货价格做分母（修旧方案夸大问题）
                profit_pct = round(
                    (cur["price"] - nxt["price"]) / chain.futures_price * 100, 2)
                net = round(profit_pct - buy_sp, 1)
                cost = nxt["price"] * mult
                tradeable = buy_sp < profit_pct and buy_sp < MAX_SPREAD_PCT
                cross_leg = (j - i) > 1

                if context.capital > 0 and cost > context.capital * SELLER_CAPITAL_PCT:
                    continue

                liq = min(
                    self._liquidity_score(cur["bid"], cur["ask"], cur["oi"]),
                    self._liquidity_score(nxt["bid"], nxt["ask"], nxt["oi"]),
                )

                # 卖低 strike（cur, 贵），买高 strike（nxt, 便宜）
                sell_leg = Leg(side="sell", option_type="P",
                               strike=cur["strike"], price=cur["bid"])
                buy_leg = Leg(side="buy", option_type="P",
                              strike=nxt["strike"], price=nxt["ask"])

                results.append(self._make_signal(
                    strategy="otm_inversion",
                    variety=chain.variety,
                    name=chain.name,
                    contract=chain.contract,
                    legs=[sell_leg, buy_leg],
                    max_profit=round((cur["price"] - nxt["price"]) * mult, 0),
                    max_loss=round(cost, 0),
                    rr_ratio=round(profit_pct / max(buy_sp, 0.1), 2),
                    tier="EXEC" if tradeable else "PAPER",
                    liquidity_score=liq,
                    buy_strike=nxt["strike"],
                    buy_price=nxt["price"],
                    buy_bid=nxt["bid"],
                    buy_ask=nxt["ask"],
                    ref_strike=cur["strike"],
                    ref_price=cur["price"],
                    profit_pct=profit_pct,
                    spread_pct=buy_sp,
                    net_pct=net,
                    cost=cost,
                    tradeable=tradeable,
                    cross_leg=cross_leg,
                    skipped_strikes=j - i - 1,
                ))

        results.sort(key=lambda s: s.metadata.get("net_pct", 0), reverse=True)
        return results
