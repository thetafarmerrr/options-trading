#!/usr/bin/env python3
"""
T3: 偏差检测 — 吾剑策略版（含滑点）
────────────────────────────
直接扫描期权链 CSV → 输出定价偏差信号 + 可交易性判断。
人做验证判断（价差、流动性、事件背景），计算机做扫描。

用法:
  python3 anomaly_checker.py --prefix au              # 扫描沪金最新数据
  python3 anomaly_checker.py --compare --capital 10000 # 含操作建议
  python3 anomaly_checker.py --mode silent             # 只输出信号数量

规则: 只做买方 + 低价为王 + 日内了结 + 14:30铁律 + 价差宽不做
"""

import argparse, sys, os, pandas as pd, re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

APPROX_FUTURES_PRICE = 870
MAX_PREMIUM = 5.0
STRIKE_RANGE_BELOW = 200
TRADE_DEADLINE = (14, 30)
MAX_SPREAD_PCT = 10  # 价差超过此值不推荐
SPREAD_RULE = "spread < profit"  # 实际规则: 价差必须小于理论利润


def load_latest(contract=None, prefix=None):
    if not os.path.exists(DATA_DIR):
        print("✗ 请先拉取数据"); sys.exit(1)
    files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith('.csv')], reverse=True)
    if prefix: files = [f for f in files if f.startswith(prefix)]
    if contract: files = [f for f in files if f.startswith(contract)]
    if not files: print("✗ 无数据"); sys.exit(1)
    path = os.path.join(DATA_DIR, files[0])
    return pd.read_csv(path), files[0].split('_')[0], files[0].split('_')[1].replace('.csv', '')


def _safe(v):
    return v if not pd.isna(v) else 0


def _spread(bid, ask):
    """计算价差百分比，无效返回大数"""
    if bid and ask and bid > 0:
        return round((ask - bid) / bid * 100, 1)
    return 999


def _make_signal(typ, strike, price, bid, ask, target_price, ref_strike):
    profit = round(target_price - price, 2)
    pnl_pct = round(profit / price * 100, 1) if price > 0 else 0
    sp = _spread(bid, ask)
    prefix = 'C' if 'C' in str(typ) else 'P'
    return {
        'type': typ,
        'strike': strike, 'price': round(price, 2),
        'bid': round(bid, 2), 'ask': round(ask, 2),
        'spread_pct': sp,
        'target_price': round(target_price, 2), 'ref_strike': ref_strike,
        'profit_pct': pnl_pct, 'net_pct': round(pnl_pct - sp, 1),
        'action': f"买{prefix}{strike}@{price:.2f}(买{bid:.2f}/卖{ask:.2f}) → {target_price:.2f}",
        'tradeable': sp < pnl_pct,  # 价差必须小于理论利润，否则滑点吃掉利润
    }


def check_call_inversions(df):
    """看涨倒挂"""
    signals = []
    rows = df[(df['行权价'] > APPROX_FUTURES_PRICE + 50) &
              (df['行权价'] <= APPROX_FUTURES_PRICE + STRIKE_RANGE_BELOW)]
    prev = None
    for _, row in rows.iterrows():
        s, p, bid, ask = int(row['行权价']), row['C_最新价'], _safe(row['C_买价']), _safe(row['C_卖价'])
        if pd.isna(p) or p <= 0 or p > MAX_PREMIUM: prev = (s, p, bid, ask); continue
        if prev and not pd.isna(prev[1]) and prev[1] > 0 and prev[1] <= MAX_PREMIUM:
            if p > prev[1]:
                signals.append(_make_signal('看涨倒挂', prev[0], prev[1], prev[2], prev[3], p, s))
        prev = (s, p, bid, ask)
    return signals


def check_put_inversions(df):
    """看跌倒挂 — 行权价高的Put反而更便宜"""
    signals = []
    rows = df[(df['行权价'] >= APPROX_FUTURES_PRICE - STRIKE_RANGE_BELOW) &
              (df['行权价'] < APPROX_FUTURES_PRICE - 50)]
    prev = None
    for _, row in rows.iterrows():
        s, p, bid, ask = int(row['行权价']), row['P_最新价'], _safe(row['P_买价']), _safe(row['P_卖价'])
        if pd.isna(p) or p <= 0 or p > MAX_PREMIUM: prev = (s, p, bid, ask); continue
        if prev and not pd.isna(prev[1]) and prev[1] > 0 and prev[1] <= MAX_PREMIUM:
            # prev=低行权价, 当前=高行权价
            # 正常: prev便宜 < p贵 (行权价越高Put越值钱)
            # 倒挂: prev贵 > p便宜 (行权价高的Put反而便宜)
            if p < prev[1]:
                # 买当前(高行权价,被低估), 目标prev价格(低行权价参考价)
                signals.append(_make_signal('看跌倒挂', s, p, bid, ask, prev[1], prev[0]))
        prev = (s, p, bid, ask)
    return signals


def print_time_warning():
    now = datetime.now(); h, m = now.hour, now.minute
    if h > TRADE_DEADLINE[0] or (h == TRADE_DEADLINE[0] and m >= TRADE_DEADLINE[1]):
        print("\n  🛑 已过14:30 — 禁止开新仓！以下信号仅供观察\n")
    elif h >= TRADE_DEADLINE[0] and m >= 0:
        print(f"\n  ⏰ 距离开仓截止还有{TRADE_DEADLINE[1]-m}分钟\n")


def print_signals(title, signals):
    tradeable = [s for s in signals if s['tradeable']]
    print(f"\n{'─'*80}")
    print(f"  {title} — {len(signals)}个（可交易: {len(tradeable)}）")
    print(f"{'─'*80}")
    if not signals:
        print("  今日无信号"); return
    for i, s in enumerate(signals, 1):
        net = s['net_pct']
        flag = "✅" if s['tradeable'] else ("⚠️ 价差大" if s['spread_pct'] > MAX_SPREAD_PCT else "⚠️ 利润薄")
        print(f"\n  [{i}] {flag} P{s['strike']}({s['price']}) < P{s['ref_strike']}({s['target_price']})")
        print(f"      理论利润: {s['profit_pct']}%  |  买价{s['bid']}/卖价{s['ask']} 价差{s['spread_pct']}%")
        if net > 0:
            print(f"      扣除滑点净利: +{net}%  {s['action']}")
        else:
            print(f"      扣除滑点净利: {net}%  ❌ 不建议")


def main():
    p = argparse.ArgumentParser(description="偏差检测—吾剑策略版(含滑点)")
    p.add_argument('--contract', type=str, default=None)
    p.add_argument('--mode', type=str, default='full', choices=['full','quick','silent'])
    p.add_argument('--price', type=int, default=APPROX_FUTURES_PRICE)
    p.add_argument('--compare', action='store_true')
    p.add_argument('--capital', type=str, default='')
    p.add_argument('--prefix', type=str, default='')
    args = p.parse_args()

    df, contract, date_str = load_latest(args.contract, args.prefix)

    print(f"\n🔍 偏差检测 — 吾剑策略(含滑点)")
    print(f"   合约:{contract}  数据:{date_str}  期价:~{args.price}")
    print(f"   范围:行权价{args.price-STRIKE_RANGE_BELOW}-{args.price-50} 权利金<{MAX_PREMIUM}元  价差>{MAX_SPREAD_PCT}%过滤")
    print_time_warning()

    put_inv = check_put_inversions(df)
    call_inv = check_call_inversions(df)

    if args.mode == 'silent':
        tradeable = sum(1 for s in put_inv if s['tradeable']) + sum(1 for s in call_inv if s['tradeable'])
        print(f"\n  看跌倒挂:{len(put_inv)}(可交易:{sum(1 for s in put_inv if s['tradeable'])})  "
              f"看涨倒挂:{len(call_inv)}(可交易:{sum(1 for s in call_inv if s['tradeable'])})")
        return

    prefix_map = {s['ref_strike']: 'P' if s['type'] == '看跌倒挂' else 'C' for s in put_inv + call_inv}
    print_signals("看跌期权倒挂", put_inv)
    print_signals("看涨期权倒挂", call_inv)

    # 操作建议
    all_sig = put_inv + call_inv
    if args.capital:
        capital = float(args.capital)
        tradeable = [s for s in all_sig if s['tradeable']]
        print(f"\n{'═'*80}")
        print(f"  🎯 操作建议（本金 {capital:,.0f} 元 | 价差≤{MAX_SPREAD_PCT}%才推荐）")
        print(f"{'═'*80}")

        now = datetime.now(); h, m = now.hour, now.minute
        if h > TRADE_DEADLINE[0] or (h == TRADE_DEADLINE[0] and m >= TRADE_DEADLINE[1]):
            print(f"\n  🛑 已过14:30 — 禁止开新仓\n")
        elif not tradeable:
            print(f"\n  😴 无价差可接受的信号\n  (有信号但滑点吃掉利润 = 不做，这是纪律)\n")
        else:
            single_max = capital * 0.10
            mins = 60*(TRADE_DEADLINE[0]-h)+(TRADE_DEADLINE[1]-m)
            print(f"\n  ✅ 可开仓 — 剩余{mins}分钟  单笔上限:{single_max:,.0f}元\n")
            ranked = sorted(tradeable, key=lambda s: s['net_pct'], reverse=True)
            for i, s in enumerate(ranked, 1):
                cost = s['price'] * 1000
                pfx = 'P' if s['type'] == '看跌倒挂' else 'C'
                print(f"  [{i}] {pfx}{s['strike']}@{s['price']:.2f}  净利+{s['net_pct']}%  "
                      f"成本{cost:,.0f}元/手")
            print(f"\n  ⚠️ 14:30前不论盈亏必须决策 | 不修复主动割 | 不过夜\n")

    print()


if __name__ == '__main__':
    main()
