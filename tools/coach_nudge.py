#!/usr/bin/env python3
"""
教练飞书轰炸 — 定时推送 + 手动补刀

用法：
  python3 tools/coach_nudge.py <slot>
  python3 tools/coach_nudge.py --list   查看所有 slot
  python3 tools/coach_nudge.py --now    立即发当前时段对应的消息

Slot 列表见 NUDGES 字典。
"""

import sys
import requests
from datetime import datetime, time

***REMOVED***

NUDGES = {
    # ── 上午 ──
    "morning": {
        "label": "09:30 签到",
        "msg": (
            "☕ 瞒瞒，签到。\n"
            "打开 Claude Code，说「签到」。"
        ),
    },
    "scanner": {
        "label": "10:00 Scanner 追命",
        "msg": (
            "📡 Scanner 跑了吗？\n"
            "3 分钟的事。不跑 = 不知道今天有没有机会 = 白过一天。\n"
            "`python3 tools/unified_scanner.py`"
        ),
    },
    "drill_b": {
        "label": "10:30 Drill B",
        "msg": (
            "🔁 Drill B。5 分钟。\n"
            "上次 92%/2.7s，别让数字往下掉。\n"
            "`python3 tools/drill_system.py B`"
        ),
    },
    "sinclair": {
        "label": "11:00 Sinclair",
        "msg": (
            "📖 Sinclair Ch5 今天的内容。\n"
            "带一个问题读：这个能不能改进我的五条打分？\n"
            "读完写 3-5 行进 journal。"
        ),
    },

    # ── 下午 ──
    "afternoon": {
        "label": "14:00 午后扫荡",
        "msg": (
            "⏰ 下午了——上午欠的现在补。\n"
            "Scanner → IV → Drill B → Sinclair。按顺序，先 Scanner。\n"
            "做完了就无视这条。"
        ),
    },
    "d_drill": {
        "label": "15:00 D-Drill",
        "msg": (
            "🛑 D-Drill 17 题。\n"
            "规则写完整句子，不写编号（「下跌趋势不卖 Put」不是「禁止 8」）。\n"
            "D 门 0/20，这是你唯一的卡点。不过=永远卡在 S1。\n"
            "`python3 tools/d_drill.py`"
        ),
    },
    "english": {
        "label": "16:00 英语",
        "msg": (
            "🇬🇧 英语 20 分钟。\n"
            "Mike 视频 → 跟读 → 90s 炸弹 → 笔译。\n"
            "不用完美，张嘴就行。"
        ),
    },

    # ── 收尾 ──
    "wrapup": {
        "label": "17:00 收尾",
        "msg": (
            "📝 收尾三连：\n"
            "① `python3 tools/daily_quiz.py`\n"
            "② 写 journal/YYYY-MM-DD.md\n"
            "③ `git add -A && git commit -m \"$(date +%F)\" && git push`\n"
            "不提交 = 今天没发生过。"
        ),
    },
    "evening": {
        "label": "20:00 晚间复盘",
        "msg": (
            "🌙 复盘一句：\n"
            "今天学到的 1 个东西，能用在明天的扫描判断上——是什么？"
        ),
    },
    "d_check": {
        "label": "21:00 D 门觉察",
        "msg": (
            "🛑 D 门每日一问：\n"
            "过去 24h 有没有想破规则的瞬间？\n"
            "「但我这次有个 read」——有过这个念头吗？\n"
            "有就写下来。不记过、不归零——只是看见它。"
        ),
    },
}

# 手动补刀 slot — 不在定时表里，我（教练）手动触发
MANUAL = {
    "scanner_miss": {
        "label": "手动：Scanner 还没跑",
        "msg": (
            "📡 Scanner 还没跑？\n"
            "签到都签了，就差这 3 分钟。现在跑——我等你。\n"
            "`python3 tools/unified_scanner.py`"
        ),
    },
    "journal_miss": {
        "label": "手动：journal 没写",
        "msg": (
            "📝 journal 空的。\n"
            "不写 = 今天做过的事明天全部忘掉 = 数据白积累。\n"
            "现在打开 journal/YYYY-MM-DD.md，训练分数 + Scanner 结论 + 学到的东西，5 行就行。"
        ),
    },
    "commit_miss": {
        "label": "手动：没 commit",
        "msg": (
            "🔴 还没 push。\n"
            "`git add -A && git commit -m \"$(date +%F)\" && git push`\n"
            "不提交 = 今天没发生过。"
        ),
    },
    "d_warning": {
        "label": "手动：D 门危险",
        "msg": (
            "⚠️ 刚才那个操作——停下来想 3 秒。\n"
            "「任何情况下」的意思就是任何情况。\n"
            "没有「但这次不一样」。"
        ),
    },
}


def send(msg: str):
    """发飞书消息，静默失败"""
    payload = {"msg_type": "text", "content": {"text": msg}}
    try:
        r = requests.post(FEISHU_WEBHOOK, json=payload, timeout=5)
        if r.status_code == 200:
            print(f"✅ 已发送")
        else:
            print(f"⚠️ 飞书返回 {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ 发送失败: {e}")


def list_slots():
    print("定时 Slot：")
    for name, cfg in NUDGES.items():
        print(f"  {name:12s}  {cfg['label']}")
    print()
    print("手动补刀 Slot：")
    for name, cfg in MANUAL.items():
        print(f"  {name:16s}  {cfg['label']}")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 tools/coach_nudge.py <slot>")
        print("      python3 tools/coach_nudge.py --list")
        print("      python3 tools/coach_nudge.py --now")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--list":
        list_slots()
        return

    if arg == "--now":
        # 根据当前时间自动匹配 slot
        now = datetime.now().time()
        matched = None
        time_map = {
            "morning": time(9, 0),
            "scanner": time(10, 0),
            "drill_b": time(10, 30),
            "sinclair": time(11, 0),
            "afternoon": time(14, 0),
            "d_drill": time(15, 0),
            "english": time(16, 0),
            "wrapup": time(17, 0),
            "evening": time(20, 0),
            "d_check": time(21, 0),
        }
        # 找最近一个已过的 slot（30 分钟内）
        best = None
        for name, t in sorted(time_map.items(), key=lambda x: x[1]):
            if t <= now:
                best = name
        if best:
            cfg = NUDGES[best]
            print(f"🕐 当前时段匹配: {best} ({cfg['label']})")
            print(f"   消息预览: {cfg['msg'][:80]}...")
            send(cfg["msg"])
        else:
            print("🕐 当前不在任何 slot 时段内")
        return

    # 精确 slot 发送
    if arg in NUDGES:
        cfg = NUDGES[arg]
        print(f"📤 {cfg['label']}")
        send(cfg["msg"])
    elif arg in MANUAL:
        cfg = MANUAL[arg]
        print(f"📤 {cfg['label']}")
        send(cfg["msg"])
    else:
        print(f"❌ 未知 slot: {arg}")
        print("   python3 tools/coach_nudge.py --list 查看全部")
        sys.exit(1)


if __name__ == "__main__":
    main()
