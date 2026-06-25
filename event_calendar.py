#!/usr/bin/env python3
"""
商品期权事件日历
────────────────
列出各品种已知的固定事件 + 判断未来N天是否有值得关注的触发点。

用法:
  python3 event_calendar.py                   # 显示近期事件
  python3 event_calendar.py --days 7          # 未来7天
  python3 event_calendar.py --variety c,m     # 只看特定品种
  python3 event_calendar.py --json            # JSON输出(供其他脚本调用)
"""

import json
import argparse
from datetime import datetime, date, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional

# ═══════════════════════════════════════════
# 品种配置
# ═══════════════════════════════════════════

VARIETIES = {
    "au": {"name": "沪金",    "futures": 870},
    "m":  {"name": "豆粕",    "futures": 2800},
    "c":  {"name": "玉米",    "futures": 2300},
    "cf": {"name": "棉花",    "futures": 13500},
    "sr": {"name": "白糖",    "futures": 5600},
    "ta": {"name": "PTA",     "futures": 4800},
    "i":  {"name": "铁矿石",  "futures": 780},
    "ru": {"name": "橡胶",    "futures": 17000},
    "ma": {"name": "甲醇",    "futures": 2450},
    "rm": {"name": "菜籽粕",  "futures": 2500},
}

# ═══════════════════════════════════════════
# 事件定义
# ═══════════════════════════════════════════

@dataclass
class CalendarEvent:
    date: str              # "2026-06-30"
    title: str             # "USDA 种植面积报告"
    varieties: List[str]   # ["c", "m", "cf"]
    impact: str            # "high" | "medium" | "low"
    category: str          # "report" | "data" | "weather" | "policy" | "expiry"
    description: str       # 一句话说明
    expected_move_pct: float  # 历史平均波动幅度(%)
    best_strategy: str     # "straddle" | "directional" | "ratio"

# ═══════════════════════════════════════════
# 2026 年事件日历
# ═══════════════════════════════════════════

EVENTS_2026 = [
    # ── 月度报告类 ──
    CalendarEvent(
        "2026-07-10", "USDA WASDE 7月供需报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "全球及美国谷物/油籽供需平衡表，历史波动 ±2-5%",
        3.0, "straddle"
    ),
    CalendarEvent(
        "2026-08-12", "USDA WASDE 8月供需报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "首次基于田间调查的单产预估，波动通常大于7月",
        4.0, "straddle"
    ),
    CalendarEvent(
        "2026-09-11", "USDA WASDE 9月供需报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "收获前关键单产调整",
        2.5, "straddle"
    ),

    # ── 季度重磅 ──
    CalendarEvent(
        "2026-06-30", "USDA 种植面积 + 季度库存报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "年度最重要的农产品报告！实际种植面积 vs 3月预估，单日波动可达 ±5%",
        5.0, "straddle"
    ),
    CalendarEvent(
        "2026-09-30", "USDA 季度谷物库存报告",
        ["c", "m", "rm"], "medium", "report",
        "截至9月1日库存，反映旧作需求",
        2.0, "straddle"
    ),

    # ── 每周数据 ──
    CalendarEvent(
        "weekly-monday", "USDA 作物生长进度 (每周二早)",
        ["c", "m", "rm", "cf", "sr"], "medium", "data",
        "优良率变化是天气炒作核心指标",
        1.5, "directional"
    ),
    CalendarEvent(
        "weekly-wednesday", "EIA 原油库存 (每周三晚)",
        ["ta", "ma"], "medium", "data",
        "PTA和甲醇受原油情绪传导明显",
        1.5, "directional"
    ),

    # ── 中国数据 ──
    CalendarEvent(
        "2026-07-01", "中国 6月 PMI",
        ["i", "ru", "ta", "ma", "au"], "medium", "data",
        "宏观情绪影响工业品，金价受利率预期传导",
        1.0, "directional"
    ),
    CalendarEvent(
        "2026-07-15", "中国 Q2 GDP + 6月经济数据",
        ["i", "ru", "ta", "ma"], "high", "data",
        "季度宏观数据包，工业品方向性波动",
        1.5, "directional"
    ),

    # ── 天气季节性 ──
    CalendarEvent(
        "2026-07-01", "美国玉米/大豆关键生长期 (7-8月)",
        ["c", "m", "rm"], "high", "weather",
        "7月授粉期天气决定单产，任何干旱预报都触发波动。持续监控，非单日事件。",
        2.0, "directional"
    ),

    # ── 政策/会议 ──
    CalendarEvent(
        "2026-07-29", "美联储 FOMC 利率决议",
        ["au", "i", "ru", "ta", "ma"], "high", "policy",
        "金价最敏感，工业品受美元传导",
        1.5, "straddle"
    ),

    # ── 合约到期 ──
    CalendarEvent(
        "2026-07-15", "au2607 最后交易日 (沪金)",
        ["au"], "low", "expiry",
        "末日轮Gamma效应，但不建议参与——价差极宽。仅供观察。",
        5.0, "straddle"
    ),
    CalendarEvent(
        "2026-08-15", "au2608 最后交易日 (沪金)",
        ["au"], "low", "expiry",
        "你最熟悉的合约末期，注意进入末日窗口后价差急剧放大",
        5.0, "straddle"
    ),
]


def next_weekday(d: date, weekday: int) -> date:
    """返回从d之后的下一个指定星期几(0=Mon, 6=Sun)"""
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def resolve_weekly_events(events: List[CalendarEvent], from_date: date, days: int) -> List[CalendarEvent]:
    """将 weekly-* 事件解析为具体日期"""
    resolved = []
    end_date = from_date + timedelta(days=days)

    for ev in events:
        if ev.date.startswith("weekly-"):
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2,
                "thursday": 3, "friday": 4
            }
            for day_name, day_num in day_map.items():
                if day_name in ev.date:
                    d = next_weekday(from_date - timedelta(days=1), day_num)
                    while d <= end_date:
                        resolved.append(CalendarEvent(
                            date=d.strftime("%Y-%m-%d"),
                            title=ev.title,
                            varieties=ev.varieties,
                            impact=ev.impact,
                            category=ev.category,
                            description=ev.description,
                            expected_move_pct=ev.expected_move_pct,
                            best_strategy=ev.best_strategy,
                        ))
                        d += timedelta(days=7)
                    break
        else:
            resolved.append(ev)
    return resolved


def get_upcoming_events(from_date: Optional[date] = None, days: int = 7,
                        varieties: Optional[List[str]] = None) -> List[dict]:
    """获取未来N天的事件列表"""
    if from_date is None:
        from_date = date.today()

    resolved = resolve_weekly_events(EVENTS_2026, from_date, days)

    upcoming = []
    for ev in resolved:
        try:
            ev_date = date.fromisoformat(ev.date)
        except ValueError:
            continue

        days_until = (ev_date - from_date).days

        if 0 <= days_until <= days:
            # 品种过滤
            if varieties:
                v_match = [v for v in ev.varieties if v in varieties]
                if not v_match:
                    continue

            upcoming.append({
                "date": ev.date,
                "days_until": days_until,
                "title": ev.title,
                "varieties": ev.varieties,
                "variety_names": [VARIETIES[v]["name"] for v in ev.varieties if v in VARIETIES],
                "impact": ev.impact,
                "category": ev.category,
                "description": ev.description,
                "expected_move_pct": ev.expected_move_pct,
                "best_strategy": ev.best_strategy,
                "urgency": "🔴 立即" if days_until <= 2 else ("🟡 准备" if days_until <= 5 else "🟢 跟踪"),
            })

    upcoming.sort(key=lambda e: e["days_until"])
    return upcoming


# ═══════════════════════════════════════════
# 输出
# ═══════════════════════════════════════════

def print_events(events: List[dict]):
    """终端友好输出"""
    if not events:
        print("\n  😴 未来几天无事件触发")
        return

    print(f"\n{'─'*80}")
    print(f"  📅 未来事件日历 — {date.today().strftime('%Y-%m-%d')}")
    print(f"{'─'*80}")

    for ev in events:
        urgency_icon = ev['urgency'].split()[0]
        impact_bar = "🔥" if ev['impact'] == 'high' else ("⚡" if ev['impact'] == 'medium' else "·")
        varieties_str = ", ".join(f"{v}({VARIETIES[v]['name']})" for v in ev['varieties'] if v in VARIETIES)
        days_str = f"D-{ev['days_until']}" if ev['days_until'] > 0 else "今天!"
        strategy_icon = "⇅" if ev['best_strategy'] == 'straddle' else ("→" if ev['best_strategy'] == 'directional' else "⋮")

        print(f"\n  {urgency_icon} {days_str:>4} │ {impact_bar} {ev['title']}")
        print(f"         │ 品种: {varieties_str}")
        print(f"         │ 策略: {strategy_icon} {ev['best_strategy']}  |  历史波动: ±{ev['expected_move_pct']}%")
        print(f"         │ {ev['description']}")

    print(f"\n{'─'*80}")
    print(f"  策略提示:")
    print(f"    straddle  = 买入ATM跨式 (Call+Put)，赌跳空，不赌方向")
    print(f"    directional = 顺势买方向性ATM期权，需要预判")
    print(f"  D-0~2 = 可以进场 | D-3~5 = 准备资金 | D-6+ = 跟踪观察")
    print(f"{'─'*80}\n")


def main():
    parser = argparse.ArgumentParser(description="商品期权事件日历")
    parser.add_argument('--days', type=int, default=7, help='未来N天 (默认: 7)')
    parser.add_argument('--variety', type=str, default=None, help='品种过滤 (逗号分隔)')
    parser.add_argument('--json', action='store_true', help='JSON输出')
    args = parser.parse_args()

    varieties = None
    if args.variety:
        varieties = [v.strip() for v in args.variety.split(',')]

    events = get_upcoming_events(days=args.days, varieties=varieties)

    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
    else:
        print_events(events)


if __name__ == '__main__':
    main()
