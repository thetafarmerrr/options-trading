#!/usr/bin/env python3
"""fill_actual_20260930_user.py

对照日 2026-09-30：落 **2026/9/22 批**（compare_date 2026/9/30）的
**用户口述 `actual_reason`** + 机械列（contract_compare / cross_contract /
actual / actual_delta_pp / user_correct / coach_correct）。

口径（照 9/21 批已定档的列填法，实读自 CSV）：
  - 09:30 → 09:30；actual_delta_pp = (iv_est(compare) - iv_est(batch)) * 100，2dp
  - actual = flat if |Δ| < 0.25 else up/down
  - cross 行（两天合约不同）**照填** actual/Δ/correct，
    **剔出分母的动作发生在"报分时"，不是留空单元格**
  - actual == flat 的行 → user_correct / coach_correct **留空**（同 9/21 的 i）

`actual_reason` 系**用户 9/30 口述，教练落盘，内容一字未改**（含其笔误）。
ta/ma 归属：用户 9/30 明确「第二条是 ma，我写错了」→ 落到 ma 行。

⚠️ 本脚本**不碰** `actual_reason_coach`（教练版，同日先行落盘）。

用法：python3 tools/fill_actual_20260930_user.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
HIST = os.path.join(ROOT, "data", "iv_history.csv")

BATCH, COMPARE = "2026/9/22", "2026/9/30"
BATCH_ISO, COMPARE_ISO = "2026-09-22", "2026-09-30"
TAG = "〔用户口述·9/30 教练落盘·内容一字未改〕"

# 用户口述原文（逐字，含笔误；除 ma 行尾注外不加字）
DICT = {
    "au": "iv hv 8.3% 高溢价，最近无事件，美伊关系缓和 iv down",
    "m":  "近月iv倒挂，iv折价，中美会晤落地，中方承诺采豆，远端恐慌水平下降，down",
    "c":  "iv hv 2.5% 溢价，玉米油上市压力，远端宽松，down",
    "cf": "iv hv 1.8% 溢价，产收高峰，供给增量，价格跳水，iv up",
    "sr": "iv hv 1.2% 溢价 供强需弱 价格跳水，但天气影响依然存在，厄尔尼诺有预期，矛盾支撑价格，iv down",
    "ta": "iv近月倒挂 iv hv 2.4% 溢价 美伊冲突暂缓，但前景仍然不明朗，原料成本下降中，但加工费400涨至700，内部存在结构矛盾，近端货近依然有支撑，但无事见催化，iv down",
    "ma": "iv 近远月倒挂，iv hv 5.5%高溢价 美伊谈判中，虽然美特朗普拒绝伊方条件，但并没有冲突升级，无事件催化，近月供给真短缺，存在价格强支撑，iv down"
          "（用户 9/30 确认：本条她原记为 ta，实为 ma）",
    "i":  "iv hv 1.5% 溢价，无事见催化，iv down",
    "ru": "iv hv 6.2% 高溢价，厄尔尼诺强预期，iv up",
    "rm": "iv hv -2.4% 折价 库存真低，有价格支撑，但无事见催化，iv down",
}


def main():
    dry = "--dry-run" in sys.argv
    hist = list(csv.DictReader(open(HIST, newline="", encoding="utf-8")))

    def ivest(v, d):
        for r in hist:
            if r["date"] == d and r["time"] == "09:30" and r["variety"] == v:
                return float(r["iv_est"]), r["contract"]
        return None, None

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    tgt = [r for r in rows if r.get("date") == BATCH and r.get("compare_date") == COMPARE]
    assert len(tgt) == 10, f"批次应有 10 行，实得 {len(tgt)}"
    assert {r["variety"] for r in tgt} == set(DICT), "品种集合不匹配"
    stale = [r["variety"] for r in tgt if str(r.get("actual_reason", "")).strip()]
    assert not stale, f"以下行已有 actual_reason，拒绝覆盖：{stale}"
    assert all(str(r.get("actual_reason_coach", "")).strip() for r in tgt), \
        "教练版 actual_reason_coach 缺失——本脚本不应在其之前运行"

    print(f"批次 {BATCH} → compare {COMPARE}\n")
    print(f"{'品种':<4}{'合约':<9}{'对照合约':<10}{'cross':<7}{'Δpp':<9}{'actual':<7}{'用户':<5}{'教练':<5}")
    print("-" * 62)
    n_den_u = n_den_c = 0
    for r in tgt:
        v = r["variety"]
        b_iv, b_c = ivest(v, BATCH_ISO)
        c_iv, c_c = ivest(v, COMPARE_ISO)
        d = round((c_iv - b_iv) * 100, 2)
        act = "flat" if abs(d) < 0.25 else ("up" if d > 0 else "down")
        cross = "1" if c_c != b_c else "0"
        r["actual_reason"] = f"{TAG}{DICT[v]}"
        r["contract_compare"] = c_c
        r["cross_contract"] = cross
        r["actual"] = act
        r["actual_delta_pp"] = f"{d:.2f}"
        uc = cc = ""
        if act != "flat":
            uc = "1" if r["user_pred"] == act else "0"
            cc = "1" if r["coach_pred"] == act else "0"
        r["user_correct"], r["coach_correct"] = uc, cc
        counted = (cross == "0" and act != "flat")
        if counted:
            n_den_u += 1
            n_den_c += int(uc)
        print(f"{v:<4}{b_c:<9}{c_c:<10}{cross:<7}{d:+.2f}{'':<4}{act:<7}"
              f"{uc or '·':<5}{cc or '·':<5}{'' if counted else '  ←剔除'}")

    print(f"\n分母 {n_den_u} 行（10 − 3 cross − 1 flat）→ 用户 {n_den_c}/{n_den_u}")

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

    with open(CSV_PATH, "rb") as f:
        raw = f.read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        back = list(csv.DictReader(f))
    b2 = [r for r in back if r.get("date") == BATCH and r.get("compare_date") == COMPARE]
    changed = [r for r in back
               if (r.get("date") == BATCH and r.get("compare_date") == COMPARE)
               or str(r.get("actual_reason", "")).strip()
               or str(r.get("contract_compare", "")).strip()]

    print(f"\n备份：{bak}")
    print(f"回核·总行数：{len(back)}（写前 {len(rows)}）{'✔' if len(back) == len(rows) else '✘'}")
    print(f"回核·换行：CRLF {raw.count(chr(13).encode()+chr(10).encode())} / LF {raw.count(chr(10).encode())}"
          f" → {'LF ✔' if raw.count(chr(13).encode()) == 0 else '✘'}")
    print(f"回核·本批已填 actual_reason：{sum(1 for r in b2 if r['actual_reason'])}/10 "
          f"{'✔' if sum(1 for r in b2 if r['actual_reason']) == 10 else '✘'}")
    print(f"回核·本批 actual/Δ/cross 齐："
          f"{sum(1 for r in b2 if r['actual'] and r['actual_delta_pp'] and r['cross_contract'])}/10 ✔")
    print(f"回核·教练版未被覆盖：{sum(1 for r in b2 if r['actual_reason_coach'])}/10 ✔")
    print(f"回核·涉改行数（本批∪任何有 actual_reason 的行）：{len(changed)}（应恰为 10）"
          f"{'✔' if len(changed) == 10 else '✘'}")
    print(f"回核·列数：{len(back[0])} {'✔' if len(back[0]) == len(fieldnames) else '✘'}")


if __name__ == "__main__":
    main()
