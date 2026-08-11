"""买方策略三合一：Debit Spread + Straddle/Strangle + 单腿买方

保留业务逻辑：
- 两关一判（标的在动 + IV 便宜 + RR≥5:1）
- Tier 3 过滤（仅有例行低冲击事件 → 不产生买方信号）
- 趋势方向过滤（涨不做 put debit，跌不做 call debit）
- 事件-到期校验 + D-1 高影响事件跳过
- 单腿：事件触发（≤5%本金）vs 趋势触发（≤2%本金）分层

新增：
- DTE 分组 IV 分位（volatility.iv_percentile）
- expected_move_pct（百分比，非权利金元）
- 事件定价 shortcut：IV>70%分位 + 事件≤5d → 买方降级 PAPER
"""

import math
import re
from datetime import datetime, date
from typing import List, Optional, Dict

from ..models import OptionChain, Signal, Leg, ScanContext
from ..config import (
    BUYER_IV_THRESHOLD, BUYER_SINGLE_IV_THRESHOLD,
    BUYER_SPREAD_CAP, BUYER_SINGLE_EVENT_CAP,
    BUYER_SINGLE_TREND_CAP, BUYER_COLOR_ENABLED, MAX_SPREAD_PCT,
    TREND_CHG_MIN, TREND_SPREAD_MAX, EVENT_SPREAD_MAX,
    MAX_STRIKE_GAP, EVENT_PRICED_IV_PCT, EVENT_PRICED_DAYS,
)
from ..volatility import expected_move_pct as _em_pct, expected_move_price as _em_price
from .base import Strategy
from ..events import EventEngine


def _spread(bid: float, ask: float) -> float:
    if bid > 0 and ask > 0:
        return round((ask - bid) / bid * 100, 1)
    return 999.0


class BuyerStrategy(Strategy):
    """买方机会统一扫描：debit spread + straddle/strangle + 单腿"""

    def __init__(self, event_engine: EventEngine = None, iv_history_rows: List[dict] = None):
        super().__init__()
        self._events = event_engine
        self._iv_rows = iv_history_rows or []

    def scan(self, chain: OptionChain, context: ScanContext) -> List[Signal]:
        results = []

        # 1. Debit Call Spread
        results.extend(self._scan_debit(chain, context, "call"))
        # 2. Debit Put Spread
        results.extend(self._scan_debit(chain, context, "put"))
        # 3. Straddle + Strangle
        results.extend(self._scan_straddles(chain, context))
        # 4. 单腿买方
        results.extend(self._scan_single_leg(chain, context))

        return results

    # ── Debit Spread ──

    def _scan_debit(self, chain: OptionChain, context: ScanContext,
                    direction: str) -> List[Signal]:
        """单侧 debit spread 扫描（两关一判）

        第一关：标的在动吗？5日涨跌≥1.5% 或 D-7 Tier1事件
        第二关：IV便宜吗？ScP≤25
        判据：盈亏比 RR≥5:1
        """
        results = []
        # 列名已在 data_source 标准化为 bid/ask（无前缀）
        bid_col = "bid"
        ask_col = "ask"

        # 用 puts/calls DataFrame（已标准化列名 bid/ask）
        df = chain.calls if direction == "call" else chain.puts
        if df.empty:
            return results

        options = df[(df["bid"] > 0) & (df["ask"] > 0)].copy()
        if options.empty:
            return results

        options = options.sort_values("strike")

        # ── 第一关：标的在动吗？──
        has_tier1 = (self._events and
                     self._events.has_tier1(chain.variety, chain.name))
        has_trend = (context.change_5d is not None
                     and abs(context.change_5d) >= 1.5)
        if not has_trend and not has_tier1:
            return results

        # 趋势方向过滤
        if context.change_5d is not None:
            if direction == "call" and context.change_5d < 0:
                return results
            if direction == "put" and context.change_5d > 0:
                return results

        # D-1 高影响事件 → 不进场
        has_d1 = (self._events and
                  self._events.has_d1_high(chain.variety, chain.name))

        # 事件-到期校验
        event_too_late = False
        if self._events:
            nearest = self._events.nearest_event_days(chain.variety, chain.name)
            if nearest is not None:
                event_too_late = nearest > chain.dte - 1

        # 事件定价 shortcut：IV 已膨胀 → 买方降级
        event_priced = context.event_priced

        for i in range(len(options)):
            for j in range(i + 1, min(i + 1 + MAX_STRIKE_GAP, len(options))):
                low_row = options.iloc[i]
                high_row = options.iloc[j]
                low_strike = float(low_row["strike"])
                high_strike = float(high_row["strike"])

                if direction == "call":
                    # 牛市看涨价差：买低 Call + 卖高 Call
                    if low_strike < chain.futures_price * 0.98:
                        continue
                    buy_ask = float(low_row["ask"])
                    sell_bid = float(high_row["bid"])
                    otm_pct = (low_strike - chain.futures_price) / chain.futures_price * 100
                    buy_strike, sell_strike = low_strike, high_strike
                    buy_sp = _spread(low_row["bid"], low_row["ask"])
                    sell_sp = _spread(high_row["bid"], high_row["ask"])
                    buy_leg_strike, sell_leg_strike = low_strike, high_strike
                else:
                    # 熊市看跌价差：买高 Put + 卖低 Put
                    if high_strike > chain.futures_price * 1.02:
                        continue
                    buy_ask = float(high_row["ask"])
                    sell_bid = float(low_row["bid"])
                    otm_pct = (chain.futures_price - high_strike) / chain.futures_price * 100
                    buy_strike, sell_strike = high_strike, low_strike
                    buy_sp = _spread(high_row["bid"], high_row["ask"])
                    sell_sp = _spread(low_row["bid"], low_row["ask"])
                    buy_leg_strike, sell_leg_strike = high_strike, low_strike

                if buy_ask <= 0 or sell_bid <= 0:
                    continue

                net_debit = round(buy_ask - sell_bid, 2)
                if net_debit <= 0:
                    continue

                strike_width = high_strike - low_strike
                max_profit = round(strike_width * chain.multiplier - net_debit * chain.multiplier, 0)
                max_loss = round(net_debit * chain.multiplier, 0)

                if max_loss <= 0 or max_profit <= 0:
                    continue

                profit_ratio = round(max_profit / max_loss, 2)

                # ── 信号条件 ──
                if otm_pct >= 5:
                    continue
                if profit_ratio < 5.0:
                    continue
                if has_d1:
                    continue
                if event_too_late:
                    continue
                if (context.iv_percentile is not None
                        and context.iv_percentile > BUYER_IV_THRESHOLD):
                    continue

                # 价差检查
                if buy_sp > MAX_SPREAD_PCT or sell_sp > MAX_SPREAD_PCT:
                    continue

                # 资金检查
                if context.capital > 0 and max_loss > context.capital * BUYER_SPREAD_CAP:
                    continue

                # 颜色编码
                if (BUYER_COLOR_ENABLED
                        and context.iv_percentile is not None
                        and context.iv_percentile < BUYER_IV_THRESHOLD
                        and has_tier1):
                    color = "green"
                else:
                    color = "yellow"

                # 事件定价降级
                if event_priced and color == "green":
                    color = "yellow"

                # 盈亏平衡点
                if direction == "call":
                    break_even = round(low_strike + net_debit, 2)
                else:
                    break_even = round(high_strike - net_debit, 2)

                strategy_label = "bull_call_spread" if direction == "call" else "bear_put_spread"

                liq = min(
                    self._liquidity_score(low_row["bid"], low_row["ask"],
                                          int(low_row.get("oi", 0))),
                    self._liquidity_score(high_row["bid"], high_row["ask"],
                                          int(high_row.get("oi", 0))),
                )

                buy_leg = Leg(side="buy", option_type="C" if direction == "call" else "P",
                              strike=buy_leg_strike, price=buy_ask)
                sell_leg = Leg(side="sell", option_type="C" if direction == "call" else "P",
                               strike=sell_leg_strike, price=sell_bid)

                results.append(self._make_signal(
                    strategy=strategy_label,
                    variety=chain.variety,
                    name=chain.name,
                    contract=chain.contract,
                    legs=[buy_leg, sell_leg],
                    max_profit=max_profit,
                    max_loss=max_loss,
                    rr_ratio=profit_ratio,
                    tier="PAPER",
                    liquidity_score=liq,
                    buy_strike=buy_strike,
                    sell_strike=sell_strike,
                    buy_ask=round(buy_ask, 2),
                    sell_bid=round(sell_bid, 2),
                    net_debit=net_debit,
                    otm_pct=round(otm_pct, 1),
                    break_even=break_even,
                    iv_percentile=context.iv_percentile,
                    event_days=(self._events.nearest_event_days(chain.variety, chain.name)
                                if self._events else None),
                    color=color,
                ))

        return results

    # ── Straddle / Strangle ──

    def _scan_straddles(self, chain: OptionChain,
                        context: ScanContext) -> List[Signal]:
        """扫描买入跨式 + 宽跨式"""
        results = []

        # ── Straddle ──
        try:
            atm_idx = (chain.calls["strike"] - chain.futures_price).abs().idxmin()
            c_row = chain.calls.loc[atm_idx]
            atm_strike = float(c_row["strike"])

            # 匹配 Put 同 strike
            p_rows = chain.puts[chain.puts["strike"] == atm_strike]

            # 预计算 Straddle/Strangle 共用条件
            has_event = self._events is not None
            iv_cheap = (context.iv_percentile is not None
                        and context.iv_percentile < BUYER_IV_THRESHOLD)
            event_too_late = (self._events and
                              self._events.event_too_late(chain.variety, chain.name, chain.dte))

            # ── Straddle（需要 ATM Call+Put 同 strike）──
            if not p_rows.empty:
                p_row = p_rows.iloc[0]

                call_ask = float(c_row.get("ask", 0))
                put_ask = float(p_row.get("ask", 0))
                call_bid = float(c_row.get("bid", 0))
                put_bid = float(p_row.get("bid", 0))

                if call_ask > 0 and put_ask > 0:
                    atm_call_spread = _spread(call_bid, call_ask)
                    atm_put_spread = _spread(put_bid, put_ask)
                    net_cost = round(call_ask + put_ask, 2)

                    # 预期波动（百分比）——修正旧方案 net_cost 元错误
                    iv_for_em = context.iv_est if context.iv_est else 0.20
                    em_pct = _em_pct(chain.futures_price, iv_for_em, chain.dte)
                    em_price = _em_price(chain.futures_price, iv_for_em, chain.dte)

                    # Straddle 条件
                    has_d2_d7 = (
                        has_event and
                        any(e["impact"] == "high"
                            and (e.get("days_until", 0) == -1 or 2 <= e.get("days_until", 0) <= 7)
                            for e in self._events.for_variety(chain.variety, chain.name))
                    )
                    atm_ok = atm_call_spread < 10 and atm_put_spread < 10

                    if iv_cheap and has_d2_d7 and atm_ok and not event_too_late:
                        cost_total = net_cost * chain.multiplier
                        if context.capital > 0 and cost_total > context.capital * BUYER_SPREAD_CAP:
                            pass
                        else:
                            straddle_color = "green" if (
                                BUYER_COLOR_ENABLED and iv_cheap and has_d2_d7) else "yellow"
                            if context.event_priced and straddle_color == "green":
                                straddle_color = "yellow"

                            nearest_title = ""
                            nearest_days = None
                            if self._events:
                                evs = self._events.for_variety(chain.variety, chain.name)
                                if evs:
                                    nearest = min(evs, key=lambda e: e.get("days_until", 999))
                                    nearest_title = nearest.get("title", "")
                                    nearest_days = nearest.get("days_until")

                            call_leg = Leg(side="buy", option_type="C",
                                           strike=atm_strike, price=call_ask)
                            put_leg = Leg(side="buy", option_type="P",
                                          strike=atm_strike, price=put_ask)

                            results.append(self._make_signal(
                                strategy="long_straddle",
                                variety=chain.variety,
                                name=chain.name,
                                contract=chain.contract,
                                legs=[call_leg, put_leg],
                                max_profit=-1,  # 理论上无限
                                max_loss=round(cost_total, 0),
                                rr_ratio=-1,
                                tier="PAPER",
                                strike=atm_strike,
                                call_ask=round(call_ask, 2),
                                put_ask=round(put_ask, 2),
                                net_cost=net_cost,
                                expected_move_pct=em_pct,
                                expected_move_price=em_price,
                                dte=chain.dte,
                                iv_percentile=context.iv_percentile,
                                event_title=nearest_title,
                                event_days=nearest_days,
                                color=straddle_color,
                            ))

            # ── Strangle ──
            otm_target_pct = 0.005
            otm_call_target = chain.futures_price * (1 + otm_target_pct)
            otm_put_target = chain.futures_price * (1 - otm_target_pct)

            # 找 OTM Call
            call_candidates = chain.calls[
                (chain.calls["strike"] > chain.futures_price) &
                (chain.calls["ask"] > 0)
            ].copy()
            call_strike = None
            c_ask_otm = 0.0
            call_spread = 999.0
            if not call_candidates.empty:
                call_candidates["dist"] = (call_candidates["strike"] - otm_call_target).abs()
                best_call = call_candidates.loc[call_candidates["dist"].idxmin()]
                call_strike = float(best_call["strike"])
                c_ask_otm = float(best_call["ask"])
                call_spread = _spread(float(best_call.get("bid", 0)), c_ask_otm)

            # 找 OTM Put
            put_candidates = chain.puts[
                (chain.puts["strike"] < chain.futures_price) &
                (chain.puts["ask"] > 0)
            ].copy()
            put_strike = None
            p_ask_otm = 0.0
            put_spread = 999.0
            if not put_candidates.empty:
                put_candidates["dist"] = (put_candidates["strike"] - otm_put_target).abs()
                best_put = put_candidates.loc[put_candidates["dist"].idxmin()]
                put_strike = float(best_put["strike"])
                p_ask_otm = float(best_put["ask"])
                put_spread = _spread(float(best_put.get("bid", 0)), p_ask_otm)

            has_any_event = (self._events and
                             len(self._events.for_variety(chain.variety, chain.name)) > 0)
            strangle_ok = call_spread < 15 and put_spread < 15
            legs_valid = (call_strike is not None and put_strike is not None
                          and c_ask_otm > 0 and p_ask_otm > 0)

            if iv_cheap and has_any_event and strangle_ok and legs_valid and not event_too_late:
                strangle_cost = round(c_ask_otm + p_ask_otm, 2)
                cost_total = strangle_cost * chain.multiplier
                if context.capital > 0 and cost_total > context.capital * BUYER_SPREAD_CAP:
                    pass
                else:
                    sc = "green" if (BUYER_COLOR_ENABLED and iv_cheap) else "yellow"
                    if context.event_priced and sc == "green":
                        sc = "yellow"

                    nearest_title = ""
                    nearest_days = None
                    if self._events:
                        evs = self._events.for_variety(chain.variety, chain.name)
                        if evs:
                            nearest = min(evs, key=lambda e: e.get("days_until", 999))
                            nearest_title = nearest.get("title", "")
                            nearest_days = nearest.get("days_until")

                    call_leg = Leg(side="buy", option_type="C",
                                   strike=call_strike, price=c_ask_otm)
                    put_leg = Leg(side="buy", option_type="P",
                                  strike=put_strike, price=p_ask_otm)

                    results.append(self._make_signal(
                        strategy="long_strangle",
                        variety=chain.variety,
                        name=chain.name,
                        contract=chain.contract,
                        legs=[call_leg, put_leg],
                        max_profit=-1,
                        max_loss=round(cost_total, 0),
                        rr_ratio=-1,
                        tier="PAPER",
                        call_strike=call_strike,
                        put_strike=put_strike,
                        call_ask=round(c_ask_otm, 2),
                        put_ask=round(p_ask_otm, 2),
                        net_cost=strangle_cost,
                        expected_move_pct=em_pct,
                        expected_move_price=em_price,
                        dte=chain.dte,
                        iv_percentile=context.iv_percentile,
                        event_title=nearest_title,
                        event_days=nearest_days,
                        color=sc,
                    ))

        except Exception:
            pass

        return results

    # ── 单腿买方 ──

    def _scan_single_leg(self, chain: OptionChain,
                         context: ScanContext) -> List[Signal]:
        """单腿买方：事件触发 + 趋势触发"""
        results = []

        if context.iv_percentile is None or context.iv_percentile >= BUYER_SINGLE_IV_THRESHOLD:
            return results

        if self._events is None:
            return results

        variety_events = self._events.for_variety(chain.variety, chain.name)

        # Tier 3 过滤
        all_t3 = EventEngine.is_all_tier3(variety_events)

        has_event = any(
            e["impact"] == "high"
            and (e.get("days_until", 0) == -1 or 2 <= e.get("days_until", 0) <= 7)
            for e in variety_events
        )
        if all_t3:
            has_event = False

        event_too_late = self._events.event_too_late(chain.variety, chain.name, chain.dte)

        has_trend = (context.change_5d is not None
                     and abs(context.change_5d) > TREND_CHG_MIN)

        if not has_event and not has_trend:
            return results

        otm_calls = chain.calls[
            (chain.calls["strike"] > chain.futures_price) &
            (chain.calls["bid"] > 0)
        ].sort_values("strike")

        otm_puts = chain.puts[
            (chain.puts["strike"] < chain.futures_price) &
            (chain.puts["bid"] > 0)
        ].sort_values("strike", ascending=False)

        # ── 事件触发 ──
        if has_event and not event_too_late:
            emit_call = context.change_5d is None or context.change_5d > 0
            emit_put = context.change_5d is None or context.change_5d < 0

            if emit_call and not otm_calls.empty:
                for _, row in otm_calls.iterrows():
                    ask = float(row.get("ask", 0))
                    bid = float(row.get("bid", 0))
                    sp = _spread(bid, ask)
                    if sp > EVENT_SPREAD_MAX:
                        continue
                    cost = ask * chain.multiplier
                    if context.capital > 0 and cost > context.capital * BUYER_SINGLE_EVENT_CAP:
                        continue

                    color = "green" if (BUYER_COLOR_ENABLED and context.iv_percentile < 20) else "yellow"
                    if context.event_priced:
                        color = "yellow"

                    results.append(self._make_signal(
                        strategy="buy_call_event",
                        variety=chain.variety,
                        name=chain.name,
                        contract=chain.contract,
                        legs=[Leg(side="buy", option_type="C",
                                  strike=float(row["strike"]), price=ask)],
                        max_profit=-1,
                        max_loss=round(cost, 0),
                        rr_ratio=-1,
                        tier="PAPER",
                        trigger="🔥事件",
                        strike=int(row["strike"]),
                        ask=round(ask, 2),
                        cost=round(cost, 0),
                        otm_pct=round((float(row["strike"]) - chain.futures_price)
                                      / chain.futures_price * 100, 1),
                        iv_percentile=round(context.iv_percentile),
                        color=color,
                    ))
                    break

            if emit_put and not otm_puts.empty:
                for _, row in otm_puts.iterrows():
                    ask = float(row.get("ask", 0))
                    bid = float(row.get("bid", 0))
                    sp = _spread(bid, ask)
                    if sp > EVENT_SPREAD_MAX:
                        continue
                    cost = ask * chain.multiplier
                    if context.capital > 0 and cost > context.capital * BUYER_SINGLE_EVENT_CAP:
                        continue

                    color = "green" if (BUYER_COLOR_ENABLED and context.iv_percentile < 20) else "yellow"
                    if context.event_priced:
                        color = "yellow"

                    results.append(self._make_signal(
                        strategy="buy_put_event",
                        variety=chain.variety,
                        name=chain.name,
                        contract=chain.contract,
                        legs=[Leg(side="buy", option_type="P",
                                  strike=float(row["strike"]), price=ask)],
                        max_profit=-1,
                        max_loss=round(cost, 0),
                        rr_ratio=-1,
                        tier="PAPER",
                        trigger="🔥事件",
                        strike=int(row["strike"]),
                        ask=round(ask, 2),
                        cost=round(cost, 0),
                        otm_pct=round((chain.futures_price - float(row["strike"]))
                                      / chain.futures_price * 100, 1),
                        iv_percentile=round(context.iv_percentile),
                        color=color,
                    ))
                    break

        # ── 趋势触发 ──
        if has_trend:
            if context.change_5d and context.change_5d > 2:
                best = None
                for _, row in otm_calls.iterrows():
                    ask = float(row.get("ask", 0))
                    bid = float(row.get("bid", 0))
                    sp = _spread(bid, ask)
                    if sp > TREND_SPREAD_MAX or bid <= 0:
                        continue
                    cost = ask * chain.multiplier
                    if cost <= 0:
                        continue
                    if context.capital > 0 and cost > context.capital * BUYER_SINGLE_TREND_CAP:
                        continue
                    best = {
                        "strike": int(row["strike"]),
                        "ask": round(ask, 2),
                        "cost": round(cost, 0),
                        "otm": round((float(row["strike"]) - chain.futures_price)
                                     / chain.futures_price * 100, 1),
                    }
                if best:
                    color = "green" if (BUYER_COLOR_ENABLED and context.iv_percentile < 20) else "yellow"
                    results.append(self._make_signal(
                        strategy="buy_call_trend",
                        variety=chain.variety,
                        name=chain.name,
                        contract=chain.contract,
                        legs=[Leg(side="buy", option_type="C",
                                  strike=best["strike"], price=best["ask"])],
                        max_profit=-1,
                        max_loss=round(best["cost"], 0),
                        rr_ratio=-1,
                        tier="PAPER",
                        trigger=f"📈5日+{context.change_5d:.1f}%",
                        strike=best["strike"],
                        ask=best["ask"],
                        cost=best["cost"],
                        otm_pct=best["otm"],
                        iv_percentile=round(context.iv_percentile),
                        color=color,
                    ))

            if context.change_5d and context.change_5d < -2:
                best = None
                for _, row in otm_puts.iterrows():
                    ask = float(row.get("ask", 0))
                    bid = float(row.get("bid", 0))
                    sp = _spread(bid, ask)
                    if sp > TREND_SPREAD_MAX or bid <= 0:
                        continue
                    cost = ask * chain.multiplier
                    if cost <= 0:
                        continue
                    if context.capital > 0 and cost > context.capital * BUYER_SINGLE_TREND_CAP:
                        continue
                    best = {
                        "strike": int(row["strike"]),
                        "ask": round(ask, 2),
                        "cost": round(cost, 0),
                        "otm": round((chain.futures_price - float(row["strike"]))
                                     / chain.futures_price * 100, 1),
                    }
                if best:
                    color = "green" if (BUYER_COLOR_ENABLED and context.iv_percentile < 20) else "yellow"
                    results.append(self._make_signal(
                        strategy="buy_put_trend",
                        variety=chain.variety,
                        name=chain.name,
                        contract=chain.contract,
                        legs=[Leg(side="buy", option_type="P",
                                  strike=best["strike"], price=best["ask"])],
                        max_profit=-1,
                        max_loss=round(best["cost"], 0),
                        rr_ratio=-1,
                        tier="PAPER",
                        trigger=f"📈5日{context.change_5d:.1f}%",
                        strike=best["strike"],
                        ask=best["ask"],
                        cost=best["cost"],
                        otm_pct=best["otm"],
                        iv_percentile=round(context.iv_percentile),
                        color=color,
                    ))

        return results
