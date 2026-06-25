#!/usr/bin/env python3
"""
全品种机会扫描器
────────────────
每天一键扫描全部10个商品期权品种，找出定价偏差机会。
输出每个品种的信号数 + 推荐今日做哪个品种。

用法:
  python3 scan_all.py                      # 扫描全部品种
  python3 scan_all.py --capital 10000      # 指定本金，过滤买不起的
  python3 scan_all.py --quick              # 快速模式(只看主力合约)
"""

import sys
import os
import argparse
import pandas as pd
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import akshare as ak

# ═══════════════════════════════════════════
# 品种配置
# ═══════════════════════════════════════════

VARIETIES = {
    "au": {"symbol": "黄金期权",   "futures": 870,  "name": "沪金",    "prefix": "au", "multiplier": 1000},
    "m":  {"symbol": "豆粕期权",   "futures": 2800, "name": "豆粕",    "prefix": "m",  "multiplier": 10},
    "c":  {"symbol": "玉米期权",   "futures": 2300, "name": "玉米",    "prefix": "c",  "multiplier": 10},
    "cf": {"symbol": "棉花期权",   "futures": 13500,"name": "棉花",    "prefix": "cf", "multiplier": 5},
    "sr": {"symbol": "白糖期权",   "futures": 5600, "name": "白糖",    "prefix": "sr", "multiplier": 10},
    "ta": {"symbol": "PTA期权",    "futures": 4800, "name": "PTA",     "prefix": "ta", "multiplier": 5},
    "i":  {"symbol": "铁矿石期权", "futures": 780,  "name": "铁矿石",  "prefix": "i",  "multiplier": 100},
    "ru": {"symbol": "橡胶期权",   "futures": 17000,"name": "橡胶",    "prefix": "ru", "multiplier": 10},
    "ma": {"symbol": "甲醇期权",   "futures": 2450, "name": "甲醇",    "prefix": "ma", "multiplier": 10},
    "rm": {"symbol": "菜籽粕期权", "futures": 2500, "name": "菜籽粕",  "prefix": "rm", "multiplier": 10},
}

MAX_PREMIUM = 5.0          # 最高权利金（吾剑策略：低价为王）
MAX_SPREAD_PCT = 10        # 买卖价差超过此值不推荐
OTM_PCT = 0.08             # 虚值程度：期价*0.92 以下的行权价

# 主力合约映射（当前月份）— 定期更新
CURRENT_MONTH = "2606"


def _safe(v):
    return v if not pd.isna(v) else 0


def _spread(bid, ask):
    if bid and ask and bid > 0:
        return round((ask - bid) / bid * 100, 1)
    return 999


def scan_variety(vcode, variety, capital=None, quick=False):
    """扫描单个品种，返回信号列表"""
    symbol = variety['symbol']
    futures = variety['futures']
    mult = variety['multiplier']
    name = variety['name']

    # 获取合约列表
    try:
        contracts_df = ak.option_commodity_contract_sina(symbol=symbol)
        contracts = contracts_df['合约'].tolist()
    except Exception:
        return [], f"❌ 获取合约失败"

    if quick:
        # 只取主力（跳过当月到期合约，取最近2个）
        contracts = sorted([c for c in contracts if not c.endswith(CURRENT_MONTH[-2:])])[:2] or contracts[:2]

    all_signals = []

    for contract in contracts:
        try:
            df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=contract)
        except Exception:
            continue

        if df is None or df.empty:
            continue

        # 解析列名
        df = df.rename(columns={
            '行权价': 'strike',
            '看跌合约-最新价': 'p_last',
            '看跌合约-买价': 'p_bid',
            '看跌合约-卖价': 'p_ask',
            '看跌合约-持仓量': 'p_oi',
            '看涨合约-最新价': 'c_last',
            '看涨合约-买价': 'c_bid',
            '看涨合约-卖价': 'c_ask',
        })

        # 只看虚值看跌区（strike < futures * (1 - OTM_PCT)）
        otm_boundary = int(futures * (1 - OTM_PCT))
        otm_puts = df[(df['strike'] < otm_boundary) & (df['strike'] >= otm_boundary - int(futures * 0.15))]
        # 放宽：只要 strike < otm_boundary
        otm_puts = df[df['strike'] < otm_boundary].copy()

        if otm_puts.empty:
            continue

        # 找看跌倒挂：行权价更高的put反而更贵
        rows = []
        for _, row in otm_puts.iterrows():
            p_last = row['p_last'] if not pd.isna(row['p_last']) else None
            p_bid = _safe(row['p_bid'])
            p_ask = _safe(row['p_ask'])
            if p_last is None or p_last <= 0 or p_last > MAX_PREMIUM:
                continue
            rows.append({
                'strike': int(row['strike']),
                'price': p_last,
                'bid': p_bid,
                'ask': p_ask,
                'oi': int(row['p_oi']) if not pd.isna(row['p_oi']) else 0,
            })

        # 比较相邻行权价
        for i in range(len(rows) - 1):
            cur = rows[i]
            nxt = rows[i + 1]
            # cur=低行权价, nxt=高行权价
            # 正常: cur便宜 < nxt贵 (行权价越高Put越值钱)
            # 倒挂: cur贵 > nxt便宜 (行权价高的Put反而便宜) ← 这才是异常
            if cur['price'] > nxt['price']:
                # 买nxt（高行权价、被低估的Put），等价格回归到cur之上
                profit_pct = round((cur['price'] - nxt['price']) / nxt['price'] * 100, 1)
                sp = _spread(nxt['bid'], nxt['ask'])
                net = round(profit_pct - sp, 1)
                cost = nxt['price'] * mult

                # 资本过滤
                if capital and cost > capital * 0.10:
                    continue

                all_signals.append({
                    'variety': vcode,
                    'name': name,
                    'contract': contract,
                    'type': '看跌倒挂',
                    'buy_strike': nxt['strike'],
                    'buy_price': nxt['price'],
                    'buy_bid': nxt['bid'],
                    'buy_ask': nxt['ask'],
                    'ref_strike': cur['strike'],
                    'ref_price': cur['price'],
                    'profit_pct': profit_pct,
                    'spread_pct': sp,
                    'net_pct': net,
                    'cost': cost,
                    'tradeable': sp < profit_pct and sp < MAX_SPREAD_PCT,
                    'multiplier': mult,
                })

    if not all_signals:
        return [], "— 无信号"

    tradeable = [s for s in all_signals if s['tradeable']]
    summary = f"{len(all_signals)}个信号 ({len(tradeable)}个可交易)"
    return all_signals, summary


def main():
    parser = argparse.ArgumentParser(description="全品种期权机会扫描器")
    parser.add_argument('--capital', type=float, default=None, help='本金(元)，用于过滤成本超限的合约')
    parser.add_argument('--quick', action='store_true', help='快速模式(只看主力合约)')
    parser.add_argument('--min-signals', type=int, default=0, help='至少N个信号才显示详情')
    parser.add_argument('--variety', type=str, default='all', help='扫描指定品种')
    args = parser.parse_args()

    if args.variety == 'all':
        target = list(VARIETIES.keys())
    else:
        target = [v.strip() for v in args.variety.split(',')]

    print(f"\n{'═'*70}")
    print(f"  🔭 全品种期权机会扫描 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if args.quick:
        print(f"  ⚡ 快速模式（仅主力合约）")
    if args.capital:
        print(f"  💰 本金: ¥{args.capital:,.0f}  |  单笔上限: ¥{args.capital*0.10:,.0f}")
    print(f"{'═'*70}")

    results = {}
    all_tradeable = []

    for vcode in target:
        variety = VARIETIES[vcode]
        print(f"  {variety['name']:6s} ({vcode}) ...", end=" ", flush=True)
        signals, summary = scan_variety(vcode, variety, args.capital, args.quick)
        results[vcode] = (signals, summary)
        print(summary)

        for s in signals:
            if s['tradeable']:
                all_tradeable.append(s)

    # 排序推荐
    if all_tradeable:
        all_tradeable.sort(key=lambda s: s['net_pct'], reverse=True)

        print(f"\n{'═'*70}")
        print(f"  🎯 今日可交易机会: {len(all_tradeable)} 个")
        print(f"{'═'*70}")

        for i, s in enumerate(all_tradeable[:15], 1):
            flag = "🟢" if s['net_pct'] > 5 else ("🟡" if s['net_pct'] > 0 else "🔴")
            print(f"\n  [{i:2d}] {flag} {s['name']} {s['contract']} "
                  f"P{s['buy_strike']}@{s['buy_price']:.2f} < P{s['ref_strike']}@{s['ref_price']:.2f}")
            print(f"       理论利润: +{s['profit_pct']}%  |  价差: {s['spread_pct']}%  |  净利: +{s['net_pct']}%")
            print(f"       成本: ¥{s['cost']:,.0f}/手  |  买{s['buy_bid']:.2f}/卖{s['buy_ask']:.2f}")
    else:
        print(f"\n{'═'*70}")
        print(f"  😴 今日无可交易机会")
        print(f"  这很正常——吾剑等了3年才等来126天窗口。")
        print(f"  没机会的日子 = 学习的日子。去跑闪卡。")
        print(f"{'═'*70}")

    # 品种排名
    print(f"\n{'─'*70}")
    print(f"  品种活跃度排名（信号总数）:")
    ranked = sorted(results.items(), key=lambda x: len([s for s in x[1][0] if s['tradeable']]), reverse=True)
    for vcode, (signals, summary) in ranked:
        t_count = len([s for s in signals if s['tradeable']])
        bar = "█" * t_count if t_count > 0 else "—"
        name = VARIETIES[vcode]['name']
        print(f"  {name:6s} ({vcode})  {bar}  {t_count}")

    print()


if __name__ == '__main__':
    main()
