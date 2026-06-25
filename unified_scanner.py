#!/usr/bin/env python3
"""
统一扫描器：虚值倒挂 + 事件驱动 + IV环境 — 三合一
─────────────────────────────────────────────
每天跑一次，告诉你三件事：
  1. 今天有没有虚值倒挂可以做？
  2. 近期有没有事件值得蹲？
  3. 当前 IV 环境适合买方还是卖方？

输出结论：「今天做什么、不做什么、为什么」

用法:
  python3 unified_scanner.py                          # 完整扫描
  python3 unified_scanner.py --capital 10000          # 含资金分配建议
  python3 unified_scanner.py --quick                  # 快速版(只看结论)
"""

import sys
import os
import json
import argparse
import pandas as pd
from datetime import datetime, date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import akshare as ak
from event_calendar import get_upcoming_events, VARIETIES as EV_VARIETIES

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

VARIETIES = {
    "au": {"symbol": "黄金期权",   "futures": 870,  "name": "沪金",    "multiplier": 1000},
    "m":  {"symbol": "豆粕期权",   "futures": 2800, "name": "豆粕",    "multiplier": 10},
    "c":  {"symbol": "玉米期权",   "futures": 2300, "name": "玉米",    "multiplier": 10},
    "cf": {"symbol": "棉花期权",   "futures": 13500,"name": "棉花",    "multiplier": 5},
    "sr": {"symbol": "白糖期权",   "futures": 5600, "name": "白糖",    "multiplier": 10},
    "ta": {"symbol": "PTA期权",    "futures": 4800, "name": "PTA",     "multiplier": 5},
    "i":  {"symbol": "铁矿石期权", "futures": 780,  "name": "铁矿石",  "multiplier": 100},
    "ru": {"symbol": "橡胶期权",   "futures": 17000,"name": "橡胶",    "multiplier": 10},
    "ma": {"symbol": "甲醇期权",   "futures": 2450, "name": "甲醇",    "multiplier": 10},
    "rm": {"symbol": "菜籽粕期权", "futures": 2500, "name": "菜籽粕",  "prefix": "rm", "multiplier": 10},
}

MAX_PREMIUM = 5.0
MAX_SPREAD_PCT = 10
OTM_PCT = 0.08


def _safe(v):
    return v if not pd.isna(v) else 0


def _spread(bid, ask):
    if bid and ask and bid > 0:
        return round((ask - bid) / bid * 100, 1)
    return 999


# ═══════════════════════════════════════════
# 模块1: 虚值倒挂扫描
# ═══════════════════════════════════════════

def scan_deep_otm(vcode, variety, capital=None):
    """扫描单个品种虚值看跌倒挂"""
    symbol = variety['symbol']
    futures = variety['futures']
    mult = variety['multiplier']
    otm_boundary = int(futures * (1 - OTM_PCT))

    try:
        contracts_df = ak.option_commodity_contract_sina(symbol=symbol)
        contracts = contracts_df['合约'].tolist()
    except Exception:
        return [], f"❌ 获取失败"

    all_signals = []

    for contract in contracts:
        try:
            df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=contract)
        except Exception:
            continue

        if df is None or df.empty:
            continue

        df = df.rename(columns={
            '行权价': 'strike', '看跌合约-最新价': 'p_last',
            '看跌合约-买价': 'p_bid', '看跌合约-卖价': 'p_ask', '看跌合约-持仓量': 'p_oi',
        })

        otm_puts = df[df['strike'] < otm_boundary].copy()
        if otm_puts.empty:
            continue

        rows = []
        for _, row in otm_puts.iterrows():
            p_last = row['p_last'] if not pd.isna(row['p_last']) else None
            p_bid = _safe(row['p_bid'])
            p_ask = _safe(row['p_ask'])
            if p_last is None or p_last <= 0 or p_last > MAX_PREMIUM:
                continue
            if p_bid <= 0:  # 必须有买价 — 否则卖了出不来
                continue
            rows.append({
                'strike': int(row['strike']),
                'price': p_last, 'bid': p_bid, 'ask': p_ask,
                'oi': int(row['p_oi']) if not pd.isna(row['p_oi']) else 0,
            })

        for i in range(len(rows) - 1):
            cur, nxt = rows[i], rows[i + 1]
            # cur=低行权价, nxt=高行权价
            # 正常: cur便宜 < nxt贵 (行权价越高Put越值钱)
            # 倒挂: cur贵 > nxt便宜 (行权价高的Put反而便宜) ← 这才是异常
            if cur['price'] > nxt['price']:
                # 买nxt（高行权价、被低估的Put），等价格回归到cur之上
                profit_pct = round((cur['price'] - nxt['price']) / nxt['price'] * 100, 1)
                sp = _spread(nxt['bid'], nxt['ask'])
                net = round(profit_pct - sp, 1)
                cost = nxt['price'] * mult
                tradeable = sp < profit_pct and sp < MAX_SPREAD_PCT and nxt['bid'] > 0

                if capital and cost > capital * 0.05:
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
# 模块2: IV 环境判断
# ═══════════════════════════════════════════

def assess_iv_environment(vcode, variety):
    """
    用 ATM 期权的价格水平做简易 IV 代理判断。
    规则: 比较 ATM Put 买价 vs 历史大致范围。
    真正 IV 分位数需要积累数周数据后才能启用。
    """
    symbol = variety['symbol']
    futures = variety['futures']

    try:
        contracts_df = ak.option_commodity_contract_sina(symbol=symbol)
        contracts = contracts_df['合约'].tolist()
        if not contracts:
            return {"iv_level": "unknown", "note": "无合约数据"}
        main_contract = contracts[0]

        df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=main_contract)
        df = df.rename(columns={
            '行权价': 'strike', '看跌合约-买价': 'p_bid', '看跌合约-卖价': 'p_ask',
            '看涨合约-买价': 'c_bid', '看涨合约-卖价': 'c_ask',
        })

        # 找最接近平值的行权价
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
    except Exception as e:
        return {"iv_level": "unknown", "note": str(e)[:60]}


# ═══════════════════════════════════════════
# 模块3: 生成每日结论
# ═══════════════════════════════════════════

def generate_conclusion(otm_results, events, iv_data, capital=None):
    """根据三个模块的结果，生成今日行动建议"""
    print(f"\n{'═'*70}")
    print(f"  📋 今日结论")
    print(f"{'═'*70}")

    # 1. 虚值倒挂
    all_otm_tradeable = []
    for vcode, (signals, _) in otm_results.items():
        for s in signals:
            if s['tradeable']:
                all_otm_tradeable.append(s)

    if all_otm_tradeable:
        all_otm_tradeable.sort(key=lambda s: s['net_pct'], reverse=True)
        top = all_otm_tradeable[0]
        print(f"\n  🟢 虚值层: 有{len(all_otm_tradeable)}个可交易信号")
        print(f"     最佳: {top['name']} {top['contract']} P{top['buy_strike']}@{top['buy_price']:.2f}")
        print(f"     净利 +{top['net_pct']}% | 成本 ¥{top['cost']:.0f}/手")
        if capital:
            max_position = int(capital * 0.05 / top['cost']) if top['cost'] > 0 else 0
            print(f"     建议: 最多买{max_position}手 (≤5%本金)")
    else:
        print(f"\n  ⚫ 虚值层: 今日无信号")
        print(f"     → 正常。大部分日子如此。")

    # 2. 事件
    high_events = [e for e in events if e['impact'] == 'high' and e['days_until'] <= 5]
    medium_events = [e for e in events if e['impact'] == 'high' and e['days_until'] <= 10]
    near_events = [e for e in events if e['days_until'] <= 3]

    if high_events:
        ev = high_events[0]
        print(f"\n  🔴 事件层: D-{ev['days_until']} {ev['title']}")
        vars_str = ", ".join(ev['variety_names'])
        print(f"     关联品种: {vars_str}")
        print(f"     历史波动: ±{ev['expected_move_pct']}%")
        print(f"     建议策略: {ev['best_strategy']}")
        if capital and ev['days_until'] <= 3:
            event_budget = capital * 0.20
            print(f"     预算: ≤¥{event_budget:.0f} (20%本金)")
        if ev['days_until'] <= 2:
            print(f"     ⚡ 可以进场了")
        elif ev['days_until'] <= 5:
            print(f"     ⏳ 准备资金中")
    elif medium_events:
        ev = medium_events[0]
        print(f"\n  🟡 事件层: D-{ev['days_until']} {ev['title']}")
        print(f"     还有时间，先跟踪品种流动性")
    elif near_events:
        print(f"\n  🟡 事件层: 有{days_until}天内的中等事件，但非高影响")
    else:
        print(f"\n  ⚫ 事件层: 近期无高影响事件")

    # 3. IV 环境
    good_liquidity = sum(1 for v, d in iv_data.items() if d.get('put_spread_pct', 999) < 10)
    print(f"\n  🔵 环境层: {good_liquidity}/{len(iv_data)}品种ATM流动性良好 (价差<10%)")
    if good_liquidity < 3:
        print(f"     ⚠️ 多数品种流动性偏紧，缩小挂单规模")

    # 4. 综合建议
    print(f"\n{'─'*70}")
    if all_otm_tradeable and high_events:
        print(f"  🎯 今日: 虚值有信号 + 事件在接近 → 双重机会，优先事件（资金有限）")
    elif all_otm_tradeable:
        print(f"  🎯 今日: 虚值有信号 → 小仓位练手，不超过5%本金")
    elif high_events:
        print(f"  🎯 今日: 无虚值信号但事件在接近 → 准备事件资金，今天不做")
    else:
        print(f"  🎯 今日: 两层都不触发 → 跑闪卡，积累品种认知。正常的一天。")
    print(f"{'─'*70}\n")


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="统一扫描器: 虚值倒挂 + 事件 + IV 三合一")
    parser.add_argument('--capital', type=float, default=None, help='本金(元)')
    parser.add_argument('--quick', action='store_true', help='快速模式(只看结论)')
    parser.add_argument('--variety', type=str, default='all', help='指定品种')
    parser.add_argument('--skip-otm', action='store_true', help='跳过虚值扫描(只看事件)')
    args = parser.parse_args()

    if args.variety == 'all':
        target = list(VARIETIES.keys())
    else:
        target = [v.strip() for v in args.variety.split(',')]

    now = datetime.now()
    print(f"\n{'█'*70}")
    print(f"  🔭 统一扫描器 — {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  {'█'*70}")

    # ── 模块1: 虚值倒挂 ──
    otm_results = {}
    if not args.skip_otm:
        print(f"\n  ┌─ 虚值倒挂扫描 ({len(target)}品种)")
        for vcode in target:
            variety = VARIETIES[vcode]
            signals, summary = scan_deep_otm(vcode, variety, args.capital)
            otm_results[vcode] = (signals, summary)
            tradeable_n = len([s for s in signals if s['tradeable']])
            icon = "🟢" if tradeable_n > 0 else "⚫"
            print(f"  │ {icon} {variety['name']:6s}: {summary}")
        print(f"  └─ 共 {sum(len(s[0]) for s in otm_results.values())} 信号, "
              f"{sum(1 for s in otm_results.values() for s2 in s[0] if s2['tradeable'])} 可交易")

    # ── 模块2: 事件 ──
    events = get_upcoming_events(days=14, varieties=target)
    print(f"\n  ┌─ 事件日历 (未来14天)")
    high_events = [e for e in events if e['impact'] == 'high']
    for ev in high_events[:5]:
        print(f"  │ D-{ev['days_until']:<3} 🔥 {ev['title']}  [{', '.join(ev['variety_names'])}]")
    medium_in_window = [e for e in events if e['impact'] == 'medium' and e['days_until'] <= 5]
    for ev in medium_in_window[:3]:
        print(f"  │ D-{ev['days_until']:<3} ⚡ {ev['title']}  [{', '.join(ev['variety_names'])}]")
    if not high_events and not medium_in_window:
        print(f"  │ 无近期高影响事件")
    print(f"  └─ 共 {len(events)} 个事件")

    # ── 模块3: IV（仅快速采样关键品种）
    iv_data = {}
    key_varieties = [v for v in target if v in ['c', 'm', 'ta', 'au', 'rm']]
    if not args.quick:
        print(f"\n  ┌─ IV/流动性采样 (关键品种ATM)")
        for vcode in key_varieties[:5]:
            iv = assess_iv_environment(vcode, VARIETIES[vcode])
            iv_data[vcode] = iv
            sp = iv.get('put_spread_pct', 999)
            icon = "✅" if sp < 10 else ("⚠️" if sp < 20 else "❌")
            print(f"  │ {icon} {VARIETIES[vcode]['name']:6s}: ATM价差 {sp}% | {iv.get('note','')}")
        print(f"  └─")

    # ── 结论 ──
    if not args.quick:
        # 展开所有虚值信号详情
        all_signals = []
        for vcode, (signals, _) in otm_results.items():
            all_signals.extend(signals)
        if all_signals:
            tradeable_signals = [s for s in all_signals if s['tradeable']]
            if tradeable_signals:
                print(f"\n  ┌─ 可交易信号详情")
                for i, s in enumerate(sorted(tradeable_signals, key=lambda x: x['net_pct'], reverse=True)[:10], 1):
                    print(f"  │ [{i}] {s['name']} {s['contract']} "
                          f"P{s['buy_strike']}({s['buy_price']:.2f}) < P{s['ref_strike']}({s['ref_price']:.2f})")
                    print(f"  │     净利 +{s['net_pct']}% | 成本 ¥{s['cost']:.0f} | "
                          f"买{s['buy_bid']:.2f}/卖{s['buy_ask']:.2f}")
                print(f"  └─")

    generate_conclusion(otm_results, events, iv_data, args.capital)


if __name__ == '__main__':
    main()
