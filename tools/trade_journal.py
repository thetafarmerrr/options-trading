#!/usr/bin/env python3
"""
T5: 交易日志系统
────────────────────────────
功能: 极简交易记录 + 自动归档 + 每周复盘
用法: python3 trade_journal.py --open     (开仓)
      python3 trade_journal.py --close    (平仓)
      python3 trade_journal.py --today    (今日交易)
      python3 trade_journal.py --weekly   (本周复盘)
      python3 trade_journal.py --summary  (全部摘要)
原则: 你只需填「为什么进场」一句话，其余自动归档
"""

import argparse
import sys
import os
import csv
from datetime import datetime, date, timedelta
from pathlib import Path

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL_DIR = os.path.join(SCRIPT_DIR, "journal")
JOURNAL_FILE = os.path.join(JOURNAL_DIR, "trades.csv")

FIELD_NAMES = [
    'id', '开仓日期', '开仓时间', '合约', '方向', '行权价', '类型',
    '开仓价', '数量', '权利金合计', '开仓理由',
    '平仓日期', '平仓时间', '平仓价', '盈亏', '盈亏%', '持仓天数', '备注'
]

# 沪金期权合约乘数
CONTRACT_MULTIPLIER = 1000


# ═══════════════════════════════════════════
# 数据操作
# ═══════════════════════════════════════════

def load_trades():
    """加载所有交易记录"""
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    if not os.path.exists(JOURNAL_FILE):
        return []
    with open(JOURNAL_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_trades(trades):
    """保存交易记录"""
    with open(JOURNAL_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(trades)


def get_next_id(trades):
    """获取下一个交易ID"""
    if not trades:
        return 1
    return max(int(t.get('id', 0)) for t in trades) + 1


# ═══════════════════════════════════════════
# 开仓
# ═══════════════════════════════════════════

def cmd_open(args):
    """记录开仓"""
    trades = load_trades()

    now = datetime.now()

    # 交互获取信息
    print("\n📝 新建交易记录")
    print("─" * 40)

    contract = args.contract or input("合约代码 (如 au2608P696): ").strip()
    direction = args.direction or input("方向 [买/卖] (默认: 买): ").strip() or "买"

    price_str = args.price or input("开仓价 (权利金单价): ").strip()
    try:
        price = float(price_str)
    except ValueError:
        print("✗ 价格格式错误")
        return

    qty_str = args.qty or input("数量 (手数, 默认: 1): ").strip() or "1"
    try:
        qty = int(qty_str)
    except ValueError:
        print("✗ 数量格式错误")
        return

    reason = args.reason or input("开仓理由 (一句话): ").strip()

    # 解析合约信息
    # 格式: au2608P696 或 au2608C696
    import re
    opt_type = "看跌" if 'P' in contract else "看涨"
    match = re.search(r'[PC](\d+)$', contract)
    strike = int(match.group(1)) if match else 0

    total_premium = price * CONTRACT_MULTIPLIER * qty

    trade = {
        'id': str(get_next_id(trades)),
        '开仓日期': now.strftime("%Y-%m-%d"),
        '开仓时间': now.strftime("%H:%M"),
        '合约': contract,
        '方向': direction,
        '行权价': str(strike),
        '类型': opt_type,
        '开仓价': f"{price:.2f}",
        '数量': str(qty),
        '权利金合计': f"{total_premium:.0f}",
        '开仓理由': reason,
        '平仓日期': '',
        '平仓时间': '',
        '平仓价': '',
        '盈亏': '',
        '盈亏%': '',
        '持仓天数': '',
        '备注': ''
    }

    trades.append(trade)
    save_trades(trades)

    # 计算仓位
    capital = float(args.capital or 10000)
    position_pct = total_premium / capital * 100

    print(f"""
✅ 交易 #{trade['id']} 已记录
   合约: {contract} {direction} @{price:.2f} ×{qty}
   权利金合计: {total_premium:.0f} 元 (占本金 {position_pct:.1f}%)
   时间: {trade['开仓日期']} {trade['开仓时间']}
   理由: {reason}
""")


# ═══════════════════════════════════════════
# 平仓
# ═══════════════════════════════════════════

def cmd_close(args):
    """记录平仓"""
    trades = load_trades()

    # 查找未平仓的交易
    open_trades = [t for t in trades if not t['平仓日期']]

    if not open_trades:
        print("\n📭 当前没有持仓")
        return

    print("\n📝 平仓")
    print("─" * 40)
    print("当前持仓:")
    for t in open_trades:
        print(f"  #{t['id']}  {t['合约']} {t['方向']} @{t['开仓价']} ×{t['数量']}  ({t['开仓日期']})")
    print()

    trade_id = args.id or input("平仓ID: ").strip()

    # 查找交易
    target = None
    for t in trades:
        if t['id'] == trade_id and not t['平仓日期']:
            target = t
            break

    if not target:
        print(f"✗ 找不到持仓 #{trade_id}")
        return

    price_str = args.price or input("平仓价: ").strip()
    try:
        close_price = float(price_str)
    except ValueError:
        print("✗ 价格格式错误")
        return

    now = datetime.now()
    open_price = float(target['开仓价'])
    qty = int(target['数量'])
    direction = target['方向']

    # 计算盈亏
    if direction == "买":
        pnl = (close_price - open_price) * CONTRACT_MULTIPLIER * qty
    else:
        pnl = (open_price - close_price) * CONTRACT_MULTIPLIER * qty

    pnl_pct = (close_price - open_price) / open_price * 100
    if direction == "卖":
        pnl_pct = -pnl_pct

    # 计算持仓天数
    open_date = datetime.strptime(target['开仓日期'], "%Y-%m-%d")
    hold_days = (now - open_date).days

    target['平仓日期'] = now.strftime("%Y-%m-%d")
    target['平仓时间'] = now.strftime("%H:%M")
    target['平仓价'] = f"{close_price:.2f}"
    target['盈亏'] = f"{pnl:.0f}"
    target['盈亏%'] = f"{pnl_pct:.1f}"
    target['持仓天数'] = str(hold_days)
    target['备注'] = args.note or ''

    save_trades(trades)

    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
    print(f"""
{emoji} 交易 #{trade_id} 已平仓
   合约: {target['合约']}
   开仓: @{open_price:.2f}  →  平仓: @{close_price:.2f}
   盈亏: {pnl:+.0f} 元 ({pnl_pct:+.1f}%)
   持仓: {hold_days} 天
""")


# ═══════════════════════════════════════════
# 今日交易
# ═══════════════════════════════════════════

def cmd_today(args):
    """查看今日交易"""
    trades = load_trades()
    today = date.today().isoformat()

    today_trades = [t for t in trades
                    if t['开仓日期'] == today or t['平仓日期'] == today]

    if not today_trades:
        print("\n📭 今日无交易记录")
        return

    print(f"\n📋 今日交易 ({today})")
    print("═" * 70)
    print(f"{'ID':>3} {'合约':<14} {'开仓':>8} {'平仓':>8} {'盈亏':>8} {'状态':<8}")
    print("─" * 70)

    total_pnl = 0
    for t in today_trades:
        status = "持仓中" if not t['平仓日期'] else "已平仓"
        open_p = f"@{t['开仓价']}"
        close_p = f"@{t['平仓价']}" if t['平仓价'] else "-"
        pnl_str = t['盈亏'] if t['盈亏'] else "-"
        total_pnl += int(t['盈亏']) if t['盈亏'] else 0
        print(f"{t['id']:>3} {t['合约']:<14} {open_p:>8} {close_p:>8} {pnl_str:>8} {status:<8}")

    print("─" * 70)
    pnl_emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
    print(f"  今日盈亏: {pnl_emoji} {total_pnl:+.0f} 元")
    print()


# ═══════════════════════════════════════════
# 本周复盘
# ═══════════════════════════════════════════

def cmd_weekly(args):
    """本周复盘摘要"""
    trades = load_trades()

    # 计算本周范围（周一到今天）
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_start = monday.isoformat()
    week_end = today.isoformat()

    week_trades = [t for t in trades
                   if t['开仓日期'] >= week_start and t['开仓日期'] <= week_end]

    if not week_trades:
        print(f"\n📭 本周 ({week_start} ~ {week_end}) 无交易")
        return

    closed = [t for t in week_trades if t['平仓日期']]
    open_positions = [t for t in week_trades if not t['平仓日期']]

    # 统计
    total_trades = len(closed)
    wins = [t for t in closed if float(t['盈亏']) > 0]
    losses = [t for t in closed if float(t['盈亏']) < 0]

    total_pnl = sum(float(t['盈亏']) for t in closed)
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0

    avg_win = sum(float(t['盈亏']) for t in wins) / len(wins) if wins else 0
    avg_loss = sum(float(t['盈亏']) for t in losses) / len(losses) if losses else 0
    pnl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    max_win = max([float(t['盈亏']) for t in closed]) if closed else 0
    max_loss = min([float(t['盈亏']) for t in closed]) if closed else 0

    print(f"""
╔═══════════════════════════════════════════╗
║     📊 本周复盘: {week_start} ~ {week_end}    ║
╠═══════════════════════════════════════════╣
║                                           ║
║  📈 交易概览                               ║
║  ─────────────────────                    ║
║  总笔数:      {total_trades + len(open_positions):>3}                            ║
║  已平仓:      {total_trades:>3}                            ║
║  盈利:        {len(wins):>3}  ({win_rate:.0f}%)                        ║
║  亏损:        {len(losses):>3}                            ║
║  持仓中:      {len(open_positions):>3}                            ║
║                                           ║
║  💰 盈亏统计                               ║
║  ─────────────────────                    ║
║  总盈亏:      {total_pnl:+.0f} 元                     ║
║  最大单笔盈利: {max_win:+.0f} 元                     ║
║  最大单笔亏损: {max_loss:+.0f} 元                     ║
║  平均盈利:    {avg_win:+.0f} 元                     ║
║  平均亏损:    {avg_loss:+.0f} 元                     ║
║  盈亏比:      {pnl_ratio:.1f}:1                         ║
║                                           ║
╚═══════════════════════════════════════════╝""")

    # 交易明细
    if closed:
        print("\n📋 本周交易明细:")
        print(f"{'ID':>3} {'合约':<14} {'开仓':>8} {'平仓':>8} {'盈亏':>10} {'天数':>4}")
        print("─" * 55)
        for t in closed:
            print(f"{t['id']:>3} {t['合约']:<14} @{t['开仓价']:>7} @{t['平仓价']:>7} "
                  f"{float(t['盈亏']):+10.0f} {t['持仓天数']:>4}天")

    # 持仓
    if open_positions:
        print(f"\n📌 当前持仓 ({len(open_positions)} 笔):")
        for t in open_positions:
            print(f"  #{t['id']} {t['合约']} @{t['开仓价']} ×{t['数量']}  ({t['开仓日期']})")

    print()


# ═══════════════════════════════════════════
# 全部摘要
# ═══════════════════════════════════════════

def cmd_summary(args):
    """全部历史摘要"""
    trades = load_trades()

    if not trades:
        print("\n📭 暂无交易记录")
        return

    closed = [t for t in trades if t['平仓日期']]
    total_pnl = sum(float(t['盈亏']) for t in closed)
    total_trades = len(closed)
    wins = len([t for t in closed if float(t['盈亏']) > 0])

    print(f"""
╔═══════════════════════════════════════════╗
║        📊 全部交易摘要                     ║
╠═══════════════════════════════════════════╣
║  总交易数:    {len(trades):>4}                             ║
║  已平仓:      {total_trades:>4}                             ║
║  累计盈亏:    {total_pnl:+.0f} 元                        ║
║  胜率:        {wins/total_trades*100 if total_trades else 0:.0f}%                            ║
║  数据文件:    {JOURNAL_FILE}
╚═══════════════════════════════════════════╝
""")


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="交易日志系统 — 极简记录 + 自动复盘",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  开仓: python3 trade_journal.py --open
  开仓(快捷): python3 trade_journal.py --open -c au2608P696 -p 0.62 -q 1 -r "偏差回归"
  平仓: python3 trade_journal.py --close
  平仓(快捷): python3 trade_journal.py --close -i 1 -p 0.70
  今日: python3 trade_journal.py --today
  本周: python3 trade_journal.py --weekly
  全部: python3 trade_journal.py --summary
        """
    )

    # 命令
    parser.add_argument('--open', action='store_true', help='记录开仓')
    parser.add_argument('--close', action='store_true', help='记录平仓')
    parser.add_argument('--today', action='store_true', help='查看今日交易')
    parser.add_argument('--weekly', action='store_true', help='本周复盘')
    parser.add_argument('--summary', action='store_true', help='全部历史摘要')

    # 开仓参数
    parser.add_argument('-c', '--contract', type=str, help='合约代码')
    parser.add_argument('-p', '--price', type=str, help='开仓/平仓价')
    parser.add_argument('-q', '--qty', type=str, help='数量(手数)')
    parser.add_argument('-d', '--direction', type=str, help='方向(买/卖)')
    parser.add_argument('-r', '--reason', type=str, help='开仓理由')
    parser.add_argument('--capital', type=str, default='10000', help='当前本金(计算仓位)')

    # 平仓参数
    parser.add_argument('-i', '--id', type=str, help='平仓交易ID')
    parser.add_argument('-n', '--note', type=str, help='备注')

    args = parser.parse_args()

    if args.open:
        cmd_open(args)
    elif args.close:
        cmd_close(args)
    elif args.today:
        cmd_today(args)
    elif args.weekly:
        cmd_weekly(args)
    elif args.summary:
        cmd_summary(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
