#!/usr/bin/env python3
"""rewrite_coach_reason_20260930.py

**规则例外 · 用户 9/30 17:2x 明确开启** —— 重写 2026/9/30 批的 `coach_reason`。

背景（留痕，不美化）：
  17:18 落的 10 条 `coach_reason` 是**纯结构量**（IV 水平 / IV−HV / 5dΔ / 期限结构），
  **A 变化性 0/10、B 三段齐 0/10** —— 无 `[事件·基本面]` 层、无 `[传导段]`。
  这违反 **9/28 立的「先搜后写」**（task-template 版外规则，原话：
  「`coach_reason` 与 `actual_reason_coach` **落盘前均须检索事件源**」）。
  我在脚本 docstring 里还写了句「依 9/28 先搜后写 → 本批窗口在未来、故只写结构量」——
  **把该规则引反了**（它下令搜索，我引它当免搜牌）。用户当场指出（Ti 对 Ti）。

与 **9/10 reason 冻结铁律**（task-template:40）的冲突，用户裁定：
  > 改开例外，这个本身是错误导致的，不能允许错误每次都影响记录
**教练反方（留痕，不撤回）**：line 40 原文预见了本情形并裁过——
  「发现**漏了事件**/理由写错 → 写进 journal 或另起备注，不回头改原文…**错就留痕**」。
  且 10/14 对照会因「事后润色」而失真。**用户为规则所有者，裁定生效，反方存档。**

不销毁原文（教练加的约束）：单元格前置标注，**原文全文逐条进
`journal/2026-09-30.md` 的「教练列自查」对照表**，两边都可读。

用法：python3 tools/rewrite_coach_reason_20260930.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
BATCH = "2026/9/30"
MARK = "〔9/30 17:3x 补写·原版违 9/28 先搜后写·原文见 journal 对照〕"

SRC = "来源：scanner 事件卡 9/27 快照（有效至 10/10）·窗内·可信度中高"

# ── 三段齐补写版：[事件·基本面] → [传导段] → [IV 结果] ──────────
# ⚠️ 三条（cf/sr/ma）事件传导与 coach_pred 不一致 —— 照实写、加标记，不迁就形。
NEW = {
    "au": "〔窗内〕10/1-10/7 上期所休市而 COMEX/伦敦金照常交易 8 个日历日 → 外盘累计跳动在 10/8 复市被一次性定价＝已实现方差被动抬升；叠加 Hormuz 未出清（9/26 特朗普拒绝伊朗「七日方案」，窗外事件）→ 避险可随时重启 → 但 IV 22.65% 已含 HV₂₀+8.28pp（全场最高溢价）、5dΔ −0.35 处在释放通道 → 溢价释放占优 → IV down。" + SRC,
    "m":  "〔窗外〕9/28 USTR 公布休战延长 2 个月至 2027-01-10＋中方承诺采购 2500 万吨美豆；〔窗内〕该承诺的执行/装运节奏是 10 月新变量，叠加国内库存 9/11 110.99 万吨环比下降 → 供应端预期宽松 → 现货波动来源减弱 → IV 已处 HV₂₀−2.55pp 折价、5dΔ −1.80 惯性未尽 → IV down。来源：scanner 事件卡 9/27 快照＋9/30 教练核实·窗内·可信度高",
    "c":  "〔窗内〕东北集中收割上市预计在国庆之后（＝落进 10/8-10/14）＋中储粮 9 月高频采购托底＋进口玉米拍卖 9/18 转公开（9/22 成交率仅 22%） → 上市压力与政策托底同时用力、方向被夹住 → 波动来源对消；叠加主力 c2611 仅 23 DTE（全批最短）临近到期自然衰减 → IV down。" + SRC,
    "cf": "〔窗外〕北疆采收高峰 9/23-25 兑现、籽棉收购价由 7.70-8.0 反转为 7.20-7.30 元/公斤；〔窗内〕10 月收购价博弈延续——加工厂按现价折皮棉每吨亏 300-400、收了就亏＝无买盘，采收自北疆向内推进 → 现货端不确定性仍在抬升通道（与 5dΔ +1.98pp 全批最大上行同向）→ **本条事件传导指向 up**。⚠️ 与 coach_pred=down（纯极值回吐、无事件依据）不一致。" + SRC,
    "sr": "〔窗外〕9/26-28 广西小到中雨、9/27-29 桂北寒露风——复核为**有利**项（工艺成熟期利于糖分积累、降水偏少利于积累），非风险项；〔窗内〕配额再分配 9/30 前已分配完＝政策窗出清 → 两个抬升源均已出清，仅剩 2026/27 减产预期 → 无新增催化 → IV down。⚠️ coach_pred=up 的依据是「IV 10.08% 全场最低、溢价 +1.20pp＝地板」＝**纯结构论、无事件传导**，与本条不一致。来源：scanner 事件卡 9/27 快照＋本日复核·可信度中高",
    "ta": "〔窗内〕Hormuz 未出清（9/26 特朗普拒绝伊朗「七日方案」）＋PTA 自身加工费 9/8 485 → 9/23 ~700 元/吨（产业利润再分配，机构称偏高可做空）＋下游负反馈（聚酯负荷 74.5%-78.1%）＋成本端退（石脑油 −6.84%、PX −2.6%） → 成本下推与产业端上顶对拉 → 不确定性维持 → IV up（弱）。" + SRC,
    "i":  "〔窗内〕45 港库存 9/18 回升至 16355 万吨（+122.47）连续去库转累库＋9/18 当周全球发运 3517.1 万吨（+158.8）回升＋钢厂盈利率 7.79% 创年内新低、复产动力不足＋西芒杜 9-12 月 300-500 万吨/月放量 → 供增需减、无方向性事件 → 波动来源持续减弱 → IV down。" + SRC,
    "ru": "〔窗内〕泰国产量加权降雨 4.73 mm/日、连续 4 周边际增量＋NINO3.4 于 9/18 达 3.0（9/11 为 2.9）超强预期增强＋9/24 泰国胶水 80.0 泰铢/公斤（同比 +44.7%）＋国内云南胶水 1.74 万元/吨、海南 1.90 万元/吨（环比 +2.4%/+2.7%） → 割胶受阻、供给收紧、原料价高位 → 波动率溢价抬升、5dΔ +5.22pp 惯性未消 → IV up。" + SRC,
    "ma": "〔窗内〕9 月甲醇进口预计降至 40-50 万吨以下（8 月约 70、7 月 99.2）＋港口持续去库（9/17 华东华南 31.24 万吨、去库 6.94）＋中东约 62% 装置停车、海外开工率 52.35%＋Hormuz 未出清（9/26 特朗普拒绝） → 近月物理断供未解＝**本条事件传导指向 up**。⚠️ 与 coach_pred=down（纯极值回摆、无事件依据）不一致；IV 已 37.20% 全场最高、5dΔ −5.67pp 全批最大下行。" + SRC,
    "rm": "〔窗外〕对加拿大油菜籽反倾销终裁落地（3/1 起统一征收 5.9%、5 年有效）；〔窗内〕10/11 月进口菜籽到港预估 58.5/52/44.5 万吨（供给端恢复兑现）＋月度进口自 2 月 18.25 万吨升至 7 月 40.95 万吨 → 供应端增量 → 波动率回落；IV 处 HV₂₀−2.41pp 折价、5dΔ −3.28 惯性向下 → IV down。来源：scanner 事件卡 9/27 快照＋9/30 教练核实·可信度中高",
}


def main():
    dry = "--dry-run" in sys.argv
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    tgt = [r for r in rows if r.get("date") == BATCH]
    assert len(tgt) == 10, f"批次应 10 行，实得 {len(tgt)}"
    assert {r["variety"] for r in tgt} == set(NEW), "品种集合不匹配"
    # 幂等：拒绝二次重写
    done = [r["variety"] for r in tgt if r.get("coach_reason", "").startswith(MARK)]
    assert not done, f"以下行已补写过，拒绝重复：{done}"

    nflag = 0
    print(f"批次 {BATCH}：重写 coach_reason 10 行\n")
    for r in sorted(tgt, key=lambda x: x["variety"]):
        v = r["variety"]
        old = r["coach_reason"].strip()
        new = NEW[v]
        # 方向一致性自查（不迁就形，只标记）
        consistent = not ("不一致" in new)
        if not consistent:
            nflag += 1
        r["coach_reason"] = f"{MARK}{new}"
        r["flag"] = (r["flag"] + "｜" if r["flag"] else "") + \
            "coach_reason 9/30 补写（用户开例外·原文见 journal 对照）"
        print(f'  {v:3s} pred={r["coach_pred"]:5s} 旧 {len(old):3d} 字 → 新 {len(new):3d} 字 '
              f'{"✔ 传导与前定一致" if consistent else "⚠️ 传导指向与 coach_pred 不一致"}')
    print(f"\n⚠️ 不一致条数：{nflag}/10 —— 照实留痕，未改 coach_pred（计数列不动）")

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
    b = [r for r in back if r.get("date") == BATCH]
    n_crlf = raw.count(b"\r\n")

    print(f"\n备份：{bak}")
    print(f"回核·总行数：{len(back)}（写前 {len(rows)}）{'✔' if len(back) == len(rows) else '✘'}")
    print(f"回核·换行：CRLF {n_crlf} / LF {raw.count(chr(10).encode())} → "
          f"{'LF ✔' if n_crlf == 0 else '✘'}")
    print(f"回核·本批 10 行均已带补写标注："
          f"{sum(1 for r in b if r['coach_reason'].startswith(MARK))}/10 "
          f"{'✔' if all(r['coach_reason'].startswith(MARK) for r in b) else '✘'}")
    exp = {"au": "down", "m": "down", "c": "down", "cf": "down", "sr": "up",
           "ta": "up", "i": "down", "ru": "up", "ma": "down", "rm": "down"}
    intact = all(r["coach_pred"] == exp[r["variety"]] for r in b)
    print(f"回核·本批 coach_pred 未被触碰："
          f"{'✔' if intact else '✘ ' + str({r['variety']: r['coach_pred'] for r in b})}")
    print(f"回核·actual 列仍全空：{'✔' if not any(r['actual'] for r in b) else '✘'}")
    print(f"回核·历史 190 行 coach_reason 未被触碰："
          f"{sum(1 for r in back if r.get('date') != BATCH and r['coach_reason'].startswith(MARK))} 行 "
          f"{'✔' if not any(r.get('date') != BATCH and r['coach_reason'].startswith(MARK) for r in back) else '✘'}")
    print(f"回核·列数：{len(back[0])} {'✔' if len(back[0]) == len(fieldnames) else '✘'}")


if __name__ == "__main__":
    main()
