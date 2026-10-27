#!/usr/bin/env python3
"""append_pred_20261021.py

批次 2026/10/21 → compare 2026/10/28。**教练列盲填**（9/15 铁律）：
在她提交 user_pred / user_reason 之前落盘，只依据当天 scanner 输出 +
weekly_event_scan.json + iv_history.csv，不看她那一行。

⚠️ 本批 compare_date = **2026/10/28 = FOMC 日（D-0）**。
   5 个品种（au/i/ru/ta/ma）日历里带 FOMC —— 这是本批最大的单因子。

用法：python3 tools/append_pred_20261021.py [--dry-run]
"""
import csv
import io
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
CAL_PATH = os.path.join(ROOT, "data", "trade_calendar.txt")

BATCH = "2026/10/21"
COMPARE = "2026/10/28"

SRC_SCAN = "〔源：scanner 10/21 09:15 实跑〕"
SRC_EVT = "〔源：weekly_event_scan.json · valid_until 2026-10-26 · 可信度中高〕"

ORDER = ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]
CONTRACT = {
    "au": "au2612", "m": "m2701", "c": "c2701", "cf": "cf2701", "sr": "sr2701",
    "ta": "ta2612", "i": "i2701", "ru": "ru2701", "ma": "ma2612", "rm": "rm2701",
}

COACH = {
    "au": ("up",
           f"ATM IV **20.3%** / HV₂₀ **13.0%** → **+7.2pp 溢价**，全品种最贵；5dΔ −0.8pp（溢价在缩）。"
           f"**多**的头：compare 日 **2026/10/28 = FOMC（D-0）**，事件前 IV 通常抬升，且 10Y 已自 5.24% "
           f"回落至 5.06–5.12%、美元指数回落，压制项在松 → 波动率有再定价空间。**空**的头：+7.2pp 已在 "
           f"前 12% 分位以上，事件溢价**可能已提前定价**；机构区间三家一致（850–950 / 880–920 / 860–910）"
           f"压在现价附近，本身在说「没有方向驱动」。⚠️ **反方（照反方强制先给）**：① 「FOMC 前 IV 必抬」"
           f"是**先验不是读数**——本批 compare 日恰在事件当天，若市场已按 D-7 提前定价，10/28 反而会是"
           f"**涨完回落的第一天**，这条预测最可能死于时点而非方向；② +7.2pp 溢价支持的是「绝对水平高」，"
           f"**不直接支持「5 日后更高」**，我把水平当变化用了，这是 9/28 批 au 的同类错。"
           f"{SRC_SCAN} {SRC_EVT}"),

    "m": ("down",
          f"ATM IV **12.8%** / HV₂₀ **14.1%** → **−1.3pp 折价**；5dΔ −0.2pp。**核心机制**：驱动已从"
          f"「供给不确定」翻成「供给已定 + 需求走弱」—— USDA 10 月报告上调单产至 53.10 蒲/英亩、期末库存"
          f" 3.15 亿蒲（**10/13–10/19 窗内已兑现**），10/2 当周新作净销售 **环比 −46.85%**，四季度压榨上调"
          f"→ **三重指向累库** ⇒ 价格层「低波动」比「高波动」更可能 ⇒ IV 继续下压。⚠️ **反方**：① 收割率仅"
          f" **25%**（五年均值 33%）、严重滞后 → 晚收 = 天气暴露窗口更长，这是**反向的波动率来源**；"
          f"② 本窗（10/21–10/28）无 USDA 供需报告，**信息真空期 IV 常自然衰减**，衰减不等于我的机制成立；"
          f"③ 中国采购若停，利空加倍 = 波动放大，方向对但**波动率会反向走高**。{SRC_EVT} {SRC_SCAN}"),

    "c": ("down",
          f"ATM IV **9.6%** / HV₂₀ **8.5%** → **+1.2pp**，全场绝对水平最低；5dΔ −0.6pp（已在降）。"
          f"**机制**：新季玉米陆续上市（辽宁上量、北港到货增、深加工压价）、华北集中上市 → **季节性供给放量"
          f"压制价格波动**，收储政策**三路搜索零命中** → 缺上行冲击源 ⇒ 低 IV 自我强化。⚠️ **反方**："
          f"① **零命中 ≠ 无政策**——收储公告常在晚间突袭，本窗随时可能横空出现，一旦落地 IV 会跳；"
          f"② 「季节性上量」每年都有，按判据四问 A「变化性」天然不过关，**我拿它当驱动是不合格的**；"
          f"③ 9.6% 已是地板价，再降空间有限，**下注的是「不涨」不是「继续跌」**。{SRC_EVT} {SRC_SCAN}"),

    "cf": ("down",
           f"ATM IV **10.5%** / HV₂₀ **12.2%** → **−1.7pp 折价**；5dΔ −0.4pp。**机制**：供给充裕"
           f"（公检 17 万吨同比 +4、储备棉累计抛储超 40 万吨、商业库存高）+ 需求转弱（10 月中旬起订单不足、"
           f"开机率回落、纺企随用随买）⇒ **双边都无冲击源** ⇒ IV 向 HV 收敛甚或更低。"
           f"⚠️ **反方**：① USDA 下调全球产量 116 万吨是**确凿多头证据**，且与国内视角**不在同一层面**，"
           f"若被市场重新定价，IV 会跟着起；② 开机率存在**口径冲突**（70.1% 同比 +3.5pct vs 78%→69.2%），"
           f"裁清前「需求疲软」这半条**证据不牢**；③ **cf 是 Data 门最薄样本（今日刚补到 60）**，"
           f"本条 Δ 的可追溯性弱于其他品种。{SRC_EVT} {SRC_SCAN}"),

    "sr": ("down",
           f"ATM IV **10.3%** / HV₂₀ **9.0%** → **+1.3pp**；5dΔ −0.4pp。**机制**：底部由配额外巴西加工糖"
           f"成本 **6,600** 托住、上方由新榨季增产预期压住 ⇒ **区间收窄 ⇒ IV 天然易降**。进口断崖"
           f"（9 月到港 9.14 万吨、同比 −28.24）是**已兑现的存量事实**，它解释的是「为什么不跌」，"
           f"**不解释「波动变大」**。⚠️ **反方**：① **南方甘蔗 10 月中下旬开榨 = 本窗最重要的信息源**，"
           f"开榨进度**一旦慢于预期，区间会重新打开**，这条预测直接死在进度数据上；② 「供应偏紧」"
           f"（进口口径）与「工业库存 372 万吨 = 历史第二高」（库存口径）**同源互斥**，我取了前者来解释"
           f"低波动，可能取错了那一半；③ 厄尔尼诺 Niño3.4 **+2.3℃** 仍在，机构明写行情滞后峰值 3–6 个月，"
           f"**本窗不该用它**——我列出来只为说明它已被排除。{SRC_EVT} {SRC_SCAN}"),

    "ta": ("up",
           f"ATM IV **29.6%** / HV₂₀ **33.0%** → **−3.5pp 折价**，全场第二深折价；5dΔ **+1.0pp**"
           f"（唯一明显抬升的品种）。**机制**：成本端由「退潮」翻成「加剧波动」—— 10/17 两艘超级油轮"
           f"霍尔木兹触雷、10/19 又一艘起火，UKMTO 一周接报 12 起，海峡通行量减少约 **300 万桶/日**；"
           f"布油 10/16 收 **109.86**（5/19 以来最高）。**compare 日本身压在 FOMC（D-0）上**，"
           f"叠加 **10/21 EIA 库存（D-0·今晚）** ⇒ 事件密度本批最高 ⇒ IV 上抬。"
           f"⚠️ **反方**：① IV 已从 34.05%（10/9）跌到 28.34%（10/16）**−5.71pp，而同期布油在涨** → "
           f"**IV 与标的方向背离且无本地解释**，在这个背离被证伪前，「IV 会跟着油价涨」是**推的**；"
           f"② 「11/3 前不打伊朗」是美方单方表态，且**不等于伊朗不出手**；③ 飓风停产已回落至约 25% 海上产量 "
           f"= 供给在回补，这是**明确的利多出尽项**。{SRC_EVT} {SRC_SCAN}"),

    "i": ("down",
          f"ATM IV **16.2%** / HV₂₀ **14.0%** → **+2.2pp 溢价**；5dΔ −0.1pp。**机制**：本窗拿到了"
          f"**实测读数**而非预期—— 45 港库存 **16,534.67 万吨（环比 +54.45）**、247 家钢厂日均铁水 "
          f"**233.66 万吨（同比 −7.29）** ⇒ 供需双弱且**库存累积已发生** ⇒ 价格单向慢压 ⇒ HV 走低 ⇒ "
          f"IV 跟着下。⚠️ **反方**：① **反向套用风险（本条最大）**：10/12 批的错因正是「方向偏空 = 低波动」"
          f"—— 方向与波动率**不是一回事**，库存累积若走成**急跌**，HV 会飙升，我这条会反向错；"
          f"② compare 日 **10/28 在 FOMC 名单里**，若宏观驱动把这波压低波动抬起来，我的机制被盖掉；"
          f"③ 铁水环比仅 −0.18 万吨（≈0.08%）、库存 +0.33%，**都是小幅**，按判据四问 A「变化性」堪忧 —— "
          f"我实际是在赌「没有新变化」，而不是赌一个已发生的变化。{SRC_EVT} {SRC_SCAN}"),

    "ru": ("up",
           f"ATM IV **23.5%** / HV₂₀ **23.9%** → **−0.4pp 贴零**；5dΔ **−2.3pp**（全场降幅最大）。"
           f"**机制**：5dΔ −2.3 是「已发生的压缩」，而供给端利多仍在 —— 泰国雨季持续扰动割胶、南部洪涝、"
           f"**国内临近停割 + 新仓单同比减少明显** ⇒ 停割是**日历上的确定事件**，不是叙事 ⇒ 供给收缩"
           f"意味着价格跳跃概率上升 ⇒ IV 从压缩位回升。⚠️ **反方**：① **「临近停割」是季节性、每年都有**，"
           f"按判据四问 A「变化性」**天然不过关**——这正是 9/28 批 ru 的原错因，我可能是在重复它；"
           f"② 需求端 10 月中旬已转偏弱（轮胎需求弱、宏观风险偏好降），**供需两边拉扯，IV 未必单向**；"
           f"③ 泰国胶水即时报价**本窗未取到**（只有「原料价格坚挺」的定性），"
           f"停割论断的**量化底座缺失**。{SRC_EVT} {SRC_SCAN}"),

    "ma": ("up",
           f"ATM IV **39.2%** / HV₂₀ **38.1%** → **+1.1pp**，全场绝对水平最高；5dΔ −0.7pp。**机制**："
           f"沿海库存 **37.41 万吨（截至 10/8，同比 −74.98%）**、可流通货源仅约 **10.5 万吨** ⇒ "
           f"**低库存 + 低可流通 = 价格弹性极大** ⇒ 小资金即能推动大波动 ⇒ IV 该在高端不下来；"
           f"叠加 **10/21 EIA（D-0）+ 10/28 FOMC（D-0·compare 日）**，本批事件密度最高的一只。"
           f"⚠️ **反方**：① **10/9–10/25 到港预估 20.05–21 万吨** —— 若如期到达，去库不可持续，"
           f"「低库存」这个前提在本窗内会被自己拆掉；② 库存两读**互斥**（37.41 万 vs 41.20 万，"
           f"后者日期更早却更高）→ 在裁清前**任何依赖库存的结论都不牢**；③ 39.2% 已是全场最高，"
           f"**向上空间被自身水平压缩**，这一注的赔率天然差。{SRC_EVT} {SRC_SCAN}"),

    "rm": ("down",
           f"ATM IV **16.3%** / HV₂₀ **20.0%** → **−3.7pp 折价**，全场最深；5dΔ −0.9pp。**机制**："
           f"新作平衡表边际转宽 —— 加拿大统计局上调 2026/27 菜籽产量 **+45 万吨至 2,205 万吨**、"
           f"库销比 **6.9% → 9%**（**10/13–10/19 窗内已兑现**）；沿海菜粕库存 2.46 万吨（环比 +44.7%）；"
           f"四季度**水产淡季** + 到港增加 ⇒ 需求端无冲击 ⇒ IV 向 HV 收敛。⚠️ **反方**：① **−3.7pp 折价本身"
           f"就是反向证据** —— 已实现波动高于隐含，均值回归的方向是 **IV 上行**，我这条是在赌折价继续扩大，"
           f"**与均值回归先验相反**；② 成本端硬读数仍在（ICE 高位 + 11 月船期 CNF 639 + 5.9% 反倾销税），"
           f"基差 **+96~+178 升水** = 现货紧张的最后一段，**随时可能剧烈修正**；③ 本地源**无 bin 级到港数据、"
           f"无加拿大天气更新**，空头侧只有机构预期、**无量化读数**，证据质量低于多头侧。{SRC_EVT} {SRC_SCAN}"),
}


def norm(s):
    s = (s or "").strip().replace("/", "-")
    p = s.split("-")
    if len(p) == 3 and all(x.isdigit() for x in p):
        return f"{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}"
    return None


def main() -> int:
    dry = "--dry-run" in sys.argv
    if os.path.exists(CAL_PATH):
        cal = set(open(CAL_PATH).read().split())
        assert norm(COMPARE) in cal, f"{COMPARE} 不是交易日"

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    assert raw.count("\r\n") == 0, "原文件有 CRLF"
    rows = list(csv.DictReader(io.StringIO(raw)))
    fieldnames = list(rows[0].keys())

    existing = [r for r in rows if norm(r["date"]) == norm(BATCH)]
    assert not existing, f"{BATCH} 已有 {len(existing)} 行，拒绝重复写入"
    assert len(COACH) == 10 and set(COACH) == set(ORDER), "教练列必须 10 品种齐全"

    for v, (p, t) in COACH.items():
        assert p in ("up", "down"), f"{v}: pred 必须 up/down，不做平"
        assert "⚠️" in t, f"{v}: 缺反方标记"
        assert "〔源：" in t, f"{v}: 缺来源"

    new = []
    for v in ORDER:
        p, t = COACH[v]
        new.append({
            "date": BATCH, "variety": v,
            "user_pred": "", "user_reason": "",
            "coach_pred": p, "coach_reason": t,
            "compare_date": COMPARE,
            "actual": "", "actual_delta_pp": "", "actual_reason": "",
            "actual_reason_coach": "", "user_correct": "", "coach_correct": "",
            "flag": "〔教练盲填 10/21 09:2x〕",
            "contract_pred": CONTRACT[v], "contract_compare": "", "cross_contract": "",
        })
    rows.extend(new)

    print(f"批次 {BATCH} → compare {COMPARE}（{'交易日 ✅' if os.path.exists(CAL_PATH) else '未核日历'}）")
    print(f"{'v':<4}{'合约':<9}{'pred':<6}理由长度")
    for v in ORDER:
        print(f"{v:<4}{CONTRACT[v]:<9}{COACH[v][0]:<6}{len(COACH[v][1])}")
    print(f"  → up {sum(1 for v in ORDER if COACH[v][0]=='up')} · "
          f"down {sum(1 for v in ORDER if COACH[v][0]=='down')}")

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

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        raw2 = f.read()
    rows2 = list(csv.DictReader(io.StringIO(raw2)))
    chk = [r for r in rows2 if norm(r["date"]) == norm(BATCH)]
    assert len(chk) == 10, f"回核行数 {len(chk)} != 10"
    assert all(not r["user_pred"].strip() for r in chk), "user 列被误写"
    assert all(r["coach_pred"].strip() for r in chk), "coach_pred 未填满"
    assert all(r["actual"].strip() == "" for r in chk), "actual 被误写"
    assert raw2.count("\r\n") == 0, "出现 CRLF"

    print(f"\n回核：行数 {len(rows)-10} → {len(rows2)}（+10）· CRLF 0 · "
          f"LF {raw.count(chr(10))} → {raw2.count(chr(10))}")
    print("      user 列仍空 10/10 · coach_pred 10/10 · actual 空 10/10")
    print(f"      备份 {bak}")
    print("\n▶ 教练列已盲填落盘。等她提交 user 列。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
