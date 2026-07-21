#!/usr/bin/env python3
"""
统一扫描器：虚值倒挂 + 信用价差/买方机会 + 事件驱动 + IV环境 — 四合一
─────────────────────────────────────────────
每天跑一次，告诉你四件事：
  1. 今天有没有虚值倒挂可以做？（买入套利）
  2. 今天有没有信用价差可以做？（卖方收租）—— 默认模式
  3. 近期有没有事件值得蹲？
  4. 当前 IV 环境适合买方还是卖方？

买方模式（--buyer）额外扫描：
  -  debit call/put spread（牛市/熊市看涨价差）
  -  long straddle（买入跨式，赌大波动）
  -  long strangle（买入宽跨式，低成本赌波动）

输出结论：「今天做什么、不做什么、为什么」

用法:
  python3 unified_scanner.py                          # 完整扫描（卖方模式）
  python3 unified_scanner.py --capital 10000          # 含资金分配建议
  python3 unified_scanner.py --quick                  # 快速版(只看结论)
  python3 unified_scanner.py --skip-otm               # 跳过虚值倒挂
  python3 unified_scanner.py --buyer                  # 买方模式扫描
"""

import sys
import os
import json
import re
import math
import argparse
import pandas as pd
from datetime import datetime, date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from _ak_data import (pick_best_contract, fetch_option_chain, estimate_iv_from_chain,
                      VALID_MONTHS, DEFAULT_FUTURES, STRIKE_INTERVAL)
from event_calendar import get_upcoming_events, VARIETIES as EV_VARIETIES

VARIETIES = {
    "au": {"futures": 870,  "name": "沪金",    "multiplier": 1000},
    "m":  {"futures": 2800, "name": "豆粕",    "multiplier": 10},
    "c":  {"futures": 2300, "name": "玉米",    "multiplier": 10},
    "cf": {"futures": 13500,"name": "棉花",    "multiplier": 5},
    "sr": {"futures": 5600, "name": "白糖",    "multiplier": 10},
    "ta": {"futures": 4800, "name": "PTA",     "multiplier": 5},
    "i":  {"futures": 780,  "name": "铁矿石",  "multiplier": 100},
    "ru": {"futures": 17000,"name": "橡胶",    "multiplier": 10},
    "ma": {"futures": 2450, "name": "甲醇",    "multiplier": 10},
    "rm": {"futures": 2500, "name": "菜籽粕",  "multiplier": 10},
}

# ── 集中配置（改阈值只改这里）──
MAX_PREMIUM = 5.0
MAX_SPREAD_PCT = 10          # 卖方价差上限
OTM_PCT = 0.08               # 虚值倒挂边界
SELLER_CAPITAL_PCT = 0.05    # 卖方单笔最大亏损占本金比
BUYER_SPREAD_CAP = 0.05      # 买方价差单笔上限
BUYER_SINGLE_EVENT_CAP = 0.05  # 单腿·事件单笔上限
BUYER_SINGLE_TREND_CAP = 0.02  # 单腿·趋势单笔上限（OTM更便宜）
BUYER_IV_THRESHOLD = 30      # 买方 IV 分位阈值
DELTA_MAX = 0.30             # 卖方 Delta 上限
RR_MIN = 0.15                # 最低盈亏比
STRIKE_WIDTH_MAX = 0.05      # 行权价宽度上限（占期货价比）
OTM_MIN_PCT = 2.0            # 卖方最低 OTM%
TREND_CHG_MIN = 2.0          # 趋势触发最低涨跌幅%
TREND_SPREAD_MAX = 15        # 趋势单腿价差上限
EVENT_SPREAD_MAX = 10        # 事件单腿价差上限
EXEC_RR_MIN = 0.25            # EXEC 显示门槛（tradeable 最低 RR_MIN=0.15，EXEC 更严）
BUYER_COLOR_ENABLED = False   # Data ≥ 30 后改为 True，此前买方信号统一 🟡
MAX_STRIKE_GAP = 3            # 双循环最大跨档数


def _safe(v):
    return v if not pd.isna(v) else 0


def load_latest_iv_hv():
    """读 iv_history.csv 返回 {contract: {iv_est, hv_20d, hv_60d}} 最新一条"""
    import csv as _csv
    hist = {}
    csv_path = os.path.join(SCRIPT_DIR, "..", "data", "iv_history.csv")
    if not os.path.exists(csv_path):
        return hist
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            c = row.get("contract", "")
            if not c:
                continue
            try:
                hv20 = float(row.get("hv_20d", 0) or 0)
                hv60 = float(row.get("hv_60d", 0) or 0)
                iv = float(row.get("iv_est", 0) or 0)
                hist[c] = {"iv_est": iv, "hv_20d": hv20, "hv_60d": hv60, "date": row.get("date", ""), "time": row.get("time", "")}
            except (ValueError, TypeError):
                pass
    return hist


def load_iv_percentiles():
    """读 iv_history.csv 全量数据，按品种计算 IV 近似分位。
    返回 {contract: (percentile, days)} —— percentile 0-100，days 为数据天数。
    样本 < 5 天的品种返回 (None, days)。"""
    import csv as _csv
    from collections import defaultdict
    raw = defaultdict(list)
    csv_path = os.path.join(SCRIPT_DIR, "..", "data", "iv_history.csv")
    if not os.path.exists(csv_path):
        return {}
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            c = row.get("contract", "")
            try:
                iv = float(row.get("iv_est", 0) or 0)
            except (ValueError, TypeError):
                continue
            if c and iv > 0:
                raw[c].append(iv)
    result = {}
    for c, ivs in raw.items():
        days = len(ivs)
        if days < 5:
            result[c] = (None, days)
        else:
            latest = ivs[-1]
            below = sum(1 for v in ivs if v < latest)
            pct = round(below / days * 100)
            result[c] = (pct, days)
    return result


def iv_hv_tier(iv_est, hv_20d):
    """返回 (spread_float, tier_str, action_str)。iv_est/hv_20d 可能是 None。"""
    NO_DATA = (None, "⚠️无HV数据", "")
    if iv_est is None or hv_20d is None or hv_20d == 0:
        return NO_DATA
    try:
        spread = float(iv_est) - float(hv_20d)
    except (TypeError, ValueError):
        return NO_DATA
    pct = spread * 100  # → 百分点
    if spread >= 0.05:
        return spread, f"≥5%", "重仓/裸卖"
    elif spread >= 0.03:
        return spread, f"3-5%", "正常仓位"
    elif spread >= 0.01:
        return spread, f"1-3%", "减半仓位"
    elif spread >= 0:
        return spread, f"<1%", "不执行"
    else:
        return spread, f"<0% · 折价", "不执行"


def _cl_str(s):
    """格式化 IV Collector 分位字符串，用于买方信号输出。"""
    pct = s.get('_cl_pct')
    if pct is not None:
        return f" Cl{pct}%({s.get('_cl_days', 0)}d)"
    return " ClN/A"


def _spread(bid, ask):
    if bid and ask and bid > 0:
        return round((ask - bid) / bid * 100, 1)
    return 999


def _make_signal(strategy, variety, name, contract, **kwargs):
    """统一信号工厂。所有 scan_* 函数通过此函数构造信号字典。"""
    return {"strategy": strategy, "variety": variety, "name": name,
            "contract": contract, **kwargs}


# ═══════════════════════════════════════════
# 模块1: 虚值倒挂扫描
# ═══════════════════════════════════════════

def scan_deep_otm(vcode, variety, contract, df, futures, capital=None):
    """
    扫描单个品种虚值看跌倒挂。
    contract, df, futures 由 main() 预取传入，本函数不再自行拉取数据。
    """
    mult = variety['multiplier']

    all_signals = []

    otm_boundary = int(futures * (1 - OTM_PCT))
    otm_puts = df[df['strike'] < otm_boundary].copy()
    if not otm_puts.empty:
        rows = []
        for _, row in otm_puts.iterrows():
            p_last = row['p_last'] if not pd.isna(row['p_last']) else None
            p_bid = _safe(row['p_bid'])
            p_ask = _safe(row['p_ask'])
            if p_last is None or p_last <= 0 or p_last > MAX_PREMIUM:
                continue
            if p_bid <= 0:
                continue
            rows.append({
                'strike': int(row['strike']),
                'price': p_last, 'bid': p_bid, 'ask': p_ask,
                'oi': int(row['p_oi']) if not pd.isna(row['p_oi']) else 0,
            })

        for i in range(len(rows) - 1):
            cur, nxt = rows[i], rows[i + 1]
            if cur['price'] > nxt['price']:
                profit_pct = round((cur['price'] - nxt['price']) / nxt['price'] * 100, 1)
                sp = _spread(nxt['bid'], nxt['ask'])
                net = round(profit_pct - sp, 1)
                cost = nxt['price'] * mult
                tradeable = sp < profit_pct and sp < MAX_SPREAD_PCT and nxt['bid'] > 0
                ref_sp = _spread(cur['bid'], cur['ask'])
                if cur['bid'] <= 0 or ref_sp > MAX_SPREAD_PCT:
                    tradeable = False
                if capital and cost > capital * SELLER_CAPITAL_PCT:
                    continue
                all_signals.append({
                    'variety': vcode, 'name': variety['name'], 'contract': contract,
                    'buy_strike': nxt['strike'], 'buy_price': nxt['price'],
                    'buy_bid': nxt['bid'], 'buy_ask': nxt['ask'],
                    'ref_strike': cur['strike'], 'ref_price': cur['price'],
                    'profit_pct': profit_pct, 'spread_pct': sp, 'net_pct': net,
                    'cost': cost, 'tradeable': tradeable,
                })

    tradeable = [s for s in all_signals if s['tradeable']]
    summary = f"{len(all_signals)}信号({len(tradeable)}可做)" if all_signals else "无信号"
    return all_signals, summary


# ═══════════════════════════════════════════
# 模块2: 虚值信用价差扫描（卖方收租）
# ═══════════════════════════════════════════

def _estimate_delta(strike, futures, otm_pct, iv_est=None, dte=30):
    """近似 Delta（绝对值）。iv_est=None 时用默认 20%。
    用于过滤 OTM 不够远的卖方信号。"""
    import math
    iv = iv_est if iv_est and 0.05 < iv_est < 2.0 else 0.20
    T = max(dte / 365, 1/365)
    d1 = (otm_pct / 100) / (iv * math.sqrt(T)) if iv > 0 and T > 0 else 0
    # N(-d1) ≈ 0.5 * exp(-d1²/2)，对 d1 > 0 近似精度足够
    return round(0.5 * (1 + math.erf(-d1 / math.sqrt(2))), 3)


def _scan_one_side(df, bid_col, ask_col, direction, futures, mult, capital,
                   vcode, variety_name, contract, iv_est=None, dte=30):
    """
    单侧信用价差扫描（Put 或 Call）。
    direction='put': 卖高行权价 Put + 买低行权价 Put（看涨/中性）
    direction='call': 卖低行权价 Call + 买高行权价 Call（看跌/中性）
    返回信号列表。
    """
    results = []
    options = df[df[bid_col] > 0].copy()
    if options.empty:
        return results

    options = options.sort_values('strike')
    for i in range(len(options)):
        for j in range(i + 1, min(i + 1 + MAX_STRIKE_GAP, len(options))):
            low_row = options.iloc[i]
            high_row = options.iloc[j]

        if direction == 'put':
            sell_row, buy_row = high_row, low_row
            sell_strike = int(high_row['strike'])
            buy_strike = int(low_row['strike'])
            if sell_strike >= futures or buy_strike >= futures:
                continue
            otm_pct = (futures - sell_strike) / futures * 100
        else:  # call
            sell_row, buy_row = low_row, high_row
            sell_strike = int(low_row['strike'])
            buy_strike = int(high_row['strike'])
            if sell_strike <= futures or buy_strike <= futures:
                continue
            otm_pct = (sell_strike - futures) / futures * 100

        strike_width = buy_strike - sell_strike
        if strike_width > futures * STRIKE_WIDTH_MAX:
            continue

        sell_bid = _safe(sell_row[bid_col])
        buy_ask = _safe(buy_row[ask_col])
        if sell_bid <= 0 or buy_ask <= 0 or sell_bid <= buy_ask:
            continue

        net_premium = round(sell_bid - buy_ask, 2)
        max_profit = net_premium * mult
        max_loss = round((strike_width * mult) - max_profit, 0)
        if capital and max_loss > capital * SELLER_CAPITAL_PCT:
            continue
        if max_loss <= 0:
            continue

        rr_ratio = round(max_profit / max_loss, 2)
        if rr_ratio < RR_MIN:
            continue

        sell_spread = _spread(sell_row[bid_col], sell_row[ask_col])
        buy_spread = _spread(buy_row[bid_col], buy_row[ask_col])
        if sell_spread > MAX_SPREAD_PCT or buy_spread > MAX_SPREAD_PCT:
            continue

        # 行权价宽度三档分类（锚 ¥1000 风险预算）
        width_pct = strike_width / futures * 100
        if width_pct <= 2:
            tier = 'green'
        elif width_pct <= 4:
            tier = 'yellow'
        else:
            tier = 'red'

        # 近值降级：卖腿 OTM < 2% → 无论宽度一律红档
        if otm_pct < OTM_MIN_PCT:
            tier = 'red'

        # Delta 约束：abs(Delta) > 0.30 → 降级（机构卖方标准）
        delta = _estimate_delta(sell_strike, futures, otm_pct, iv_est, dte)
        if delta > DELTA_MAX:
            if tier == 'green':
                tier = 'yellow'
            elif tier == 'yellow':
                tier = 'red'

        tradeable = tier in ('green', 'yellow')
        results.append({
            'variety': vcode,
            'name': variety_name,
            'contract': contract,
            'sell_strike': sell_strike,
            'buy_strike': buy_strike,
            'sell_bid': round(float(sell_bid), 2),
            'buy_ask': round(float(buy_ask), 2),
            'net_premium': net_premium,
            'max_profit': round(max_profit, 0),
            'max_loss': max_loss,
            'rr_ratio': rr_ratio,
            'tier': tier,
            'strike_width_pct': round(width_pct, 1),
            'otm_pct': round(otm_pct, 1),
            'delta': delta,
            'direction': direction,
            'tradeable': tradeable,
        })

    # 多维排序：盈亏比 40% + OTM 安全边际 30% + 流动性 20%
    def _sort_key(s):
        rr = s.get('rr_ratio', 0)
        otm = min(s.get('otm_pct', 0) / 15.0, 1.0)  # 15% 封顶
        sell_sp = s.get('sell_spread', 0)
        buy_sp = s.get('buy_spread', 0)
        spread_pct = (sell_sp + buy_sp) / 2 if (sell_sp + buy_sp) > 0 else 0
        liq = 1.0 / (1.0 + spread_pct)
        return rr * 0.4 + otm * 0.3 + liq * 0.2
    results.sort(key=_sort_key, reverse=True)

    return results


def scan_credit_spreads(vcode, variety, contract, df, futures, capital=None):
    """
    扫描虚值信用价差机会（Put + Call）。
    contract, df, futures 由 main() 预取传入。
    """
    mult = variety['multiplier']
    name = variety['name']

    # 估算 IV（从 ATM 跨式，供 Delta 约束用）和 DTE
    import math, re
    iv_est = None
    dte = 30
    try:
        atm_idx = (df['strike'] - futures).abs().idxmin()
        atm_row = df.loc[atm_idx]
        p_bid = _safe(atm_row.get('p_bid', 0))
        p_ask = _safe(atm_row.get('p_ask', 0))
        c_bid = _safe(atm_row.get('c_bid', 0))
        c_ask = _safe(atm_row.get('c_ask', 0))
        straddle = (p_bid + p_ask + c_bid + c_ask) / 2
        if futures > 0 and straddle > 0:
            m = re.search(r'(\d{4})$', contract)
            if m:
                yy, mm = int(m.group(1)[:2]), int(m.group(1)[2:])
                expiry = datetime(2000 + yy, mm, 1)
                dte = max((expiry - datetime.now()).days - 5, 5)
            iv_est = straddle / (0.8 * futures * math.sqrt(max(dte, 1) / 365))
            iv_est = round(float(iv_est), 4)
    except Exception:
        pass

    all_signals = []
    all_signals.extend(_scan_one_side(
        df, 'p_bid', 'p_ask', 'put', futures, mult, capital, vcode, name, contract, iv_est, dte))
    all_signals.extend(_scan_one_side(
        df, 'c_bid', 'c_ask', 'call', futures, mult, capital, vcode, name, contract, iv_est, dte))

    tradeable = [s for s in all_signals if s['tradeable']]
    green_n = len([s for s in tradeable if s.get('tier') == 'green'])
    yellow_n = len([s for s in tradeable if s.get('tier') == 'yellow'])
    nc = len([s for s in tradeable if s['sell_strike'] > futures])
    np = len([s for s in tradeable if s['sell_strike'] < futures])
    summary = f"{len(all_signals)}信号({len(tradeable)}可做: {np}P {nc}C | 🟢{green_n} 🟡{yellow_n})" if all_signals else "无信号"
    return all_signals, summary


# ═══════════════════════════════════════════
# 模块2B: 买方机会扫描（debit spread + straddle/strangle）
# ═══════════════════════════════════════════

def _compute_dte(contract_code):
    """
    从合约代码估算到期天数。
    合约代码如 'au2608' → 2026年8月。商品期权通常在交割月前到期，
    用合约月1日-5天近似（前月末最后交易日附近）。精度 ±2 天。
    """
    match = re.search(r'(\d{2})(\d{2})$', str(contract_code))
    if match:
        yy = int(match.group(1)) + 2000
        mm = int(match.group(2))
        exp_date = date(yy, mm, 1) - timedelta(days=5)
        dte = (exp_date - date.today()).days
        return max(dte, 1)
    return 30  # fallback


def _estimate_iv_percentile(df, futures):
    """
    用 ATM 跨式成本/期货价格作为 IV 代理，映射到近似分位数。
    ⚠️ 无历史数据，仅为粗略估计。积累数据后改用真实分位。

    返回近似分位数（0-100），或 None（无法计算）。
    """
    if df is None or df.empty:
        return None

    atm_idx = (df['strike'] - futures).abs().argsort()
    if len(atm_idx) == 0:
        return None

    atm_row = df.iloc[atm_idx.values[0] if hasattr(atm_idx, 'values') else atm_idx.iloc[0]]

    p_ask = _safe(atm_row.get('p_ask', 0))
    c_ask = _safe(atm_row.get('c_ask', 0))

    if p_ask <= 0 or c_ask <= 0:
        return None

    atm_straddle_cost = p_ask + c_ask
    iv_proxy = atm_straddle_cost / futures

    # 分位映射：proxy = straddle/futures ≈ 0.8*IV*√(DTE/365)
    # DTE≈60 → √(60/365)≈0.405 → proxy≈0.324*IV
    # IV=12%→proxy≈0.04, IV=25%→0.08, IV=30%→0.10, IV=40%→0.13, IV=50%→0.16
    if iv_proxy < 0.03:
        return 5
    elif iv_proxy < 0.05:
        return 15
    elif iv_proxy < 0.07:
        return 25
    elif iv_proxy < 0.10:
        return 28
    elif iv_proxy < 0.10:
        return 50
    elif iv_proxy < 0.12:
        return 65
    elif iv_proxy < 0.16:
        return 80
    else:
        return 95


def _filter_events_for_variety(events, vcode, variety_name):
    """从事件列表中筛选与当前品种相关的事件。"""
    relevant = []
    for e in events:
        ev_vcodes = e.get('varieties', [])
        ev_names = e.get('variety_names', [])
        if vcode in ev_vcodes or variety_name in ev_names:
            relevant.append(e)
    return relevant


def _scan_buyer_debit_side(df, direction, futures, mult, capital,
                           vcode, variety_name, contract,
                           events, iv_percentile):
    """
    单侧 debit spread 扫描。

    direction='call': 牛市看涨价差（买低行权价Call + 卖高行权价Call）
        net_debit = buy_ask(low_strike) - sell_bid(high_strike)
        OTM = (low_strike - futures) / futures

    direction='put': 熊市看跌价差（买高行权价Put + 卖低行权价Put）
        net_debit = buy_ask(high_strike) - sell_bid(low_strike)
        OTM = (futures - high_strike) / futures

    信号条件：OTM < 5%, IV < 40th percentile, 无 D-1 高影响事件, profit_ratio >= 1.5
    """
    results = []

    if direction == 'call':
        bid_col, ask_col = 'c_bid', 'c_ask'
    else:
        bid_col, ask_col = 'p_bid', 'p_ask'

    options = df[(df[bid_col] > 0) & (df[ask_col] > 0)].copy()
    if options.empty:
        return results

    options = options.sort_values('strike')

    # 筛选与品种相关的事件
    variety_events = _filter_events_for_variety(events, vcode, variety_name)

    # Tier 3 过滤：仅有例行低冲击事件 → 不产生买方方向信号
    _has_events = len(variety_events) > 0
    _all_tier3 = _has_events and not any(
        not e.get('routine', True) or e.get('impact', 'low') != 'low'
        for e in variety_events)
    if _all_tier3:
        return results

    # 检查是否有 D-1 高影响事件（排除持续事件和 D-0/D-1 固定事件）
    has_d1_high_event = any(
        0 <= e.get('days_until', 0) <= 1 and e['impact'] == 'high'
        for e in variety_events
    )

    # 最近的事件天数（排除持续事件 days_until=-1）
    dated_events = [e for e in variety_events if e.get('days_until', 0) >= 0]
    nearest_event_days = min(e['days_until'] for e in dated_events) if dated_events else None

    # 事件-到期校验：事件在到期后才发生则过滤
    dte = _compute_dte(contract)
    event_too_late = (nearest_event_days is not None and dte is not None and
                      nearest_event_days > dte - 1)

    for i in range(len(options)):
        for j in range(i + 1, min(i + 1 + MAX_STRIKE_GAP, len(options))):
            low_row = options.iloc[i]
            high_row = options.iloc[j]

            low_strike = int(low_row['strike'])
            high_strike = int(high_row['strike'])

        if direction == 'call':
            # 牛市看涨价差：买入低行权价 Call，卖出高行权价 Call
            if low_strike < futures * 0.98:
                continue  # 买腿允许近值（≥98%期货价），但不能深度实值
            buy_ask = _safe(low_row[ask_col])
            sell_bid = _safe(high_row[bid_col])
            otm_pct = (low_strike - futures) / futures * 100
            buy_strike, sell_strike = low_strike, high_strike
            buy_sp = _spread(low_row[bid_col], low_row[ask_col])
            sell_sp = _spread(high_row[bid_col], high_row[ask_col])
        else:
            # 熊市看跌价差：买入高行权价 Put，卖出低行权价 Put
            if high_strike > futures * 1.02:
                continue  # 买腿允许近值（≤102%期货价），但不能深度实值
            buy_ask = _safe(high_row[ask_col])
            sell_bid = _safe(low_row[bid_col])
            otm_pct = (futures - high_strike) / futures * 100
            buy_strike, sell_strike = high_strike, low_strike
            buy_sp = _spread(high_row[bid_col], high_row[ask_col])
            sell_sp = _spread(low_row[bid_col], low_row[ask_col])

        if buy_ask <= 0 or sell_bid <= 0:
            continue

        net_debit = round(buy_ask - sell_bid, 2)
        if net_debit <= 0:
            continue

        strike_width = high_strike - low_strike
        max_profit = round(strike_width * mult - net_debit * mult, 0)
        max_loss = round(net_debit * mult, 0)

        if max_loss <= 0 or max_profit <= 0:
            continue

        profit_ratio = round(max_profit / max_loss, 2)

        # ── 信号条件 ──
        if otm_pct >= 5:
            continue  # OTM 太远
        if profit_ratio < 1.5:
            continue  # 盈亏比不够
        if has_d1_high_event:
            continue  # D-1 有高影响事件，不进场
        if event_too_late:
            continue  # 事件在合约到期后，等不到催化剂
        if iv_percentile is not None and iv_percentile >= 40:
            continue  # IV 不够便宜

        # 检查价差质量
        if buy_sp > MAX_SPREAD_PCT or sell_sp > MAX_SPREAD_PCT:
            continue

        # 资金检查
        if capital and max_loss > capital * SELLER_CAPITAL_PCT:
            continue

        # ── 颜色编码 ──
        has_event = len(variety_events) > 0
        # TODO: Data ≥ 30 后恢复 iv_percentile < BUYER_IV_THRESHOLD and has_event → green
        if BUYER_COLOR_ENABLED and iv_percentile is not None and iv_percentile < BUYER_IV_THRESHOLD and has_event:
            color = 'green'
        else:
            color = 'yellow'

        # 计算盈亏平衡点
        if direction == 'call':
            break_even = round(low_strike + net_debit, 2)
        else:
            break_even = round(high_strike - net_debit, 2)

        strategy_label = 'bull_call_spread' if direction == 'call' else 'bear_put_spread'

        results.append({
            'strategy': strategy_label,
            'variety': vcode,
            'name': variety_name,
            'contract': contract,
            'buy_strike': buy_strike,
            'sell_strike': sell_strike,
            'buy_ask': round(float(buy_ask), 2),
            'sell_bid': round(float(sell_bid), 2),
            'net_debit': net_debit,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'profit_ratio': profit_ratio,
            'otm_pct': round(otm_pct, 1),
            'break_even': break_even,
            'iv_percentile': iv_percentile,
            'event_days': nearest_event_days,
            'color': color,
            'tradeable': True,
        })

    return results


def _scan_buyer_straddles_strangles(df, futures, mult, capital,
                                    vcode, variety_name, contract,
                                    events, iv_percentile):
    """
    扫描买入跨式（straddle）和宽跨式（strangle）机会。

    Straddle: 买入 ATM Call + ATM Put
      信号：IV < 30th percentile AND D-2 ~ D-7 高影响事件 AND ATM spread < 10%

    Strangle: 买入 ~0.5% OTM Call + ~0.5% OTM Put
      信号：IV < 30th percentile AND 事件存在 AND 两腿 spread < 15%
    """
    results = []

    dte = _compute_dte(contract)

    # 筛选品种相关事件
    variety_events = _filter_events_for_variety(events, vcode, variety_name)

    # 事件-到期校验：最近事件是否在合约到期后才发生
    dated_evs = [e for e in variety_events if e.get('days_until', 0) >= 0]
    nearest_ev_days = min(e['days_until'] for e in dated_evs) if dated_evs else None
    event_too_late = (nearest_ev_days is not None and dte is not None and
                      nearest_ev_days > dte - 1)

    # ── Straddle ──
    atm_idx_series = (df['strike'] - futures).abs().argsort()
    if len(atm_idx_series) > 0:
        atm_idx = atm_idx_series.values[0] if hasattr(atm_idx_series, 'values') else atm_idx_series.iloc[0]
        atm_row = df.iloc[atm_idx]
        atm_strike = int(atm_row['strike'])

        call_ask = _safe(atm_row.get('c_ask', 0))
        put_ask = _safe(atm_row.get('p_ask', 0))

        # ATM spread 检查
        atm_call_spread = _spread(_safe(atm_row.get('c_bid', 0)), call_ask)
        atm_put_spread = _spread(_safe(atm_row.get('p_bid', 0)), put_ask)

        net_cost = round(call_ask + put_ask, 2)

        # 预期波动 ≈ strike × IV_proxy × √(DTE/365)
        if iv_percentile is not None:
            iv_proxy_raw = (call_ask + put_ask) / futures if futures > 0 else 0.05
        else:
            iv_proxy_raw = 0.02  # fallback
        expected_move = round(atm_strike * iv_proxy_raw * (dte / 365) ** 0.5, 2)

        # 检查 straddle 条件（持续事件 days_until=-1 也算，代表持续高波动背景）
        has_event_d2_d7 = any(
            e['impact'] == 'high' and (e.get('days_until', 0) == -1 or 2 <= e['days_until'] <= 7)
            for e in variety_events
        )
        atm_spread_ok = atm_call_spread < 10 and atm_put_spread < 10
        iv_cheap = iv_percentile is not None and iv_percentile < BUYER_IV_THRESHOLD

        nearest_event = None
        if variety_events:
            nearest_event = min(variety_events, key=lambda e: e['days_until'])

        if iv_cheap and has_event_d2_d7 and atm_spread_ok and not event_too_late:
            if capital and net_cost * mult > capital * SELLER_CAPITAL_PCT:
                pass  # skip due to capital
            else:
                straddle_color = 'green' if (BUYER_COLOR_ENABLED and iv_percentile is not None and iv_percentile < BUYER_IV_THRESHOLD and has_event_d2_d7) else 'yellow'
                event_title = nearest_event['title'] if nearest_event else ''
                event_days = nearest_event['days_until'] if nearest_event else None

                results.append({
                    'strategy': 'long_straddle',
                    'variety': vcode,
                    'name': variety_name,
                    'contract': contract,
                    'strike': atm_strike,
                    'call_ask': round(float(call_ask), 2),
                    'put_ask': round(float(put_ask), 2),
                    'net_cost': net_cost,
                    'max_profit': None,  # 理论上无限
                    'max_loss': round(net_cost * mult, 0),
                    'expected_move': expected_move,
                    'dte': dte,
                    'iv_percentile': iv_percentile,
                    'event_title': event_title,
                    'event_days': event_days,
                    'color': straddle_color,
                    'tradeable': True,
                })

        # ── Strangle ──
        otm_target_pct = 0.005  # 0.5% OTM
        otm_call_target = futures * (1 + otm_target_pct)
        otm_put_target = futures * (1 - otm_target_pct)

        # 找最接近目标价的 OTM Call
        call_candidates = df[(df['strike'] > futures) & (df['c_ask'] > 0)].copy()
        if not call_candidates.empty:
            call_candidates = call_candidates.copy()
            call_candidates['dist'] = (call_candidates['strike'] - otm_call_target).abs()
            call_idx = call_candidates['dist'].idxmin()
            call_row = call_candidates.loc[call_idx]
            call_strike = int(call_row['strike'])
            c_ask_otm = _safe(call_row.get('c_ask', 0))
            c_bid_otm = _safe(call_row.get('c_bid', 0))
            call_spread = _spread(c_bid_otm, c_ask_otm) if c_bid_otm > 0 else 999
        else:
            call_strike = None
            c_ask_otm = 0
            call_spread = 999

        # 找最接近目标价的 OTM Put
        put_candidates = df[(df['strike'] < futures) & (df['p_ask'] > 0)].copy()
        if not put_candidates.empty:
            put_candidates = put_candidates.copy()
            put_candidates['dist'] = (put_candidates['strike'] - otm_put_target).abs()
            put_idx = put_candidates['dist'].idxmin()
            put_row = put_candidates.loc[put_idx]
            put_strike = int(put_row['strike'])
            p_ask_otm = _safe(put_row.get('p_ask', 0))
            p_bid_otm = _safe(put_row.get('p_bid', 0))
            put_spread = _spread(p_bid_otm, p_ask_otm) if p_bid_otm > 0 else 999
        else:
            put_strike = None
            p_ask_otm = 0
            put_spread = 999

        # 检查 strangle 条件
        has_any_event = len(variety_events) > 0
        strangle_spread_ok = call_spread < 15 and put_spread < 15
        legs_valid = (call_strike is not None and put_strike is not None
                      and c_ask_otm > 0 and p_ask_otm > 0)

        if iv_cheap and has_any_event and strangle_spread_ok and legs_valid and not event_too_late:
            strangle_cost = round(c_ask_otm + p_ask_otm, 2)
            if capital and strangle_cost * mult > capital * SELLER_CAPITAL_PCT:
                pass
            else:
                strangle_color = 'green' if (BUYER_COLOR_ENABLED and iv_percentile is not None and iv_percentile < BUYER_IV_THRESHOLD) else 'yellow'
                event_title = nearest_event['title'] if nearest_event else ''
                event_days = nearest_event['days_until'] if nearest_event else None

                results.append({
                    'strategy': 'long_strangle',
                    'variety': vcode,
                    'name': variety_name,
                    'contract': contract,
                    'call_strike': call_strike,
                    'put_strike': put_strike,
                    'call_ask': round(float(c_ask_otm), 2),
                    'put_ask': round(float(p_ask_otm), 2),
                    'net_cost': strangle_cost,
                    'max_profit': None,
                    'max_loss': round(strangle_cost * mult, 0),
                    'expected_move': expected_move,
                    'dte': dte,
                    'iv_percentile': iv_percentile,
                    'event_title': event_title,
                    'event_days': event_days,
                    'color': strangle_color,
                    'tradeable': True,
                })

    return results


def scan_single_leg_buyer(df, futures, variety_name, contract, vcode,
                           events, capital, mult, iv_percentile):
    """单腿买方 — 统一入口。事件/趋势触发，向外走直到流动性尽头。
    
    事件触发（🔥）：持续地缘 OR D-2~D-7 高影响事件 → ATM ± 向外走，≤5%本金，≤10%价差
    趋势触发（📈）：5日涨跌>2% + IV<30% → OTM 向外走，≤2%本金，≤15%价差
    走到 bid=0 或价差>15% → 停。"""
    results = []
    if iv_percentile is None or iv_percentile >= 30:
        return results

    # ── 事件数据 ──
    variety_events = _filter_events_for_variety(events, vcode, variety_name)

    # Tier 3 过滤：仅有例行低冲击事件 → 不产生买方方向事件信号（趋势触发不受影响）
    _has_ev = len(variety_events) > 0
    _all_t3 = _has_ev and not any(
        not e.get('routine', True) or e.get('impact', 'low') != 'low'
        for e in variety_events)

    has_event = any(
        e['impact'] == 'high' and (e.get('days_until', 0) == -1 or 2 <= e['days_until'] <= 7)
        for e in variety_events)
    if _all_t3:
        has_event = False  # Tier 3 事件不触发方向信号，趋势照常

    # 事件-到期校验
    dte = _compute_dte(contract)
    dated_evs_sl = [e for e in variety_events if e.get('days_until', 0) >= 0]
    nearest_ev_days_sl = min(e['days_until'] for e in dated_evs_sl) if dated_evs_sl else None
    event_too_late_sl = (nearest_ev_days_sl is not None and dte is not None and
                          nearest_ev_days_sl > dte - 1)

    # ── 趋势数据 ──
    change_5d = None
    try:
        from _ak_data import fetch_futures_daily
        daily = fetch_futures_daily(vcode, 10)
        if daily is not None and len(daily) >= 6:
            daily = daily.sort_values("date")
            closes = daily["close"].astype(float)
            change_5d = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100
    except Exception:
        pass
    has_trend = change_5d is not None and abs(change_5d) > 2

    if not has_event and not has_trend:
        return results

    # ── 扫描 Call 侧（OTM call: strike > futures）──
    otm_calls = df[(df['strike'] > futures) & (df['c_bid'] > 0)].sort_values('strike')
    # ── 扫描 Put 侧（OTM put: strike < futures）──
    otm_puts  = df[(df['strike'] < futures) & (df['p_bid'] > 0)].sort_values('strike', ascending=False)

    # ━━ 事件触发：Call/Put 各独立，不合并 ━━
    # 事件在到期后则不产生方向性信号（趋势触发不受影响）
    if has_event and not event_too_late_sl:
        for _, row in otm_calls.iterrows():
            ask = _safe(row.get('c_ask', 0))
            bid = _safe(row.get('c_bid', 0))
            sp = _spread(bid, ask)
            if sp > EVENT_SPREAD_MAX:
                continue
            cost = ask * mult
            if capital and cost > capital * SELLER_CAPITAL_PCT:
                continue
            results.append({
                'strategy': 'buy_call_event', 'trigger': '🔥事件',
                'variety': vcode, 'name': variety_name, 'contract': contract,
                'strike': int(row['strike']), 'ask': round(float(ask), 2),
                'cost': round(cost, 0), 'max_loss': round(cost, 0),
                'otm_pct': round((int(row['strike'])-futures)/futures*100, 1),
                'iv_percentile': round(iv_percentile),
                # TODO: Data ≥ 30 后恢复 iv_percentile < 20 → green
                'color': 'green' if (BUYER_COLOR_ENABLED and iv_percentile < 20) else 'yellow',
                'tradeable': True,
            })
            break
        for _, row in otm_puts.iterrows():
            ask = _safe(row.get('p_ask', 0))
            bid = _safe(row.get('p_bid', 0))
            sp = _spread(bid, ask)
            if sp > EVENT_SPREAD_MAX:
                continue
            cost = ask * mult
            if capital and cost > capital * SELLER_CAPITAL_PCT:
                continue
            results.append({
                'strategy': 'buy_put_event', 'trigger': '🔥事件',
                'variety': vcode, 'name': variety_name, 'contract': contract,
                'strike': int(row['strike']), 'ask': round(float(ask), 2),
                'cost': round(cost, 0), 'max_loss': round(cost, 0),
                'otm_pct': round((futures-int(row['strike']))/futures*100, 1),
                'iv_percentile': round(iv_percentile),
                # TODO: Data ≥ 30 后恢复 iv_percentile < 20 → green
                'color': 'green' if (BUYER_COLOR_ENABLED and iv_percentile < 20) else 'yellow',
                'tradeable': True,
            })
            break

    # ━━ 趋势触发（走到底，取最深 OTM 杠杆最大那一档）━━
    if has_trend:
        if change_5d > 2:
            best = None
            for _, row in otm_calls.iterrows():
                ask = _safe(row.get('c_ask', 0))
                bid = _safe(row.get('c_bid', 0))
                sp = _spread(bid, ask)
                if sp > TREND_SPREAD_MAX or bid <= 0:
                    continue  # 跳过没流动性或价差太宽的，继续往外走
                cost = ask * mult
                if cost <= 0:
                    continue
                if capital and cost > capital * BUYER_SINGLE_TREND_CAP:
                    continue  # 太贵，继续往外
                # 找到一档符合的，记录但不 break——继续走找更深的
                best = {'strike': int(row['strike']), 'ask': round(float(ask), 2),
                        'cost': round(cost, 0), 'otm': round((int(row['strike'])-futures)/futures*100, 1)}
            if best:
                results.append({
                    'strategy': 'buy_call_trend', 'trigger': f'📈5日+{change_5d:.1f}%',
                    'variety': vcode, 'name': variety_name, 'contract': contract,
                    'strike': best['strike'], 'ask': best['ask'],
                    'cost': best['cost'], 'max_loss': best['cost'],
                    'otm_pct': best['otm'],
                    'iv_percentile': round(iv_percentile),
                    # TODO: Data ≥ 30 后恢复 iv_percentile < 20 → green
                'color': 'green' if (BUYER_COLOR_ENABLED and iv_percentile < 20) else 'yellow',
                    'tradeable': True,
                })
        if change_5d < -2:
            best = None
            for _, row in otm_puts.iterrows():
                ask = _safe(row.get('p_ask', 0))
                bid = _safe(row.get('p_bid', 0))
                sp = _spread(bid, ask)
                if sp > TREND_SPREAD_MAX or bid <= 0:
                    continue
                cost = ask * mult
                if cost <= 0:
                    continue
                if capital and cost > capital * BUYER_SINGLE_TREND_CAP:
                    continue
                best = {'strike': int(row['strike']), 'ask': round(float(ask), 2),
                        'cost': round(cost, 0), 'otm': round((futures-int(row['strike']))/futures*100, 1)}
            if best:
                results.append({
                    'strategy': 'buy_put_trend', 'trigger': f'📈5日{change_5d:.1f}%',
                    'variety': vcode, 'name': variety_name, 'contract': contract,
                    'strike': best['strike'], 'ask': best['ask'],
                    'cost': best['cost'], 'max_loss': best['cost'],
                    'otm_pct': best['otm'],
                    'iv_percentile': round(iv_percentile),
                    # TODO: Data ≥ 30 后恢复 iv_percentile < 20 → green
                'color': 'green' if (BUYER_COLOR_ENABLED and iv_percentile < 20) else 'yellow',
                    'tradeable': True,
                })

    return results


def scan_buyer_opportunities(vcode, variety, contract, df, futures,
                             events, capital=None):
    """
    买方机会统一扫描：debit spread + straddle/strangle。
    contract, df, futures 由 main() 预取传入。
    """
    mult = variety['multiplier']
    name = variety['name']

    all_signals = []

    # IV 分位估计（所有买方策略共用）
    iv_pct = _estimate_iv_percentile(df, futures)

    # 1. Debit Call Spread（牛市看涨）
    all_signals.extend(_scan_buyer_debit_side(
        df, 'call', futures, mult, capital, vcode, name, contract, events, iv_pct))

    # 2. Debit Put Spread（熊市看跌）
    all_signals.extend(_scan_buyer_debit_side(
        df, 'put', futures, mult, capital, vcode, name, contract, events, iv_pct))

    # 3. Straddle + Strangle
    all_signals.extend(_scan_buyer_straddles_strangles(
        df, futures, mult, capital, vcode, name, contract, events, iv_pct))

    tradeable = [s for s in all_signals if s['tradeable']]
    green_n = len([s for s in tradeable if s.get('color') == 'green'])
    yellow_n = len([s for s in tradeable if s.get('color') == 'yellow'])
    debit_n = len([s for s in tradeable if 'spread' in s.get('strategy', '')])
    vol_n = len([s for s in tradeable if 'straddle' in s.get('strategy', '') or 'strangle' in s.get('strategy', '')])

    iv_str = f"ScP{iv_pct}" if iv_pct is not None else "IV?"
    summary = (f"{len(all_signals)}信号({len(tradeable)}可做: {debit_n}价差 {vol_n}波动率 | "
               f"🟢{green_n} 🟡{yellow_n} | {iv_str})" if all_signals else f"无信号 ({iv_str})")
    return all_signals, summary


# ═══════════════════════════════════════════
# 模块3: IV 环境判断
# ═══════════════════════════════════════════

def assess_iv_environment(vcode, variety, contract, df, futures):
    """
    用 ATM 期权的价格水平做简易 IV 代理判断。
    contract, df, futures 由 main() 预取传入，本函数不再自行拉取数据。
    """
    atm = df.iloc[(df['strike'] - futures).abs().argsort()[:1]]
    p_bid = atm['p_bid'].values[0] if not pd.isna(atm['p_bid'].values[0]) else 0
    p_ask = atm['p_ask'].values[0] if not pd.isna(atm['p_ask'].values[0]) else 0
    c_bid = atm['c_bid'].values[0] if not pd.isna(atm['c_bid'].values[0]) else 0
    c_ask = atm['c_ask'].values[0] if not pd.isna(atm['c_ask'].values[0]) else 0

    if p_bid <= 0 or p_ask <= 0:
        return {"iv_level": "unknown", "note": "ATM无流动性"}

    spread_pct = round((p_ask - p_bid) / p_bid * 100, 1)

    return {
        "iv_level": "normal",  # 暂时不做分位判断，积累数据后启用
        "atm_strike": int(atm['strike'].values[0]),
        "atm_put_bid": round(float(p_bid), 2),
        "atm_put_ask": round(float(p_ask), 2),
        "atm_call_bid": round(float(c_bid), 2),
        "atm_call_ask": round(float(c_ask), 2),
        "put_spread_pct": spread_pct,
        "note": "ATM流动性良好" if spread_pct < 10 else f"ATM价差{spread_pct}%偏宽",
    }


# ═══════════════════════════════════════════
# 模块4: 生成每日结论
# ═══════════════════════════════════════════

# ═══════════════════════════════════════════
# [OBSERVE] 铁秃鹰 + 日历价差 — 只计数
# ═══════════════════════════════════════════

def scan_observe_tier(vcode, variety, cs_results, events, iv_data, chain_data):
    """扫描高级策略：只返回计数，不显示具体参数。
    日历用 IV 期限结构（非 HV），铁蝴蝶/蝶式/比率用现有链数据。
    返回 {strategy_name: count} 或 0。"""
    result = {"iron_condor": 0, "iron_butterfly": 0, "butterfly": 0,
              "ratio_spread": 0, "calendar": 0,
              "variety": vcode, "name": variety["name"]}

    # 铁秃鹰：同品种同时有卖 Put 和卖 Call 信号
    if vcode in cs_results and cs_results[vcode]:
        signals = cs_results[vcode][0] if cs_results[vcode] else []
        puts = [s for s in signals if s.get("tradeable") and s.get("direction") == "put"]
        calls = [s for s in signals if s.get("tradeable") and s.get("direction") == "call"]
        if puts and calls:
            result["iron_condor"] = 1

    # 链数据检查
    if vcode not in chain_data:
        return result
    _, df = chain_data[vcode]

    # 铁蝴蝶：ATM 跨式收 > OTM 保护成本
    try:
        atm_idx = (df['strike'] - variety['futures']).abs().idxmin()
        atm = df.loc[atm_idx]
        p_bid, p_ask = _safe(atm.get('p_bid', 0)), _safe(atm.get('p_ask', 0))
        c_bid, c_ask = _safe(atm.get('c_bid', 0)), _safe(atm.get('c_ask', 0))
        straddle_credit = p_bid + c_bid  # 卖跨式收的钱
        # OTM 保护腿（距 ATM 2 档）
        interval = abs(df['strike'].diff()).median()
        wing_strike_low = atm['strike'] - interval * 2
        wing_strike_high = atm['strike'] + interval * 2
        wing_low = df[df['strike'] == wing_strike_low]
        wing_high = df[df['strike'] == wing_strike_high]
        if not wing_low.empty and not wing_high.empty:
            wing_cost = _safe(wing_low.iloc[0].get('p_ask', 0)) + _safe(wing_high.iloc[0].get('c_ask', 0))
            if straddle_credit > wing_cost:
                result["iron_butterfly"] = 1
    except Exception:
        pass

    # 蝶式：三连续行权价，净支出 < 价差宽度
    try:
        strikes = sorted(df['strike'].unique())
        for i in range(len(strikes) - 2):
            s1, s2, s3 = strikes[i], strikes[i+1], strikes[i+2]
            r1, r2, r3 = df[df['strike'] == s1], df[df['strike'] == s2], df[df['strike'] == s3]
            if r1.empty or r2.empty or r3.empty:
                continue
            cost = (_safe(r1.iloc[0].get('p_ask', 0)) + _safe(r3.iloc[0].get('p_ask', 0)))  # 买两翼
            credit = 2 * _safe(r2.iloc[0].get('p_bid', 0))  # 卖2倍中
            net_debit = cost - credit
            if net_debit < (s2 - s1) * 0.8 and net_debit > 0:
                result["butterfly"] += 1
                break  # 每个品种只计一次
    except Exception:
        pass

    # 比率价差：卖 2×OTM > 买 1×近值，净收
    try:
        for i in range(len(df) - 2):
            near_row = df.iloc[i]
            otm_row = df.iloc[i + 2] if i + 2 < len(df) else None
            if otm_row is None:
                continue
            credit = 2 * _safe(otm_row.get('p_bid', 0))
            cost = _safe(near_row.get('p_ask', 0))
            if credit > cost and cost > 0:
                result["ratio_spread"] = 1
                break
    except Exception:
        pass

    # 日历价差：需要近月+远月两个合约的 IV — 当前只有单合约数据，强制返回 0
    # 时序 IV 不能替代期限结构。等 S2 多合约数据到位后再激活。

    return result


def _save_observe_log(observe_results):
    """后台 CSV：只积累数据，不提供多巴胺"""
    from pathlib import Path
    import csv as _csv
    log_file = Path(__file__).parent.parent / "data" / "observe_signals.csv"
    today = datetime.now().strftime("%Y-%m-%d")
    file_exists = log_file.exists()
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = _csv.writer(f)
        if not file_exists:
            writer.writerow(["date", "variety", "name", "strategy", "count", "note"])
        for r in observe_results:
            if r["iron_condor"] > 0:
                writer.writerow([today, r["variety"], r["name"], "iron_condor", r["iron_condor"], "仅计数"])
            if r["calendar"] > 0:
                writer.writerow([today, r["variety"], r["name"], "calendar", r["calendar"], "期限结构倾斜"])


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="统一扫描器: 虚值倒挂 + 信用价差/买方机会 + 事件 + IV 四合一")
    parser.add_argument('--capital', type=float, default=20000, help='本金(元)，默认20000')
    parser.add_argument('--quick', action='store_true', help='快速模式(只看结论)')
    parser.add_argument('--variety', type=str, default='all', help='指定品种')
    parser.add_argument('--skip-otm', action='store_true', help='跳过虚值倒挂扫描')
    parser.add_argument('--skip-cs', action='store_true', help='跳过信用价差扫描')
    parser.add_argument('--buyer', action='store_true', help='买方模式：扫描 debit spread + straddle/strangle')
    parser.add_argument('--show', type=int, default=10, help='信号详情显示数量，默认10。填0显示全部')
    parser.add_argument('--raw', action='store_true', help='不过滤，显示全部原始信号')
    args = parser.parse_args()

    if args.variety == 'all':
        target = list(VARIETIES.keys())
    else:
        target = [v.strip() for v in args.variety.split(',')]

    now = datetime.now()
    buyer_detail = args.buyer
    print(f"\n{'█'*70}")
    print(f"  🔭 全策略扫描 v3 — {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  {'█'*70}")

    # ── akshare 拉取期权链（REST，不挂）──
    print(f"\n  📡 akshare 拉取期权链中...")
    AK_SYMBOLS = {"沪金": "黄金期权", "铁矿石": "铁矿石期权", "橡胶": "橡胶期权"}
    chain_data = {}
    for vcode in target:
        vname = VARIETIES[vcode]['name']
        symbol = AK_SYMBOLS.get(vname, vname + "期权")
        try:
            contract, df, fp = fetch_option_chain(vcode, symbol)
            VARIETIES[vcode]['futures'] = fp
            chain_data[vcode] = (contract, df)
            iv_est, dte = estimate_iv_from_chain(df, fp, contract)
            print(f"     ✅ {vname:6s} {contract} → 期货 {fp} | 链 {len(df)} 档"
                  f"{' | IV≈' + f'{iv_est:.1%}' if iv_est else ''}")
        except Exception as e:
            print(f"     ❌ {vname:6s} → {str(e)[:50]}")
    print()

    # ── 事件数据（买方模式需要提前获取） ──
    events = get_upcoming_events(days=14, varieties=target)

    # ── 模块1: 虚值倒挂 ──
    otm_results = {}
    cs_results = {}
    buyer_results = {}
    if not args.skip_otm:
        print(f"\n  ┌─ 虚值倒挂扫描 ({len(target)}品种)")
        for vcode in target:
            variety = VARIETIES[vcode]
            if vcode in chain_data:
                contract, df = chain_data[vcode]
                signals, summary = scan_deep_otm(vcode, variety, contract, df, variety['futures'], args.capital)
            else:
                signals, summary = [], "❌ 无链数据"
            otm_results[vcode] = (signals, summary)
            tradeable_n = len([s for s in signals if s['tradeable']])
            icon = "🟢" if tradeable_n > 0 else "⚫"
            print(f"  │ {icon} {variety['name']:6s}: {summary}")
        print(f"  └─ 共 {sum(len(s[0]) for s in otm_results.values())} 信号, "
              f"{sum(1 for s in otm_results.values() for s2 in s[0] if s2['tradeable'])} 可交易")

    # ── 模块2a: 信用价差（卖方）──
    if not args.skip_cs:
        print(f"\n  ┌─ 信用价差扫描 ({len(target)}品种)")
        for vcode in target:
            variety = VARIETIES[vcode]
            if vcode in chain_data:
                contract, df = chain_data[vcode]
                signals, summary = scan_credit_spreads(vcode, variety, contract, df, variety['futures'], args.capital)
            else:
                signals, summary = [], "❌ 无链数据"
            cs_results[vcode] = (signals, summary)
            tradeable_n = len([s for s in signals if s['tradeable']])
            icon = "🟡" if tradeable_n > 0 else "⚫"
            print(f"  │ {icon} {variety['name']:6s}: {summary}")
        total_cs = sum(len(s[0]) for s in cs_results.values())
        total_cs_ok = sum(1 for s in cs_results.values() for s2 in s[0] if s2['tradeable'])
        print(f"  └─ 共 {total_cs} 信号, {total_cs_ok} 可交易")

    # ── 模块2b: 买方价差+跨式（分两组存，统一扫描）──
    buyer_results = {}
    if not args.skip_cs:
        for vcode in target:
            variety = VARIETIES[vcode]
            if vcode in chain_data:
                contract, df = chain_data[vcode]
                signals, summary = scan_buyer_opportunities(
                    vcode, variety, contract, df, variety['futures'], events, args.capital)
            else:
                signals, summary = [], "❌ 无链数据"
            buyer_results[vcode] = (signals, summary)

    # ── 模块2c: 单腿买方 ──
    single_leg_results = {}
    if not args.skip_cs:
        for vcode in target:
            variety = VARIETIES[vcode]
            if vcode in chain_data:
                contract, df = chain_data[vcode]
                iv_pct = _estimate_iv_percentile(df, variety['futures'])
                signals = scan_single_leg_buyer(
                    df, variety['futures'], variety['name'], contract, vcode,
                    events, args.capital, variety['multiplier'], iv_pct)
            else:
                signals = []
            single_leg_results[vcode] = signals

    # ── PAPER 扫描汇总 ──
    all_buyer_signals = []
    for vcode, (signals, _) in buyer_results.items():
        all_buyer_signals.extend(signals)
    buyer_ok = [s for s in all_buyer_signals if s['tradeable']]
    spreads_n = len([s for s in buyer_ok if 'spread' in str(s.get('strategy',''))])
    straddles_n = len([s for s in buyer_ok if 'straddle' in str(s.get('strategy','')) or 'strangle' in str(s.get('strategy',''))])

    all_sl = []
    for vcode, signals in single_leg_results.items():
        all_sl.extend(signals)
    sl_ok = [s for s in all_sl if s['tradeable']]
    sl_events_n = len([s for s in sl_ok if 'event' in str(s.get('strategy',''))])
    sl_trends_n = len([s for s in sl_ok if 'trend' in str(s.get('strategy',''))])

    print(f"\n  ┌─ [PAPER] 买方价差: {spreads_n}个 | 跨式/宽跨式: {straddles_n}个 | 单腿·事件: {sl_events_n}个 | 单腿·趋势: {sl_trends_n}个")

    # ── 模块2d: 铁秃鹰 + 铁蝴蝶 + 蝶式 + 比率 + 日历 [OBSERVE] ──
    iv_data = {}  # 提前初始化，IV 评估在后面填充
    observe_results = []
    for vcode in target:
        variety = VARIETIES[vcode]
        observe_results.append(scan_observe_tier(vcode, variety, cs_results, events, iv_data, chain_data))
    try:
        _save_observe_log(observe_results)
    except Exception:
        pass

    # ── 模块3: 事件 ──
    print(f"\n  ┌─ 事件日历")
    # 持续性地缘事件（始终显示，无倒计时）
    ongoing = [e for e in events if e.get('days_until') == -1]
    for ev in ongoing:
        tag = "[例行]" if ev.get('routine', True) else "[⚠非例行]"
        print(f"  │ 🔥🔄 {tag} {ev['title']}  [{', '.join(ev['variety_names'])}]")
        if ev.get('description'):
            print(f"  │    {ev['description'][:80]}")
    # 固定日期事件
    high_events = [e for e in events if e['impact'] == 'high' and e.get('days_until', -1) >= 0]
    for ev in high_events[:5]:
        tag = "[例行]" if ev.get('routine', True) else "[⚠非例行]"
        print(f"  │ D-{ev['days_until']:<3} 🔥 {tag} {ev['title']}  [{', '.join(ev['variety_names'])}]")
    medium_in_window = [e for e in events if e['impact'] == 'medium' and 0 <= e.get('days_until', -1) <= 5]
    for ev in medium_in_window[:3]:
        tag = "[例行]" if ev.get('routine', True) else "[⚠非例行]"
        print(f"  │ D-{ev['days_until']:<3} ⚡ {tag} {ev['title']}  [{', '.join(ev['variety_names'])}]")
    if not ongoing and not high_events and not medium_in_window:
        print(f"  │ 无近期高影响事件")
    total = len(ongoing) + len(high_events) + len(medium_in_window)
    print(f"  └─ 共 {len(events)} 个事件（含 {len(ongoing)} 个持续中）")

    # ── 模块4: IV（仅快速采样关键品种）
    key_varieties = [v for v in target if v in ['c', 'm', 'ta', 'au', 'rm']]
    if not args.quick:
        print(f"\n  ┌─ IV/流动性采样 (关键品种ATM)")
        for vcode in key_varieties[:5]:
            variety = VARIETIES[vcode]
            if vcode in chain_data:
                contract, df = chain_data[vcode]
                iv = assess_iv_environment(vcode, variety, contract, df, variety['futures'])
            else:
                iv = {"iv_level": "unknown", "note": "无链数据"}
            iv_data[vcode] = iv
            sp = iv.get('put_spread_pct', 999)
            icon = "✅" if sp < EVENT_SPREAD_MAX else ("⚠️" if sp < 20 else "❌")
            print(f"  │ {icon} {variety['name']:6s}: ATM价差 {sp}% | {iv.get('note','')}")
        print(f"  └─")

    # ── 三层结论 ──
    # 事件品种标记
    event_vcodes = set()
    for e in events:
        if e['impact'] == 'high' and e['days_until'] <= 7:
            for vn in e.get('variety_names', []):
                for vc, vi in VARIETIES.items():
                    if vi['name'] == vn:
                        event_vcodes.add(vc)

    buyer_detail = args.buyer

    print(f"\n{'═'*70}")
    print(f"  📊 三层信号汇总")
    print(f"  {'═'*70}")

    # ── [EXEC] 卖方 ──
    print(f"\n  ⚠️ IV分位：Scanner=工程近似 | Collector=8天历史 | 均无统计显著性 | Data≥30天后可参考")
    print(f"\n  🟢 [EXEC] 卖方信用价差 — 可执行")
    all_cs = []
    for vcode, (signals, _) in cs_results.items():
        all_cs.extend(signals)
    cs_ok = [s for s in all_cs if s['tradeable'] and s.get('rr_ratio', 0) >= EXEC_RR_MIN]
    iv_hv = load_latest_iv_hv()  # 读最新 IV-HV 数据，给每个信号打分
    iv_percentiles = load_iv_percentiles()  # IV Collector 历史分位
    filtered = []  # 去重后的真实机会数——汇总行与显示同口径
    if cs_ok:
        seen = {}
        for s in sorted(cs_ok, key=lambda x: x['rr_ratio'], reverse=True):
            key = f"{s['variety']}_{s['contract']}"
            if key not in seen:
                seen[key] = s
                s['_event_warning'] = s['variety'] in event_vcodes
                # 查 IV-HV 分层
                hv_info = iv_hv.get(s['contract'])
                if hv_info:
                    s['_iv_hv_spread'], s['_iv_hv_tier'], s['_iv_hv_action'] = iv_hv_tier(
                        hv_info['iv_est'], hv_info['hv_20d'])
                else:
                    s['_iv_hv_spread'], s['_iv_hv_tier'], s['_iv_hv_action'] = None, "⚠️无HV数据", ""
                filtered.append(s)
        limit = args.show if args.show > 0 else len(filtered)
        for i, s in enumerate(filtered[:limit], 1):
            warn = " ⚠️有事件" if s.get('_event_warning') else ""
            tier_icon = "🟢" if s.get('tier') == 'green' else "🟡"
            opt_type = "C" if s['sell_strike'] < s['buy_strike'] else "P"
            # IV-HV 分层标签
            spread_str = f"IV-HV {s['_iv_hv_spread']*100:+.1f}% " if s['_iv_hv_spread'] is not None else ""
            tier_str = f"[{spread_str}| {s['_iv_hv_tier']} · {s['_iv_hv_action']}]" if s['_iv_hv_action'] else f"[{s['_iv_hv_tier']}]"
            print(f"    [{i}] {tier_icon} {s['name']} {s['contract']} "
                  f"卖{opt_type}{s['sell_strike']}/{s['buy_strike']}  "
                  f"净收 ¥{s['net_premium']}  卖bid ¥{s.get('sell_bid','?')} 买ask ¥{s.get('buy_ask','?')}  "
                  f"盈亏比 {s['rr_ratio']}:1  OTM {s.get('otm_pct','?')}%{warn}")
            print(f"        {tier_str}")
            tp = round(s['max_profit'] * 0.5, 0)
            print(f"        止盈 ¥{tp:.0f}/手  止损预警: {opt_type}{s['buy_strike']}")
    else:
        iv_note_parts = []
        for vcode in target:
            if vcode in iv_data:
                iv = iv_data[vcode]
                if isinstance(iv, dict) and iv.get("iv_level"):
                    iv_note_parts.append(f"{VARIETIES[vcode]['name']} IV {iv.get('iv_level','?')}")
        if iv_note_parts:
            print(f"    今日无卖方机会。{'; '.join(iv_note_parts[:4])}")
        else:
            print(f"    今日无卖方机会。")

    # ── 接近 EXEC 但盈亏比不足（RR_MIN ≤ rr < EXEC_RR_MIN）
    near_miss = [s for s in all_cs if s['tradeable'] and
                 RR_MIN <= s.get('rr_ratio', 0) < EXEC_RR_MIN]
    if near_miss:
        print(f"\n  🟠 [NEAR] 接近 EXEC 但盈亏比不足（{RR_MIN}≤rr<{EXEC_RR_MIN}）：")
        near_sorted = sorted(near_miss, key=lambda x: x.get('rr_ratio', 0), reverse=True)
        for s in near_sorted[:3]:
            opt_t = "C" if s.get('sell_strike', 0) < s.get('buy_strike', 0) else "P"
            print(f"    {s['name']} {s['contract']} 卖{opt_t}{s['sell_strike']}/{s['buy_strike']}  "
                  f"净收 ¥{s['net_premium']}  rr={s['rr_ratio']}  OTM {s.get('otm_pct','?')}%")

    # ── 注入 IV Collector 历史分位到买方信号 ──
    for _vcode, (_signals, _) in buyer_results.items():
        for _s in _signals:
            _contract = _s.get('contract', '')
            _cl = iv_percentiles.get(_contract, (None, 0))
            _s['_cl_pct'] = _cl[0]
            _s['_cl_days'] = _cl[1]
    for _vcode, _sl_signals in single_leg_results.items():
        for _s in (_sl_signals or []):
            _contract = _s.get('contract', '')
            _cl = iv_percentiles.get(_contract, (None, 0))
            _s['_cl_pct'] = _cl[0]
            _s['_cl_days'] = _cl[1]

    # ── [PAPER] 买方 ──
    print(f"\n  🟡 [PAPER] 买方组合（价差/跨式/宽跨式）— 纸面跟踪")
    all_buyer = []
    for vcode, (signals, _) in buyer_results.items():
        all_buyer.extend(signals)
    buyer_ok = [s for s in all_buyer if s['tradeable']]
    spreads_ok = [s for s in buyer_ok if 'spread' in str(s.get('strategy',''))]
    straddles_ok = [s for s in buyer_ok if 'straddle' in str(s.get('strategy','')) or 'strangle' in str(s.get('strategy',''))]

    # ── 买方价差（2腿·有保护）──
    if spreads_ok:
        print(f"\n  🟡 [PAPER] 买方价差（2腿·封顶亏损）— 纸面跟踪")
        seen = {}
        for s in sorted(spreads_ok, key=lambda x: (x.get('color')=='green', x.get('profit_ratio',0)), reverse=True):
            key = f"{s['variety']}_{s['contract']}_{s.get('strategy','')}"
            if key not in seen:
                seen[key] = s
        for s in list(seen.values())[:args.show or 5]:
            color = "🟢" if s.get('color')=='green' else "🟡"
            opt_t = "C" if 'call' in str(s.get('strategy','')).lower() else "P"
            ev_str = f"D-{s.get('event_days','?')}" if s.get('event_days') else ""
            print(f"    {color} {s['name']} {s['contract']} "
                  f"买{opt_t}{s.get('buy_strike','?')}/卖{opt_t}{s.get('sell_strike','?')}  "
                  f"成本≈¥{s.get('net_debit','?')}  买ask ¥{s.get('buy_ask','?')} 卖bid ¥{s.get('sell_bid','?')}  "
                  f"盈亏比 {s.get('profit_ratio','?')}:1  ScP{s.get('iv_percentile','?')}{_cl_str(s)}  {ev_str}")
        print(f"    ⚠️ 共 {len(spreads_ok)} 个。不执行，仅纸面。")
    else:
        print(f"\n  🟡 [PAPER] 买方价差（2腿·封顶亏损）— 今日无")

    # ── 买方跨式/宽跨式（2腿·赌波动）──
    if straddles_ok:
        print(f"\n  🟡 [PAPER] 买方跨式/宽跨式（2腿·赌波动）— 纸面跟踪")
        for s in straddles_ok[:args.show or 3]:
            color = "🟢" if s.get('color')=='green' else "🟡"
            ev_str = f"D-{s.get('event_days','?')}" if s.get('event_days') else ""
            # strangle 两腿分开，straddle 同一 ATM 行权价
            if s.get('call_strike') is not None:
                legs = f"C{s.get('call_strike')}/P{s.get('put_strike')}"
            else:
                legs = f"ATM {s.get('strike','?')}"
            print(f"    {color} {s['name']} {s['contract']} {s.get('strategy','')} {legs}  "
                  f"成本≈¥{s.get('net_cost','?')}  Cask ¥{s.get('call_ask','N/A')} Pask ¥{s.get('put_ask','N/A')}  "
                  f"预期波动 ¥{s.get('expected_move','?')}  {ev_str}")
        print(f"    ⚠️ 共 {len(straddles_ok)} 个。不执行，仅纸面。")
    else:
        print(f"\n  🟡 [PAPER] 买方跨式/宽跨式（2腿·赌波动）— 今日无（缺IV<30%+事件）")

    # ── [PAPER] 单腿买方 ──
    all_sl = []
    for vcode, signals in single_leg_results.items():
        all_sl.extend(signals)
    sl_ok = [s for s in all_sl if s['tradeable']]
    if sl_ok:
        events_sl = [s for s in sl_ok if 'event' in str(s.get('strategy',''))]
        trends_sl = [s for s in sl_ok if 'trend' in str(s.get('strategy',''))]
        if events_sl:
            print(f"\n  🟡 [PAPER] 买单腿·事件触发 — 纸面跟踪")
            for s in events_sl[:5]:
                color = "🟢" if s.get('color')=='green' else "🟡"
                opt_t = "Call" if 'call' in str(s.get('strategy','')) else "Put"
                print(f"    {color} {s['name']} 买{opt_t} {s.get('strike','?')}  "
                      f"OTM {s.get('otm_pct','?')}%  权利金≈¥{s.get('cost','?')}  ask ¥{s.get('ask','N/A')}  "
                      f"ScP{s.get('iv_percentile','?')}{_cl_str(s)}")
            print(f"    ⚠️ {len(events_sl)} 个事件触发。不执行，仅纸面。")
        else:
            print(f"\n  🟡 [PAPER] 买单腿·事件触发 — 今日无（日历无D-2~D-7事件）")
        if trends_sl:
            print(f"\n  🟡 [PAPER] 买单腿·趋势触发 — 纸面跟踪")
            for s in trends_sl[:5]:
                color = "🟢" if s.get('color')=='green' else "🟡"
                opt_t = "Call" if 'call' in str(s.get('strategy','')) else "Put"
                print(f"    {color} {s['name']} 买{opt_t} {s.get('strike','?')}  "
                      f"OTM {s.get('otm_pct','?')}%  权利金≈¥{s.get('cost','?')}  ask ¥{s.get('ask','N/A')}  "
                      f"{s.get('trigger','')}  ScP{s.get('iv_percentile','?')}{_cl_str(s)}")
            print(f"    ⚠️ {len(trends_sl)} 个趋势触发单腿信号。不执行，仅纸面。")

    # ── [OBSERVE] 铁秃鹰 + 铁蝴蝶 + 蝶式 + 比率 + 日历 ──
    print(f"\n  ⚪ [OBSERVE] 高级策略 — 仅计数，S2 解锁")
    obs_strategies = {
        "iron_condor": "铁秃鹰", "iron_butterfly": "铁蝴蝶",
        "butterfly": "蝶式", "ratio_spread": "比率价差", "calendar": "日历价差"}
    obs_total = 0
    obs_lines = []
    for key, label in obs_strategies.items():
        total = sum(r.get(key, 0) for r in observe_results)
        obs_total += total
        if total > 0:
            names = [r["name"] for r in observe_results if r.get(key, 0) > 0]
            obs_lines.append(f"    {label}：{total} 个（{', '.join(names)}）")
    if obs_lines:
        for line in obs_lines:
            print(line)
        print(f"    → 共 {obs_total} 个机会。仅计数，不做。后台 CSV 在积累。")
    else:
        print(f"    今日无 OBSERVE 信号。数据积累中。")

    # ── [IGNORE] S1 不扫，仅提示策略存在 ──
    print(f"\n  🔘 [IGNORE] 未扫描（需额外数据或S2+解锁）")
    print(f"    合成期货 · 备兑Call · 品种间价差 · 对角价差 · 跨市场套利 · 期货对冲")

    # ── 汇总行 ──
    print(f"\n  {'─'*70}")
    exec_n = len(filtered)
    paper_n = len(buyer_ok) + len(sl_ok)
    print(f"  📊 {exec_n} 可执行 + {paper_n} 纸面 + {obs_total} 观察 + 6 未扫描")
    if exec_n == 0:
        # ── 干旱智能总结：从 iv_hv 汇总 IV-HV 卖方窗口 ──
        seller_windows = []
        for contract, hv_info in iv_hv.items():
            spread = hv_info['iv_est'] - hv_info['hv_20d']
            if spread >= 0.03:
                # contract like "ma2609" → vcode = letters part
                vcode = re.match(r'([a-z]+)', contract)
                name = VARIETIES.get(vcode.group(1), {}).get('name', contract) if vcode else contract
                seller_windows.append(f"{name}({spread*100:+.1f}%)")
        if seller_windows:
            print(f"  💧 卖方窗口：{', '.join(seller_windows)}，但无可执行腿组合。")
            print(f"    系统在拦，不在漏。")
        else:
            print(f"  💧 今日无卖方窗口（IV-HV ≥3% 品种=0）。")
        if paper_n > 0:
            print(f"  📋 买方/单腿纸面窗口已标出（共 {paper_n} 个），不执行仅跟踪。")
        print(f"  📖 无信号日操作规程 → monitoring-rules.md「无信号日操作规程」")
    print(f"  {'═'*70}\n")



if __name__ == '__main__':
    main()
