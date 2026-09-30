#!/usr/bin/env python3
"""fill_actual_reason_coach_20260930.py

对照日 2026-09-30：回填 **2026/9/22 批**（compare_date 2026/9/30）的
`actual_reason_coach`（事后归因列）。

口径（本脚本只写一列，其余列留给流程 ③ 或用户）：
  - 窗口 = **[9/23, 9/30]**。依据：9/21 批的 au 行原文写
    「〔窗外〕9/17 FOMC…（9/17 < 窗口起点 9/22）」，即 **窗口起点 = 批次日 + 1**。
    9/22 当天的事件因此记〔窗外〕。
  - 只写 actual_reason_coach；不写 actual / actual_delta_pp /
    contract_compare / cross_contract / user_correct / coach_correct。
    理由：流程 ① 只要求落这一列，其余三列（含对错）在 ③ 之后落，
    避免用户口述 actual_reason 前从本表反推自己的对错、污染口述。

来源标注：本批可用的唯一事件源是 scanner 事件卡（**2026-09-27 手动扫描快照，
有效至 2026-10-10**）。该快照覆盖 9/23-9/30 窗口，但 **9/28-9/30 的增量未重扫**
→ 每行来源统一标「可信度中高」并在末尾注明快照性质。

用法：python3 tools/fill_actual_reason_coach_20260930.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")

BATCH_DATE = "2026/9/22"
COMPARE_DATE = "2026/9/30"
SRC = "scanner 事件卡（9/27 重扫快照·有效至 10/10）"

# ── 10 条事后归因 ────────────────────────────────────────────────
REASONS = {
    "au": (
        "〔窗外〕9/17 FOMC 加息 25bp 至 3.75-4.00%（9/17 < 窗口起点 9/23，已出清）"
        "+〔窗内〕9/25-26 霍尔木兹出现缓和信号（伊朗提「七日方案」、美方护航 4000 万桶通过、"
        "沙特与约 80 国施压）"
        " → 事件出清后无新催化 + 地缘避险降温 → IV 继续小幅回落 −0.35pp。"
        f"来源：{SRC}·窗内·可信度中高（快照，9/28-9/30 增量未重扫）。"
    ),
    "m": (
        "〔窗内〕9/28 USTR 格里尔公布中美会晤详细成果：①贸易休战延长 2 个月、新到期日 "
        "2027-01-10 ②中方承诺采购 2500 万吨美豆 —— 公布日正是复市首日、落在本窗口第 1 天；"
        "叠加国内库存 9/11 为 110.99 万吨（环比下降）"
        " → 休战延长＝风险溢价继续释放（偏空 IV）、采购承诺＝供应端增量（偏空现货）"
        "＝两头对卖方都不利 → IV 回落 −1.80pp。"
        f"来源：{SRC}·窗内·可信度高。"
    ),
    "c": (
        "〔窗内〕新粮集中上市、下行加速（华北基层收购价普遍跌破 2100、河南部分破 2000，"
        "山东企业半月累计下调 60-158 元/吨）"
        "+ 政策托底同步加码（中储粮 9 月高频采购、9/15-16 全国秋粮收购工作会议定调守住底线）"
        "+ 进口玉米拍卖 9/18 重启转公开（9/22 计划 19479 吨、成交率仅 22%）"
        " → 上市压力与政策托底同时用力＝方向被夹住、波动压缩 → IV 回落 −1.19pp。"
        "东北集中收割上市预计在国庆之后＝窗口外，本窗口内增量尚未到。"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
    "cf": (
        "〔窗内〕北疆采收高峰 9/23-25 兑现（落在窗口第 1-3 天）"
        "+ 籽棉收购价方向由上窗口的「抬升」反转为「下移」"
        "（9/21 记 7.70-8.0 → 现主流 7.20-7.30 元/公斤）"
        "+ 皮棉产销倒挂：按现收购价折皮棉成本，加工厂每吨亏 300-400 元、收了就亏"
        " → 现货端不确定性抬升＋加工端无买盘 → IV 抬升 +1.98pp。"
        "（本批最大正向之一；cf 亦是 Data 门卡点 cf=47。）"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
    "sr": (
        "〔窗内〕9/26-28 广西小到中雨、9/27-29 桂北寒露风（气象窗口期正在过）"
        "+ 配额再分配 9/30 前分配完（政策窗在本窗口内）"
        " → 天气项被本批复核证伪为「非风险项」：寒露风在甘蔗工艺成熟期利于糖分积累、"
        "降水偏少 1-3 成利于糖分积累（旧表把有利项错列成风险项，属分类错误而非强度错误）"
        " → 无抬升 IV 的催化 → IV 回落 −0.37pp，**刚过 flat 线（|Δ|>0.25）**。"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
    "ta": (
        "⚠️ cross 口径（ta2611→ta2701；基线＝9/22 该行 ref_iv＝同合约、无换月跳变）。"
        "〔窗内〕9/28 布伦特一度破 100 美元、美伊冲突升温、霍尔木兹通航受阻"
        "（9/24 仅 9 艘船通行，约为过去 10 天日均一半）→ PX/石脑油成本抬升"
        "；但同时 PTA 自身加工费从 9/14 约 400 反向走强至 9/23 约 700 元/吨、"
        "聚酯负荷降至 74.5%-78.1%（下游负反馈）"
        " → 成本上推与需求端下塌互抵、方向被夹住但不确定性净增 → IV 抬升 +2.69pp。"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
    "i": (
        "〔窗内〕45 港库存 9/18 回升至 16355 万吨（+122.47）、连续去库中断转累库"
        "+ 9/18 当周全球发运 3517.1 万吨（+158.8）回升"
        "+ 钢厂盈利率降至 7.79% 创年内新低、复产动力不足"
        "+ 西芒杜 9-12 月维持 300-500 万吨/月放量"
        " → 供增需减、无方向性事件 → IV 微升 +0.24pp，"
        "**落 flat 线内（|Δ|<0.25）、排除出分母**（仅差 0.01pp 就进分母）。"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
    "ru": (
        "〔窗内〕9 月泰国产量加权降雨量增至 4.73 mm/日、**连续 4 周边际增量**"
        "（割胶主力区在北部/东北部；旧表用南部叻他尼/宋卡「同比偏低 58%/51%」口径，"
        "南部偏少 ≠ 全国偏少，口径读反了）"
        "+ 厄尔尼诺增强：NINO3.4 于 9/18 达 3.0（9/11 为 2.9）、超强预期持续增强"
        "+ 9/24 泰国胶水约 80.0 泰铢/公斤（同比 +44.7%）、杯胶 75.5（+48.6%）"
        "+ 国内云南胶水 1.74 万元/吨、海南胶乳 1.90 万元/吨（环比 +2.4%/+2.7%）"
        " → 割胶受阻、供给收紧、原料价高位 → 波动率溢价抬升 → "
        "**+5.22pp，本批最大正变动**。"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
    "ma": (
        "⚠️ cross 口径（ma2611→ma2701；基线＝9/22 该行 ref_iv＝同合约、无换月跳变）。"
        "〔窗内〕9 月甲醇进口预计降至 40-50 万吨以下（8 月约 70 万吨、7 月 99.2 万吨，"
        "三个月腰斩再腰斩）+ 港口持续去库（9/17 华东华南 31.24 万吨、去库 6.94）"
        "+ 中东约 62% 装置停车、海外开工率 52.35%"
        "+ 霍尔木兹 9/26 特朗普明确拒绝伊朗「七日方案」"
        " → 近月物理断供未解＋地缘未落地 → 近月波动率抬升 → IV 抬升 +3.99pp。"
        "⚠️ 与 9/21 批对**同一对合约**记的 −5.77pp 方向相反，"
        "差异源于该批用了裸换月口径（Δ 含换月跳变），见其 flag。"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
    "rm": (
        "⚠️ cross 口径（rm2611→rm2701；基线＝9/22 该行 ref_iv＝同合约、无换月跳变）。"
        "〔窗内〕对加拿大油菜籽反倾销终裁已落地（自 3/1 起统一征收 5.9%、5 年有效）"
        "+ 9/10/11 月进口菜籽到港预估 58.5/52/44.5 万吨（供给端恢复）"
        "+ 月度进口自 2 月 18.25 万吨升至 7 月 40.95 万吨"
        " → 供应端增量兑现，9/16 主力单日 +4.16% 后回吐 → 波动率回落 −2.14pp。"
        f"来源：{SRC}·窗内·可信度中高。"
    ),
}


def main():
    dry = "--dry-run" in sys.argv
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    tgt = [r for r in rows if r.get("date") == BATCH_DATE
           and r.get("compare_date") == COMPARE_DATE]

    # ── 断言 ────────────────────────────────────────────────
    assert len(tgt) == 10, f"批次 {BATCH_DATE} 应有 10 行，实得 {len(tgt)}"
    assert {r["variety"] for r in tgt} == set(REASONS), "品种集合不匹配"
    overwritten = [r["variety"] for r in tgt
                   if str(r.get("actual_reason_coach", "")).strip()]
    assert not overwritten, f"以下行已有 actual_reason_coach，拒绝覆盖：{overwritten}"
    # 窗口口径提示：本批不含 9/22 当天事件
    assert all("actual_reason_coach" in r for r in rows), "列名不匹配"

    for r in tgt:
        r["actual_reason_coach"] = REASONS[r["variety"]]

    print(f"批次 {BATCH_DATE} → compare {COMPARE_DATE}：命中 {len(tgt)} 行")
    print(f"待写 actual_reason_coach：{len(tgt)} 行（无覆盖）")
    for r in tgt:
        print(f"  {r['variety']:3s}  {len(REASONS[r['variety']]):3d} 字  "
              f"pred={r['user_pred']}/{r['coach_pred']}")

    if dry:
        print("\n--dry-run：未落盘。")
        return

    # ── 备份（git 之外的第二道）──────────────────────────────
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)

    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, CSV_PATH)

    # ── 回核（只打行数/换行/断言，不回显正文）─────────────────
    with open(CSV_PATH, "rb") as f:
        raw = f.read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        back = list(csv.DictReader(f))

    n_crlf = raw.count(b"\r\n")
    n_lf = raw.count(b"\n")
    filled = [r for r in back if r.get("date") == BATCH_DATE
              and r.get("compare_date") == COMPARE_DATE
              and str(r.get("actual_reason_coach", "")).strip()]
    others_touched = [r for r in back
                      if str(r.get("actual_reason_coach", "")).strip()
                      and not (r.get("date") == BATCH_DATE
                               and r.get("compare_date") == COMPARE_DATE)]

    print(f"\n备份：{bak}")
    print(f"回核·总行数：{len(back)}（写前 {len(rows)}）{'✔' if len(back) == len(rows) else '✘'}")
    print(f"回核·换行：CRLF {n_crlf} / LF {n_lf} → {'LF ✔' if n_crlf == 0 else '✘'}")
    print(f"回核·本批已填 actual_reason_coach：{len(filled)}/10 "
          f"{'✔' if len(filled) == 10 else '✘'}")
    print(f"回核·其他行被改动：{len(others_touched)} {'✔' if not others_touched else '✘'}")
    print(f"回核·列数：{len(back[0])} {'✔' if len(back[0]) == len(fieldnames) else '✘'}")


if __name__ == "__main__":
    main()
