#!/usr/bin/env python3
"""
T4: 每日风控看板
────────────────────────────
功能: 开市前/交易中输出风控状态一览
用法: python3 risk_dashboard.py            (完整看板)
      python3 risk_dashboard.py --quick    (快速摘要)
依赖: trade_journal.py 的交易记录
原则: 外部纪律层 — 提醒规则，不替代决策
"""

import argparse
import sys
import os
import csv
from datetime import datetime, date

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL_FILE = os.path.join(SCRIPT_DIR, "journal", "trades.csv")

# 风控参数
MAX_POSITION_PCT = 10          # 单笔最大仓位 (%)
MAX_DRAWDOWN_PCT = 4.2         # 最大回撤红线 (%)
WARNING_DRAWDOWN = 3.5         # 回撤警告线 (%)
CAUTION_DRAWDOWN = 2.0         # 回撤关注线 (%)
NEW_TRADE_CUTOFF_HOUR = 14     # 开新仓截止时间
NEW_TRADE_CUTOFF_MIN = 30      # 开新仓截止分钟

# 交易时段
MORNING_START = (8, 30)
MORNING_OPEN = (9, 0)
AFTERNOON_OPEN = (13, 30)
MARKET_CLOSE = (15, 0)

# 沪金合约乘数
CONTRACT_MULTIPLIER = 1000


# ═══════════════════════════════════════════
# 数据
# ═══════════════════════════════════════════

def load_trades():
    """加载交易记录"""
    if not os.path.exists(JOURNAL_FILE):
        return []
    with open(JOURNAL_FILE, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def get_today_trades(trades):
    """获取今日交易"""
    today = date.today().isoformat()
    return [t for t in trades if t['开仓日期'] == today or t['平仓日期'] == today]


def get_open_positions(trades):
    """获取当前持仓"""
    return [t for t in trades if not t['平仓日期']]


def calc_drawdown(trades, current_capital, peak_capital):
    """计算当前回撤"""
    if peak_capital <= 0:
        return 0
    return (peak_capital - current_capital) / peak_capital * 100


def get_time_status():
    """获取当前时间约束状态"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # 简化：检查是否在交易时段
    if hour < MORNING_START[0] or (hour == MORNING_START[0] and minute < MORNING_START[1]):
        return "盘前准备", "⏳", True, "08:30后可预埋单"

    if hour < MORNING_OPEN[0]:
        return "盘前预埋", "📝", True, "可预埋单，等待开盘"

    after_cutoff = (hour > NEW_TRADE_CUTOFF_HOUR or
                    (hour == NEW_TRADE_CUTOFF_HOUR and minute >= NEW_TRADE_CUTOFF_MIN))

    if after_cutoff and hour < MARKET_CLOSE[0]:
        return "⚠️ 禁止开新仓", "🔴", False, "仅可平仓，14:30后不开新仓"

    if hour >= MARKET_CLOSE[0] and hour < 21:
        return "已收盘", "🌙", False, "等待夜盘或次日"

    return "正常交易", "✅", True, ""


# ═══════════════════════════════════════════
# 看板输出
# ═══════════════════════════════════════════

def print_full(args):
    """完整看板"""
    trades = load_trades()
    today_trades = get_today_trades(trades)
    open_positions = get_open_positions(trades)

    capital = float(args.capital)
    peak = float(args.peak or capital)

    # 计算今日已用
    today_open = [t for t in today_trades if t['开仓日期'] == date.today().isoformat()]
    today_used = sum(float(t.get('权利金合计', 0)) for t in today_open)

    # 持仓合计
    position_used = sum(float(t.get('权利金合计', 0)) for t in open_positions)
    total_used = today_used + position_used

    # 计算盈亏
    closed = [t for t in trades if t['平仓日期']]
    total_pnl = sum(float(t['盈亏']) for t in closed)
    today_closed = [t for t in today_trades if t['平仓日期'] == date.today().isoformat()]
    today_pnl = sum(float(t['盈亏']) for t in today_closed)

    # 当前权益
    current_equity = capital + total_pnl

    # 回撤
    peak_equity = max(capital, float(args.peak or current_equity))
    drawdown = calc_drawdown(trades, current_equity, peak_equity)

    # 时间
    time_status, time_icon, can_open, time_hint = get_time_status()
    now = datetime.now()
    minutes_to_cutoff = max(0, (NEW_TRADE_CUTOFF_HOUR - now.hour) * 60 + NEW_TRADE_CUTOFF_MIN - now.minute)

    # 仓位
    max_single = capital * MAX_POSITION_PCT / 100
    remaining_slots = max(0, int((capital - total_used) / max_single * 10) // 10)

    # 回撤状态
    if drawdown > MAX_DRAWDOWN_PCT:
        dd_status = "🛑 超标"
        dd_action = "立即停止交易，复盘"
    elif drawdown > WARNING_DRAWDOWN:
        dd_status = "🔴 警告"
        dd_action = "暂停开新仓"
    elif drawdown > CAUTION_DRAWDOWN:
        dd_status = "⚠️ 关注"
        dd_action = "减半仓位"
    else:
        dd_status = "✅ 正常"
        dd_action = "—"

    print(f"""
╔═══════════════════════════════════════════╗
║         📋 每日风控看板                    ║
║         {now.strftime("%Y-%m-%d %H:%M")}                      ║
╠═══════════════════════════════════════════╣
║                                           ║
║  💰 资金状况                               ║
║  ─────────────────────────────            ║
║  初始本金:    {capital:>10,.0f} 元              ║
║  当前权益:    {current_equity:>10,.0f} 元              ║
║  累计盈亏:    {total_pnl:>+10,.0f} 元              ║
║  今日盈亏:    {today_pnl:>+10,.0f} 元              ║
║  单笔上限:    {max_single:>10,.0f} 元  ({MAX_POSITION_PCT}%)         ║
║                                           ║
║  📊 仓位状态                               ║
║  ─────────────────────────────            ║
║  今日已开:    {len(today_open):>3} 笔 / {today_used:>10,.0f} 元        ║
║  当前持仓:    {len(open_positions):>3} 笔 / {position_used:>10,.0f} 元        ║
║  合计占用:    {total_used:>10,.0f} 元              ║
║  可用仓位:    {remaining_slots:>3} 笔                    ║
║                                           ║
║  📈 回撤监控                               ║
║  ─────────────────────────────            ║
║  峰值权益:    {peak_equity:>10,.0f} 元              ║
║  当前回撤:    {drawdown:>6.1f}%   {dd_status}               ║
║  建议操作:    {dd_action:<30}║
║  红线:        {MAX_DRAWDOWN_PCT}%                            ║
║                                           ║
║  ⏰ 时间约束                               ║
║  ─────────────────────────────            ║
║  状态:        {time_icon} {time_status:<20}          ║
║  开新仓截止:  14:30 (剩余 {minutes_to_cutoff} 分钟)           ║
║  {time_hint:<40}║
║                                           ║
║  ⚠️ 今日提醒                               ║
║  ─────────────────────────────            ║
║  • 14:30后禁止开新仓                      ║
║  • 收盘前平掉流动性差的虚值合约            ║
║  • 单笔亏损≥100元立即评估是否止损          ║
║  • 日内不追高，不报复性加仓                ║
║                                           ║
╚═══════════════════════════════════════════╝
""")


def print_quick(args):
    """快速摘要"""
    trades = load_trades()
    open_positions = get_open_positions(trades)
    capital = float(args.capital)

    now = datetime.now()
    time_status, time_icon, can_open, _ = get_time_status()

    position_used = sum(float(t.get('权利金合计', 0)) for t in open_positions)
    remaining = max(0, int((capital - position_used) / (capital * MAX_POSITION_PCT / 100)))

    print(f"[{now.strftime('%H:%M')}] "
          f"本金{captal:,.0f} | "
          f"持仓{len(open_positions)}笔 | "
          f"可用{remaining}笔 | "
          f"{time_icon}{'可开' if can_open else '禁开'}")


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="每日风控看板 — 开市前/交易中检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python3 risk_dashboard.py                    # 完整看板
  python3 risk_dashboard.py --quick            # 快速摘要(一行)
  python3 risk_dashboard.py --capital 10000    # 指定本金
  python3 risk_dashboard.py --peak 10500       # 指定峰值权益
        """
    )
    parser.add_argument('--quick', action='store_true', help='快速摘要模式')
    parser.add_argument('--capital', type=str, default='10000', help='初始本金')
    parser.add_argument('--peak', type=str, default='', help='峰值权益(用于计算回撤)')

    args = parser.parse_args()

    if args.quick:
        print_quick(args)
    else:
        print_full(args)


if __name__ == '__main__':
    main()
