#!/usr/bin/env python3
"""rewrite_pred_ruler_20260927.py — 把 iv_direction_pred.csv 的「已填」行换到
交易所规则真尺，并给每一行记上它用的合约码。

═══ 为什么 ═══
`data/iv_history.csv` 已于 2026-09-27 回填到真尺（见 backfill_dte_20260927.py）。
预测表的 `actual_delta_pp` / `actual` 是**从 iv_history 的 iv_est 推出来的**，
若不跟着换，文件里就会 120 行旧尺 + 50 行新尺混在一起 —— 回填白做。

═══ 改哪几列（**只改已填的 120 行，未填的 50 行一个字不动**）═══
  actual_delta_pp  = (iv_est(compare_date) - iv_est(date)) * 100，四舍五入 2 位
  actual           = flat if |Δ| < 0.25pp else up/down
  user_correct     = 1 if user_pred == actual else 0     ← 必须跟着 actual 一起改，
  coach_correct    = 1 if coach_pred == actual else 0       否则同一行自相矛盾

═══ 新增 3 列 ═══
  contract_pred     预测日该品种 09:30 那行采的主采合约
  contract_compare  对照日该品种 09:30 那行采的主采合约
  cross_contract    1 = 两天不是同一个合约（**这种行的 Δ 混了换月，成绩别算进去**）
                    0 = 同合约 ｜ 空 = 对照日还没到

═══ 不动 ═══
  user_pred / user_reason / coach_pred / coach_reason / compare_date
  actual_reason / actual_reason_coach（人写的叙述，与尺子无关）
  flag
  **未填的 50 行**全部不动（它们本来就在新尺上）

═══ 用法 ═══
  python3 tools/rewrite_pred_ruler_20260927.py            # 干跑（默认）
  python3 tools/rewrite_pred_ruler_20260927.py --write    # 落盘
"""

import csv
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(_REPO, "data", "iv_history.csv")
PRED = os.path.join(_REPO, "data", "iv_direction_pred.csv")
NEW_COLS = ["contract_pred", "contract_compare", "cross_contract"]
FLAT = 0.25          # |Δpp| < 0.25 → flat（与既有口径一致，见 2026-09-27 复核）


def _norm(iso):
    """'2026-09-24' → '2026/9/24'（预测表用的是不带前导零的斜杠格式）"""
    y, m, d = iso.split("-")
    return "%s/%d/%d" % (y, int(m), int(d))


def _label(delta):
    return "flat" if abs(delta) < FLAT else ("up" if delta > 0 else "down")


def _load(path):
    with open(path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), list(r.fieldnames)


def main(write=False):
    hist, _ = _load(HIST)
    # 09:30 那行是分数的基准腿（2026-09-27 复核：120/120 由此复现）
    idx = {}
    for r in hist:
        if r.get("time") == "09:30":
            idx[(_norm(r["date"]), r["variety"])] = r

    rows, fields = _load(PRED)
    for c in NEW_COLS:
        if c not in fields:
            fields.append(c)

    filled = [r for r in rows if (r.get("actual_delta_pp") or "").strip()]
    n_flip = n_miss = 0
    flips = []
    old_u = old_c = new_u = new_c = 0
    n_cross = 0

    for r in rows:
        a = idx.get((r["date"], r["variety"]))
        b = idx.get((r["compare_date"], r["variety"]))
        # ── 记合约（对已填/未填都记；对照日没到就是空）──
        r["contract_pred"] = a["contract"] if a else ""
        r["contract_compare"] = b["contract"] if b else ""
        r["cross_contract"] = ("1" if a["contract"] != b["contract"] else "0") \
            if (a and b) else ""

        if not (r.get("actual_delta_pp") or "").strip():
            continue                      # 未填的 50 行：只记合约，其余不动
        if not a or not b:
            n_miss += 1
            continue

        new_delta = round((float(b["iv_est"]) - float(a["iv_est"])) * 100, 2)
        new_act = _label(new_delta)
        old_delta = float(r["actual_delta_pp"])
        old_act = r["actual"]

        old_u += r["user_pred"] == old_act
        old_c += r["coach_pred"] == old_act
        new_u += r["user_pred"] == new_act
        new_c += r["coach_pred"] == new_act
        if a["contract"] != b["contract"]:
            n_cross += 1
        if _label(old_delta) != new_act:
            n_flip += 1
            flips.append((r["date"], r["variety"], a["contract"], b["contract"],
                          old_delta, new_delta, old_act, new_act,
                          "跨" if a["contract"] != b["contract"] else "同"))

        r["actual_delta_pp"] = "%.2f" % new_delta   # 保持字符串 + 两位小数（与既有行一致）
        r["actual"] = new_act
        r["user_correct"] = "1" if r["user_pred"] == new_act else "0"
        r["coach_correct"] = "1" if r["coach_pred"] == new_act else "0"

    n = len(filled)
    print("=" * 78)
    print("预测表换尺 · data/iv_direction_pred.csv")
    print("=" * 78)
    print("\n【范围】已填 %d 行参与重算 ｜ 未填 %d 行只记合约、一个字不动"
          % (n, len(rows) - n))
    if n_miss:
        print("  ⚠️ %d 行在 iv_history 里找不到 09:30 腿 → 未改" % n_miss)

    print("\n【标签翻转】")
    print("  翻转 %d / %d 行" % (n_flip, n))
    for f in flips:
        print("    %-11s %-4s %-8s→%-8s  旧Δ%+6.2f→新Δ%+6.2f   %-5s→%-5s  %s"
              % f)

    print("\n【成绩变化】")
    print("  用户  %3d/%d (%.0f%%) → %3d/%d (%.0f%%)" %
          (old_u, n, 100 * old_u / n, new_u, n, 100 * new_u / n))
    print("  教练  %3d/%d (%.0f%%) → %3d/%d (%.0f%%)" %
          (old_c, n, 100 * old_c / n, new_c, n, 100 * new_c / n))

    print("\n【跨合约行】已填的里面 %d 行预测日与对照日不是同一个合约" % n_cross)
    print("  → 这些行的 Δ 混了换月，**报成绩时不算进去**（新列 cross_contract=1 标出）")

    # ── 落盘前自洽：actual 必须与 actual_delta_pp 一致；correct 必须与 actual 一致 ──
    # （2026-09-27 回填 iv_history 时踩过一次「算了新值但忘了写回列」，
    #   落盘后文件自相矛盾。这一步让同类 bug 逃不过去。）
    bad_act = bad_cor = bad_pp = 0
    for r in rows:
        raw = r.get("actual_delta_pp")
        if raw is None or str(raw).strip() == "":
            continue
        try:
            pp = float(raw)
        except (TypeError, ValueError):
            bad_pp += 1
            continue
        if _label(pp) != r["actual"]:
            bad_act += 1
        if r["user_correct"] != ("1" if r["user_pred"] == r["actual"] else "0"):
            bad_cor += 1
        if r["coach_correct"] != ("1" if r["coach_pred"] == r["actual"] else "0"):
            bad_cor += 1
    print("\n【自洽校验】actual↔Δpp 不一致 %d ｜ correct↔actual 不一致 %d ｜ Δpp 非数 %d"
          % (bad_act, bad_cor, bad_pp))
    if bad_act or bad_cor or bad_pp:
        print("  🔴 不自洽 → 拒绝落盘")

    if not write:
        print("\n（干跑，未落盘。确认无误后加 --write）")
        return 0
    if bad_act or bad_cor or bad_pp:
        return 1

    tmp = PRED + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    os.replace(tmp, PRED)
    print("\n✅ 已落盘 %s（%d 行，%d 列）" % (PRED, len(rows), len(fields)))
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--write" in sys.argv))
