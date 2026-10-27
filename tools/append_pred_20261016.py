#!/usr/bin/env python3
"""append_pred_20261016.py

落 **2026/10/16 批**（compare_date 2026/10/23）的 IV 方向预测 10 行。

**本脚本只写教练列。** 依据 task-template:35 **教练盲填铁律（9/15 立）**：
scanner 跑完 → 教练**独立**写 `coach_pred` / `coach_reason` 落盘 → 她再提交她的。
本批**顺序正确**（她只贴了 scanner 输出、未提交 pred）→ **不标 〔非盲填〕**。

⚠️ **本批数据来之不易**：今天 09:15 采集被一个 18 小时僵尸进程堵掉（launchd 单实例语义
   下，"上一实例未退出 → 后续所有 StartCalendarInterval 静默跳过"），教练 09:27 杀掉僵尸体、
   09:30 主采正常落盘。**09:21 那份 scanner 输出用的是 10-15 旧数据（表尾 @10-15 09:30），已作废**，
   本脚本依据的是重跑后的 **@10-16 09:30** 输出。

compare_date 依据（实测历史批次，规律 = 批次日 + 5 个交易日）：
    10/16(0) 10/19(1) 10/20(2) 10/21(3) 10/22(4) **10/23(5)**
    已用 `data/trade_calendar.txt` 实点核对（脚本内 assert）。

窗口 = **[10/17, 10/23]**（窗口起点 = 批次日 + 1）。窗内交易日 = 10/19 · 10/20 · 10/21 ·
10/22 · 10/23（**5 个**）；窗内非交易日 = 10/17 · 10/18（周末）。

coach_reason 来源（依 9/28「先搜后写」：落盘前须检索事件源，标来源·窗内/窗外·可信度）：
  ① `scanner` **10/16 09:30** 输出（IV / HV₂₀ / IV−HV / 5dΔ / 期限结构 / 趋势）—— 实物
  ② `data/weekly_event_scan.json`（scan_date 2026-10-12 · valid_until **2026-10-19**）
     —— ⚠️ **只覆盖窗口首日 10/19**，10/20–10/23 **落在其有效期外** →
     该快照对本批 **主要是「前窗基线」**，不是窗内新料。已在逐条行文中标明。
  ⚠️ 09:15–09:30 为决策窗口 + 9:00-18:00 大 token 禁令 → **未起当日网络搜索**。
     本列证据上限 = 上述两个本地源，**不冒充「已独立核实」**。

用法：python3 tools/append_pred_20261016.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
CAL_PATH = os.path.join(ROOT, "data", "trade_calendar.txt")

BATCH, COMPARE = "2026/10/16", "2026/10/23"
SRC_SCAN = "〔源：scanner 10/16 09:30 实跑〕"
SRC_EVT = "〔源：weekly_event_scan.json 10/12 快照 · valid_until 10/19 · **对本窗主要是前窗基线** · 可信度中高〕"
SRC_EVT_MID = "〔源：weekly_event_scan.json 10/12 快照 · 可信度中〕"

ORDER = ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]

# ── 主采合约（09:30 实读，同时写入 contract_pred 列）──────────────
CONTRACT = {
    "au": "au2612", "m": "m2701", "c": "c2701", "cf": "cf2701", "sr": "sr2701",
    "ta": "ta2701", "i": "i2701", "ru": "ru2701", "ma": "ma2612", "rm": "rm2701",
}

# ── 教练列（盲写，她提交前落盘）──────────────────────────────
# 统一判据（本批首次明写，防「照上批结算拟合」）：
#   溢价 (IV>HV) + 窗内无新增催化 → IV down（溢价释放）
#   折价 (IV<HV) + 窗内无新增催化 → IV up  （折价收敛 / HV 拉动）
#   窗内有新增催化 → 沿催化方向
# 冲突时在行内写明走哪一侧，并标出被压低的那一侧。
COACH = {
    "au": ("down",
           f"IV **20.4%** / HV₂₀ 13.9% → **+6.5pp 溢价**（全批最高溢价）；5dΔ **−0.2pp**（溢价几乎未释放）{SRC_SCAN}。"
           f"事件：**FOMC 是 D-12（10/28）** → **落在本窗 [10/17,10/23] 之外**，构不成窗内新料；"
           f"压制项 **10/8 10 年期美债约 5.23%**、避险项 Hormuz（10/6 仅 7 艘商船通过）"
           f"**均为窗内既有状态、非窗内新增**{SRC_EVT}。"
           f"**判：IV down** —— 走「溢价 + 无窗内新增催化」一侧。"
           f"⚠️ 反方：**+6.5pp 溢价已挂了多个交易日未释放**（5dΔ 仅 −0.2pp），说明有承接；"
           f"白宫被指仍要求五角大楼拟定对伊打击方案 → **避险可随时重启**，那样 IV 会先跳。"
           f"另注：au 已连续两批实际 down（10/12 批 −1.60pp、9/29 批 −2.27pp）—— **本行有「照结算拟合」风险，故理由写机制不写历史**。"),

    "m":  ("up",
           f"IV **13.2%** / HV₂₀ 14.6% → **−1.4pp 折价**；5dΔ **−1.1pp**（IV 在掉、HV 没跟）{SRC_SCAN}。"
           f"⚠️ **参考月 m2705 盘口失真（`ref_liquidity_ok=0`、`ref_iv` 空）→ 期限结构本行不判定**。"
           f"事件：**未复搜到 m 窗内专项新增事实**；厄尔尼诺对南美大豆**净效应方向不确定**（美洲系多数年份增产）"
           f"→ 属「新增驱动弱化」而非强化{SRC_EVT_MID}。主导项仍是「10–11 月收割完成、题材空窗至 12 月南美播种」。"
           f"**判：IV up** —— 走「折价 + 无窗内新增压制」一侧：IV 低于已实现，收敛压力向上。"
           f"⚠️ 反方：**本行是对前两批的翻转**（9/29 批实际 +0.40pp、10/12 批 **+0.62pp**，两次我都判 down、两次都错）"
           f"→ **有「输了就翻面」的嫌疑**，必须靠机制而非结果站住：折价 −1.4pp 是当下实读，不是从结算倒推。"
           f"另一侧：题材空窗若持续，IV 会沿阴跌惯性继续走低。"),

    "c":  ("down",
           f"IV **9.5% = 全批最低**，HV₂₀ 8.9% → 仅 **+0.6pp 薄溢价**；5dΔ −0.4pp{SRC_SCAN}。"
           f"⚠️ 近 c2701 9.48% > 远 c2703 8.24% = **倒挂（法则①封卖方）**。"
           f"事件：**东北新粮集中上市**（锦州港 15 水 2135-2140、较节前 −25）**属窗内既有、非本窗新增**；"
           f"**未复搜到 2026 年 10 月新增的收储/政策公告**，一号文件是 **2 月（窗外）**"
           f"→ 旧表「中储粮高频采购 + 秋粮会议定调」**未被复搜证实、也未被推翻**{SRC_EVT_MID}。"
           f"**判：IV down** —— 溢价侧 + 上市持续压制，两侧同向。"
           f"⚠️ 反方：**c 的 IV 已是全批最低（9.5%），向下空间本来就小** —— 「down」很可能落在 flat 带（|Δ|<0.25pp）里；"
           f"且上市进程本身伴随价格波动，若跌幅加大则 HV 抬升、IV 会被顶上去。"),

    "cf": ("up",
           f"IV **10.6%** / HV₂₀ 12.7% → **−2.0pp 折价**；5dΔ **+0.2pp**（唯一 5dΔ 为正的品种）{SRC_SCAN}。"
           f"⚠️ 近 cf2701 10.63% > 远 cf2703 9.84% = **倒挂（法则①封卖方）**。"
           f"事件：**未复搜到 cf 窗内专项新增事实**；窗内主导项仍是旧表的下游断崖"
           f"（纺纱开机率 78%→69.2%、织布 42%→37.17%、「金九」旺季落空）**已定价数日**{SRC_EVT_MID}。"
           f"**判：IV up** —— 走「折价 + 无窗内新增压制」一侧。"
           f"⚠️ 反方：**cf 是 Data 门卡点（样本最薄）** → 本行任何 Δ 的可追溯性弱于其他品种；"
           f"且 9/29 批 cf 实际 **−2.05pp（down）**、我当时判 down 且对 —— **同一个折价结构下 IV 照样能往下走**，"
           f"故「折价→收敛」这条在 cf 上并非稳的。"),

    "sr": ("down",
           f"IV **10.4%** / HV₂₀ 9.4% → **+1.0pp 溢价**；5dΔ **−0.8pp**（在释放）{SRC_SCAN}。"
           f"⚠️ 近 sr2701 10.39% > 远 sr2703 9.80% = **倒挂（法则①封卖方）**。"
           f"事件：**印度已禁止食糖出口**（窗内政策事实）；ICE 原糖假期暴涨 +12.08% → **均已兑现、非本窗新增**{SRC_EVT_MID}。"
           f"快照自己给的硬反方仍挂着：全国工业库存 372 万吨 = 历史第二高、北方糖厂已开榨。"
           f"**判：IV down** —— 溢价 + 已兑现外盘项降温，走溢价释放一侧。"
           f"⚠️ 反方：**机构明写「行情滞后于峰值 3–6 个月」** → 外盘冲击的**二次传导可能还没走完**，IV 可再上一档；"
           f"且 9/29 批 sr 实际 **+1.81pp（up）**、10/12 批 **+0.87pp（up）** —— **sr 连续两批 up，本行有逆势嫌疑**。"),

    "ta": ("up",
           f"IV **28.3%** / HV₂₀ 32.3% → **−4.0pp 折价 = 全批最大折价**；5dΔ **−2.3pp**；期货 5 日 **−5.0%**{SRC_SCAN}。"
           f"⚠️ ref ta2612（近月）28.33% ≈ main ta2701 28.34% → **基本持平、不倒挂**。"
           f"事件〔**唯一一条真正落在窗内的新增项**〕：**飓风「伊萨亚斯」致墨西哥湾约 63%–72% 原油产量停产** + "
           f"霍尔木兹日均运输量降至 200 万桶以下、**白宫被指仍要求五角大楼拟定对伊打击方案**"
           f"→ **成本端上行尾部仍在**{SRC_EVT}。"
           f"**判：IV up** —— 折价 + 成本端上行尾部，两侧同向。"
           f"⚠️ 反方：**ta 的 5 日 −5.0% 是价格单边下行**，若延续则成本端逻辑弱化、ta 可能转为「价跌 IV 也跌」；"
           f"且快照自带 WTI 口径冲突（89.44-89.91 vs 91.5-91.85，**标存疑、不选边**）→ 成本端方向证据本身不牢。"),

    "i":  ("up",
           f"IV **16.7%** / HV₂₀ 13.7% → **+3.0pp 溢价**；5dΔ −0.1pp；期货 5 日 **−1.61%（📉单边下跌）**{SRC_SCAN}。"
           f"⚠️ **本行两侧打架，明写走哪一侧**：溢价侧说 down、趋势侧说 up。"
           f"**取趋势侧**，理由 = **9/29 批 i 的教训已写进 `mistakes`**：「单边下行趋势本身会推已实现波动率（HV）上行，"
           f"单边跌本身就在制造波动」—— 那次我按「方向偏空 → 低波动」判 down，实际 **+0.83pp（up）**，判错。"
           f"⚠️ 近 i2612 **16.07%** < 远 i2701 **16.68%** = **正常结构、不倒挂**（今日 EXEC 行已无法则①黄标）。"
           f"事件：**未复搜到 i 窗内新增事实**；`真实风险` 维持 false；主导项仍是 61% 粉矿 90.55 美元/干吨创年内新低{SRC_EVT}。"
           f"⚠️ 反方（最强的一条，必须写在明处）：**溢价 +3.0pp 是当下实读，而 5 日跌幅 −1.61% 明显弱于 10/13 批的 −4.06%** "
           f"→ 「跌幅够不够制造波动」存疑；若趋势只是温和阴跌，溢价会照常释放 → **本行可能是把上一批的教训过度外推**，"
           f"即我自己批评过的「照上批结算拟合」的镜像版本。"),

    "ru": ("down",
           f"IV **27.5%** / HV₂₀ 24.2% → **+3.3pp 溢价**；5dΔ **−1.1pp**（在释放）{SRC_SCAN}。"
           f"⚠️ 近 ru2701 27.51% > 远 ru2705 24.62% = **倒挂（法则①封卖方）**。"
           f"事件：**未复搜到 ru 窗内新增供给冲击**；已兑现项（泰国胶水 83 泰铢/公斤、节中洪灾扰动割胶）**非窗内新增**{SRC_EVT_MID}。"
           f"**判：IV down** —— 溢价 + 无窗内新增。"
           f"⚠️ 反方两条：① **中信 10/7「胶价创近十年同期新高 + 泰国四季度季节性放量 → 警惕减产溢价修正」是反向硬证据**，"
           f"本行方向与它相反（我押溢价回归、它说溢价该修 —— 方向其实同侧，但**它给的触发是「季节性放量」= 供给恢复 → 价格跌 → HV 升**，那会把 IV 顶上去）；"
           f"② 9/29 批 ru 实际 **+7.36pp（全批最大涨幅，up）**、10/12 批 **+5.53pp（最大，up）** —— "
           f"**ru 连续两批大涨，本行是明确逆势**；快照明写「厄尔尼诺对 ru 是 2027 年的故事、不是本窗的故事」，"
           f"我**不用长周期叙事站台**（判据四问 A 过不了），但同样**不能因为它是长周期就断言本窗无驱动**。"),

    "ma": ("up",
           f"IV **38.9% = 全批最高**，HV₂₀ 41.0% → **−2.1pp 折价**；5dΔ **−3.9pp（全批最大跌幅）**{SRC_SCAN}。"
           f"⚠️ 近 ma2612 38.90% > 远 ma2701 34.02% = **倒挂（法则①封卖方）**。"
           f"事件：**10/8 前后美财政部制裁 17 艘伊朗「影子船队」** + 霍尔木兹通行量降至 200 万桶以下"
           f"→ **供给缺口被两个既有事实加固**；港口库存 41.20 万吨 = 历史新低{SRC_EVT}。"
           f"**判：IV up** —— **这是 9/28 判句「补偿 vs 错价」的正解所在：溢价不是错价、是补偿**"
           f"（真短缺），补偿型溢价在 5 日窗内**不按均值回归走**。"
           f"📌 **写进本行的方法论**：我 9/28 判 ma down（实际 +5.29pp）、9/29 判 ma down（实际 +7.09pp）**两次都错、两次同一个错**——"
           f"把 supply 型短缺的溢价当成均值回归对象。**本行是第三次，改判 up 是在改机制不是改结果。**"
           f"⚠️ 反方：① **5dΔ −3.9pp 是实读** —— IV 已经在大幅回落，若这个回落是趋势而非噪声，up 就判反了"
           f"② 「美伊谈判实质进展 → 浮仓集中释放」可短时间反转，本窗内**没有谈判进展的证据，但也没有证据说不会有**"
           f"③ **本行是「输了两次以后翻面」的典型嫌疑**，唯一能站住的是机制（补偿型溢价 + 2.1pp 折价），不是历史战绩。"),

    "rm": ("up",
           f"IV **17.4%** / HV₂₀ 19.4% → **−2.1pp 折价**；5dΔ −0.6pp{SRC_SCAN}。"
           f"⚠️ 近 rm2701 17.35% > 远 rm2703 15.79% = **倒挂（法则①封卖方）**。"
           f"事件：**未复搜到 rm 窗内新增事实**，且本条是快照自认的**「本次扫描覆盖最薄的一条」**"
           f"（三路搜索无一直接覆盖加拿大菜籽）= **覆盖缺口，不是「无风险」**{SRC_EVT_MID}。"
           f"**判：IV up** —— 折价 + 无窗内新增压制；与 m 同向（菜系联动）。"
           f"⚠️ 反方：① **9/29 批 rm 实际 +1.80pp（up）、我判 down 判错**；但 9/28 批我判 down 是对的"
           f"→ **样本两边都有，方向依据弱** ② 快照自带「成本端抬升 = 卖 P 的下行保护变弱 → 尾部风险上升一档」"
           f"**仍未兑现**，若兑现则 IV 再上一档（**与本行同向，但不构成支撑**——未兑现项不能当理由）"
           f"③ **覆盖最薄 = 我此刻对 rm 的了解最少**，本行的证据强度全批最低。"),
}


def main():
    dry = "--dry-run" in sys.argv

    if os.path.exists(CAL_PATH):
        cal = set(open(CAL_PATH).read().split())
        assert COMPARE.replace("/", "-") in cal, f"compare_date {COMPARE} 不在交易日历中"
        print(f"✅ compare_date {COMPARE} 在 data/trade_calendar.txt 内")

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    dup = [r["variety"] for r in rows if r.get("date") == BATCH]
    assert not dup, f"批次 {BATCH} 已存在行，拒绝重复追加：{dup}"
    assert set(COACH) == set(ORDER) == set(CONTRACT), "品种集合不一致"
    for v, (p, t) in COACH.items():
        assert p in ("up", "down"), f"{v}: pred 非法 {p}"
        assert t.count("⚠️") >= 1, f"{v}: 缺反方"

    new = []
    for v in ORDER:
        r = {k: "" for k in fieldnames}
        r["date"] = BATCH
        r["variety"] = v
        r["coach_pred"] = COACH[v][0]
        r["coach_reason"] = COACH[v][1]
        r["compare_date"] = COMPARE
        r["contract_pred"] = CONTRACT[v]
        r["flag"] = "〔盲填✅〕教练列于用户提交前落盘（9/15 铁律顺序正确）"
        new.append(r)

    nu = sum(1 for r in new if r["coach_pred"] == "up")
    print(f"批次 {BATCH} → compare {COMPARE}：新增 {len(new)} 行（教练列，user 列留空）")
    for r in new:
        print(f'  {r["variety"]:<4} {r["contract_pred"]:<7} coach={r["coach_pred"]:<5} reason {len(r["coach_reason"])} 字')
    print(f"\n教练 up 计数：{nu}/10 · down {10-nu}/10")

    if dry:
        print("\n--dry-run：未落盘。")
        return

    b = open(CSV_PATH, "rb").read()
    n_before = (b.count(b"\n"), b.count(b"\r\n"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)
    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows + new)
    os.replace(tmp, CSV_PATH)

    # ── 回核 ────────────────────────────────────────────────
    b2 = open(CSV_PATH, "rb").read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows2 = list(csv.DictReader(f))
    added = [r for r in rows2 if r.get("date") == BATCH]
    assert len(rows2) == len(rows) + 10, "行数异常，拒绝"
    assert all(r.get("user_pred") == "" for r in added), "user 列被误写"
    assert all(r.get("actual") == "" for r in added), "actual 被误写"
    assert all(r.get("contract_pred") for r in added), "contract_pred 缺失"
    print(f"\n回核：行数 {len(rows)} → {len(rows2)}（+{len(rows2)-len(rows)}）")
    print(f"      本批 {len(added)} 行 · 列数 {len(rows2[0])} · user 列仍空 {sum(1 for r in added if not r['user_pred'])}/10")
    print(f"      LF {n_before[0]} → {b2.count(b'\n')} · CRLF {n_before[1]} → {b2.count(b'\r\n')}（须为 0）")
    print(f"      备份 {bak}")
    print("\n▶ 教练列已落盘。**正文不在此回显** —— 等你提交 user 列后，两侧同时亮出。")


if __name__ == "__main__":
    main()
