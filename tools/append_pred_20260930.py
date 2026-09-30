#!/usr/bin/env python3
"""append_pred_20260930.py

落 **2026/9/30 批**（compare_date 2026/10/14）的 IV 方向预测 10 行。

compare_date 依据（实测 8 个历史批次，规律 = 批次日 + 5 个交易日）：
    9/21→9/29 · 9/22→9/30 · 9/23→10/8 · 9/24→10/9 · 9/28→10/12 · 9/29→10/13
    9/30 之后：10/8(1) 10/9(2) 10/12(3) 10/13(4) 10/14(5)  → 10/14
    （10/1-10/7 国庆连休，故 9/29 与 9/30 相差一个交易日 = 10/13 vs 10/14）

`user_reason` = 用户 9/30 口述，**逐字照录**（含 2 处笔误：ma「美伊冲出」、
sr「未造成影星」）。依据 task-template:40 **reason 冻结铁律（9/10 立）**：
一经写入、对照日前一律不改 → 本脚本不做任何润色。

`flag` 标 `〔非盲填〕`。依据 task-template:37 **教练盲填铁律（9/15 立）**：
操作顺序应为「scanner 跑完 → 教练盲写 → 她再提交」；本次**她先贴出 10 条
pred**（顺序反转）→ 教练列必须标 〔非盲填〕，且该行**不进「教练 vs 用户」
对比统计**，只进各自绝对准确率。

⚠️ 教练列 coach_reason **只引 iv_history 9/30 09:30 实测数**（可追溯），
不引未经检索的新闻事件（依 9/28「先搜后写」——本批窗口 10/1-10/14 为
未来窗口，事件尚未发生，故只写结构量，不编事件因果）。

用法：python3 tools/append_pred_20260930.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")

BATCH, COMPARE = "2026/9/30", "2026/10/14"
TAG = "〔用户口述·9/30 教练落盘·内容一字未改〕"

# ── 用户 9/30 口述（逐字，含笔误）───────────────────────────────
USER = {
    "m":  ("down", "iv-hv -2.5%折价 近远月倒挂，中方承诺进口美豆，远月供给宽松，厄尔尼诺短期难以造成影响，iv down"),
    "c":  ("down", "iv-hv 2.5% 溢价 近远月倒挂，中储粮支撑，但供给集中上市，远月供给宽松，厄尔尼诺短期难以造成影响，iv down"),
    "rm": ("down", "iv-hv -2.4% 折价 供给近期真紧缺，但豆粕供给充足，缓解压力，iv down"),
    "ta": ("up",   "iv-hv 2.4% 溢价 近远月倒挂，美伊冲突暂无新进展，加工费上涨，iv up"),
    "ma": ("up",   "iv-hv 5.5%溢价 近远月倒挂 进口断供，供给紧张，美伊冲出暂无新进展，iv up"),
    "au": ("down", "iv-hv 8.3% 溢价 fomc开完事件落地，暂无其他新催化出现，iv down"),
    "cf": ("up",   "iv-hv 1.8% 供给集中上市，成本端下移，价格跳水，iv up"),
    "sr": ("down", "iv-hv1.2% 溢价 近期天气利于糖分积累，虽然有预告称厄尔尼诺将导致广西等地区降雨增加，但短期未造成影星，iv down"),
    "i":  ("down", "iv-hv 1.5% 供给长期过剩，无新事件催化，iv 不上涨，则iv down"),
    "ru": ("up",   "iv-hv 6.2% 溢价产地泰国，东南亚等地降雨集中，厄尔尼诺在增强，对产量影响大，iv up"),
}

# ── 教练列（〔非盲填〕）。仅引 iv_history 9/30 09:30 实测 ────────
COACH = {
    "au": ("down", "IV 22.65%/HV20 14.37% → +8.28pp 全场最高溢价，5dΔ −0.35 仍在释放；正挂(au2611 21.16<au2612 22.65)。窗口跨国庆 10/1-10/7 休市=外盘黄金照常交易的跳动风险未出清，但溢价本身高→向下回归压力大于向上"),
    "m":  ("down", "IV 13.61% 处 HV−2.55pp 折价（换 HV60 13.32% 则 +0.29 溢价→符号不稳）；近月 m2611 15.42>主力 13.61=倒挂；5dΔ −1.80 惯性向下"),
    "c":  ("down", "IV 11.49%/+2.51pp；主力 c2611 仅 23 DTE=全批最短→临近到期自然衰减；近月 11.49>c2701 9.22=倒挂；5dΔ −1.19"),
    "cf": ("down", "IV 14.36%/+1.84pp；5dΔ +1.98=全批最大上行→回吐压力；参考月 cf2703 因价差闸为空=期限结构今日不可判（数据缺失，不猜）"),
    "sr": ("up",   "IV 10.08%/HV20 8.88% → +1.20pp 为全批最薄一档，IV 亦为全批最低；向下空间被地板限制；5dΔ −0.37"),
    "ta": ("up",   "IV 33.20%/+2.43pp；近月 ta2612 35.75>主力 33.20=倒挂；5dΔ −0.38 已基本走平"),
    "i":  ("down", "IV 16.16%/+1.46pp=全批最薄正溢价；5dΔ +0.24；正挂(i2611 15.80<i2701 16.16)。薄溢价无向上催化"),
    "ru": ("up",   "IV 26.09%/+6.16pp；5dΔ +5.22=全批最大→惯性未消；近月 ru2611 30.06>主力 26.09=倒挂"),
    "ma": ("down", "IV 37.20%=全批最高/+5.49pp；5dΔ −5.67=全批最大下行；近月 ma2612 43.03>主力 37.20=倒挂"),
    "rm": ("down", "IV 17.45% 处 HV−2.41pp 折价（换 HV60 15.94% 则 +1.51 溢价→符号不稳）；5dΔ −3.28 下行惯性；参考月 rm2703 价差闸为空，期限结构今日不可判"),
}

FLAG = ("〔非盲填〕教练列：用户 9/30 先提交 pred（违 9/15 盲填铁律的操作顺序）"
        "→ 本行不进「教练 vs 用户」对比统计，只进各自绝对准确率")


def main():
    dry = "--dry-run" in sys.argv
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    dup = [r["variety"] for r in rows if r.get("date") == BATCH]
    assert not dup, f"批次 {BATCH} 已存在行，拒绝重复追加：{dup}"
    assert set(USER) == set(COACH), "两列品种集合不一致"
    for v, (p, t) in USER.items():
        assert t.rstrip().endswith(p), f"{v}: user_reason 结句与 user_pred 不符"
        assert "iv" in t.lower(), f"{v}: user_reason 首句缺波动率量（task-template:30 检查）"

    new = []
    for v in ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]:
        r = {k: "" for k in fieldnames}
        r["date"] = BATCH
        r["variety"] = v
        r["user_pred"] = USER[v][0]
        r["user_reason"] = TAG + USER[v][1]
        r["coach_pred"] = COACH[v][0]
        r["coach_reason"] = COACH[v][1]
        r["compare_date"] = COMPARE
        r["flag"] = FLAG
        new.append(r)

    print(f"批次 {BATCH} → compare {COMPARE}：新增 {len(new)} 行")
    print(f"{'品种':<4}{'用户':<6}{'教练':<6}{'一致':<6}{'user_reason 字数'}")
    for r, v in zip(new, ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]):
        same = "✓" if r["user_pred"] == r["coach_pred"] else "✗ 分歧"
        print(f'{v:<4}{r["user_pred"]:<6}{r["coach_pred"]:<6}{same:<6}{len(USER[v][1])}')
    nu = sum(1 for r in new if r["user_pred"] == "up")
    nc = sum(1 for r in new if r["coach_pred"] == "up")
    print(f"\nup 计数：用户 {nu}/10 · 教练 {nc}/10")

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
        w.writerows(rows + new)
    os.replace(tmp, CSV_PATH)

    # ── 回核（只打计数/断言，不回显正文）─────────────────────
    with open(CSV_PATH, "rb") as f:
        raw = f.read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        back = list(csv.DictReader(f))
    b = [r for r in back if r.get("date") == BATCH]
    n_crlf = raw.count(b"\r\n")

    print(f"\n备份：{bak}")
    print(f"回核·总行数：{len(back)}（写前 {len(rows)} → 应 {len(rows)+10}）"
          f"{'✔' if len(back) == len(rows) + 10 else '✘'}")
    print(f"回核·换行：CRLF {n_crlf} / LF {raw.count(chr(10).encode())} → "
          f"{'LF ✔' if n_crlf == 0 else '✘'}")
    print(f"回核·本批行数：{len(b)}/10 {'✔' if len(b) == 10 else '✘'}")
    print(f"回核·本批品种齐：{'✔' if {r['variety'] for r in b} == set(USER) else '✘'}")
    print(f"回核·compare_date 全为 {COMPARE}："
          f"{'✔' if all(r['compare_date'] == COMPARE for r in b) else '✘'}")
    print(f"回核·actual 列全空（对照日 10/14 才填）："
          f"{'✔' if not any(r['actual'] for r in b) else '✘'}")
    print(f"回核·教练列已标 〔非盲填〕："
          f"{'✔' if all('非盲填' in r['flag'] for r in b) else '✘'}")
    print(f"回核·列数：{len(back[0])} {'✔' if len(back[0]) == len(fieldnames) else '✘'}")
    print(f"回核·历史行未被触碰：{len(back) - len(b)} 行，末历史行 "
          f"{back[-11]['date']}/{back[-11]['compare_date']}")


if __name__ == "__main__":
    main()
