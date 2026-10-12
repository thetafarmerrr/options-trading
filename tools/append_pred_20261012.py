#!/usr/bin/env python3
"""append_pred_20261012.py

落 **2026/10/12 批**（compare_date 2026/10/19）的 IV 方向预测 10 行。

**本脚本只写教练列。** 依据 task-template:35 **教练盲填铁律（9/15 立）**：
scanner 跑完 → 教练**独立**写 `coach_pred` / `coach_reason` 落盘 → 她再提交她的。
本批**顺序正确**（她只贴了 scanner 输出、未提交 pred）→ **不标 〔非盲填〕**。
`user_pred` / `user_reason` 留空，待她提交后由第二个脚本填。

compare_date 依据（实测 9 个历史批次，规律 = 批次日 + 5 个交易日）：
    9/28→10/12 · 9/29→10/13 · 9/30→10/14
    10/12(0) 10/13(1) 10/14(2) 10/15(3) 10/16(4) **10/19(5)**
    已用 `data/trade_calendar.txt`（末行 2026-12-31，8797 行）实点核对。

coach_reason 来源（依 9/28「先搜后写」：落盘前须检索事件源，标来源·窗内/窗外·可信度）：
  ① `scanner` 10/12 09:15 输出（IV / HV20 / 5dΔ / 倒挂结构）——她刚贴的实物
  ② `data/weekly_event_scan.json`（scan_date 2026-10-08 · valid_until 2026-10-16）
     —— 窗口 [10/12, 10/19] **完全落在其有效期内**，**未做额外搜索**（09:15-09:30
     为决策窗口，按 CLAUDE.md 大 token 禁令不在盘中起搜）
  ⚠️ 该快照每条自带「来源：国庆假期复盘多家机构 · 窗内 · 可信度中高」，
     本列**逐条转引该标注**，不新增未检索的事实。

用法：python3 tools/append_pred_20261012.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")

BATCH, COMPARE = "2026/10/12", "2026/10/19"
SRC_SCAN = "〔源：scanner 10/12 09:15〕"
SRC_EVT = "〔源：weekly_event_scan.json 10/8 快照 · 窗内 · 可信度中高〕"

ORDER = ["au", "m", "c", "cf", "sr", "ta", "i", "ru", "ma", "rm"]

# ── 教练列（盲写，她提交前落盘）──────────────────────────────
COACH = {
    "au": ("down",
           f"IV 21.2%/HV20 13.9% → **+7.2pp** 全批第二高溢价（仅次于 ma）；5dΔ −0.9pp 已在释放{SRC_SCAN}。"
           f"事件〔窗内·10/3-10/7〕Hormuz 升级（10/7 革命卫队顾问称海峡「关闭状态」）+ 10Y 美债 5.27-5.35%（2002 以来最高）；"
           f"压制源由「点阵图偏鹰」换成「美债利率」→ 真实风险 true、概率中{SRC_EVT}。"
           f"**判：IV down** —— 节后补定价 10/8-10/9 两日已完成，金价 10/7 已跳水 −2%（4,179.82→约 4,115.95），恐慌高点释放；"
           f"+7.2pp 溢价无新增催化支撑。"
           f"⚠️ 反方：Hormuz 未解，避险可随时重启；连休 7 天累积的跳空风险对卖方是尾部。"),
    "m":  ("down",
           f"IV 14.0% 处 HV20 14.8% 折价 **−0.8pp**；5dΔ −0.4pp{SRC_SCAN}。"
           f"事件〔窗内〕矛盾双向：偏多=美豆产区偏干/压榨高于预估/中国采购预期 + 榨利深亏（−399/−331 元/吨）挺价；"
           f"偏空=11 月到港 980 万吨（同比 +170）+ 中美降税框架向好{SRC_EVT}。"
           f"**判：IV down** —— 10-11 月美豆收割完成，机构自判「天气题材阶段性告一段落」，题材空窗至 12 月南美播种；"
           f"折价态无向上催化。"
           f"⚠️ 反方：机构同判「远月强于近月、12 月起买船缺口预期」→ 远月可能提前给波动率，折价可被反手修正。"),
    "c":  ("up",
           f"IV 9.7% = **全批最低**，HV20 8.8% → +0.9pp 薄溢价；5dΔ +0.1pp{SRC_SCAN}。"
           f"事件〔窗内〕**国庆期间东北新粮已集中上市**——锦州港 15 水 2135-2140（较节前 −25）、北方港口假期跌 20-30 元/吨、"
           f"产地深加工门前上量价跌 20-90 元/吨{SRC_EVT}。"
           f"**判：IV up** —— 旧表判「窗口内无东北上量变量」**已被证伪**，变量刚刚兑现、实际波动正在发生；"
           f"而 IV 处全批地板（9.7%），向下空间被测量噪声限制。"
           f"⚠️ 反方：上市冲击是**季节性已知项**，市场早有预期 → 可能反而兑现为「利空出尽、IV 回落」。"),
    "cf": ("down",
           f"IV 10.7%/HV20 12.3% → **−1.6pp 折价**；5dΔ **−1.9pp = 全批最大下行**{SRC_SCAN}。"
           f"事件〔窗内〕下游开机率断崖——纺纱 78%→69.2%、织布 42%→37.17%（均年内低位）、「金九」旺季落空；"
           f"成本倒挂 300-400 元/吨（折皮棉成本 16,100-16,700 vs 区间 15,500-16,300）{SRC_EVT}。"
           f"**判：IV down** —— 需求端塌陷 = 价格重心偏弱 = 低波动环境；IV 已折价且 5dΔ 大幅下行，惯性未消。"
           f"⚠️ 反方：cf 是 **Data 门卡点（52/60，全批最薄）**，IV 数据点最少、样本噪声最大，本行的 Δ 可追溯性弱于其他品种。"),
    "sr": ("up",
           f"IV 11.8%/HV20 8.4% → **+3.3pp**；5dΔ +0.1pp；近 11.8% > 远 11.6% = **倒挂（法则①封卖方）**{SRC_SCAN}。"
           f"事件〔窗内〕ICE 原糖假期**暴涨 +12.08%**（10/6 收 20.87 美分/磅、近 19 个月新高）；"
           f"配额外巴西进口加工糖成本约 **6600 元/吨** vs 郑糖 5354 → 节后高开概率大；五矿/国泰君安/兴业同向{SRC_EVT}。"
           f"**判：IV up** —— 外强内弱 = **跳空风险**（非趋势风险），跳空恰恰推 IV 上行；溢价虽已 +3.3pp，外盘传导刚开始。"
           f"⚠️ 反方（快照自带）：全国工业库存 372 万吨 = 历史第二高、北方糖厂已开榨、华泰提示终端采购不及旺季 → 内弱可兑现为**震荡而非跳空**，IV 反落。"),
    "ta": ("down",
           f"IV 33.0%/HV20 33.1% → **−0.1pp 基本持平**；5dΔ −0.2pp{SRC_SCAN}。"
           f"事件〔窗内〕原油**先冲 +6%（Brent 破 100）再回落** → WTI 约 89.44-89.91、累计 −0.48%；"
           f"G7/IEA 协调释放 1 亿桶；中东出口增量恢复{SRC_EVT}。"
           f"**判：IV down** —— 净方向仍是「成本端退潮」，与旧表同向；振幅放大不改变方向。"
           f"⚠️ 反方：振幅放大 = 区间上下沿被拉宽 → 对卖方「不越界」假设变弱；Hormuz 硬风险未解除。"),
    "i":  ("down",
           f"IV 16.7%/HV20 13.6% → **+3.1pp**；5dΔ +0.9pp{SRC_SCAN}。"
           f"事件〔窗内〕Mysteel 61% 粉矿指数 **90.55 美元/干吨、创年内新低**；94% 受访钢厂看跌节后；"
           f"焦炭首轮提降落地{SRC_EVT}。**该条 `真实风险=false`** = 无未定价项{SRC_EVT}。"
           f"**判：IV down** —— 方向偏空但已在盘面/机构预期内（真实风险 false），无未定价催化；"
           f"+3.1pp 溢价有回落空间。"
           f"⚠️ 反方：单边下行趋势本身会推**已实现**波动率（HV）上行，HV 可能追上 IV → 溢价收窄反而不利卖方。"),
    "ru": ("up",
           f"IV 29.0%/HV20 24.0% → **+5.0pp**；5dΔ **+2.1pp（上行惯性未消）**{SRC_SCAN}。"
           f"事件〔窗内〕泰国胶水 **83 泰铢/公斤**（10/8 隆众，较旧表 9/24 的 80.0 续涨）+ "
           f"**节中泰国部分地区洪灾扰动割胶**（本批新增）{SRC_EVT}。"
           f"**判：IV up** —— 洪灾 = 窗内**新增未定价项** + 原料续涨，看涨情绪推动。"
           f"⚠️ 反方：中信 10/7「胶价创近十年同期新高 + 泰国四季度季节性放量 → 警惕减产溢价修正」= 反向硬证据；"
           f"且原料价两来源冲突（83 vs 54.06）**标存疑、不选边**。"),
    "ma": ("down",
           f"IV **42.6% = 全批最高**，/HV20 32.1% → **+10.5pp = 全批最大溢价**；5dΔ **+2.8pp**；"
           f"近 48.6% > 远 42.6% = **倒挂（法则①封卖方）**{SRC_SCAN}。"
           f"事件〔窗内〕港口库存 **41.20 万吨 = 历史新低**；9 月伊朗装港仅约 15.4 万吨、10 月进口预估约 47 万吨维持低位；"
           f"伊朗日产回升至约 21,000 吨（仍远低于冲突前）{SRC_EVT}。"
           f"**判：IV down** —— 断供未解，但 +10.5pp 溢价叠加 5dΔ 连续上行 → **均值回归压力 > 新增驱动**。"
           f"⚠️ 反方：中信 10/3「工厂与港口库存均五年同期最低、长假下游延续备货、期现货偏强」→ 库存继续去化则 IV 可继续上行；"
           f"且「美伊谈判若实质进展 → 浮仓集中释放」可在很短时间内反转方向（快照自带反方）。"),
    "rm": ("down",
           f"IV 18.0% 处 HV20 18.7% 折价 **−0.7pp**；5dΔ +0.1pp{SRC_SCAN}。"
           f"事件〔窗内〕两头夹：偏多=加籽收割艰难（降雨+夜间低温压缩作业窗、品质下降）；"
           f"偏空=沿海油厂菜籽菜粕库存环比增加、开机率 35.18%、到港 58.5/52/44.5 万吨{SRC_EVT}。"
           f"**判：IV down** —— 无单边驱动 + 折价态无向上催化，跟随豆粕偏弱运行。"
           f"⚠️ 反方：快照明记「成本端抬升 = **卖 P 的下行保护变弱** → 尾部风险上升一档」，可推 IV 上行。"),
}


def main():
    dry = "--dry-run" in sys.argv
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    dup = [r["variety"] for r in rows if r.get("date") == BATCH]
    assert not dup, f"批次 {BATCH} 已存在行，拒绝重复追加：{dup}"
    assert set(COACH) == set(ORDER), "品种集合不一致"
    for v, (p, t) in COACH.items():
        assert p in ("up", "down"), f"{v}: pred 非法 {p}"
        assert t.rstrip().endswith("。") or t.count("⚠️") >= 1, f"{v}: 缺反方"

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
