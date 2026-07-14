#!/usr/bin/env python3
"""
monthly_report.py — Monthly P&L Report Generator
══════════════════════════════════════════════════
Generates a Markdown monthly report template from trade_log.md and iv_history.csv.

Report sections:
  1. Account overview (start/end cumulative P&L, net monthly P&L)
  2. Trades table for the month
  3. Strategy breakdown (P&L by strategy type)
  4. IV environment summary (from iv_history.csv)
  5. Discipline check
  6. Key lesson (placeholder)
  7. Next month plan (placeholder)

用法：
  python3 tools/monthly_report.py                       # 当前月份
  python3 tools/monthly_report.py --month 2026-07       # 指定月份
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
TRADE_LOG = PROJECT_DIR / "trade_log.md"
IV_HISTORY = PROJECT_DIR / "data" / "iv_history.csv"
REPORTS_DIR = PROJECT_DIR / "reports"

# ── 辅助函数 ─────────────────────────────────────────────


def parse_pnl(raw: str) -> float:
    """Parse a P&L cell like '**−¥40**' or '**+¥10**' into a float."""
    s = raw.strip()
    s = s.replace("**", "")
    s = s.replace("¥", "").replace("￥", "")
    s = s.replace("−", "-").replace("－", "-")
    s = s.replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(date_str: str, year: int = 2026) -> date:
    """Parse a date cell like '06-26→07-02', '06-26→29', or '06-26'.

    Returns the *closing* date (end of range).
    """
    date_str = date_str.strip()
    if "→" in date_str:
        parts = date_str.split("→")
        start_part = parts[0].strip()
        end_part = parts[1].strip()
        if "-" in end_part:
            month, day = end_part.split("-")
        else:
            start_month = start_part.split("-")[0]
            month = start_month
            day = end_part
    else:
        month, day = date_str.split("-")

    return date(year, int(month), int(day))


def parse_trade_log(filepath: Path) -> list[dict]:
    """Parse trade_log.md and return a list of trade dicts including all fields."""
    if not filepath.exists():
        return []

    trades = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]
            if not cells:
                continue
            first = cells[0]
            if not first.isdigit():
                continue
            if len(cells) < 9:
                continue

            try:
                trade = {
                    "num": int(first),
                    "date_raw": cells[1],
                    "variety": cells[2],
                    "strategy": cells[3],
                    "entry": cells[4] if len(cells) > 4 else "",
                    "exit": cells[5] if len(cells) > 5 else "",
                    "futures": cells[6] if len(cells) > 6 else "",
                    "holding": cells[7] if len(cells) > 7 else "",
                    "pnl": parse_pnl(cells[8]),
                    "attribution": cells[9] if len(cells) > 9 else "",
                    "close_date": parse_date(cells[1]),
                }
                trades.append(trade)
            except (ValueError, IndexError):
                continue

    return trades


def parse_iv_history(filepath: Path, target_month: str) -> dict[str, dict]:
    """Parse iv_history.csv and return IV stats per variety for the target month.

    Returns dict like: {"菜籽粕": {"min": 0.14, "max": 0.16, "rows": 5}, ...}
    """
    result: dict[str, dict] = {}
    if not filepath.exists():
        return result

    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_date = row.get("date", "").strip()
            if not row_date.startswith(target_month):
                continue

            name = row.get("name", "").strip()
            iv_str = row.get("iv_est", "").strip()
            if not name or not iv_str:
                continue

            try:
                iv_val = float(iv_str)
            except ValueError:
                continue

            if name not in result:
                result[name] = {"min": iv_val, "max": iv_val, "values": []}
            else:
                result[name]["min"] = min(result[name]["min"], iv_val)
                result[name]["max"] = max(result[name]["max"], iv_val)
            result[name]["values"].append(iv_val)

    # Add count and average
    for name in result:
        vals = result[name]["values"]
        result[name]["count"] = len(vals)
        result[name]["avg"] = sum(vals) / len(vals) if vals else 0.0
        del result[name]["values"]

    return result


def extract_strategy_group(strategy_raw: str) -> str:
    """Extract a clean strategy group name from the raw strategy description.

    Examples:
      "Put 信用价差 P2375/P2350" → "Put 信用价差"
      "买跨式 C2320+P2320"      → "买跨式"
    """
    import re
    # Strip strike/suffix info: everything after the first occurrence of a
    # strike-like pattern (C/P followed by digits, or standalone digits after space)
    s = strategy_raw.strip()
    # Try to cut at the strike pattern: letter+digits
    m = re.search(r"\s[CcPp]\d{3,}", s)
    if m:
        return s[: m.start()].strip()
    # Also try just digits at end
    m = re.search(r"\s\d{3,}", s)
    if m:
        return s[: m.start()].strip()
    return s


# ── 报告生成 ──────────────────────────────────────────────


def generate_report(
    target_month: str,
    month_trades: list[dict],
    all_trades: list[dict],
    iv_data: dict[str, dict],
) -> str:
    """Generate the full Markdown report string."""
    year, month_num = target_month.split("-")
    month_name = f"{year}年{int(month_num)}月"

    # ── Account overview ──
    # Cumulative P&L BEFORE this month (all trades with close_date < month start)
    month_start = date(int(year), int(month_num), 1)
    if int(month_num) == 12:
        month_end = date(int(year) + 1, 1, 1)
    else:
        month_end = date(int(year), int(month_num) + 1, 1)

    cum_before = sum(t["pnl"] for t in all_trades if t["close_date"] < month_start)
    month_pnl = sum(t["pnl"] for t in month_trades)
    cum_after = cum_before + month_pnl

    lines = []
    lines.append(f"# 月度报告：{month_name}")
    lines.append("")
    lines.append(f"> 生成日期：{date.today().isoformat()}")
    lines.append("")

    # 1. Account overview
    lines.append("## 1. 账户概况")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 月初累计盈亏 | {cum_before:+.0f} ¥ |")
    lines.append(f"| 月末累计盈亏 | {cum_after:+.0f} ¥ |")
    lines.append(f"| 本月净盈亏 | {month_pnl:+.0f} ¥ |")
    lines.append(f"| 本月交易笔数 | {len(month_trades)} |")
    month_wins = [t for t in month_trades if t["pnl"] > 0]
    month_losses = [t for t in month_trades if t["pnl"] < 0]
    if month_trades:
        month_win_rate = len(month_wins) / len(month_trades) * 100
        lines.append(f"| 本月胜率 | {month_win_rate:.1f}% ({len(month_wins)}W/{len(month_losses)}L) |")
    else:
        lines.append(f"| 本月胜率 | N/A |")
    lines.append("")
    lines.append("> 注：账户值 = 初始本金 + 累计盈亏。若需实际账户值，请加上初始本金。")
    lines.append("")

    # 2. Trades table
    lines.append("## 2. 本月交易明细")
    lines.append("")
    if month_trades:
        lines.append("| # | 日期 | 品种 | 策略 | 持有 | P&L | 归因 |")
        lines.append("|---|------|------|------|------|-----|------|")
        for t in month_trades:
            pnl_str = f"**{t['pnl']:+.0f} ¥**"
            lines.append(
                f"| {t['num']} | {t['date_raw']} | {t['variety']} | {t['strategy']} "
                f"| {t['holding']} | {pnl_str} | {t['attribution']} |"
            )
    else:
        lines.append("> 本月无交易记录。")
    lines.append("")

    # 3. Strategy breakdown
    lines.append("## 3. 策略分析")
    lines.append("")
    if month_trades:
        strategy_groups: dict[str, dict] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0})
        for t in month_trades:
            group = extract_strategy_group(t["strategy"])
            strategy_groups[group]["count"] += 1
            strategy_groups[group]["pnl"] += t["pnl"]
            if t["pnl"] > 0:
                strategy_groups[group]["wins"] += 1

        lines.append("| 策略 | 笔数 | 总 P&L | 胜率 |")
        lines.append("|------|------|--------|------|")
        for group, stats in sorted(strategy_groups.items()):
            wr = (stats["wins"] / stats["count"] * 100) if stats["count"] > 0 else 0
            lines.append(
                f"| {group} | {stats['count']} | {stats['pnl']:+.0f} ¥ | {wr:.0f}% |"
            )
    else:
        lines.append("> 本月无交易，无策略数据。")
    lines.append("")

    # 4. IV environment
    lines.append("## 4. IV 环境概况")
    lines.append("")
    lines.append(f"> 数据来源：`data/iv_history.csv`，当月采集记录")
    lines.append("")
    if iv_data:
        lines.append("| 品种 | IV 最低 | IV 最高 | IV 均值 | 采集次数 |")
        lines.append("|------|---------|---------|---------|----------|")
        for name in sorted(iv_data.keys()):
            stats = iv_data[name]
            lines.append(
                f"| {name} | {stats['min']:.1%} | {stats['max']:.1%} "
                f"| {stats['avg']:.1%} | {stats['count']} |"
            )
    else:
        lines.append("> 本月暂无 IV 采集数据。请运行 `python3 tools/iv_collector.py` 采集。")
    lines.append("")

    # 5. Discipline check
    lines.append("## 5. 纪律检查")
    lines.append("")
    lines.append("- [ ] 本月无规则违反（裸空 / 腿序反 / 越止盈线不平 / override）")
    lines.append("- 违反记录：")
    lines.append("  - （如有，请逐条记录）")
    lines.append("")
    lines.append("> 自查清单：每笔交易是否满足四道门？平仓是否按规则？是否因「那一下爽」追单？")
    lines.append("")

    # 6. Key lesson
    lines.append("## 6. 关键教训")
    lines.append("")
    lines.append("> （待填写 — 本月最大的一个教训是什么？）")
    lines.append("")
    lines.append("<!-- 提示：复盘本周所有亏损交易，找共性 → 更新 mistakes.md -->")
    lines.append("")

    # 7. Next month plan
    lines.append("## 7. 下月计划")
    lines.append("")
    lines.append("> （待填写 — 下个月的重点改进方向？）")
    lines.append("")
    lines.append("<!-- 提示：从本月教训出发，定 1-2 个可执行的改进动作 -->")
    lines.append("")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="月度 P&L 报告生成器 — 从 trade_log.md 和 iv_history.csv 生成月度 Markdown 报告"
    )
    parser.add_argument(
        "--month",
        type=str,
        default=date.today().strftime("%Y-%m"),
        help="目标月份，格式 YYYY-MM（默认：当前月份）",
    )
    args = parser.parse_args()

    # Validate month format
    try:
        datetime.strptime(args.month, "%Y-%m")
    except ValueError:
        print(f"⚠️  月份格式错误: {args.month}")
        print("   请使用 YYYY-MM 格式，例如 2026-07")
        sys.exit(1)

    target_month = args.month

    # Parse trade log
    all_trades = parse_trade_log(TRADE_LOG)
    month_start = date(int(target_month[:4]), int(target_month[5:7]), 1)
    if int(target_month[5:7]) == 12:
        month_end = date(int(target_month[:4]) + 1, 1, 1)
    else:
        month_end = date(int(target_month[:4]), int(target_month[5:7]) + 1, 1)

    month_trades = [t for t in all_trades if month_start <= t["close_date"] < month_end]

    # Parse IV history
    iv_data = parse_iv_history(IV_HISTORY, target_month)

    # Generate report
    report = generate_report(target_month, month_trades, all_trades, iv_data)

    # Write to file
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"{target_month}.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 月度报告已生成: {output_path}")
    if month_trades:
        month_pnl = sum(t["pnl"] for t in month_trades)
        print(f"   本月 {len(month_trades)} 笔交易，净盈亏 {month_pnl:+.0f} ¥")
    else:
        print(f"   本月无交易记录（已生成骨架报告）")
    if iv_data:
        print(f"   IV 数据覆盖 {len(iv_data)} 个品种")
    else:
        print(f"   ⚠️  本月暂无 IV 采集数据")


if __name__ == "__main__":
    main()
