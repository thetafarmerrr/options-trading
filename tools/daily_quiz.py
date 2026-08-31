#!/usr/bin/env python3
"""
daily_quiz.py — 每日验收题自动出题器
─────────────────────────────────
从当日扫描/IV/交易日志中提取数据，自动生成 3 道验收题。
commit 前答对再 push。防"打卡式签到"。

用法：
  python3 tools/daily_quiz.py          # 出 3 道题
  python3 tools/daily_quiz.py --topic greeks  # 指定主题
"""

import sys, os, random, json, argparse, unicodedata
from datetime import datetime, date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
HISTORY_FILE = DATA_DIR / "quiz_history.json"

# ── 题库 ──

QUESTIONS = {
    "greeks": [
        {
            "q": "买 Call 借方价差，期货没动但 IV 从 18% 涨到 35%（ScP5→ScP80）。浮盈 ¥35。平还是等D-3事件？",
            "a": ["平", "锁利"],
            "hint": "Vega 利润已兑现（IV涨了17个点）。事件还没到 IV 已经涨了=市场提前定价。不等方向——锁 Vega 利润离开。买方离场不需要完美高点",
        },
        {
            "q": "卖 Put 信用价差。期货跌了 2%，IV 涨了 5%。浮亏主要来自哪个 Greek？",
            "a": ["delta", "Delta"],
            "hint": "标的跌了=Delta 亏。IV 涨=Vega 也亏（卖方 Vega 为负），但 2% 的标的移动=Delta 主导",
        },
        {
            "q": "买方买 ATM 跨式，D-3 USDA 报告。赚的是哪两个 Greek？说出来再下单。",
            "a": ["gamma vega", "Gamma Vega", "vega gamma", "Vega Gamma"],
            "hint": "买方=多 Gamma（方向对了加速）+ 多 Vega（IV 涨你赚）",
        },
        {
            "q": "卖方信用价差到期前 3 天，期货在卖腿上方安全。持仓还是平？主因是哪个 Greek？",
            "a": ["平", "gamma", "Gamma"],
            "hint": "Gamma 爆炸=风险太大。一天 Theta 换不来 Gamma 跳的风险",
        },
        {
            "q": "卖 Call 价差 vs 卖 Put 价差，哪个 Vega 风险天然更小？为什么？",
            "a": ["卖Call", "sell call", "Call", "call"],
            "hint": "杠杆效应不对称：跌时 IV 跳 > 涨时 IV 跳。卖 Call 的 Vega 风险天然小",
        },
        {
            "q": "IV 分位 17%（P17<价差P25阈值）。卖方该做什么？买方该做什么？",
            "a": ["卖方不做", "买方两关一判", "买方看趋势"],
            "hint": "卖方：权利金薄=不做。买方：过两关一判→第一关趋势≥1%或Tier1事件→第二关IV≤P25已过→判据RR≥5:1可进场",
        },
        {
            "q": "Thet 对卖方是___（朋友/敌人），对买方是___（朋友/敌人）",
            "a": ["朋友敌人", "朋友 敌人", "朋友，敌人"],
            "hint": "卖方赚 Theta=每天自动收钱。买方亏 Theta=每天自动扣钱",
        },
    ],
    "discipline": [
        {
            "q": "纪律计数器归零的五个触发条件，说出至少三个。",
            "a": ["裸空", "分腿", "止盈", "红线", "直觉"],
            "hint": "裸空窗口/分腿顺序错/越50%止盈线不平/破'任何情况下'红线/凭直觉赌方向",
        },
        {
            "q": "浮盈到了 credit 的 50%，规则怎么说？平还是等？",
            "a": ["平"],
            "hint": "开仓即写死止盈价。50% = 规则线，不讨论",
        },
        {
            "q": "D-1 高影响事件。卖方该做什么？",
            "a": ["不做", "不平仓", "不做卖方"],
            "hint": "事件前卖方退场。D-0/D-1 不做卖方",
        },
        {
            "q": "同品种已有持仓，Scanner 出来第二个信号。做还是不做？",
            "a": ["不做", "不加"],
            "hint": "同一品种不加同款。风险集中=纪律计数器归零的温床",
        },
    ],
    "strategy": [
        {
            "q": "借方价差第一关不过（标的5日涨跌<1%且无Tier1事件），但第二关过了（IV ScP5极便宜）。做不做？",
            "a": ["不做", "不做 "],
            "hint": "不做。第一关是硬门——标的横盘，IV再便宜 Theta也会吃掉权利金。两关一判顺序不能反：先看标的动不动，再看IV便不便宜",
        },
        {
            "q": "卖 Put 价差 OTM 公式是什么？",
            "a": ["(期货-卖腿)/期货", "期货-卖腿/期货"],
            "hint": "(期货−卖腿)÷期货。例：期货 2900 卖 2800 → OTM=3.4%",
        },
        {
            "q": "卖 Call 价差 OTM 公式是什么？和卖 Put 有什么区别？",
            "a": ["(卖腿-期货)/期货", "卖腿-期货/期货"],
            "hint": "(卖腿−期货)÷期货。分子反了——卖 Call 期货在卖腿下方是安全的",
        },
        {
            "q": "借方价差（买方）进场两关一判是什么？顺序不能乱。",
            "a": ["第一关趋势", "第二关iv", "判据rr", "趋势iv rr"],
            "hint": "第一关：标的在动吗（5日≥1%或Tier1事件）→第二关：IV便宜吗（价差ScP≤25）→判据：RR≥5:1。第一关不过直接跳过，IV再便宜也不进",
        },
        {
            "q": "盈亏比 0.25 是什么意思？低于这个数怎么做？",
            "a": ["不做"],
            "hint": "亏¥1 赚¥0.25=不值得。低于 0.25=不做",
        },
    ],
    "events": [
        {
            "q": "临近 D-0/D-1 高影响宏观事件（如中国 GDP），PTA/甲醇/铁矿石/橡胶有卖方信号。卖方该做什么？",
            "a": ["不做", "旁观", "等"],
            "hint": "D-0/D-1 高影响事件→不做卖方。等事件落地 IV 稳定再扫",
        },
        {
            "q": "USDA WASDE 报告 D-5（例行发布·高冲击·结果不可预知），豆粕 IV ScP12（极低）。卖方还是买方有优势？",
            "a": ["买方"],
            "hint": "IV P12<P25（第二关过）+ D-5 WASDE 例行发布但结果不可预知=高冲击催化（第一关过）+ 看RR→买方两关一判全中有优势。卖方IV极低权利金薄不做",
        },
        {
            "q": "USDA 作物周报 D-1，白糖买 Call IV P5 盈亏比 9:1。做不做买方？",
            "a": ["不做", "不做 "],
            "hint": "①USDA 周报覆盖豆粕/玉米/棉花，不覆盖白糖→假催化剂。②D-1 买方不进。③就算标的对，例行事件已被预期",
        },
    ],
}


def pick_topic():
    """根据当日情况自动选题。优先选近期薄弱环节。"""
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
            topics = [h["topic"] for h in history[-10:]]
            # 最近 10 次出现最少的话题优先
            for t in ["greeks", "discipline", "strategy", "events"]:
                if topics.count(t) < 2:
                    return t
        except Exception:
            pass
    return random.choice(list(QUESTIONS.keys()))


def generate_quiz(topic=None):
    """出 3 道题，返回题目列表"""
    if topic is None:
        topic = pick_topic()
    pool = QUESTIONS.get(topic, QUESTIONS["greeks"])
    selected = random.sample(pool, min(3, len(pool)))
    return topic, selected


def save_results(topic, results):
    """记录答题结果"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if HISTORY_FILE.exists():
        history = json.loads(HISTORY_FILE.read_text())
    else:
        history = []
    history.append({
        "date": datetime.now().isoformat(),
        "topic": topic,
        "correct": sum(1 for r in results if r),
        "total": len(results),
    })
    history = history[-200:]
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def _normalize(s):
    """判题归一化：全角→半角、符号统一、去空白。

    8/21 判错根因：用户中文输入法打出全角「（期货－卖腿）÷期货」，
    答案存半角「(期货-卖腿)/期货」→ 子串匹配失败误判❌。
    NFKC 转全角字母/数字，显式替换 −÷× 与全角括号，去空格统一。
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("−", "-").replace("÷", "/").replace("×", "*")
    s = s.replace("（", "(").replace("）", ")")
    # 8/31 判错根因：用户中文输入法写"gamma和vega"、"朋友，敌人"，
    # 中文连词/标点把答案词隔开 → 子串匹配失败误杀。统一替换为空格再去除。
    for sep in ["和", "与", "及", "跟", "，", "、", "。", "：", "；", "·", ","]:
        s = s.replace(sep, " ")
    return s.replace(" ", "").strip().lower()


def _match(a, answer_norm):
    """归一化后的子串匹配；公式题额外接受数字代入。

    公式题答案含「期货/卖腿」占位符（如 (期货-卖腿)/期货），用户常代入
    数字算结果（如 (2900-2800)/2900=3.4%）——占位符子串匹配不上。
    若答案含数字+除号在做计算 → 视为理解了公式，判对。
    """
    a_norm = _normalize(a)
    if a_norm in answer_norm:
        return True
    if ("期货" in a_norm or "卖腿" in a_norm) and "/" in a_norm:
        if any(ch.isdigit() for ch in answer_norm) and "/" in answer_norm:
            return True
    return False


def run_quiz(topic=None):
    """交互式答题"""
    topic, questions = generate_quiz(topic)
    correct = 0

    print(f"\n{'═'*50}")
    print(f"  📝 每日验收（{topic}）— commit 前答对再 push")
    print(f"{'═'*50}")

    results = []
    for i, q in enumerate(questions, 1):
        print(f"\n  [{i}/{len(questions)}] {q['q']}")
        answer = input(f"  → ").strip()
        answer_norm = _normalize(answer)
        is_correct = any(_match(a, answer_norm) for a in q["a"])
        results.append(is_correct)

        if is_correct:
            correct += 1
            print(f"  ✅")
        else:
            print(f"  ❌ 提示：{q['hint']}")

    save_results(topic, results)

    print(f"\n  {'─'*40}")
    print(f"  结果：{correct}/{len(questions)} 正确")

    if correct == 3:
        print(f"  🎉 全对！可以 commit 了。")
    elif correct >= 2:
        print(f"  ⚠️ 差一道。再想想，或者直接 commit（不建议）。")
    else:
        print(f"  ❌ 建议重做：python3 tools/daily_quiz.py --topic {topic}")

    print()
    return correct == 3


def main():
    parser = argparse.ArgumentParser(description="每日验收题自动出题器")
    parser.add_argument("--topic", type=str, default=None,
                        help=f"主题：{'/'.join(QUESTIONS.keys())}")
    parser.add_argument("--stats", action="store_true", help="显示答题历史")
    args = parser.parse_args()

    if args.stats:
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text())
            print(f"\n  📊 答题历史（最近 10 次）：")
            for h in history[-10:]:
                bar = "🟢" * h["correct"] + "🔴" * (h["total"] - h["correct"])
                print(f"    {h['date'][:10]}  {h['topic']:12s}  {bar}  {h['correct']}/{h['total']}")
            print()
        else:
            print("\n  尚无答题记录。跑一次就有了。\n")
        return

    run_quiz(args.topic)


if __name__ == "__main__":
    main()
