#!/usr/bin/env python3
"""append_user_pred_20261012.py

落 **2026/10/12 批**的 `user_pred` / `user_reason` 10 行（教练列已于此前落盘）。

依据：
- task-template:35 **教练盲填铁律（9/15 立）**——教练列已在她提交前落盘 → **不标 〔非盲填〕**。
  落盘后教练列**不得改写**，本脚本只写 `user_*` 两列，教练列一个字不碰。
- **reason 冻结铁律（9/10 立）**：一经写入、对照日（2026/10/19）之前一律不改。
- 9/30 先例：`user_reason` **逐字照录**，不润色、不补全、不删改。
- task-template:30 **教练执行期检查（9/21 补）**：`user_reason` 第一句须出现
  「波动率」三字或一个波动率量（IV / 方差 / 隐含 vs 已实现 / 期限结构）。本批 10/10 合规。

用法：python3 tools/append_user_pred_20261012.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")

BATCH = "2026/10/12"

# （pred, reason 逐字照录）———— 用户 10/12 盘中原话
USER = {
    "cf": ("down", "iv-hv -1.6%折价。棉花供应宽松，下游开机率下降，接货意愿不高，无事件催化 iv down"),
    "m":  ("up",   "iv-hv -0.8% 折价，供应压力减弱，当前美豆收割完毕，短期无天气影响，需要到12月天气会影响南美播种，豆粕期货价格处于近期高位有下调压力，波动会变大，iv up"),
    "rm": ("up",   "iv-hv -0.7% 折价，供给端家菜籽收割艰难，供给端游压力，但豆粕供应宽松，价格跟随豆粕下跌，价格有支撑，iv up"),
    "sr": ("up",   "iv-hv 3.3%，溢价，厄尔尼诺影响，巴西产糖量下跌，但国内库存充足，近期恐慌，iv up"),
    "au": ("up",   "iv-hv 7.2% 高溢价，年内加息预期持续，美伊冲突持续，新进展不太乐观，iv up"),
    "ta": ("down", "iv-hv -0.1% 折价，原油价格冲高回落，供给端暂无压力，iv down"),
    "ma": ("up",   "iv-hv 10.5% 高溢价，国内供应紧张，进口断供，库存低，价格脉冲上升但有回调压力，预期波动变大，iv up"),
    "i":  ("down", "iv-hv 3% 溢价 供应宽松，无事件催化，iv down"),
    "ru": ("up",   "iv-hv 5% 溢价 厄尔尼诺影响，成本上涨，天气影响强预期，iv up"),
    "c":  ("down", "iv-hv 0.9% 新粮收割季，对价格冲击大，中粮政策托底，iv down"),
}

VOL_MARKERS = ("波动率", "iv", "IV", "方差", "隐含", "已实现", "期限结构")


def main():
    dry = "--dry-run" in sys.argv
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    batch_rows = [r for r in rows if r.get("date") == BATCH]
    assert len(batch_rows) == 10, f"批次 {BATCH} 应有 10 行，实际 {len(batch_rows)}"
    for r in batch_rows:
        assert r["coach_pred"], f"{r['variety']}: 教练列缺失（盲填顺序被破坏）"
        assert not r["user_pred"], f"{r['variety']}: user_pred 已有值，拒绝覆盖"

    for v, (p, t) in USER.items():
        assert p in ("up", "down"), f"{v}: pred 非法 {p}"
        assert p in t, f"{v}: reason 结尾与 pred 不一致"
        first = t.split("。")[0].split("，")[0]
        assert any(mk in first for mk in VOL_MARKERS), f"{v}: 第一句缺波动率量 → {first!r}"

    agreement = 0
    print(f"批次 {BATCH}：写入 user 列 {len(batch_rows)} 行")
    print(f"  {'品种':<5}{'用户':<7}{'教练':<7} 一致")
    for r in batch_rows:
        v = r["variety"]
        same = USER[v][0] == r["coach_pred"]
        agreement += same
        print(f"  {v:<5}{USER[v][0]:<7}{r['coach_pred']:<7} {'✅' if same else '✗'}")

    up_u = sum(1 for v in USER if USER[v][0] == "up")
    up_c = sum(1 for r in batch_rows if r["coach_pred"] == "up")
    print(f"\n用户 up {up_u}/10 · 教练 up {up_c}/10 · 一致 **{agreement}/10**")

    if dry:
        print("\n--dry-run：未落盘。")
        return

    b = open(CSV_PATH, "rb").read()
    n_before = (b.count(b"\n"), b.count(b"\r\n"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)

    for r in batch_rows:
        r["user_pred"], r["user_reason"] = USER[r["variety"]]

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
    added = [r for r in rows2 if r.get("date") == BATCH]
    assert len(rows2) == len(rows), "行数变了，拒绝"
    assert all(r["user_pred"] and r["user_reason"] for r in added), "有行未写满"
    assert all(r["coach_pred"] and r["coach_reason"] for r in added), "教练列被破坏"
    print(f"\n回核：总行数 {len(rows2)}（未变）· 本批 {len(added)} · 列数 {len(rows2[0])}")
    print(f"      LF {n_before[0]} → {b2.count(b'\n')} · CRLF {n_before[1]} → {b2.count(b'\r\n')}（须为 0）")
    print(f"      user 列已写 {sum(1 for r in added if r['user_pred'])}/10 · coach 列完好 {sum(1 for r in added if r['coach_pred'])}/10")
    print(f"      备份 {bak}")


if __name__ == "__main__":
    main()
