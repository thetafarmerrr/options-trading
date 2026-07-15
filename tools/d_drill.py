#!/usr/bin/env python3
"""
D-Drill v1.1 -- 纪律训练
每天 17 题，覆盖五大 override + 十大禁止 + 四层绿灯 + 离场规则。
题库分 A/B 两半，隔天轮换。答做/不做 + 原因。
"""

import json, random, time
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_FILE = SCRIPT_DIR / "d_drill_data.json"
STATE_FILE = SCRIPT_DIR.parent / "drill_state" / "d_drill.json"
STATE_FILE.parent.mkdir(exist_ok=True)


def load_questions():
    with open(DATA_FILE) as f:
        return json.load(f)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"sessions": [], "streak": 0, "best_streak": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def run():
    all_q = load_questions()
    today = date.today()

    # Split into A/B halves, alternate by date parity
    half = len(all_q) // 2
    pool_a = all_q[:half]
    pool_b = all_q[half:]
    random.shuffle(pool_a)
    random.shuffle(pool_b)
    use_pool = pool_a if today.day % 2 == 1 else pool_b
    pool_label = "A" if today.day % 2 == 1 else "B"

    print(f"\n{'='*55}")
    print(f"  D-Drill -- 题库{pool_label} ({len(use_pool)}题) | {today}")
    print(f"  答「做」或「不做」+ 一句原因。Ctrl+C 退出。")
    print(f"{'='*55}\n")

    correct = 0
    total = len(use_pool)
    start_time = time.time()

    for i, q in enumerate(use_pool, 1):
        print(f"  [{i}/{total}] {q['s']}")
        try:
            t0 = time.time()
            ans = input("  -> ").strip()
            elapsed = time.time() - t0
        except (EOFError, KeyboardInterrupt):
            print("\n  已退出。\n")
            break

        if not ans:
            print(f"  超时! 正确答案: {q['a']}\n")
            continue

        actual_do = q["a"].startswith("做") or q["a"].startswith("平")
        user_do = ans.startswith("做") or ans.startswith("平")

        if actual_do == user_do:
            print(f"  正确 ({elapsed:.1f}s)\n")
            correct += 1
        else:
            print(f"  错误。正确答案: {q['a']}\n")

    elapsed_total = time.time() - start_time
    accuracy = round(correct / total * 100, 1) if total > 0 else 0

    print(f"{'-'*55}")
    print(f"  结果: {correct}/{total} 正确 ({accuracy}%) | 用时 {elapsed_total:.0f}s")

    state = load_state()
    if accuracy == 100:
        state["streak"] += 1
        if state["streak"] > state["best_streak"]:
            state["best_streak"] = state["streak"]
        print(f"  全对! 连续 {state['streak']} 天。最佳: {state['best_streak']} 天。")
    else:
        if state["streak"] > 0:
            print(f"  连续 {state['streak']} 天中断。")
        state["streak"] = 0

    state["sessions"].append({
        "date": today.isoformat(),
        "pool": pool_label,
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
    })
    state["sessions"] = state["sessions"][-60:]
    save_state(state)
    print(f"{'='*55}\n")


if __name__ == "__main__":
    run()
