#!/usr/bin/env python3
"""fill_actual_reason_coach_20261013.py

对照日 **2026-10-13**：落 **2026/9/29 批**（compare_date 2026/10/13）的
`actual_reason_coach` 10 行 —— **对照日三步的第 ① 步**。

流程铁律（weekly-rhythm）：① 教练搜事实写 `actual_reason_coach` → 落盘，
回执**只打印行数/CRLF/断言，不回显正文** → ② 用户口述 `actual_reason` → ③ 两侧同时亮出。
**本脚本运行时用户尚未口述** → 教练侧盲写成立。

窗口 = **[9/30, 10/13]**（窗口起点 = 批次日 + 1）。窗内交易日 = 9/30 · 10/8 · 10/9 · 10/12 · 10/13
（**5 个**）；窗内非交易日 = **10/1-10/7 国庆连休 7 天**。

来源（依 9/28「先搜后写」：落盘前须检索事件源，标 来源 · 窗内/窗外 · 可信度）：
  ① `data/weekly_event_scan.json`（scan_date 2026-10-12 · valid_until 2026-10-19）——
     覆盖窗口**后段**（10/12-10/13）。
  ② `data/scanner_log/2026-10-09.md` 内 10/8 快照（valid_until 2026-10-16）——
     **国庆假期复盘**，覆盖窗口主体（10/8 起）。
  ③ `data/scanner_log/2026-09-30.md` 内 9/27 快照（valid_until 2026-10-10）——
     覆盖窗口**前段**（9/30）。
  ④ `data/iv_history.csv` —— 机械读数，见下方 ACTUAL，**不入本列正文的因果**。

⚠️ **本列未起当日网络搜索**（10:2x 属决策时段 + 9-18 大 token 禁令）→ 全部依据上述**本地
   事件源**，每条均标来源与可信度。**这是本列的证据上限，不冒充「已独立核实」。**
⚠️ **本脚本不碰** `actual` / `actual_delta_pp` / `user_correct` / `coach_correct` /
   `contract_compare` / `cross_contract` / `user_reason` —— 全归第 ② 步。

用法：python3 tools/fill_actual_reason_coach_20261013.py [--dry-run]
"""
import csv
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "iv_direction_pred.csv")

BATCH = "2026/9/29"
SRC10 = "〔源：weekly_event_scan.json 10/12 快照 · 窗内 · 可信度中高〕"
SRC08 = "〔源：scanner_log/2026-10-09.md 内 10/8 快照（国庆复盘）· 窗内 · 可信度中高〕"
SRC27 = "〔源：scanner_log/2026-09-30.md 内 9/27 快照 · 窗内 · 可信度中高〕"

# 机械读数（09:30 → 09:30；10/13 无 09:30 者用 09:31 代），**仅供行文参考，不写入**
ACTUAL = {
    "au": ("down", -2.27), "m": ("up", +0.40), "c": ("down", -2.09),
    "cf": ("down", -2.05), "sr": ("up", +1.81), "ta": ("flat", -0.24),
    "i": ("up", +0.83), "ru": ("up", +7.36), "ma": ("up", +7.09), "rm": ("up", +1.80),
}

REASON = {
    "au": (f"实际 23.17% → 20.90%（**−2.27pp**，down）。"
           f"窗内事实链：**10/7 晚间伦敦金现一度跌超 2%**、回落至约 4,115.95（盘中高 4,179.82），"
           f"金价自 9 月中旬 4,400 上方已回落 5-7%；压制源 = **10Y 美债 5.27-5.35%（2002 年以来最高）**，"
           f"10/28 议息维持不变概率约 78%{SRC08}。"
           f"⇒ 事前判 down（高溢价无承接）**方向对上**。"
           f"⚠️ 反方 / 未兑现项：Hormuz 窗内**升级未解**（10/3 革命卫队对 7 艘油轮行动、10/7 顾问称海峡「关闭状态」），"
           f"避险随时可重启 —— **本批 down 含运气成分，不是「事件已出清」被证实**{SRC08}。"),

    "m":  (f"实际 14.16% → 14.56%（**+0.40pp**，up）。"
           f"窗内已知项：**10/9 WASDE（美东 12:00 → 京 10/10）**；我事前以「对照时点 10/13 在报告后 "
           f"2 个交易日、事件溢价已过」判 down。"
           f"⇒ **事前判 down，方向错。**"
           f"⚠️ **驱动未能确证**：+0.40pp 的具体来源，现有本地来源**给不出量化证据**（候选 = WASDE 后 "
           f"10/12-10/13 两日的新定价、或 11 月到港 980 万吨同比 +170 的供给端再定价）"
           f"→ 按判据四问 D 记**「原因不明」**，不编因果{SRC08}{SRC10}。"
           f"📌 **错因（写下来）：我把「事件已过峰」直接等同于「IV 必回落」——忽略了报告后到对照日之间"
           f"还有定价窗口（10/10 报告 → 10/12/10/13）。这与 10/12 落地的 9/28 批同型。**"),

    "c":  (f"实际 11.76% → 9.67%（**−2.09pp**，down）。"
           f"⚠️ **本行为跨合约行（c2611 → c2701），Δ 含换月口径差，报分时剔出分母**。"
           f"窗内事实：国庆期间**东北新粮集中上市** —— 锦州港 15 水 **2135-2140（较节前 −25）**、"
           f"北方港口假期跌 20-30 元/吨、产地深加工门前上量价跌 20-90 元/吨{SRC08}。"
           f"⇒ 事前判 down（溢价已过峰）**方向对上**。"
           f"⚠️ **但跨合约行的 Δ 不能当作纯预测力的证据** —— 本行 −2.09pp 里有多少来自换月、多少来自行情，"
           f"**未做分解、也不该声称做过**。"),

    "cf": (f"实际 12.75% → 10.70%（**−2.05pp**，down）。"
           f"窗内事实：下游开机率断崖 —— 纺纱 **78%→69.2%**、织布 **42%→37.17%**（均年内低位）、"
           f"「金九」旺季落空；成本倒挂 300-400 元/吨{SRC08}。"
           f"⇒ 事前判 down（需求塌陷 + 折价态）**方向对上**。"
           f"⚠️ cf 是 **Data 门卡点（52/60，样本最薄）**，本行证据强度弱于其他品种。"),

    "ta": (f"实际 32.00% → 31.76%（**−0.24pp**）→ **flat（|Δ| < 0.25pp），不计分**。"
           f"窗内两条对冲：①成本端 **旧表的「退潮」在 9/27 快照被证实**（Brent 破 100 后回落、"
           f"石脑油 −6.84%、PX −2.6%）{SRC27}；②**飓风「伊萨亚斯」致墨西哥湾约 63%-72% 产量停产**"
           f"为窗内新增收缩项{SRC10}；③9/27 快照记 **PTA 加工费从 ~400 冲到 ~700 元/吨、"
           f"下游聚酯负荷降至 74.5%-78.1%**（**产业级压制，非事件级**）{SRC27}。"
           f"⇒ 上下对冲 → IV 基本走平，**flat 是这组对冲的合理结果**，非「判对了」。"
           f"⚠️ 反方：本行我事前判 down、实际 flat —— flat 行**不计分**，故本行两边都不进分子分母。"),

    "ma": (f"实际 37.58% → 44.67%（**+7.09pp**，up）。"
           f"⚠️ **本行为跨合约行（ma2701 → ma2612），Δ 含换月口径差，报分时剔出分母**。"
           f"窗内事实：**10/8 前后美国财政部制裁 17 艘伊朗「影子船队」**；霍尔木兹日均运输量降至 "
           f"200 万桶以下（10/6 仅 7 艘商船，7/23 以来最低）；**港口库存 41.20 万吨 = 历史新低**；"
           f"伊朗日产回升至约 21,000 吨仍远低于冲突前{SRC10}{SRC08}。"
           f"⇒ **事前判 down（理由写的是「窗口内无甲醇专属新催化」），方向错。**"
           f"📌 **错因：我把 supply 型短缺的溢价当成了均值回归对象 —— 事实上「制裁 + 海峡通行量」"
           f"两个新事实是在窗口内把缺口**再次加固**。这与 10/12 落地的 9/28 批完全同型"
           f"（那批 ma 实际 +5.29pp、我同样判 down）。另注：本行跨合约，+7.09pp 里有一部分是换月，"
           f"不能全算作行情。**"),

    "i":  (f"实际 16.17% → 17.00%（**+0.83pp**，up）。"
           f"窗内事实：10/12 快照明记 **无 i 专项新增事实**、`真实风险` 维持 false；"
           f"主导项 = Mysteel 61% 粉矿指数 **90.55 美元/干吨创年内新低**、94% 受访钢厂看跌节后、"
           f"焦炭首轮提降落地{SRC10}。"
           f"⇒ **事前判 down，方向错。**"
           f"⚠️ **未兑现项**：i2701 期限结构须当日重取（9/29 记倒挂：近 17.5% > 远 16.2%），本行未复核。"
           f"📌 **错因：我自己事前写下的反方已经预警了这一点 ——「单边下行趋势本身会推已实现波动率（HV）上行」"
           f"—— 单边跌本身就在制造波动，我却在主判里按「方向偏空 → 低波动」处理，把反方写在了旁边没有并进主判。**"),

    "ru": (f"实际 21.92% → 29.28%（**+7.36pp = 全批最大涨幅**，up）。"
           f"窗内事实：泰国胶水 **83 泰铢/公斤**（10/8 隆众，较 9/24 的 80.0 续涨）+ "
           f"节中泰国部分地区**洪灾扰动割胶**{SRC08}{SRC10}。"
           f"⇒ 事前判 up **方向对上**。"
           f"⚠️ **但理由成分不纯**：我事前押 up 的文本里混着「厄尔尼诺长周期」，而 10/12 快照明写"
           f"**「厄尔尼诺对 ru 是 2027 年的故事、不是本窗的故事」**（行情滞后峰值 3-6 个月、胶价高点"
           f"甚至滞后 4-5 个季度）{SRC10} → **判据四问 A「变化性」这一条，我事前过得不干净**。"
           f"窗口内真实驱动应是**原料续涨 + 洪灾**这两条已兑现项。"),

    "sr": (f"实际 10.24% → 12.05%（**+1.81pp**，up）。"
           f"窗内事实：**ICE 原糖假期暴涨 +12.08%**（10/6 收 20.87 美分/磅、近 19 个月新高）"
           f"→ 外强内弱 = **跳空风险**；**印度已禁止食糖出口**；配额外巴西进口加工糖成本约 "
           f"6,600 元/吨 vs 郑糖 5,354{SRC08}{SRC10}。"
           f"⇒ 事前判 up **方向对上**。"
           f"⚠️ **反方未兑现**：全国工业库存 372 万吨（历史第二高）、北方糖厂已开榨 **本窗未压住 IV** "
           f"→ 说明本窗主导项是**外盘传导**而非内盘库存。"),

    "rm": (f"实际 16.98% → 18.78%（**+1.80pp**，up）。"
           f"窗内事实：10/12 快照**未复搜到 rm 窗内新增事实**，且明记这是**本次扫描覆盖最薄的一条**"
           f"（三路搜索无一直接覆盖加拿大菜籽）= **覆盖缺口，不是「无风险」**；已知项 = 沿海油厂菜籽菜粕"
           f"库存环比增加、开机率 35.18%、到港 58.5/52/44.5 万吨；**10/9 WASDE**{SRC10}。"
           f"⇒ **事前判 down，方向错。**"
           f"⚠️ **本行我写不出已证实的因果** —— 现有本地来源未给出 rm 窗内 IV 上行的驱动；"
           f"候选（WASDE 联动 / 菜系整体走强）**均无量化证据**，按判据四问 D 记**「原因不明」**，不编因果。"),
}


def main():
    dry = "--dry-run" in sys.argv
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    tgt = {r["variety"]: r for r in rows if r.get("date") == BATCH}
    assert len(tgt) == 10, f"批次 {BATCH} 应有 10 行，实际 {len(tgt)}"
    assert set(REASON) == set(tgt), "品种集合不一致"
    assert ACTUAL == {v: (p, d) for v, (p, d) in ACTUAL.items()}, "内部一致性"
    for v, r in tgt.items():
        assert not r["actual_reason_coach"], f"{v}: actual_reason_coach 已有值，拒绝覆盖"
        assert r["coach_pred"], f"{v}: coach_pred 缺失"
        assert REASON[v].count("⚠️") >= 1, f"{v}: 缺反方/诚实标注"

    print(f"批次 {BATCH} → 落 actual_reason_coach {len(REASON)} 行")
    for v in REASON:
        print(f'  {v:<4} {ACTUAL[v][0]:<5} {ACTUAL[v][1]:>+6.2f}pp  reason {len(REASON[v])} 字')
    print("\n⚙️ 本次盲写成立：用户尚未口述 actual_reason。")

    if dry:
        print("\n--dry-run：未落盘。")
        return

    b = open(CSV_PATH, "rb").read()
    n_before = (b.count(b"\n"), b.count(b"\r\n"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"/tmp/iv_direction_pred.csv.{stamp}.bak"
    shutil.copy2(CSV_PATH, bak)

    for v, r in tgt.items():
        r["actual_reason_coach"] = REASON[v]

    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, CSV_PATH)

    # ── 回核（行数/CRLF/断言；正文不回显）────────────────────
    b2 = open(CSV_PATH, "rb").read()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows2 = list(csv.DictReader(f))
    tgt2 = [r for r in rows2 if r.get("date") == BATCH]
    assert len(rows2) == len(rows), "行数变了，拒绝"
    assert all(r["actual_reason_coach"] for r in tgt2), "有行未写满"
    assert all(not r["actual"] and not r["actual_reason"] for r in tgt2), "第 ② 步的列被误写"
    print(f"回核：总行数 {len(rows2)}（未变）· 本批 {len(tgt2)} · 列数 {len(rows2[0])}")
    print(f"      actual_reason_coach 已写 {sum(1 for r in tgt2 if r['actual_reason_coach'])}/10"
          f" · actual 仍空 {sum(1 for r in tgt2 if not r['actual'])}/10")
    print(f"      LF {n_before[0]} → {b2.count(b'\n')} · CRLF {n_before[1]} → {b2.count(b'\r\n')}（须为 0）")
    print(f"      备份 {bak}")
    print("\n▶ 第 ① 步完成。**正文不在此回显** —— 等用户口述 actual_reason 落盘后，第 ③ 步两侧同时亮出。")


if __name__ == "__main__":
    main()
