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
    estimated_move_pct: float  # ⚠️常识估算，非实测，禁用于交易判断（7/27 数据诚实约束，8/14 核实无数据源）
    best_strategy: str     # "straddle" | "directional" | "ratio"
    routine: bool = True   # True=例行(已消化) False=非例行(意外·不可预知)
    time_edt: str = ""     # 美东发布时间 "14:00" / "10:30" 等，空=不适用


def edt_to_bjt(time_edt: str) -> str:
    """美东时间→北京时间。EDT=UTC-4, BJT=UTC+8, 差12小时。"""
    if not time_edt:
        return ""
    try:
        parts = time_edt.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        bjt_h = h + 12
        if bjt_h >= 24:
            return f"次日 {bjt_h - 24:02d}:{m:02d}"
        return f"{bjt_h:02d}:{m:02d}"
    except (ValueError, IndexError):
        return ""

# ═══════════════════════════════════════════
# 持续性地缘事件（无固定日期，始终有效）
# ═══════════════════════════════════════════

@dataclass
class OngoingEvent:
    title: str
    varieties: List[str]
    impact: str
    description: str
    best_strategy: str
    estimated_move_pct: float  # ⚠️常识估算，非实测（与 CalendarEvent 同约束）
    started: str  # 开始日期

ONGOING_EVENTS = [
    # 持续性地缘事件已移除。地缘事件通过趋势触发（5日涨跌>2%）自动捕捉，
    # 不需要人工维护。日历只保留固定日期事件（USDA/GDP/FOMC等）。
]

# ═══════════════════════════════════════════
# 2026 年事件日历
# ═══════════════════════════════════════════
# ⚠️ 数据诚实（8/14）：所有 estimated_move_pct 均为常识估算，无历史数据源/统计口径/回测。
#    禁止用于交易判断（进/离场、仓位、缓冲比较）。真正的事件-波动库 → S2 待办。
#    已有 IV 数据时优先用 volatility.expected_move_pct()（IV×√(DTE/365)，可追溯）。

EVENTS_2026 = [
    # ── 月度报告类 ──
    CalendarEvent(
        "2026-07-10", "USDA WASDE 7月供需报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "全球及美国谷物/油籽供需平衡表，历史波动 ±2-5%",
        3.0, "straddle",
        time_edt="12:00"
    ),
    CalendarEvent(
        "2026-08-12", "USDA WASDE 8月供需报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "首次基于田间调查的单产预估，波动通常大于7月",
        4.0, "straddle",
        time_edt="12:00"
    ),
    CalendarEvent(
        "2026-09-11", "USDA WASDE 9月供需报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "收获前关键单产调整",
        2.5, "straddle",
        time_edt="12:00"
    ),

    # ── 季度重磅 ──
    CalendarEvent(
        "2026-06-30", "USDA 种植面积 + 季度库存报告",
        ["c", "m", "rm", "cf"], "high", "report",
        "年度最重要的农产品报告！实际种植面积 vs 3月预估，单日波动可达 ±5%",
        5.0, "straddle",
        time_edt="12:00"
    ),
    CalendarEvent(
        "2026-09-30", "USDA 季度谷物库存报告",
        ["c", "m", "rm"], "medium", "report",
        "截至9月1日库存，反映旧作需求",
        2.0, "straddle",
        time_edt="12:00"
    ),

    # ── 每周数据 ──
    CalendarEvent(
        "weekly-monday", "USDA 作物生长进度 (每周二早)",
        ["c", "m", "rm", "cf"], "medium", "data",
        "优良率变化是天气炒作核心指标",
        1.5, "directional",
        time_edt="16:00"
    ),
    CalendarEvent(
        "weekly-wednesday", "EIA 原油库存 (每周三晚)",
        ["ta", "ma"], "medium", "data",
        "PTA和甲醇受原油情绪传导明显",
        1.5, "directional",
        time_edt="10:30"
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
        1.5, "straddle",
        time_edt="14:00"
    ),
    CalendarEvent(
        "2026-09-16", "美联储 FOMC 利率决议 (含SEP/点阵图)",
        ["au", "i", "ru", "ta", "ma"], "high", "policy",
        "9月会议含经济预测摘要，波动通常大于无SEP会议",
        2.0, "straddle",
        time_edt="14:00"
    ),
    CalendarEvent(
        "2026-10-28", "美联储 FOMC 利率决议",
        ["au", "i", "ru", "ta", "ma"], "high", "policy",
        "10月会议无SEP，波动相对可控",
        1.5, "straddle",
        time_edt="14:00"
    ),
    CalendarEvent(
        "2026-12-09", "美联储 FOMC 利率决议 (含SEP/点阵图)",
        ["au", "i", "ru", "ta", "ma"], "high", "policy",
        "年度最后一次+经济预测，波动通常最大",
        2.0, "straddle",
        time_edt="14:00"
    ),

    # ── OPEC+ ──
    CalendarEvent(
        "2026-09-06", "OPEC+ 七国产量审查会议",
        ["ta", "ma"], "medium", "policy",
        "沙特/俄罗斯等七国月度产量合规审查，原油情绪传导PTA/甲醇",
        1.5, "directional"
    ),
    CalendarEvent(
        "2026-10-04", "OPEC+ JMMC 第68次监测会议",
        ["ta", "ma"], "medium", "policy",
        "联合部长级监测委员会，评估减产执行率",
        2.0, "directional"
    ),
    CalendarEvent(
        "2026-11-29", "OPEC+ 部长级全体会议",
        ["ta", "ma"], "high", "policy",
        "决定2027年产量政策框架，年度最重要OPEC+事件",
        3.0, "straddle"
    ),

    # ── 月度经济数据（中国）──
    CalendarEvent(
        "monthly-pmi", "中国月度 PMI (月底/月初发布)",
        ["i", "ru", "ta", "ma", "au"], "medium", "data",
        "宏观情绪影响工业品，金价受利率预期传导",
        1.0, "directional"
    ),

    # ── 白糖 ──
    CalendarEvent(
        "2026-11-15", "中国糖会 (郑州/昆明·年度)",
        ["sr"], "medium", "policy",
        "新榨季产量预估+政策定调（收储/进口配额），白糖方向性窗口",
        2.0, "directional"
    ),

    # ── 铁矿石政策 ──
    CalendarEvent(
        "2027-03-04", "全国两会 + 华北钢厂环保限产",
        ["i"], "high", "policy",
        "两会期间华北钢厂限产30%+，铁矿石需求骤降。每年例行，持续1-2周。",
        3.0, "directional"
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


def resolve_recurring_events(events: List[CalendarEvent], from_date: date, days: int) -> List[CalendarEvent]:
    """将 weekly-* / monthly-* 事件解析为具体日期"""
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
                            estimated_move_pct=ev.estimated_move_pct,
                            best_strategy=ev.best_strategy,
                            time_edt=ev.time_edt,
                        ))
                        d += timedelta(days=7)
                    break
        elif ev.date.startswith("monthly-"):
            # 月度事件：在日期范围内每个月的月底/月初各生成一条
            d = date(from_date.year, from_date.month, 1)
            while d <= end_date:
                # 月末：当月最后一天
                last_day = date(d.year, d.month, 1) + timedelta(days=32)
                last_day = date(last_day.year, last_day.month, 1) - timedelta(days=1)
                if from_date <= last_day <= end_date:
                    resolved.append(CalendarEvent(
                        date=last_day.strftime("%Y-%m-%d"),
                        title=ev.title,
                        varieties=ev.varieties,
                        impact=ev.impact,
                        category=ev.category,
                        description=ev.description,
                        estimated_move_pct=ev.estimated_move_pct,
                        best_strategy=ev.best_strategy,
                        time_edt=ev.time_edt,
                    ))
                # 下个月
                d = date(d.year, d.month, 1) + timedelta(days=32)
                d = date(d.year, d.month, 1)
        else:
            resolved.append(ev)
    return resolved


def get_upcoming_events(from_date: Optional[date] = None, days: int = 7,
                        varieties: Optional[List[str]] = None) -> List[dict]:
    """获取未来N天的事件列表 + 持续性地缘事件"""
    if from_date is None:
        from_date = date.today()

    resolved = resolve_recurring_events(EVENTS_2026, from_date, days)

    upcoming = []

    # 持续性地缘事件（始终显示，不参与倒计时）
    for oe in ONGOING_EVENTS:
        if varieties:
            v_match = [v for v in oe.varieties if v in varieties]
            if not v_match:
                continue
        upcoming.append({
            "date": "ongoing",
            "days_until": -1,  # 特殊标记：持续中
            "title": oe.title,
            "varieties": oe.varieties,
            "variety_names": [VARIETIES[v]["name"] for v in oe.varieties if v in VARIETIES],
            "impact": oe.impact,
            "category": "geo",
            "description": oe.description,
            "estimated_move_pct": oe.estimated_move_pct,
            "best_strategy": oe.best_strategy,
            "urgency": "🔴 持续中",
        })

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
                "routine": getattr(ev, 'routine', True),
                "description": ev.description,
                "estimated_move_pct": ev.estimated_move_pct,
                "best_strategy": ev.best_strategy,
                "time_edt": ev.time_edt,
                "time_bjt": edt_to_bjt(ev.time_edt),
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

        # 时区标注
        time_display = ""
        if ev.get('time_edt'):
            edt_str = f"{ev['time_edt']} EDT"
            bjt_str = f"{ev['time_bjt']} 北京"
            time_display = f"  🕐 {edt_str} / {bjt_str}"

        print(f"\n  {urgency_icon} {days_str:>4} │ {impact_bar} {ev['title']}{time_display}")
        print(f"         │ 品种: {varieties_str}")
        print(f"         │ 策略: {strategy_icon} {ev['best_strategy']}  |  预期波幅(常识估算): ±{ev['estimated_move_pct']}%")
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
