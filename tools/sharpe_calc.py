#!/usr/bin/env python3
"""
sharpe_calc.py — Sharpe Ratio & Drawdown Calculator
═════════════════════════════════════════════════════
Reads trade_log.md and calculates key performance metrics:
  - Total P&L, total trades, win rate
  - Average win / average loss
  - Profit factor (total won / |total lost|)
  - Annualized Sharpe ratio (242 trading days, Chinese futures)
  - Maximum drawdown (peak-to-trough)
  - Monthly P&L breakdown

用法：
  python3 tools/sharpe_calc.py                     # 打印汇总表
  python3 tools/sharpe_calc.py --csv               # CSV 输出
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
TRADE_LOG = PROJECT_DIR / "trade_log.md"
TRADING_DAYS_PER_YEAR = 242
MIN_TRADING_DAYS = 5

# ── 辅助函数 ─────────────────────────────────────────────


def parse_pnl(raw: str) -> float:
    """Parse a P&L cell like '**−¥40**' or '**+¥10**' into a float."""
    s = raw.strip()
    # Strip markdown bold
    s = s.replace("**", "")
    # Remove currency symbol
    s = s.replace("¥", "").replace("￥", "")
    # Handle Unicode minus sign (U+2212) and fullwidth hyphen
    s = s.replace("−", "-").replace("－", "-")
    # Remove stray spaces and commas
    s = s.replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(date_str: str, year: int = 2026) -> date:
    """Parse a date cell like '06-26→07-02', '06-26→29', or '06-26'.

    Returns the *closing* date (end of range) for multi-day trades.
    """
    date_str = date_str.strip()
    if "→" in date_str:
        parts = date_str.split("→")
        start_part = parts[0].strip()
        end_part = parts[1].strip()
        if "-" in end_part:
            month, day = end_part.split("-")
        else:
            # Day only — inherit month from start
            start_month = start_part.split("-")[0]
            month = start_month
            day = end_part
    else:
        month, day = date_str.split("-")

    return date(year, int(month), int(day))


def parse_trade_log(filepath: Path) -> list[dict]:
    """Parse trade_log.md and return a list of trade dicts.

    Each dict has: num, date_raw, variety, strategy, pnl, close_date
    """
    if not filepath.exists():
        return []

    trades = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue

            cells = [c.strip() for c in line.split("|")]
            # Remove leading/trailing empty cells from split
            cells = [c for c in cells if c]

            if not cells:
                continue

            # Data rows have a digit as first cell; skip headers, separators, summaries
            first = cells[0]
            if not first.isdigit():
                continue

            # Need at least: #, 日期, 品种, 策略, ..., P&L
            if len(cells) < 9:
                continue

            try:
                trade = {
                    "num": int(first),
                    "date_raw": cells[1],
                    "variety": cells[2],
                    "strategy": cells[3],
                    "pnl": parse_pnl(cells[8]),
                    "close_date": parse_date(cells[1]),
                }
                trades.append(trade)
            except (ValueError, IndexError):
                continue

    return trades


# ── 计算函数 ─────────────────────────────────────────────


def compute_daily_pnl(trades: list[dict]) -> dict[date, float]:
    """Group trades by close date and sum P&L per day."""
    daily: dict[date, float] = defaultdict(float)
    for t in trades:
        daily[t["close_date"]] += t["pnl"]
    return dict(sorted(daily.items()))


def compute_sharpe(daily_pnl: dict[date, float]) -> Optional[float]:
    """Compute annualized Sharpe ratio from daily P&L.

    Formula: mean(daily_pnl) / std(daily_pnl) * sqrt(242)
    """
    if len(daily_pnl) < MIN_TRADING_DAYS:
        return None

    values = list(daily_pnl.values())
    mean_val = sum(values) / len(values)
    if len(values) < 2:
        return None
    variance = sum((v - mean_val) ** 2 for v in values) / (len(values) - 1)
    std_val = math.sqrt(variance)
    if std_val == 0:
        return None
    return (mean_val / std_val) * math.sqrt(TRADING_DAYS_PER_YEAR)


def compute_max_drawdown(trades: list[dict]) -> float:
    """Compute maximum drawdown (peak-to-trough) from cumulative P&L."""
    if not trades:
        return 0.0
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in sorted(trades, key=lambda x: x["close_date"]):
        cumulative += t["pnl"]
        if cumulative > peak:
            peak = cumulative
        dd = cumulative - peak
        if dd < max_dd:
            max_dd = dd
    return max_dd


def compute_monthly_breakdown(trades: list[dict]) -> dict[str, float]:
    """Group P&L by YYYY-MM."""
    monthly: dict[str, float] = defaultdict(float)
    for t in trades:
        key = t["close_date"].strftime("%Y-%m")
        monthly[key] += t["pnl"]
    return dict(sorted(monthly.items()))


# ── 输出 ──────────────────────────────────────────────────


def print_summary(trades: list[dict], daily_pnl: dict[date, float], as_csv: bool = False):
    """Print summary statistics as a table or CSV."""
    if not trades:
        print("ℹ️  trade_log.md 中暂无有效交易记录。")
        return

    total_pnl = sum(t["pnl"] for t in trades)
    total_trades = len(trades)
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    total_won = sum(wins)
    total_lost = abs(sum(losses))
    profit_factor = total_won / total_lost if total_lost > 0 else float("inf")
    sharpe = compute_sharpe(daily_pnl)
    max_dd = compute_max_drawdown(trades)
    monthly = compute_monthly_breakdown(trades)

    if as_csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_trades", total_trades])
        writer.writerow(["total_pnl", f"{total_pnl:.2f}"])
        writer.writerow(["win_count", win_count])
        writer.writerow(["loss_count", loss_count])
        writer.writerow(["win_rate_pct", f"{win_rate:.1f}"])
        writer.writerow(["avg_win", f"{avg_win:.2f}"])
        writer.writerow(["avg_loss", f"{avg_loss:.2f}"])
        writer.writerow(["profit_factor", f"{profit_factor:.2f}"])
        if sharpe is not None:
            writer.writerow(["sharpe_ratio", f"{sharpe:.3f}"])
        else:
            writer.writerow(["sharpe_ratio", "N/A (样本不足)"])
        writer.writerow(["max_drawdown", f"{max_dd:.2f}"])
        for month, pnl in monthly.items():
            writer.writerow([f"monthly_pnl_{month}", f"{pnl:.2f}"])
        return

    # Human-readable table
    print()
    print("═" * 56)
    print("  📊  Sharpe Ratio & Drawdown 分析")
    print("═" * 56)
    print(f"  数据来源: {TRADE_LOG.name}")
    print(f"  交易日数: {len(daily_pnl)} 天")
    print(f"  交易笔数: {total_trades} 笔")
    print("─" * 56)
    print(f"  总 P&L:          {total_pnl:>+10.0f} ¥")
    print(f"  胜率:            {win_rate:>10.1f}%  ({win_count}W / {loss_count}L)")
    print(f"  平均盈利:        {avg_win:>+10.0f} ¥")
    print(f"  平均亏损:        {avg_loss:>+10.0f} ¥")
    print(f"  盈亏比 (PF):     {profit_factor:>10.2f}")
    print("─" * 56)
    if sharpe is not None:
        print(f"  年化 Sharpe:     {sharpe:>10.3f}")
    else:
        print(f"  年化 Sharpe:     {'N/A':>10s}  ⚠️  样本不足（需至少 {MIN_TRADING_DAYS} 个交易日）")
    print(f"  最大回撤:        {max_dd:>+10.0f} ¥")
    print("─" * 56)
    if monthly:
        print("  月度 P&L 分解:")
        for month, pnl in monthly.items():
            marker = "✅" if pnl > 0 else "❌"
            print(f"    {month}:  {pnl:>+10.0f} ¥  {marker}")
    else:
        print("  月度 P&L 分解:  (暂无)")
    print("═" * 56)
    print()


# ── CLI ───────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Sharpe Ratio & Drawdown Calculator — 从 trade_log.md 计算绩效指标"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="以 CSV 格式输出（便于导入外部工具）",
    )
    args = parser.parse_args()

    if not TRADE_LOG.exists():
        print(f"⚠️  找不到交易记录文件: {TRADE_LOG}")
        print("   请确保 trade_log.md 存在于项目根目录。")
        sys.exit(1)

    trades = parse_trade_log(TRADE_LOG)
    if not trades:
        print("ℹ️  trade_log.md 存在但没有有效的交易记录。")
        print("   请在 trade_log.md 中按格式添加交易记录后重试。")
        sys.exit(0)

    daily_pnl = compute_daily_pnl(trades)
    print_summary(trades, daily_pnl, as_csv=args.csv)


if __name__ == "__main__":
    main()
