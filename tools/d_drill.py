#!/usr/bin/env python3
"""
D-Drill v1.1 -- 纪律训练
每天 17 题，覆盖五大 override + 十大禁止 + 四层绿灯 + 离场规则。
题库分 A/B 两半，**逐次轮换**（9/23 改：原按日期奇偶，人不一定每天跑 → 常失效）。答做/不做 + 原因。
"""

import json, random, re, time
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
    # 9/23 改：显式轮转，不看日历。
    # 原先按"几号"奇偶，而 D-Drill 常只在奇数日跑 → 事实上连续多次落同一池
    # （9/15–9/23 连跑 5 次全是 A），"隔天轮换"从未发生。
    _st = load_state()
    _last = _st["sessions"][-1]["pool"] if _st.get("sessions") else None
    pool_label = "B" if _last == "A" else "A"
    use_pool = pool_b if pool_label == "B" else pool_a
    # 9/23：本轮实际出现的题号（题库文件序），供重复率统计
    _idmap = {id(q): i + 1 for i, q in enumerate(all_q)}
    _ids_used = [_idmap[id(q)] for q in use_pool]

    print(f"\n{'='*55}")
    print(f"  D-Drill -- 题库{pool_label} ({len(use_pool)}题) | {today}")
    print(f"  答「做/不做」或「过/不过」（层次题）+ 一句原因。Ctrl+C 退出。")
    print(f"{'='*55}\n")

    correct = 0
    total = len(use_pool)
    start_time = time.time()

    for i, q in enumerate(use_pool, 1):
        label = q.get("v", "")
        # 根据正确答案推断问法
        raw_ans = q.get("a", "")
        # 9/15 加：层次题（题干含「第N层：XXX」）改问「这一层过不过？」。
        # 原因：原来用执行动词「做/不做」问单层问题，而答案本身写「继续看后三层」
        # ——等于承认单层不足以决定执行，问法与语义冲突（9/12 一道层次题因此判错）。
        # 层次题的过/不过按同一套 做/不做 内部逻辑比对，只换问法与输入词。
        is_layer = bool(re.search(r"第[一二三四]层", q.get("s", "")))
        if is_layer:
            ask_type = "【这一层过不过？】"
        elif "不做" in raw_ans:
            ask_type = "【做不做？】"
        elif raw_ans.startswith("平"):
            ask_type = "【平不平？】"
        elif "平" in raw_ans and "不平" not in raw_ans and "平仓" not in raw_ans:
            ask_type = "【平不平？】"
        else:
            ask_type = "【做不做？】"
        print(f"  [{i}/{total}] {label} {q['s']} {ask_type}")
        print(f"  ⏸ 反证？", end=" ")
        try:
            t0 = time.time()
            ans = input().strip()
            elapsed = time.time() - t0
        except (EOFError, KeyboardInterrupt):
            print("\n  已退出。\n")
            break

        if not ans:
            print(f"  超时! 正确答案: {q['a']}\n")
            continue

        # Extract answer keyword (last occurrence in case user types 反证 prefix)
        def _extract_ans(text, layer_style=False):
            # 层次题：用户答「过/不过」，内部映射回 做/不做 参与比对。
            # 只对用户输入启用；答案键仍走 做/不做（a 均以「做。」/「不做。」开头）。
            if layer_style:
                for kw in ("不过", "过"):
                    idx = text.rfind(kw)
                    if idx >= 0:
                        return "不做" if kw == "不过" else "做"
                return text
            for kw in ("不做", "不平", "做", "平"):
                idx = text.rfind(kw)
                if idx >= 0:
                    return kw
            return text

        user_ans = _extract_ans(ans, layer_style=is_layer)
        actual_ans = _extract_ans(q["a"])
        actual_do = actual_ans in ("做", "平")
        user_do = user_ans in ("做", "平")
        # Disambiguate "平": if correct answer is 做/不做 (entry Q),
        # then "平" from user means close = 不做.
        if actual_ans in ("做", "不做") and user_ans == "平":
            user_do = False

        if actual_do == user_do:
            print(f"  ✅ 正确 ({elapsed:.1f}s)")
            print(f"  📖 {q['a']}\n")
            correct += 1
        else:
            print(f"  ❌ 错误。你的输入: 「{ans}」→ 解析为「{user_ans}」")
            print(f"  正确答案: {q['a']}\n")

    elapsed_total = time.time() - start_time
    accuracy = round(correct / total * 100, 1) if total > 0 else 0

    print(f"{'-'*55}")
    print(f"  结果: {correct}/{total} 正确 ({accuracy}%) | 用时 {elapsed_total:.0f}s")

    state = load_state()
    if accuracy == 100:
        state["streak"] += 1
        if state["streak"] > state["best_streak"]:
            state["best_streak"] = state["streak"]
        print(f"  全对! 连续 {state['streak']} 次。最佳: {state['best_streak']} 次。")
    else:
        if state["streak"] > 0:
            print(f"  连续 {state['streak']} 次中断。")
        state["streak"] = 0

    state["sessions"].append({
        "date": today.isoformat(),
        "pool": pool_label,
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        # 9/23：记录本轮实际题号，重复率可算（原先只存 pool 标签，测不出重复）
        "question_ids": _ids_used,
    })
    state["sessions"] = state["sessions"][-60:]
    save_state(state)
    print(f"{'='*55}\n")


if __name__ == "__main__":
    run()
