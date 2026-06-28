#!/usr/bin/env python3
"""
T1: 多品种商品期权数据格式化工具
────────────────────────────────
功能: 一键拉取 10个商品品种全合约期权链，格式化输出 + CSV存储
原则: 工具放大学习，不替代学习 — 仅省体力，不替代眼力
数据源: 新浪财经 (via akshare)
"""

import akshare as ak
import pandas as pd
import argparse
import sys
import os
from datetime import datetime

# ═══════════════════════════════════════════
# 品种配置 — 10个可用商品期权
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

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONSOLE_WIDTH = 90
MAX_RETRIES = 2
RETRY_DELAY = 3


# ═══════════════════════════════════════════
# 数据获取
# ═══════════════════════════════════════════

def fetch_contracts(symbol):
    """获取所有可用期权合约列表"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            df = ak.option_commodity_contract_sina(symbol=symbol)
            return df['合约'].tolist()
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"  ⚠ 获取合约列表失败，{RETRY_DELAY}秒后重试 ({attempt+1}/{MAX_RETRIES})")
                import time; time.sleep(RETRY_DELAY)
            else:
                print(f"  ✗ 获取合约列表失败: {e}")
                return []


def fetch_option_chain(symbol, contract):
    """获取单个合约的期权链"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=contract)
            df = df.rename(columns={
                '行权价': '行权价',
                '看涨合约-最新价': 'C_最新价',
                '看涨合约-买价': 'C_买价',
                '看涨合约-卖价': 'C_卖价',
                '看涨合约-持仓量': 'C_持仓',
                '看跌合约-最新价': 'P_最新价',
                '看跌合约-买价': 'P_买价',
                '看跌合约-卖价': 'P_卖价',
                '看跌合约-持仓量': 'P_持仓',
            })
            cols = ['行权价', 'C_最新价', 'C_买价', 'C_卖价', 'C_持仓',
                    'P_最新价', 'P_买价', 'P_卖价', 'P_持仓']
            df = df[cols]
            for col in cols:
                if col != '行权价':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df['行权价'] = df['行权价'].astype(int)
            return df
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"  ⚠ {contract} 获取失败，{RETRY_DELAY}秒后重试 ({attempt+1}/{MAX_RETRIES})")
                import time; time.sleep(RETRY_DELAY)
            else:
                print(f"  ✗ {contract} 获取失败: {e}")
                return None


# ═══════════════════════════════════════════
# 终端格式化输出
# ═══════════════════════════════════════════

def _fmt(val, width=8, integer=False):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "-".rjust(width)
    if integer:
        return f"{int(val):>{width}}"
    return f"{val:>{width}.2f}"


def print_console(variety, contract, df, timestamp, futures_price):
    """终端格式化输出 — 标注虚值区域"""
    name = variety['name']
    print()
    print("╔" + "═" * (CONSOLE_WIDTH - 2) + "╗")
    print(f"║  {name} {contract} 期权链   数据时间: {timestamp}".ljust(CONSOLE_WIDTH - 1) + "║")
    print("╠" + "═" * (CONSOLE_WIDTH - 2) + "╣")
    header = f"║ {'行权价':>6} │ {'C 最新':>8} │ {'C 买/卖':>14} │ {'P 最新':>8} │ {'P 买/卖':>14} │ {'P持仓':>6} ║"
    print(header)
    print("╟" + "─" * (CONSOLE_WIDTH - 2) + "╢")

    deep_otm_start = futures_price - int(futures_price * 0.08)  # 8% 以下为虚值区
    deep_itm = futures_price - int(futures_price * 0.15)

    for _, row in df.iterrows():
        strike = int(row['行权价'])
        p_last = row['P_最新价']
        p_bid = row['P_买价']
        p_ask = row['P_卖价']
        p_oi = row['P_持仓']
        c_last = row['C_最新价']
        c_bid = row['C_买价']
        c_ask = row['C_卖价']

        zone = ""
        if strike < deep_itm:
            zone = " █"
        elif strike < deep_otm_start and p_last and not pd.isna(p_last) and p_last < 2:
            zone = " ●"
        elif strike < deep_otm_start:
            zone = " ○"

        c_bidask = f"{_fmt(c_bid,6)}/{_fmt(c_ask,6)}"
        p_bidask = f"{_fmt(p_bid,6)}/{_fmt(p_ask,6)}"
        p_oi_str = f"{int(p_oi) if not pd.isna(p_oi) else '-':>6}"

        line = (
            f"║ {strike:>6} │ {_fmt(c_last, 8)}│ {c_bidask} │"
            f" {_fmt(p_last, 8)}│ {p_bidask} │ {p_oi_str} ║{zone}"
        )
        print(line)

    print("╚" + "═" * (CONSOLE_WIDTH - 2) + "╝")
    print("  ● = 深度虚值看跌区 (吾剑策略核心关注区)")
    print(f"  期货参考价: ~{futures_price}  |  虚值线: {deep_otm_start}")
    print()


def print_plain(variety, contract, df, timestamp, futures_price):
    """纯文本输出 — 适合 GUI/非等宽环境"""
    name = variety['name']
    deep_otm_start = futures_price - int(futures_price * 0.08)
    deep_itm = futures_price - int(futures_price * 0.15)

    print()
    print(f"=== {name} {contract} 期权链 === {timestamp}")
    print(f"{'行权价':>6}  {'C最新':>8}  {'C买':>8}  {'C卖':>8}  {'P最新':>8}  {'P买':>8}  {'P卖':>8}  {'P持仓':>6}  信号")
    print("-" * 95)

    for _, row in df.iterrows():
        strike = int(row['行权价'])
        c_last = row['C_最新价']; c_bid = row['C_买价']; c_ask = row['C_卖价']
        p_last = row['P_最新价']; p_bid = row['P_买价']; p_ask = row['P_卖价']
        p_oi = row['P_持仓']

        zone = ""
        if strike < deep_itm:
            zone = "深实"
        elif strike < deep_otm_start and p_last and not pd.isna(p_last) and p_last < 2:
            zone = "★虚值"
        elif strike < deep_otm_start:
            zone = "虚值"

        print(f"{strike:>6}  {_fmt(c_last):>8}  {_fmt(c_bid):>8}  {_fmt(c_ask):>8}  "
              f"{_fmt(p_last):>8}  {_fmt(p_bid):>8}  {_fmt(p_ask):>8}  {_fmt(p_oi,6,True):>6}  {zone}")

    print("-" * 95)
    print(f"★虚值 = 策略核心关注区 | 期货参考价 ~{futures_price}")
    print()


# ═══════════════════════════════════════════
# CSV 存储
# ═══════════════════════════════════════════

def save_csv(variety, contract, df, data_dir):
    os.makedirs(data_dir, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    prefix = variety['prefix']
    filename = os.path.join(data_dir, f"{prefix}_{contract}_{today}.csv")
    df.to_csv(filename, index=False, encoding='utf-8')
    return filename


# ═══════════════════════════════════════════
# 交易时段判断
# ═══════════════════════════════════════════

def trading_status():
    now = datetime.now()
    wd = now.weekday()
    h = now.hour
    if wd >= 5:
        return "⚠ 今日非交易日（周末）"
    # 商品期货交易时段: 9:00-10:15, 10:30-11:30, 13:30-15:00, 夜盘21:00-23:00(部分品种至凌晨)
    if h < 9:
        return "⏳ 盘前，数据为上一交易日"
    if h >= 15 and h < 21:
        return "⏸ 日盘已收盘，等待夜盘"
    return "🟢 交易时段"


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="多品种商品期权数据格式化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python3 fetch_options.py                                 # 全部品种
  python3 fetch_options.py --variety au                    # 仅沪金
  python3 fetch_options.py --variety au --contract au2608  # 单合约
  python3 fetch_options.py --variety m,c,cf                # 豆粕+玉米+棉花
  python3 fetch_options.py --list                          # 列出可用品种
  python3 fetch_options.py --output csv                    # 仅存CSV不显示
  python3 fetch_options.py --plain                         # 纯文本输出(适合GUI)
        """
    )
    parser.add_argument('--variety', type=str, default='all',
                        help='品种代码(逗号分隔)，all=全部')
    parser.add_argument('--contract', type=str, default='all',
                        help='指定合约，all=全部')
    parser.add_argument('--output', type=str, default='both',
                        choices=['console', 'csv', 'both'])
    parser.add_argument('--dir', type=str, default=DATA_DIR)
    parser.add_argument('--futures-price', type=int, default=None,
                        help='覆盖期货参考价')
    parser.add_argument('--plain', action='store_true',
                        help='纯文本输出')
    parser.add_argument('--list', action='store_true',
                        help='列出所有可用品种')

    args = parser.parse_args()

    if args.list:
        print("\n可用品种:")
        for code, v in VARIETIES.items():
            print(f"  {code:4s} — {v['name']:6s}  (期货约{v['futures']:>8,}元, 乘数{v['multiplier']})")
        print()
        return

    # 确定要拉取的品种
    if args.variety == 'all':
        target_varieties = list(VARIETIES.keys())
    else:
        target_varieties = [v.strip() for v in args.variety.split(',')]
        for v in target_varieties:
            if v not in VARIETIES:
                print(f"✗ 未知品种: {v}，用 --list 查看可用品种")
                sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    ts = trading_status()

    print(f"\n{'═'*70}")
    print(f"  📊 商品期权数据拉取 — {timestamp}  {ts}")
    print(f"  📡 数据源: 新浪财经 (via akshare)")
    print(f"  📋 目标品种: {len(target_varieties)} 个")
    print(f"{'═'*70}")

    total_contracts = 0
    total_rows = 0
    saved_files = []

    for vcode in target_varieties:
        variety = VARIETIES[vcode]
        symbol = variety['symbol']
        name = variety['name']
        futures_price = args.futures_price if args.futures_price else variety['futures']

        print(f"\n{'─'*70}")
        print(f"  🏷 {name} ({vcode})  |  期价参考: ~{futures_price}")
        print(f"{'─'*70}")

        contracts = fetch_contracts(symbol)
        if not contracts:
            print(f"  ✗ 无可用合约，跳过\n")
            continue

        if args.contract != 'all':
            if args.contract not in contracts:
                print(f"  ✗ 合约 {args.contract} 不可用: {contracts}")
                continue
            contracts = [args.contract]

        print(f"  合约: {', '.join(contracts)}")

        for contract in contracts:
            print(f"    {contract} ...", end=" ", flush=True)
            df = fetch_option_chain(symbol, contract)
            if df is None:
                print("✗")
                continue
            print(f"✓ ({len(df)}档)")

            total_contracts += 1
            total_rows += len(df)

            # 输出
            if args.output in ('console', 'both'):
                if args.plain:
                    print_plain(variety, contract, df, timestamp, futures_price)
                else:
                    print_console(variety, contract, df, timestamp, futures_price)

            if args.output in ('csv', 'both'):
                fname = save_csv(variety, contract, df, args.dir)
                saved_files.append(fname)

    # 汇总
    print(f"\n{'═'*70}")
    print(f"  ✅ 完成: {len(target_varieties)} 品种, {total_contracts} 合约, {total_rows} 档行权价")
    if saved_files:
        print(f"  📁 {len(saved_files)} 个 CSV 存入 {args.dir}/")
    print(f"{'═'*70}\n")


if __name__ == '__main__':
    main()
