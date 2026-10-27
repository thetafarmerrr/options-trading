#!/usr/bin/env python3
"""backfill_actuals_20261020.py

回填 **两批逾期未结算** 的机械列（不是 actual_reason）：

    批次 2026/09/29 → compare 2026/10/13（逾期 7 天）
    批次 2026/09/30 → compare 2026/10/14（逾期 6 天）

**只写机械列，绝不碰 `actual_reason`（用户写的）与 `actual_reason_coach`（教练已写）。**
本脚本 = 对照日流程的第 ① 步的**机械部分**：教练侧 `actual_reason_coach`
两批 **10/10 早已落盘**（`tools/fill_actual_reason_coach_20261013.py` / `_20261014.py`），
此处只补 `actual` / `actual_delta_pp` / `cross_contract` / `user_correct` / `coach_correct`
以及 9/30 批缺失的 `contract_pred`。

口径（依 docs/task-template.md）：
  - 主采 = **09:30** 那一采；09:30 缺 → **09:31 代**，并在回执里**显式点名**
  - `actual_delta_pp = (iv_est(compare) − iv_est(batch)) × 100`，2dp
  - `actual = flat if |Δ| < 0.25 else up/down`；**flat 行的 user_correct/coach_correct 留空**
  - `cross_contract = 1 ⟺ contract_pred ≠ contract_compare`；**跨合约行照填，计分时剔分母**
  - `contract_pred` 空 → 从**批次日主采合约**恢复（9/29 批已有，9/30 批缺）

用户裁定（10/20）：「9/29、9/30 两批的 actual_reason **写**」——故本脚本**留空**
`actual_reason`，等她口述后再落。

用法：python3 tools/backfill_actuals_20261020.py [--dry-run]
"""
import csv
import io
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
IV_PATH = os.path.join(ROOT, "data", "iv_history.csv")

BATCHES = [
    ("2026/9/29", "2026/10/13"),
    ("2026/9/30", "2026/10/14"),
]

ORDER = ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]


def n(s):
    s = (s or "").strip().replace("/", "-")
    p = s.split("-")
    if len(p) == 3 and all(x.isdigit() for x in p):
        return f"{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}"
    return None


def load_iv():
    with open(IV_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sample_morning(iv_rows, date, v):
    """主采 09:30；缺则 09:31 代；再缺则 09:15 代。返回 (time, contract, iv, 代采标记)。"""
    rs = [r for r in iv_rows if r.get("date") == date and r.get("variety") == v
          and (r.get("iv_est") or "").strip()]
    if not rs:
        return None
    for t, tag in (("09:30", ""), ("09:31", "09:31代"), ("09:15", "09:15代")):
        for r in rs:
            if r.get("time") == t:
                return (t, r["contract"], float(r["iv_est"]), tag)
    return None


def main() -> int:
    dry = "--dry-run" in sys.argv
    iv_rows = load_iv()

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    assert raw.count("\r\n") == 0, f"原文件有 CRLF {raw.count(chr(13)+chr(10))} 处"
    rows = list(csv.DictReader(io.StringIO(raw)))
    fieldnames = list(rows[0].keys())

    plan = {}
    for bd, cd in BATCHES:
        sel = [r for r in rows if n(r["date"]) == n(bd)]
        assert len(sel) == 10, f"{bd}: 行数 {len(sel)} != 10"
        assert all((r["actual_reason_coach"] or "").strip() for r in sel), \
            f"{bd}: 有行缺 actual_reason_coach —— 教练侧未完成，不得先填机械列"
        assert all(not (r["actual"] or "").strip() for r in sel), \
            f"{bd}: actual 已有值，拒绝覆盖"
        plan[bd] = (cd, sel)

    print("=" * 88)
    for bd, (cd, sel) in plan.items():
        bdn, cdn = n(bd), n(cd)
        print(f"\n批次 {bdn} → compare {cdn}")
        print(f"{'v':<4}{'pred合约':<9}{'compare合约':<12}{'Δpp':>8}  {'actual':<6}{'cross':<6}"
              f"{'u_pred':<7}{'c_pred':<7}{'u_ok':<5}{'c_ok':<5} 备注")
        for r in sorted(sel, key=lambda x: ORDER.index(x["variety"])):
            v = r["variety"]
            a = sample_morning(iv_rows, bdn, v)
            b = sample_morning(iv_rows, cdn, v)
            if not a or not b:
                raise SystemExit(f"❌ {bdn}/{v} 缺 IV 数据: {a} {b}")
            d = round((b[2] - a[2]) * 100, 2)
            actual = "flat" if abs(d) < 0.25 else ("up" if d > 0 else "down")
            cp = (r["contract_pred"] or "").strip()
            if not cp:
                cp = a[1]
                r["contract_pred"] = cp
                r["_cp_filled"] = "填"
            cross = "1" if cp != b[1] else "0"
            if actual == "flat":
                u_ok = c_ok = ""
            else:
                u_ok = "1" if r["user_pred"] == actual else "0"
                c_ok = "1" if r["coach_pred"] == actual else "0"
            r["actual"] = actual
            r["actual_delta_pp"] = f"{d:.2f}"
            r["cross_contract"] = cross
            r["user_correct"] = u_ok
            r["coach_correct"] = c_ok
            r["_contract_compare"] = b[1]
            note = " ".join(x for x in [
                f"{a[0]}→{b[0]}" if a[0] != b[0] else "",
                "CROSS" if cross == "1" else "",
                r.pop("_cp_filled", ""),
            ] if x)
            print(f"{v:<4}{cp:<9}{b[1]:<12}{d:+8.2f}  {actual:<6}{cross:<6}"
                  f"{r['user_pred']:<7}{r['coach_pred']:<7}{str(u_ok):<5}{str(c_ok):<5} {note}")

        scored = [r for r in sel if r["actual"] != "flat" and r["cross_contract"] != "1"]
        nf = sum(1 for r in sel if r["actual"] == "flat")
        nc = sum(1 for r in sel if r["cross_contract"] == "1")
        us = sum(1 for r in scored if r["user_correct"] == "1")
        cs = sum(1 for r in scored if r["coach_correct"] == "1")
        print(f"  → 计分 {len(scored)} 行（剔平 {nf} · 剔跨合约 {nc}）："
              f"user {us}/{len(scored)} = {us/len(scored):.1%} · "
              f"coach {cs}/{len(scored)} = {cs/len(scored):.1%}")

    if dry:
        print("\n--dry-run：未落盘。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)

    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    os.replace(tmp, CSV_PATH)

    # 回核
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        raw2 = f.read()
    rows2 = list(csv.DictReader(io.StringIO(raw2)))
    assert len(rows2) == len(rows), "行数变了"
    for bd, cd in BATCHES:
        s2 = [r for r in rows2 if n(r["date"]) == n(bd)]
        assert len(s2) == 10
        assert all(r["actual"].strip() for r in s2), f"{bd}: actual 未填满"
        assert all(r["actual_delta_pp"].strip() for r in s2), f"{bd}: delta 未填满"
        assert all(not r["actual_reason"].strip() for r in s2), f"{bd}: actual_reason 被误写"
        assert all(r["actual_reason_coach"].strip() for r in s2), f"{bd}: acoach 被抹"
        assert all(r["contract_pred"].strip() for r in s2), f"{bd}: contract_pred 仍空"
    assert raw2.count("\r\n") == 0, "出现 CRLF"

    print(f"\n回核：行数 {len(rows)} 不变 · CRLF 0 · LF {raw.count(chr(10))} → {raw2.count(chr(10))}")
    print(f"      两批 actual 10/10 · delta 10/10 · actual_reason 仍空 20/20 · acoach 完好 20/20")
    print(f"      备份 {bak}")
    print("\n▶ 机械列已落盘。等用户口述 actual_reason 后再落第二步。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
