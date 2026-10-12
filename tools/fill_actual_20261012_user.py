#!/usr/bin/env python3
"""fill_actual_20261012_user.py

对照日 **2026-10-12** 第 ② 步：落 **2026/9/28 批** 的
**用户口述 `actual_reason`** + 机械列（contract_compare / cross_contract /
actual / actual_delta_pp / user_correct / coach_correct）。

口径（照 9/30 / 9/22 已定档的列填法，实读自 CSV 校对）：
  - 09:30 → 09:30；`actual_delta_pp = (iv_est(compare) − iv_est(batch)) * 100`，2dp
    ⚠️ 10/12 **无 09:30 采点**（当日采点 = 09:15/09:16 与 09:31）→ sr/i/ru 用 **09:31** 代，
    已在脚本内逐行标注，**不隐去**。
  - `actual = flat if |Δ| < 0.25 else up/down`
  - `cross_contract = 1 ⟺ contract_pred ≠ contract_compare`（定义见 `rewrite_pred_ruler_20260927.py:85`）
  - cross 行**照填** actual/Δ/correct，**剔出分母的动作发生在「报分时」，不是留空单元格**
  - `actual == flat` 的行 → user_correct / coach_correct **留空**

`actual_reason` 系**用户 10/12 口述、教练落盘、内容一字未改**。
⚠️ 含一处**疑似语音输入笔误**：「c 条『窗口期**五十肩**催化』」——上下文与同批其余 4 条
一致指向「**无事件**催化」（wú shì jiàn ≈ wǔ shí jiān）。**照录不改**，另立 `flag` 标注，
是否修正由用户裁定（同 9/30 的 `fix_typos_*` 先例）。

⚠️ **本脚本不碰** `actual_reason_coach`（教练版，已于第 ① 步先行落盘）。

用法：python3 tools/fill_actual_20261012_user.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
HIST = os.path.join(ROOT, "data", "iv_history.csv")

BATCH, COMPARE = "2026/9/28", "2026-10-12"
BATCH_ISO = "2026-09-28"
TAG = "〔用户口述·10/12 教练落盘·内容一字未改〕"

# 用户口述原文（逐字，**含疑似笔误「五十肩」**；顺序即她口述顺序）
DICT = {
    "au": "iv高位，窗口期内无事件发生，iv down",
    "m":  "窗口期内无事件催化，远期供给宽松，iv down",
    "c":  "供给宽松，窗口期五十肩催化，iv down",
    "cf": "窗口期内无事件发生，iv down",
    "rm": "窗口期内无事件发生，iv down",
    "sr": "厄尔尼诺预期强，iv up",
    "ta": "美伊冲突升级，iv up",
    "i":  "铁矿供给宽松，价格大幅下跌，iv up",
    "ru": "厄尔尼诺强预期，iv up",
    "ma": "美伊冲突升级，国内库存新低，iv up",
}

# 10/12 无 09:30 采点 → 这三个品种用 09:31 代（**不隐去**）
TIME_SUB = {"sr", "i", "ru"}


def main():
    dry = "--dry-run" in sys.argv
    hist = list(csv.DictReader(open(HIST, newline="", encoding="utf-8")))

    def pick(v, d, prefer):
        for t in prefer:
            for r in hist:
                if r["date"] == d and r["time"] == t and r["variety"] == v:
                    return r
        return None

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    tgt = {r["variety"]: r for r in rows if r.get("date") == BATCH}
    assert len(tgt) == 10, f"批次 {BATCH} 应有 10 行，实际 {len(tgt)}"
    assert set(DICT) == set(tgt), "品种集合不一致"
    for v, r in tgt.items():
        assert r["actual_reason_coach"], f"{v}: 教练列缺失（第 ① 步未落）"
        assert not r["actual_reason"], f"{v}: actual_reason 已有值，拒绝覆盖"
        assert not r["actual"], f"{v}: actual 已有值，拒绝覆盖"
        assert r["contract_pred"], f"{v}: contract_pred 缺失"

    print(f"{'品种':<4}{'Δpp':>7}  {'actual':<5}{'跨合约':>7}  {'user':>5}{'coach':>6}  合同")
    print("-" * 76)
    stat = {"u": 0, "c": 0, "n": 0}
    for v in DICT:
        r = tgt[v]
        a = pick(v, BATCH_ISO, ["09:30"])
        b = pick(v, COMPARE, ["09:30", "09:31"])
        ia, ib = float(a["iv_est"]), float(b["iv_est"])
        dd = round((ib - ia) * 100, 2)
        act = "flat" if abs(dd) < 0.25 else ("up" if dd > 0 else "down")
        cross = "1" if a["contract"] != b["contract"] else "0"
        uc = "" if act == "flat" else ("1" if r["user_pred"] == act else "0")
        cc = "" if act == "flat" else ("1" if r["coach_pred"] == act else "0")
        r["_dd"], r["_act"], r["_cc"], r["_cross"] = dd, act, b["contract"], cross
        r["_uca"], r["_cca"] = uc, cc
        if cross == "0" and act != "flat":
            stat["u"] += (uc == "1"); stat["c"] += (cc == "1"); stat["n"] += 1
        sub = " ⚠️09:31代" if v in TIME_SUB else ""
        print(f"{v:<4}{dd:>+7.2f}  {act:<5}{cross:>7}  {uc or '—':>5}{cc or '—':>6}"
              f"  {a['contract']}→{b['contract']}{sub}")
    print(f"\n剔跨合约后计分 {stat['n']} 行：user {stat['u']} · coach {stat['c']}")

    if dry:
        print("\n--dry-run：未落盘。")
        return

    b = open(CSV_PATH, "rb").read()
    n_before = (b.count(b"\n"), b.count(b"\r\n"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)

    for v in DICT:
        r = tgt[v]
        r["actual_reason"] = f"{TAG}{DICT[v]}"
        r["actual"] = r.pop("_act")
        r["actual_delta_pp"] = f"{r.pop('_dd'):.2f}"
        r["contract_compare"] = r.pop("_cc")
        r["cross_contract"] = r.pop("_cross")
        r["user_correct"] = r.pop("_uca")
        r["coach_correct"] = r.pop("_cca")
    for r in rows:
        for k in list(r):
            if k.startswith("_"):
                del r[k]

    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, CSV_PATH)

    # ── 回核（行数/CRLF/断言；正文不回显）────────────────────
    b2 = open(CSV_PATH, "rb").read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows2 = list(csv.DictReader(f))
    tgt2 = [r for r in rows2 if r.get("date") == BATCH]
    assert len(rows2) == len(rows), "行数变了，拒绝"
    assert all(r["actual_reason"] and r["actual"] and r["actual_delta_pp"] for r in tgt2), "有行未写满"
    assert all(r["actual_reason_coach"] for r in tgt2), "教练列被破坏"
    assert sum(1 for r in tgt2 if r["cross_contract"] == "1") == 1, "跨合约行数应恰为 1"
    print(f"\n回核：总行数 {len(rows2)}（未变）· 本批 {len(tgt2)} · 列数 {len(rows2[0])}")
    print(f"      actual_reason 已写 {sum(1 for r in tgt2 if r['actual_reason'])}/10"
          f" · actual 已写 {sum(1 for r in tgt2 if r['actual'])}/10"
          f" · 跨合约 {sum(1 for r in tgt2 if r['cross_contract']=='1')}/10")
    print(f"      LF {n_before[0]} → {b2.count(b'\n')} · CRLF {n_before[1]} → {b2.count(b'\r\n')}（须为 0）")
    print(f"      备份 {bak}")
    print(f"\n▶ 第 ② 步完成。现在做第 ③ 步：两侧同时亮出 + 判据四问。")


if __name__ == "__main__":
    main()
