#!/usr/bin/env python3
"""append_pred_20261022.py

批次 2026/10/22 → compare 2026/10/29。**教练列盲填**（9/15 铁律）：
在她提交 user_pred / user_reason 之前落盘，只依据当天 scanner 输出 +
weekly_event_scan.json + iv_history.csv，不看她那一行。

⚠️ 本批两处口径警告（写进 reason，也写进 flag）：
  1. **ma / ta 今日换月**（ma2612→ma2701、ta2612→ta2701）。新 ref_contract
     ma2703 / ta2703 的 `ref_iv` **为空** → 倒挂闸拿到 None → 静默放行。
     ⇒ 今天 ma/ta 的「没有 ⚠️倒挂 标签」**不是倒挂已解，是测不出来**。
  2. ma 的 `5dΔ -2.3pp` **跨了换月**，含合约口径差 → **不入判据**。

用法：python3 tools/append_pred_20261022.py [--dry-run]
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

BATCH = "2026/10/22"
COMPARE = "2026/10/29"

SRC_SCAN = "〔源：scanner 10/22 09:33 实跑〕"
SRC_EVT = "〔源：weekly_event_scan.json · scan_date 2026-10-19 · valid_until 2026-10-26 · 可信度中高〕"

ORDER = ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]
CONTRACT = {
    "au": "au2612", "m": "m2701", "c": "c2701", "cf": "cf2701", "sr": "sr2701",
    "ta": "ta2701", "i": "i2701", "ru": "ru2701", "ma": "ma2701", "rm": "rm2701",
}

COACH = {
    "au": ("down",
           f"ATM IV **20.0%** / HV₂₀ **12.9%** → **+7.1pp 溢价**，全场最高；5dΔ −0.4pp。"
           f"**核心机制 = 时点**：compare 日 **2026/10/29 是 FOMC 的次日**（10/28 = D-0），"
           f"事件溢价在决议落地后**通常释放**，而不是继续累积。机构区间三家一致"
           f"（850–950 / 880–920 / 860–910）全部压在现价 900 附近 → 本身在说「没有方向驱动」"
           f"⇒ 事件前抬的那部分 IV 没有新东西托住。"
           f"⚠️ **反方（照反方强制先给）**：① **「FOMC 后 IV 必落」是先验不是读数** —— "
           f"若 10/28 决议超预期（点阵图/缩表路径），10/29 反而是 IV 继续上冲的第一天，"
           f"这条最可能死于事件本身而非机制；② +7.1pp 支持的是「绝对水平贵」，"
           f"**不直接支持「5 日后更便宜」**，这与我 9/28 批 au 的同类错只隔一步；"
           f"③ 10/29 若落在 FOMC 后第一个完整交易日，盘口常出现流动性重建期的 IV 假高。"
           f"{SRC_SCAN} {SRC_EVT}"),

    "m": ("up",
          f"ATM IV **12.7%** / HV₂₀ **14.4%** → **−1.7pp 折价**；5dΔ −0.1pp（几乎不动）。"
          f"**机制**：已实现波动高于隐含 ⇒ 均值回归的方向是 **IV 上行**。驱动侧确实偏空"
          f"（USDA 10 月上调单产至 53.10、期末库存 3.15 亿蒲、10/2 当周新作净销售环比 −46.85%、"
          f"四季度压榨上调），但**偏空解释的是价格方向，不是波动幅度**——"
          f"这正是 10/12 批的错因，我这次把它翻过来用。"
          f"⚠️ **反方**：① **反向套用风险（本条最大）**：折价也可能只是 HV 被某几根大阴线撑高，"
          f"并不预示 IV 上行，我是在用一个统计倾向赌一个基本面向下的品种；② 收割率仅 **25%**"
          f"（五年均值 33%）→ 晚收意味着天气暴露窗口更长，**这是波动率的上行源**，"
          f"但它落在本窗之外的概率更大；③ 本窗（10/22–10/29）有 **10/27 USDA 作物生长进度**，"
          f"单点数据可能一次性把 IV 推上去 —— 我的判断对，但**对的理由可能不是我写的这个**。"
          f"{SRC_EVT} {SRC_SCAN}"),

    "c": ("down",
          f"ATM IV **9.2%** / HV₂₀ **8.4%** → **+0.8pp**（落 1–3% 档下沿）；5dΔ **−0.0pp**，"
          f"全品种最平。**机制**：新季玉米上市高峰（辽宁上量、北港到货增、深加工压价、"
          f"华北集中上市）**在本窗仍在持续**，供应端是**日历上的确定事件**；"
          f"收储三路搜索**零命中** → 缺上行冲击源 ⇒ 低 IV 自我维持。"
          f"⚠️ **反方**：① **零命中 ≠ 无政策**（数据诚实第 3 条）—— 收储公告常在晚间突袭，"
          f"一旦落地 IV 立刻跳，这正是本品种最大的敞口；② 「季节性上量」每年都有，"
          f"按判据四问 A「变化性」**天然不过关**，我拿它当驱动是不合格的，"
          f"实际赌的是「没有新变化」；③ 9.2% 已是全场第二低，向下空间被自身水平压缩，"
          f"这一注赔率天然差。{SRC_EVT} {SRC_SCAN}"),

    "cf": ("down",
           f"ATM IV **10.1%** / HV₂₀ **12.4%** → **−2.3pp 折价**；5dΔ **−1.4pp**（全场降幅第二）。"
           f"**机制**：IV 已在下行通道里，而两边都缺冲击源 —— 供给充裕（公检 17 万吨同比 +4、"
           f"储备棉累计抛储超 40 万吨、商业库存高）＋ 需求转弱（10 月中旬起订单不足、"
           f"纺企随用随买）⇒ 折价继续扩大。**我赌的是动量延续，不是均值回归。**"
           f"⚠️ **反方**：① **−2.3pp 折价本身就是反向证据** —— 已实现高于隐含，"
           f"均值回归方向是 IV 上行，我这条与最常见的先验相反，**理由必须比先验更硬**，"
           f"而我拿出的只是「两边没冲击源」这种弱陈述；② **开机率口径冲突未裁清**"
           f"（70.1% 同比 +3.5pct vs 78%→69.2%），「需求疲软」这半条**证据不牢**；"
           f"③ cf 是 **Data 门最薄样本**，本条 Δ 的可追溯性弱于其他品种。{SRC_EVT} {SRC_SCAN}"),

    "sr": ("down",
           f"ATM IV **10.3%** / HV₂₀ **8.8%** → **+1.4pp**（1–3% 减半档）；5dΔ −0.2pp。"
           f"**机制**：底部由配额外巴西加工糖成本 **6,600** 托住、上方由新榨季增产预期压住 ⇒ "
           f"**区间收窄 ⇒ IV 天然易降**。进口断崖（9 月到港 9.14 万吨、同比 −28.24）解释的是"
           f"「为什么不跌」，**不解释「波动变大」**。"
           f"⚠️ **反方**：① **南方甘蔗 10 月中下旬开榨 = 本窗唯一硬信息源**，"
           f"开榨进度一旦慢于预期，区间立刻重新打开，这条直接死在进度数据上；"
           f"② 「供应偏紧」（进口口径）与「工业库存 372 万吨 = 历史第二高」（库存口径）"
           f"**同源互斥**，我取了前者来解释低波动，可能取错了那一半；③ 厄尔尼诺 Niño3.4 "
           f"**+2.3℃** 仍在，机构明写行情滞后峰值 3–6 个月 → **本窗不该用它**，"
           f"我列出来只为说明已被排除。{SRC_EVT} {SRC_SCAN}"),

    "ta": ("up",
           f"ATM IV **29.0%** / HV₂₀ **31.6%** → **−2.6pp 折价**；5dΔ −0.4pp。"
           f"**机制**：成本端由「退潮」翻成「加剧波动」—— 10/17 两艘超级油轮霍尔木兹触雷、"
           f"10/19 又一艘起火，UKMTO 一周接报 12 起，海峡通行量减少约 **300 万桶/日**；"
           f"布油 10/16 收 **109.86**（5/19 以来最高）。**折价 + 尾部风险升 = IV 有上修空间。**"
           f"⚠️ **反方**：① **最大的事实是反向的** —— ta 的 IV 从 10/9 的 34.05% 跌到 10/16 的 "
           f"28.34%（**−5.71pp**），**而同期布油在涨** → **IV 与标的方向背离且无本地解释**，"
           f"在这个背离被证伪前，「IV 会跟着油价涨」是**推的**；② 「11/3 前不打伊朗」是"
           f"美方单方表态，**不等于伊朗不出手**；③ 飓风停产已回落至约 25% 海上产量 = "
           f"供给在回补，这是**明确的利多出尽项**。"
           f"⚙️ **换月提示**：ta 今日 ta2612→**ta2701**，新 ref ta2703 的 `ref_iv` 为空 → "
           f"**倒挂状态本日测不出**，本条不含倒挂判据。{SRC_EVT} {SRC_SCAN}"),

    "i": ("down",
           f"ATM IV **16.6%** / HV₂₀ **14.1%** → **+2.4pp 溢价**，5dΔ **+0.7pp**（全场唯一明显抬升）。"
           f"**机制**：溢价在扩大而基本面在走弱 —— 45 港库存 **16,534.67 万吨（环比 +54.45）**、"
           f"247 家钢厂日均铁水 **233.66 万吨（同比 −7.29）** ⇒ 供需双弱、库存累积已发生 ⇒ "
           f"价格单向慢压 ⇒ HV 走低 ⇒ **IV 从溢价位回落**。5dΔ +0.7 是「已发生的抬升」，"
           f"没有新东西托住它。"
           f"⚠️ **反方**：① **反向套用风险（本条最大）**：10/12 批的错因正是「方向偏空 = 低波动」"
           f"—— 方向与波动率不是一回事，库存累积若走成**急跌**，HV 会飙升，我这条会反向错；"
           f"② 铁水环比仅 −0.18 万吨（≈0.08%）、库存 +0.33%，**都是小幅**，按判据四问 A"
           f"「变化性」堪忧 —— 我实际在赌「没有新变化」；③ compare 日本身在 FOMC 名单里"
           f"（10/28 D-0），宏观驱动可能把整个板块的波动抬起来，盖掉我的品种机制。"
           f"{SRC_EVT} {SRC_SCAN}"),

    "ru": ("up",
           f"ATM IV **24.7%** / HV₂₀ **24.1%** → **+0.7pp 贴零**；5dΔ **+0.0pp**，全品种最平。"
           f"**机制**：IV 与 HV 已经贴在一起 = **没有溢价可回吐，也没有折价要补**，"
           f"此时方向由**供给侧的日历事件**定 —— 泰国雨季尾声扰动仍在、**国内临近停割**、"
           f"新仓单同比减少明显 ⇒ 供给收缩意味着价格跳跃概率上升 ⇒ IV 从贴零位向上。"
           f"⚠️ **反方**：① **「临近停割」是季节性、每年都有**，按判据四问 A「变化性」"
           f"**天然不过关** —— 这正是 9/28 批 ru 的原错因，我可能是在重复它；"
           f"② 需求端 10 月中旬已转偏弱（轮胎需求弱、宏观风险偏好降），**供需两边拉扯，"
           f"IV 未必单向**；③ 泰国胶水即时报价**本窗未取到**（只有「原料价格坚挺」的定性），"
           f"停割论断的**量化底座缺失**。{SRC_EVT} {SRC_SCAN}"),

    "ma": ("up",
           f"ATM IV **36.0%** / HV₂₀ **34.2%** → **+1.8pp**（1–3% 减半档）。**机制**："
           f"沿海库存 **37.41 万吨（截至 10/8，同比 −74.98%）**、可流通货源仅约 **10.5 万吨** ⇒ "
           f"**低库存 + 低可流通 = 价格弹性极大** ⇒ 小资金即可推动大波动 ⇒ IV 在高位不下来。"
           f"🔴 **本条不使用 5dΔ**：今日 ma 合约 **ma2612→ma2701 换月**，scanner 报的 "
           f"`5dΔ −2.3pp` **跨了合约**，是口径差不是行情 —— 拿它当动量会得出反向结论。"
           f"⚠️ **反方**：① **10/9–10/25 到港预估 20.05–21 万吨** —— 若如期到达，"
           f"「低库存」这个前提**在本窗内被自己拆掉**；② 库存两读**互斥**（37.41 万 vs 41.20 万，"
           f"后者日期更早却更高）→ 裁清前**任何依赖库存的结论都不牢**；"
           f"③ 36.0% 已是全场最高，**向上空间被自身水平压缩**，这一注赔率天然差。"
           f"⚙️ **换月提示**：新 ref ma2703 的 `ref_iv` **为空** → **倒挂状态本日测不出**，"
           f"EXEC 行没有 ⚠️倒挂 标签 **不代表倒挂已解**。{SRC_EVT} {SRC_SCAN}"),

    "rm": ("up",
           f"ATM IV **16.5%** / HV₂₀ **19.9%** → **−3.4pp 折价**，全场第二深；5dΔ −0.4pp。"
           f"**机制**：已实现波动显著高于隐含 ⇒ 均值回归方向是 **IV 上行**。"
           f"成本端硬读数仍在（ICE 高位 + 11 月船期 CNF **639** + **5.9% 反倾销税**），"
           f"基差 **+96~+178 升水** = 现货紧张的最后一段 ⇒ **随时可能剧烈修正**，"
           f"而折价说明市场还没为这个可能性定价。"
           f"⚠️ **反方**：① 新作平衡表边际转宽是**确凿的空头证据** —— 加拿大统计局上调 "
           f"2026/27 菜籽产量 **+45 万吨至 2,205 万吨**、库销比 **6.9% → 9%**，"
           f"方向与我的判断相反；② 四季度**水产淡季** + 到港增加，需求端确实无冲击，"
           f"「均值回归」可能只是一个统计倾向而非机制；③ 本地源**无 bin 级到港数据、"
           f"无加拿大天气更新**，两侧证据质量都不高。{SRC_EVT} {SRC_SCAN}"),
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
            "flag": "〔教练盲填 10/22 09:4x〕〔⚠️ma/ta 换月·ref_iv 空·倒挂不可测〕",
            "contract_pred": CONTRACT[v], "contract_compare": "", "cross_contract": "",
        })
    rows.extend(new)

    print(f"批次 {BATCH} → compare {COMPARE}（交易日 ✅）")
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
