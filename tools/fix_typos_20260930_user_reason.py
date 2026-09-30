#!/usr/bin/env python3
"""fix_typos_20260930_user_reason.py

用户 9/30 裁定「改」：修 **9/22 批** `actual_reason` 列的 4 类笔误。
**最小改动**——只纠错字，不加词、不删观点、不动 `actual_reason_coach`。

  玉米油上市压力 → 玉米上市压力        （c）
  无事见催化     → 无事件催化          （ta / i / rm 共3处）
  近端货近       → 近端供给            （ta）
  美特朗普       → 特朗普              （ma）

用法：python3 tools/fix_typos_20260930_user_reason.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
BATCH, COMPARE = "2026/9/22", "2026/9/30"

REPL = [("玉米油上市压力", "玉米上市压力"),
        ("无事见催化", "无事件催化"),
        ("近端货近", "近端供给"),
        ("美特朗普", "特朗普")]


def main():
    dry = "--dry-run" in sys.argv
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    tgt = [r for r in rows if r.get("date") == BATCH and r.get("compare_date") == COMPARE]
    assert len(tgt) == 10, f"批次应有 10 行，实得 {len(tgt)}"

    hits = 0
    print(f"批次 {BATCH} · 仅改 `actual_reason` 列\n")
    for r in tgt:
        src = r["actual_reason"]
        for a, b in REPL:
            if a in src:
                n = src.count(a)
                src = src.replace(a, b)
                hits += n
                print(f"  {r['variety']:3s}  {a} → {b}   ×{n}")
        r["actual_reason"] = src

    assert hits == 6, f"预期 6 处替换，实得 {hits}——拒绝在预期外落盘"
    print(f"\n合计替换 {hits} 处 / 涉及行 "
          f"{sorted({x['variety'] for x in tgt if any(a not in x['actual_reason'] for a, _ in REPL)})}")
    print("（未动手行：au / m / cf / sr / ru）")

    if dry:
        print("\n--dry-run：未落盘。")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)
    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, CSV_PATH)

    # 回核（只打计数/断言，不回显正文）
    with open(CSV_PATH, "rb") as f:
        raw = f.read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        back = list(csv.DictReader(f))
    b2 = [r for r in back if r.get("date") == BATCH and r.get("compare_date") == COMPARE]

    print(f"\n备份：{bak}")
    print(f"回核·总行数：{len(back)}（写前 {len(rows)}）{'✔' if len(back) == len(rows) else '✘'}")
    n_crlf, n_lf = raw.count(b"\r\n"), raw.count(b"\n")
    print(f"回核·换行：CRLF {n_crlf} / LF {n_lf} → {'LF ✔' if n_crlf == 0 else '✘'}")
    print(f"回核·残留笔误：{sum(r['actual_reason'].count(a) for r in b2 for a, _ in REPL)}"
          f" {'✔' if sum(r['actual_reason'].count(a) for r in b2 for a, _ in REPL) == 0 else '✘'}")
    print(f"回核·教练版未被触碰：{sum(1 for r in b2 if r['actual_reason_coach'])}/10 "
          f"{'✔' if sum(1 for r in b2 if r['actual_reason_coach']) == 10 else '✘'}")
    print(f"回核·列数：{len(back[0])} {'✔' if len(back[0]) == len(fieldnames) else '✘'}")


if __name__ == "__main__":
    main()
