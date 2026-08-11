"""卖方信用价差策略 — S1 核心。

修正：
- Delta: BSM 标准公式，区分 Call/Put
- 组合 Greeks: delta/gamma/theta/vega
- Tier: green=width≤3% 且 OTM≥2%（且逻辑，修旧方案 green 不可达）
- Edge score: RR×0.4 + OTM×0.3 + liquidity×0.3（权重和=1.0）
"""

import math
from typing import List, Dict, Optional

from ..models import OptionChain, Signal, Leg, ScanContext
from ..config import (
    MAX_SPREAD_PCT, SELLER_CAPITAL_PCT, DELTA_MAX, RR_MIN,
    STRIKE_WIDTH_MAX, OTM_MIN_PCT, MAX_STRIKE_GAP,
    TIER_GREEN_WIDTH, TIER_YELLOW_WIDTH, TIER_GREEN_OTM,
    RISK_FREE_RATE, BSM_DEFAULT_IV,
)
from ..bsm import delta as bsm_delta, gamma as bsm_gamma
from ..bsm import theta as bsm_theta, vega as bsm_vega
from ..bsm import estimate_atm_iv
from .base import Strategy


def _spread(bid: float, ask: float) -> float:
    """价差百分比"""
    if bid > 0 and ask > 0:
        return round((ask - bid) / bid * 100, 1)
    return 999.0


class CreditSpreadStrategy(Strategy):
    """卖方信用价差扫描"""

    def scan(self, chain: OptionChain, context: ScanContext) -> List[Signal]:
        results = []
        r = RISK_FREE_RATE
        T = max(chain.dte / 365.0, 1.0 / 365.0)

        # ── ATM IV 估算（作 Delta 计算的 IV 输入）──
        atm_iv = self._est_atm_iv(chain)

        for direction in ["put", "call"]:
            df = chain.puts if direction == "put" else chain.calls
            if df.empty:
                continue

            bid_col = "bid"
            ask_col = "ask"

            options = df[df[bid_col] > 0].copy()
            if options.empty:
                continue

            options = options.sort_values("strike")

            for i in range(len(options)):
                for j in range(i + 1, min(i + 1 + MAX_STRIKE_GAP, len(options))):
                    low_row = options.iloc[i]
                    high_row = options.iloc[j]

                    if direction == "put":
                        # 卖高行权价 Put + 买低行权价 Put
                        sell_row, buy_row = high_row, low_row
                        sell_strike = float(high_row["strike"])
                        buy_strike = float(low_row["strike"])
                        if sell_strike >= chain.futures_price or buy_strike >= chain.futures_price:
                            continue
                        otm_pct = (chain.futures_price - sell_strike) / chain.futures_price * 100
                        option_type = "P"
                    else:
                        # 卖低行权价 Call + 买高行权价 Call
                        sell_row, buy_row = low_row, high_row
                        sell_strike = float(low_row["strike"])
                        buy_strike = float(high_row["strike"])
                        if sell_strike <= chain.futures_price or buy_strike <= chain.futures_price:
                            continue
                        otm_pct = (sell_strike - chain.futures_price) / chain.futures_price * 100
                        option_type = "C"

                    strike_width = abs(buy_strike - sell_strike)
                    if strike_width > chain.futures_price * STRIKE_WIDTH_MAX:
                        continue

                    sell_bid = float(sell_row[bid_col])
                    buy_ask = float(buy_row[ask_col])
                    if sell_bid <= 0 or buy_ask <= 0 or sell_bid <= buy_ask:
                        continue

                    net_premium = round(sell_bid - buy_ask, 2)
                    max_profit = net_premium * chain.multiplier
                    max_loss = round((strike_width * chain.multiplier) - max_profit, 0)

                    if context.capital > 0 and max_loss > context.capital * SELLER_CAPITAL_PCT:
                        continue
                    if max_loss <= 0:
                        continue

                    rr_ratio = round(max_profit / max_loss, 2)
                    if rr_ratio < RR_MIN:
                        continue

                    # ── 流动性 ──
                    sell_spread = _spread(sell_row[bid_col], sell_row[ask_col])
                    buy_spread = _spread(buy_row[bid_col], buy_row[ask_col])
                    if sell_spread > MAX_SPREAD_PCT or buy_spread > MAX_SPREAD_PCT:
                        continue

                    sell_liq = self._liquidity_score(
                        sell_row[bid_col], sell_row[ask_col], int(sell_row.get("oi", 0)))
                    buy_liq = self._liquidity_score(
                        buy_row[bid_col], buy_row[ask_col], int(buy_row.get("oi", 0)))
                    liq = min(sell_liq, buy_liq)

                    # ── 正确 Delta（区分 C/P）──
                    iv_for_delta = atm_iv if atm_iv else BSM_DEFAULT_IV
                    sell_delta = bsm_delta(
                        chain.futures_price, sell_strike, T, r, iv_for_delta, option_type)
                    sell_delta_abs = abs(sell_delta)

                    buy_delta = bsm_delta(
                        chain.futures_price, buy_strike, T, r, iv_for_delta, option_type)

                    # ── Tier 三档（且逻辑：width 且 OTM 都满足）──
                    width_pct = strike_width / chain.futures_price * 100
                    if width_pct <= TIER_GREEN_WIDTH and otm_pct >= TIER_GREEN_OTM:
                        tier = "green"
                    elif width_pct <= TIER_YELLOW_WIDTH:
                        tier = "yellow"
                    else:
                        tier = "red"

                    # 近值降级
                    if otm_pct < OTM_MIN_PCT:
                        tier = "red"

                    # Delta 降级
                    if sell_delta_abs > DELTA_MAX:
                        if tier == "green":
                            tier = "yellow"
                        elif tier == "yellow":
                            tier = "red"

                    # D-1 事件降级已由 ScanContext.event_priced 统一处理

                    # ── 组合 Greeks ──
                    sell_greeks = {
                        "delta": sell_delta,
                        "gamma": bsm_gamma(chain.futures_price, sell_strike, T, r, iv_for_delta),
                        "theta": bsm_theta(chain.futures_price, sell_strike, T, r, iv_for_delta, option_type),
                        "vega": bsm_vega(chain.futures_price, sell_strike, T, r, iv_for_delta),
                    }
                    buy_greeks = {
                        "delta": buy_delta,
                        "gamma": bsm_gamma(chain.futures_price, buy_strike, T, r, iv_for_delta),
                        "theta": bsm_theta(chain.futures_price, buy_strike, T, r, iv_for_delta, option_type),
                        "vega": bsm_vega(chain.futures_price, buy_strike, T, r, iv_for_delta),
                    }
                    combined = self._combine_greeks(sell_greeks, buy_greeks)

                    # ── Edge score（权重和=1.0）──
                    rr_norm = min(rr_ratio / 0.5, 1.0)  # rr=0.5→1.0
                    otm_norm = min(otm_pct / 15.0, 1.0)  # OTM=15%→1.0
                    liq_norm = liq / 100.0
                    edge_score = round(rr_norm * 40 + otm_norm * 30 + liq_norm * 30, 1)

                    # ── 构造 Signal ──
                    sell_leg = Leg(side="sell", option_type=option_type,
                                   strike=sell_strike, price=sell_bid)
                    buy_leg = Leg(side="buy", option_type=option_type,
                                  strike=buy_strike, price=buy_ask)

                    strategy_name = f"credit_{direction}"

                    signal = self._make_signal(
                        strategy=strategy_name,
                        variety=chain.variety,
                        name=chain.name,
                        contract=chain.contract,
                        legs=[sell_leg, buy_leg],
                        max_profit=round(max_profit, 0),
                        max_loss=max_loss,
                        rr_ratio=rr_ratio,
                        greeks=combined,
                        tier="EXEC" if tier in ("green", "yellow") else "PAPER",
                        edge_score=edge_score,
                        liquidity_score=liq,
                        # 元数据（用于输出显示）
                        sell_strike=sell_strike,
                        buy_strike=buy_strike,
                        sell_bid=round(sell_bid, 2),
                        buy_ask=round(buy_ask, 2),
                        net_premium=net_premium,
                        direction=direction,
                        width_pct=round(width_pct, 1),
                        otm_pct=round(otm_pct, 1),
                        delta=sell_delta_abs,
                        tier_color=tier,
                        sell_spread=round(sell_spread, 1),
                        buy_spread=round(buy_spread, 1),
                    )
                    results.append(signal)

        # ── 排序（edge_score 降序）──
        results.sort(key=lambda s: (s.tier == "EXEC", s.edge_score), reverse=True)
        return results

    @staticmethod
    def _est_atm_iv(chain: OptionChain) -> Optional[float]:
        """用 ATM 跨式估算 IV"""
        try:
            # 找最接近 ATM 的行
            atm_idx = (chain.puts["strike"] - chain.futures_price).abs().idxmin()
            p_row = chain.puts.loc[atm_idx]
            strike_target = p_row["strike"]
            c_row = chain.calls.loc[(chain.calls["strike"] - strike_target).abs() < 0.01]
            if c_row.empty:
                return None

            return estimate_atm_iv(
                chain.futures_price,
                float(p_row.get("bid", 0)), float(p_row.get("ask", 0)),
                float(c_row.iloc[0].get("bid", 0)), float(c_row.iloc[0].get("ask", 0)),
                chain.dte,
            )
        except Exception:
            return None
