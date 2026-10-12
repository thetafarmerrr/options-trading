#!/usr/bin/env python3
"""fill_score_20260923_24.py

补 **2026/9/23 批** 与 **2026/9/24 批** 的判分列（`user_correct` / `coach_correct`），
并补录此前漏掉的 **`contract_compare` / `cross_contract`**。

为什么这两批一直没判分：`contract_pred` 有值，但 `contract_compare` / `cross_contract`
**列全空**，跨合约行标不出来。这两批各有 **4 行换月**：
    c  c2611 → c2701
    ta ta2611 → ta2701
    ma ma2611 → ma2701
    rm rm2611 → rm2701
（同批 au/m/cf/sr/i/ru 合约未变。）

口径（照 9/30 / 10/12 已定档）：
  - 09:30 → 09:30；compare 日**无 09:30 采点 → 用 09:31 代**（本批 ru 两行如此，已标注）
  - `actual_delta_pp = (iv_est(compare) − iv_est(batch)) * 100`，2dp；本脚本**逐行断言**与
    已记录的 `actual` / `actual_delta_pp` 一致 —— **不改动任何已判定的 `actual`**
  - `cross_contract = 1 ⟺ contract_pred ≠ contract_compare`
  - cross 行**照填** correct，**剔出分母的动作发生在「报分时」，不是留空单元格**
  - `actual == flat` 的行 → correct 列**留空**

⚠️ 本脚本**不碰** `actual_reason`（用户事后归因）。10/12 裁定：这两批**不补口述**
  → 对照日三步的第 ③ 步（判据四问）对这两批**不作**，已在 `flag` 追加说明。

用法：python3 tools/fill_score_20260923_24.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
HIST = os.path.join(ROOT, "data", "iv_history.csv")

BATCHES = {"2026/9/23": "2026-10-08", "2026/9/24": "2026-10-09"}
PREF_BATCH = ["09:30", "09:15", "09:16"]
PREF_COMPARE = ["09:30", "09:31", "09:15", "09:16"]
NOTE = " · 10/12 补判分：合约列补齐·跨合约4行剔出分母·事后归因不补(10/12裁定)"


def iso(b):
    return datetime.strptime(b, "%Y/%m/%d").strftime("%Y-%m-%d")


def main():
    dry = "--dry-run" in sys.argv
    hist = list(csv.DictReader(open(HIST, newline="", encoding="utf-8")))

    def pick(v, d, times):
        for t in times:
            for r in hist:
                if r["date"] == d and r["time"] == t and r["variety"] == v:
                    return r
        return None

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    plan = []
    for batch, cd in BATCHES.items():
        tgt = [r for r in rows if r.get("date") == batch]
        assert len(tgt) == 10, f"{batch} 应有 10 行，实际 {len(tgt)}"
        for r in tgt:
            assert r["actual"], f"{batch}/{r['variety']}: actual 空"
            assert not r["user_correct"] and not r["coach_correct"], \
                f"{batch}/{r['variety']}: correct 已有值，拒绝覆盖"
            assert not r["contract_compare"], \
                f"{batch}/{r['variety']}: contract_compare 已有值，拒绝覆盖"
            a = pick(r["variety"], iso(batch), PREF_BATCH)
            c = pick(r["variety"], cd, PREF_COMPARE)
            assert a and c, f"{batch}/{r['variety']}: 缺采点"
            dd = round((float(c["iv_est"]) - float(a["iv_est"])) * 100, 2)
            assert abs(dd - float(r["actual_delta_pp"])) < 0.011, \
                f"{batch}/{r['variety']}: Δ 重算 {dd} ≠ 记录 {r['actual_delta_pp']}"
            act = "flat" if abs(dd) < 0.25 else ("up" if dd > 0 else "down")
            assert act == r["actual"], \
                f"{batch}/{r['variety']}: actual 口径冲突 重算{act} 记录{r['actual']}"
            cross = "1" if a["contract"] != c["contract"] else "0"
            uc = "" if act == "flat" else ("1" if r["user_pred"] == act else "0")
            cc = "" if act == "flat" else ("1" if r["coach_pred"] == act else "0")
            plan.append((r, c["contract"], cross, uc, cc))

    print(f"{'批次':<12}{'品种':<5}{'合约':<18}{'跨':<4}{'u':<3}{'c':<3}{'实':<6}判")
    print("-" * 68)
    for r, cmpc, cross, uc, cc in plan:
        m = lambda x: "✅" if x == "1" else ("✗" if x == "0" else "—")
        print(f"{r['date']:<12}{r['variety']:<5}{r['contract_pred']}→{cmpc:<11}"
              f"{cross:<4}{r['user_pred']:<3}{r['coach_pred']:<3}{r['actual']:<6}"
              f"u{m(uc)} c{m(cc)}")

    print()
    for batch in BATCHES:
        sub = [(r, x, uc, cc) for r, _, x, uc, cc in plan if r["date"] == batch]
        n_all = sum(1 for _, _, uc, _ in sub if uc != "")
        su = sum(1 for _, _, uc, _ in sub if uc == "1")
        sc = sum(1 for _, _, _, cc in sub if cc == "1")
        keep = [(r, uc, cc) for r, x, uc, cc in sub if x == "0" and uc != ""]
        ku = sum(1 for _, uc, _ in keep if uc == "1")
        kc = sum(1 for _, _, cc in keep if cc == "1")
        print(f"  {batch}：全量 {n_all} 行 user {su}/{n_all} · coach {sc}/{n_all}"
              f"  ‖  剔跨合约后 {len(keep)} 行 user {ku}/{len(keep)} · coach {kc}/{len(keep)}")

    if dry:
        print("\n--dry-run：未落盘。")
        return

    b = open(CSV_PATH, "rb").read()
    n_before = (b.count(b"\n"), b.count(b"\r\n"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)

    for r, cmpc, cross, uc, cc in plan:
        r["contract_compare"] = cmpc
        r["cross_contract"] = cross
        r["user_correct"] = uc
        r["coach_correct"] = cc
        r["flag"] = r["flag"] + NOTE

    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, CSV_PATH)

    # ── 回核（只打印行数/CRLF/断言，不回显正文）────────────────
    b2 = open(CSV_PATH, "rb").read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows2 = list(csv.DictReader(f))
    assert len(rows2) == len(rows), "行数变了，拒绝"
    for batch in BATCHES:
        t2 = [r for r in rows2 if r.get("date") == batch]
        assert all(r["contract_compare"] and r["cross_contract"] is not None
                   and r["cross_contract"] != "" for r in t2), f"{batch}: 合约列未写满"
        assert sum(1 for r in t2 if r["cross_contract"] == "1") == 4, \
            f"{batch}: 跨合约行数应恰为 4"
        assert all(r["user_correct"] != "" or r["actual"] == "flat" for r in t2), \
            f"{batch}: 有非 flat 行未判分"
    print(f"\n回核：总行数 {len(rows2)}（未变）· 列数 {len(rows2[0])}")
    print(f"      LF {n_before[0]} → {b2.count(b'\n')} · CRLF {n_before[1]} → {b2.count(b'\r\n')}（须为 0）")
    print(f"      备份 {bak}")
    print(f"\n▶ 9/23 · 9/24 两批判分完成。")


if __name__ == "__main__":
    main()
