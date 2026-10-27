#!/usr/bin/env python3
"""append_pred_20261013.py

落 **2026/10/13 批**（compare_date 2026/10/20）的 IV 方向预测 10 行。

**本脚本只写教练列。** 依据 task-template:35 **教练盲填铁律（9/15 立）**：
scanner 跑完 → 教练**独立**写 `coach_pred` / `coach_reason` 落盘 → 她再提交她的。
本批**顺序正确**（她只贴了 scanner 输出、未提交 pred）→ **不标 〔非盲填〕**。
`user_pred` / `user_reason` 留空，待她提交后由第二个脚本填。

compare_date 依据（实测 10 个历史批次，规律 = 批次日 + 5 个交易日）：
    10/13(0) 10/14(1) 10/15(2) 10/16(3) 10/19(4) **10/20(5)**
    已用 `data/trade_calendar.txt` 实点核对（脚本内 assert）。

coach_reason 来源（依 9/28「先搜后写」：落盘前须检索事件源，标来源·窗内/窗外·可信度）：
  ① `scanner` 10/13 09:15 输出（IV / HV20 / 5dΔ / 倒挂结构）——她刚贴的实物
  ② `data/weekly_event_scan.json`（scan_date 2026-10-12 · valid_until 2026-10-19）
     —— 窗口 [10/13, 10/20] 的前 5 个交易日**完全落在其有效期内**，**未做额外搜索**
     （09:15-09:30 为决策窗口，按 CLAUDE.md 大 token 禁令不在盘中起搜）
  ⚠️ 该快照每条自带来源与可信度标注，本列**逐条转引该标注**，不新增未检索的事实。

用法：python3 tools/append_pred_20261013.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")
CAL_PATH = os.path.join(ROOT, "data", "trade_calendar.txt")

BATCH, COMPARE = "2026/10/13", "2026/10/20"
SRC_SCAN = "〔源：scanner 10/13 09:15〕"
SRC_EVT = "〔源：weekly_event_scan.json 10/12 快照 · 窗内 · 可信度中高〕"

ORDER = ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]

# ── 教练列（盲写，她提交前落盘）──────────────────────────────
COACH = {
    "au": ("down",
           f"IV 20.8%/HV20 13.9% → **+6.9pp** 偏高溢价；5dΔ −0.4pp 已在释放{SRC_SCAN}。"
           f"事件〔窗内〕压制项仍是 **10/8 的 10Y 美债约 5.23%**；避险项仍是 Hormuz"
           f"（10/6 仅 7 艘商船通过、7/23 以来最低；白宫被指要求五角大楼拟定对伊打击方案）"
           f"—— **双向尾部，与旧表同构**{SRC_EVT}。"
           f"**判：IV down** —— 10/12 批 au 实读 **−1.60pp** 说明窗内避险没有重启、压制项占上风；"
           f"+6.9pp 溢价无新增催化支撑。"
           f"⚠️ 反方：打击方案传闻仍在挂，**不等于事件已出清**，避险可随时重启；专题搜索未返回 10/12 后新的金价读数（单日快照不外推）。"),
    "m":  ("down",
           f"IV 14.6% ≈ HV20 14.5% → **+0.1pp 基本持平**；5dΔ +0.2pp（噪声内）{SRC_SCAN}。"
           f"事件〔窗内〕**无专项新增事实**；厄尔尼诺对南美大豆**净效应方向上不确定**（美洲系多数年份增产），"
           f"属「新增驱动弱化」而非强化{SRC_EVT}。主导项仍是「10–11 月收割完成、题材空窗至 12 月南美播种」"
           f"+ 11 月到港 980 万吨（同比 +170）。**今日 D-0 USDA 作物生长进度报告**。"
           f"**判：IV down** —— 持平/薄溢价态 + 无向上催化。"
           f"⚠️ 反方：**D-0 USDA 报告当日可造成单日 IV 冲击**；机构同判「远月强于近月」的 open 项未兑现，若兑现则远月 IV 抬升。"),
    "c":  ("down",
           f"IV **9.7% = 全批最低**，HV20 9.0% → 仅 +0.7pp 薄溢价；5dΔ +0.3pp（噪声内）{SRC_SCAN}。"
           f"事件〔窗内〕**东北新粮集中上市已兑现**（锦州港 15 水 2135-2140、较节前 −25）"
           f"—— 上市已推进数日而 IV 只微升 +0.3pp ⇒ **「上市冲击推 IV」这条逻辑未被数据支持**{SRC_EVT}。"
           f"**今日 D-0 USDA 作物生长进度报告**。"
           f"**判：IV down** —— 供应充裕 = 价格重心偏弱 = 低波动环境；季节性已知项市场早有定价。"
           f"⚠️ 反方：**IV 9.7% 已是全批地板，向下空间被测量噪声限制**（flat 带 0.25pp）；D-0 USDA 可造成单日上冲。"),
    "cf": ("down",
           f"IV 10.7%/HV20 12.4% → **−1.7pp 折价**；5dΔ −0.6pp{SRC_SCAN}。"
           f"事件〔窗内〕主导项仍是**下游断崖**（纺纱开机率 78%→69.2%、织布 42%→37.17%、「金九」旺季落空）；"
           f"10/12 实搜**未复搜到 cf 窗内新增事实**，厄尔尼诺对棉花**影响不确定**（机构列为弹性较小品种）{SRC_EVT}。"
           f"**今日 D-0 USDA 作物生长进度报告**。"
           f"**判：IV down** —— 需求端塌陷 + 折价态 + 5dΔ 下行惯性。"
           f"⚠️ 反方：cf 是 **Data 门卡点（52/60，全批最薄）**，样本噪声最大、本行 Δ 可追溯性弱于其他品种；折价态遇事件可反手修正向上。"),
    "sr": ("up",
           f"IV 12.0%/HV20 8.5% → **+3.6pp**；5dΔ +0.7pp；近 12.0% > 远 11.1% = **倒挂（法则①封卖方）**{SRC_SCAN}。"
           f"事件〔窗内〕**印度已禁止食糖出口**（厄尔尼诺专题唯一硬政策事实）；ICE 原糖假期**暴涨 +12.08%**（10/6 收 20.87 美分/磅、"
           f"近 19 个月新高）→ 外强内弱 = **跳空风险**，跳空恰推 IV 上行{SRC_EVT}。"
           f"**判：IV up** —— 外盘传导刚开始；机构提示「预期炒作 vs 减产兑现」须待 9–11 月验证，**本窗仍是预期项**。"
           f"⚠️ 反方：全国工业库存 **372 万吨 = 历史第二高**、北方糖厂已开榨、华泰提示终端采购不及旺季 → 内弱可兑现为**震荡而非跳空**，IV 反落；"
           f"且库存口径冲突（372 vs 222 万吨）**标存疑、不选边**。"),
    "ta": ("up",
           f"IV 31.4%/HV20 33.9% → **−2.5pp 折价**；5dΔ **−2.6pp（下行较快）**{SRC_SCAN}。"
           f"事件〔窗内·新增〕**飓风「伊萨亚斯」致墨西哥湾约 63%–72%（130–146 万桶/日）原油停产** = 供给端窗内新增收缩项；"
           f"霍尔木兹日均运输量降至 200 万桶以下（10/6 仅 7 艘商船，7/23 以来最低）；打击方案传闻（升级非降温）"
           f"⇒ **成本端方向由「退潮」翻成「未定」**{SRC_EVT}。**关键观察点：10/14 EIA 库存数据**。"
           f"**判：IV up** —— 折价 + 5dΔ 快速下行后可反手修正，成本端尾部一档。"
           f"⚠️ 反方：旧表「中东出口增量恢复 / G7-IEA 释放 1 亿桶」未复搜到推翻证据、**沿用** → 净方向仍可能退潮；"
           f"且振幅放大 ≠ 方向改变；**油价口径冲突（89.44-89.91 vs 91.5-91.85）标存疑、两者都不入判据**。"),
    "i":  ("down",
           f"IV 17.1%/HV20 13.4% → **+3.7pp**；5dΔ +0.7pp{SRC_SCAN}。"
           f"事件〔窗内〕**无 i 专项新增事实**；`真实风险` 维持 **false**（= 无未定价项）{SRC_EVT}。"
           f"主导项：Mysteel 61% 粉矿指数 90.55 美元/干吨创年内新低、94% 受访钢厂看跌节后、焦炭首轮提降落地。"
           f"**判：IV down** —— 方向偏空但已在盘面/机构预期内，无未定价催化，+3.7pp 溢价有回落空间。"
           f"⚠️ 反方：**单边下行趋势本身会推已实现波动率（HV）上行**，HV 追近 IV → 溢价收窄反而不利卖方；"
           f"且 i2701 期限结构须当日重取（9/29 记倒挂：近 17.5% > 远 16.2%）。"),
    "ru": ("up",
           f"IV 29.3%/HV20 24.0% → **+5.3pp**；5dΔ **+3.8pp = 全批最强上行惯性**{SRC_SCAN}。"
           f"事件〔窗内〕泰国胶水 **83 泰铢/公斤**（10/8 隆众，较旧表 9/24 的 80.0 续涨）+ "
           f"节中泰国部分地区洪灾扰动割胶{SRC_EVT}。"
           f"**判：IV up** —— 洪灾 = 窗内新增未定价项 + 原料续涨，看涨情绪推动、上行惯性未消。"
           f"⚠️ 反方：**厄尔尼诺对 ru 是 2027 年的故事、不是本窗的故事**（机构明写行情滞后峰值 3–6 个月、胶价高点甚至滞后 4–5 个季度）——"
           f"若把长周期叙事塞进 5 天窗，判据四问 A「变化性」不过关；"
           f"且中信 10/7「创近十年同期新高 + 泰国四季度季节性放量 → 警惕减产溢价修正」= 反向硬证据；原料价两来源冲突（83 vs 54.06）标存疑、不选边。"),
    "ma": ("up",
           f"IV **45.0% = 全批最高**，HV20 40.3% → **+4.7pp**；5dΔ +1.8pp；近 45.0% > 远 40.0% = **倒挂（法则①封卖方）**{SRC_SCAN}。"
           f"事件〔窗内·新增〕**10/8 前后美国财政部制裁 17 艘伊朗「影子船队」**（含运输伊朗原油/石化产品的个人与网络）；"
           f"霍尔木兹通行量降至 200 万桶以下 → **伊朗装港直接受制**；港口库存 **41.20 万吨 = 历史新低**{SRC_EVT}。"
           f"**判：IV up** —— ⚠️ **这是 9/28 判句「补偿 vs 错价」的正解所在：+溢价不是错价、是补偿**（真短缺），"
           f"补偿型溢价在 5 日窗内**不按均值回归走**（10/12 批 ma 实读 +5.29pp、9/28 批 ma 实读 up —— 我两次判 down 两次错）。"
           f"⚠️ 反方：**本行有「照上批结算拟合」的风险**——反转理由可以是「+4.7pp 溢价叠加 5dΔ 连续上行 → 均值回归压力 > 新增驱动」；"
           f"且「美伊谈判若实质进展 → 浮仓集中释放」可在很短时间内反转方向（本窗内**没有任何谈判进展的证据**）。"),
    "rm": ("down",
           f"IV 17.9% 处 HV20 18.5% 折价 **−0.6pp**；5dΔ −0.2pp{SRC_SCAN}。"
           f"事件〔窗内〕两头夹：偏多=加籽收割艰难（降雨+夜间低温压缩作业窗、品质下降）；"
           f"偏空=沿海油厂菜籽菜粕库存环比增加、开机率 35.18%、到港 58.5/52/44.5 万吨{SRC_EVT}。"
           f"**今日 D-0 USDA 作物生长进度报告**。"
           f"**判：IV down** —— 无单边驱动 + 折价态无向上催化，跟随豆粕偏弱运行。"
           f"⚠️ 反方：快照明记「成本端抬升 = **卖 P 的下行保护变弱** → 尾部风险上升一档」，可推 IV 上行；"
           f"且本条是**本次扫描覆盖最薄的一条**（三路搜索无一直接覆盖加拿大菜籽）= 明确的覆盖缺口、不是「无风险」。"),
}


def main():
    dry = "--dry-run" in sys.argv

    # compare_date 合法性核对（task-template ⑨b）
    if os.path.exists(CAL_PATH):
        cal = set(open(CAL_PATH).read().split())
        assert COMPARE.replace("/", "-") in cal, f"compare_date {COMPARE} 不在交易日历中"
        print(f"✅ compare_date {COMPARE} 在 data/trade_calendar.txt 内")

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    dup = [r["variety"] for r in rows if r.get("date") == BATCH]
    assert not dup, f"批次 {BATCH} 已存在行，拒绝重复追加：{dup}"
    assert set(COACH) == set(ORDER), "品种集合不一致"
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
        r["flag"] = "〔盲填✅〕教练列于用户提交前落盘（9/15 铁律顺序正确）"
        new.append(r)

    nu = sum(1 for r in new if r["coach_pred"] == "up")
    print(f"批次 {BATCH} → compare {COMPARE}：新增 {len(new)} 行（教练列，user 列留空）")
    for r in new:
        print(f'  {r["variety"]:<4} coach={r["coach_pred"]:<5} reason {len(r["coach_reason"])} 字')
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
    print(f"\n回核：行数 {len(rows)+1} → {len(rows2)+1}（+{len(rows2)-len(rows)}）")
    print(f"      LF {n_before[0]} → {b2.count(b'\n')} · CRLF {n_before[1]} → {b2.count(b'\r\n')}（须为 0）")
    print(f"      本批行数 {len(added)} · 列数 {len(rows2[0])}")
    print(f"      备份 {bak}")


if __name__ == "__main__":
    main()
