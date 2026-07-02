#!/usr/bin/env python3
"""
期权交易速度训练系统 v1.0
─────────────────────────
替代旧闪卡。练判断力+反应速度，不练记忆力。

四种训练每天轮转:
  A — 链面扫异常   (周一/四)
  B — 心算价差     (周二/五)
  C — 天气→策略    (周三/六)
  D — Greek 直觉   (周日)

每次训练计时+记分，数据存 drill_state/history.json。
"""

import sys, os, json, random, time, argparse
from datetime import datetime, date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
STATE_DIR = SCRIPT_DIR.parent / "drill_state"
STATE_DIR.mkdir(exist_ok=True)
HISTORY_FILE = STATE_DIR / "history.json"

# ── 市场参考数据（用于生成真实感题目）──
FUTURES_PRICES = {
    "沪金": 870, "豆粕": 2800, "玉米": 2300, "PTA": 4800,
    "甲醇": 2450, "菜籽粕": 2500, "白糖": 5600, "棉花": 13500,
    "铁矿石": 780, "橡胶": 17000,
}

STRIKE_INTERVALS = {
    "沪金": 8, "豆粕": 50, "玉米": 40, "PTA": 50,
    "甲醇": 50, "菜籽粕": 50, "白糖": 100, "棉花": 200,
    "铁矿石": 20, "橡胶": 500,
}

# ── 数据持久化 ──

def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return {"sessions": [], "personal_bests": {}}

def save_session(module, score, accuracy, avg_time, total_q):
    h = load_history()
    h["sessions"].append({
        "date": datetime.now().isoformat(),
        "module": module,
        "score": score,
        "accuracy": round(accuracy, 1),
        "avg_time_ms": round(avg_time, 0),
        "total_questions": total_q,
        "day_of_week": date.today().strftime("%A"),
    })
    # 更新个人最佳
    key = f"{module}_score"
    if key not in h["personal_bests"] or score > h["personal_bests"][key]:
        h["personal_bests"][key] = score
    key = f"{module}_accuracy"
    if key not in h["personal_bests"] or accuracy > h["personal_bests"][key]:
        h["personal_bests"][key] = round(accuracy, 1)

    # 只保留最近 200 条
    h["sessions"] = h["sessions"][-200:]
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2))


def show_progress():
    h = load_history()
    if not h["sessions"]:
        print("\n  尚无训练记录。跑一次训练就有了。\n")
        return

    sessions = h["sessions"]
    modules = ["A", "B", "C", "D", "E", "F", "G"]
    module_names = {"A": "链面扫异常", "B": "价差判断", "C": "天气→策略", "D": "Greek场景", "E": "信用价差扫描", "F": "持仓管理", "G": "腿位判断"}

    print(f"\n{'═'*60}")
    print(f"  📊 训练统计（共 {len(sessions)} 次）")
    print(f"{'═'*60}")

    for m in modules:
        mod_sessions = [s for s in sessions if s["module"] == m]
        if not mod_sessions:
            continue
        recent = mod_sessions[-10:]
        avg_acc = sum(s["accuracy"] for s in recent) / len(recent)
        avg_time = sum(s["avg_time_ms"] for s in recent) / len(recent)
        pb = h["personal_bests"].get(f"{m}_accuracy", 0)

        # ASCII 进度条
        bar_len = int(avg_acc / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)

        print(f"\n  训练{m} {module_names[m]}:")
        print(f"    最近10次均: 正确率 {avg_acc:.1f}%  |  速度 {avg_time/1000:.1f}s/题")
        print(f"    个人最佳:   {pb}%")
        print(f"    趋势: [{bar}]")
        print(f"    总练习: {len(mod_sessions)} 次")

    # 今日推荐
    dow = date.today().weekday()
    today_module = {0: "A", 1: "B", 2: "C", 3: "A", 4: "B", 5: "C", 6: "D"}[dow]
    print(f"\n  📅 今天推荐: 训练 {today_module} ({module_names[today_module]})")
    print(f"{'═'*60}\n")


# ═══════════════════════════════════════════
# 训练 A：链面扫异常
# ═══════════════════════════════════════════

def generate_chain_segment():
    """生成一段模拟期权链（看跌），模拟真实市场特征。
    包含：bid/ask 跳动、零买价、价差过宽、倒挂（真+假）。
    0-3个混合异常，需要区分可交易 vs 不可交易。"""
    product = random.choice(list(FUTURES_PRICES.keys()))
    fut = FUTURES_PRICES[product]
    interval = STRIKE_INTERVALS[product]

    n_strikes = random.randint(9, 12)
    start_strike = fut - interval * (n_strikes + random.randint(1, 4))
    strikes = [start_strike + i * interval for i in range(n_strikes)]

    # 生成递增的基准价格，但 bid/ask 有真实跳动
    prices = []
    base_theo = round(random.uniform(0.15, 3.0), 2)
    base_bid = round(base_theo * random.uniform(0.85, 0.95), 2)
    base_ask = round(base_theo * random.uniform(1.05, 1.15), 2)
    prices.append({
        "theo": max(0.02, base_theo),
        "bid": max(0.01, base_bid),
        "ask": base_ask,
    })

    for i in range(1, n_strikes):
        increment = random.uniform(0.03, 1.2)
        theo = round(prices[i-1]["theo"] + increment, 2)
        if random.random() < 0.15:
            theo = round(prices[i-1]["theo"] + random.uniform(1.0, 3.0), 2)
        # 真实市场：bid/ask 随机跳动。一半行权价价差较紧（可交易），一半较宽
        theo += random.uniform(-0.15, 0.15)
        if random.random() < 0.5:
            # 紧价差：bid 贴近 theo，ask 小幅加价
            bid = round(theo * random.uniform(0.90, 0.97), 2)
            ask = round(theo * random.uniform(1.03, 1.10), 2)
        else:
            # 宽价差：模拟真实深度虚值区
            bid = round(theo * random.uniform(0.80, 0.90), 2)
            ask = round(theo * random.uniform(1.10, 1.25), 2)
        # 随机零买价
        otm_pct = (fut - strikes[i]) / fut
        if otm_pct > 0.25 and random.random() < 0.06:
            bid = 0.0
        prices.append({
            "theo": max(prices[i-1]["theo"] + 0.01, theo),
            "bid": max(0.01, bid) if bid > 0 else 0.0,
            "ask": ask,
        })

    # 注入 1-3 个混合异常（加权：可交易倒挂出现概率更高）
    tradeable_strikes = []
    all_anomalies = []
    n_anomalies = random.randint(1, 3)
    candidates = list(range(2, len(strikes) - 2))
    random.shuffle(candidates)

    for idx in candidates[:n_anomalies]:
        anomaly_type = random.choice(["inversion_tradeable", "inversion_tradeable",
                                       "inversion_untradeable", "zero_bid", "wide_spread"])
        if anomaly_type == "inversion_tradeable":
            # 检查参考腿（低行权价，idx-1）的流动性
            ref_bid = prices[idx-1]["bid"]
            ref_ask = prices[idx-1]["ask"]
            ref_spread_pct = (ref_ask - ref_bid) / ref_bid * 100 if ref_bid > 0 else 999

            if ref_bid <= 0:
                # 参考腿没买价 → 不可交易
                prices[idx]["theo"] = round(prices[idx-1]["theo"] * random.uniform(0.5, 0.8), 2)
                prices[idx]["bid"] = 0.0
                all_anomalies.append({"strike": strikes[idx], "type": "假倒挂",
                                       "detail": f"行权价{strikes[idx]}：价格倒挂但参考腿买价为零 → 不能做"})
            elif ref_spread_pct > 15:
                # 参考腿价差太宽 → 不可交易
                prices[idx]["theo"] = round(prices[idx-1]["theo"] * random.uniform(0.5, 0.8), 2)
                prices[idx]["bid"] = round(prices[idx]["theo"] * random.uniform(0.88, 0.94), 2)
                prices[idx]["ask"] = round(prices[idx]["bid"] * random.uniform(1.03, 1.10), 2)
                all_anomalies.append({"strike": strikes[idx], "type": "假倒挂",
                                       "detail": f"行权价{strikes[idx]}：价格倒挂但参考腿价差{ref_spread_pct:.0f}%太宽 → 不能做"})
            else:
                # 参考腿流动性好 → 真正可交易
                prices[idx]["theo"] = round(prices[idx-1]["theo"] * random.uniform(0.5, 0.8), 2)
                prices[idx]["bid"] = round(prices[idx]["theo"] * random.uniform(0.88, 0.94), 2)
                prices[idx]["ask"] = round(prices[idx]["bid"] * random.uniform(1.03, 1.10), 2)
                tradeable_strikes.append(strikes[idx])
                all_anomalies.append({"strike": strikes[idx], "type": "可交易倒挂",
                                       "detail": f"行权价{strikes[idx]}：更高但更便宜，买价{prices[idx]['bid']:.2f}存在，参考腿价差{ref_spread_pct:.0f}%合理"})
        elif anomaly_type == "inversion_untradeable":
            prices[idx]["theo"] = round(prices[idx-1]["theo"] * random.uniform(0.5, 0.8), 2)
            ref_bid = prices[idx-1]["bid"]
            ref_spread = (prices[idx-1]["ask"] - ref_bid) / ref_bid * 100 if ref_bid > 0 else 999

            # 四种不可交易原因，随机选一种
            roll = random.random()
            if roll < 0.25 and ref_bid <= 0:
                # 参考腿无流动性
                prices[idx]["bid"] = round(prices[idx]["theo"] * random.uniform(0.88, 0.94), 2)
                prices[idx]["ask"] = round(prices[idx]["bid"] * random.uniform(1.03, 1.10), 2)
                detail = f"行权价{strikes[idx]}：价格倒挂但参考腿买价为零 → 参考价不可信，不能做"
            elif roll < 0.50 and ref_spread > 15:
                # 参考腿价差太宽
                prices[idx]["bid"] = round(prices[idx]["theo"] * random.uniform(0.88, 0.94), 2)
                prices[idx]["ask"] = round(prices[idx]["bid"] * random.uniform(1.03, 1.10), 2)
                detail = f"行权价{strikes[idx]}：价格倒挂但参考腿价差{ref_spread:.0f}%太宽 → 参考价不可信，不能做"
            elif roll < 0.75:
                # 倒挂腿自身买价为零
                prices[idx]["bid"] = 0.0
                prices[idx]["ask"] = round(prices[idx]["theo"] * 1.5, 2)
                detail = f"行权价{strikes[idx]}：价格倒挂了但买价为零 → 无法平仓，不能做"
            else:
                # 倒挂腿自身价差过宽
                prices[idx]["bid"] = round(prices[idx]["theo"] * 0.2, 2)
                prices[idx]["ask"] = round(prices[idx]["theo"] * 3.0, 2)
                detail = f"行权价{strikes[idx]}：价格倒挂了但价差过宽 → 滑点吃掉利润，不能做"
            all_anomalies.append({"strike": strikes[idx], "type": "假倒挂", "detail": detail})
        elif anomaly_type == "zero_bid":
            prices[idx]["bid"] = 0.0
            all_anomalies.append({"strike": strikes[idx], "type": "零买价",
                                   "detail": f"行权价{strikes[idx]}：买价为零，流动性垃圾，不是机会"})
        elif anomaly_type == "wide_spread":
            prices[idx]["bid"] = round(prices[idx]["theo"] * 0.3, 2)
            prices[idx]["ask"] = round(prices[idx]["theo"] * 2.5, 2)
            all_anomalies.append({"strike": strikes[idx], "type": "价差过宽",
                                   "detail": f"行权价{strikes[idx]}：价差太宽，不能做"})

    return {
        "product": product, "futures": fut, "strikes": strikes,
        "prices": [{**p} for p in prices],
        "tradeable_strikes": tradeable_strikes,
        "all_anomalies": all_anomalies,
    }


def run_drill_a(quick=False):
    """训练 A：链面扫异常 — 真实市场链面，辨真假机会"""
    print(f"\n{'─'*60}")
    print(f"  训练 A — 链面扫异常")
    print(f"  规则：真实市场链面，有多处异常。找出真正可交易的倒挂。")
    print(f"  可交易 = 有买价 + 价差合理。零买价/价差过宽 = 流动性垃圾，忽略。")
    print(f"  目标：正确率 > 85%，不漏真机会，不误报假机会")
    print(f"{'─'*60}")

    n_rounds = 5 if quick else 10
    score = 0
    total_time = 0
    correct = 0

    for round_num in range(1, n_rounds + 1):
        chain = generate_chain_segment()

        print(f"\n  [{round_num}/{n_rounds}] {chain['product']} 期货≈{chain['futures']}")
        col_fmt = f"  {{:>6}} │ {{:>8}} {{:>8}} {{:>8}} {{:>8}}"
        print(col_fmt.format('行权价', 'P买价', 'P卖价', 'P价格', '价差%'))
        print(f"  {'─'*6}─┼─{'─'*32}")

        for i, (s, p) in enumerate(zip(chain["strikes"], chain["prices"])):
            bid_str = f"{p['bid']:.2f}" if p['bid'] > 0 else "0.00"
            ask_str = f"{p['ask']:.2f}"
            theo_str = f"{p['theo']:.2f}"
            if p['bid'] > 0 and p['ask'] > 0:
                sp = round((p['ask'] - p['bid']) / p['bid'] * 100, 1)
                flag = " ⚠️" if sp > 15 else ""
                spread_str = f"{sp}%{flag}"
            elif p['bid'] == 0:
                spread_str = "零买价 ❌"
            else:
                spread_str = "—"
            print(col_fmt.format(s, bid_str, ask_str, theo_str, spread_str))

        t_start = time.time()
        try:
            answer = input(f"  → 可交易倒挂在哪些行权价？(逗号分隔，或'无'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。已保存当前进度。")
            return
        elapsed = (time.time() - t_start) * 1000
        total_time += elapsed

        if answer.lower() in ["无", "none", "n", "no", ""]:
            user_strikes = set()
        else:
            try:
                user_strikes = set(int(x.strip()) for x in answer.replace("，", ",").split(",") if x.strip())
            except ValueError:
                user_strikes = set()

        expected = set(chain["tradeable_strikes"])
        false_positives = user_strikes - expected
        misses = expected - user_strikes
        hits = user_strikes & expected

        if not false_positives and not misses:
            correct += 1
            score += 3 if elapsed < 15000 else (2 if elapsed < 25000 else 1)
            if expected:
                print(f"  ✅ 全对！({elapsed/1000:.1f}s) 可交易: {sorted(expected)}")
            else:
                print(f"  ✅ 正确！({elapsed/1000:.1f}s) 这条链没有可交易机会")
        else:
            if misses:
                print(f"  ❌ 漏了真正的机会: {sorted(misses)}")
            if false_positives:
                print(f"  ❌ 误报（流动性垃圾，不是机会）: {sorted(false_positives)}")
            if hits:
                print(f"  ✓ 答对: {sorted(hits)}")

            if chain["all_anomalies"]:
                print(f"  📝 全部异常解析:")
                for a in chain["all_anomalies"]:
                    icon = "🟢" if a["strike"] in chain["tradeable_strikes"] else "🔴"
                    print(f"     {icon} {a['detail']}")

        if round_num < n_rounds:
            input(f"  (按回车继续)")

    accuracy = correct / n_rounds * 100
    avg_time = total_time / n_rounds
    save_session("A", score, accuracy, avg_time, n_rounds)

    print(f"\n  {'─'*40}")
    print(f"  训练A 完成: {correct}/{n_rounds} 正确 ({accuracy:.0f}%)")
    print(f"  平均用时: {avg_time/1000:.1f}s/题  得分: {score}")
    rating = "⭐ 目光如炬！" if accuracy >= 85 else ("👍 继续磨" if accuracy >= 65 else "🐢 多看真实链面")
    print(f"  {rating}")
    print()


# ═══════════════════════════════════════════
# 训练 B：心算价差
# ═══════════════════════════════════════════

def run_drill_b(quick=False):
    """训练 B：价差判断 — 能不能做"""
    print(f"\n{'─'*60}")
    print(f"  训练 B — 价差判断")
    print(f"  规则：看 bid/ask，判断能不能做。不计算，只判断。")
    print(f"  可 (价差<10%)  |  警 (10-15%看情况)  |  不 (价差>15%)")
    print(f"  目标：3秒/题，正确率>85%")
    print(f"{'─'*60}")

    n_rounds = 5 if quick else 25
    score = 0
    total_time = 0
    correct = 0

    labels = {"可": "✅可(<10%)", "警": "⚠️警(10-15%)", "不": "❌不(>15%)"}

    for round_num in range(1, n_rounds + 1):
        scenario_type = random.choice(["deep_otm", "atm", "itm", "wide", "tight"])
        if scenario_type == "deep_otm":
            bid = round(random.uniform(0.10, 2.00), 2)
            ask = round(bid * random.uniform(1.05, 3.00), 2)
        elif scenario_type == "atm":
            bid = round(random.uniform(5.00, 50.00), 2)
            ask = round(bid * random.uniform(1.01, 1.25), 2)
        elif scenario_type == "itm":
            bid = round(random.uniform(30.00, 200.00), 2)
            ask = round(bid * random.uniform(1.01, 1.20), 2)
        elif scenario_type == "wide":
            bid = round(random.uniform(0.20, 3.00), 2)
            ask = round(bid * random.uniform(2.00, 8.00), 2)
        else:
            bid = round(random.uniform(1.00, 20.00), 2)
            ask = round(bid * random.uniform(1.02, 1.06), 2)

        actual_spread = round((ask - bid) / bid * 100, 1)
        if actual_spread < 10:
            expected = "可"
        elif actual_spread <= 15:
            expected = "警"
        else:
            expected = "不"

        print(f"\n  [{round_num}/{n_rounds}]  买价={bid:.2f}  卖价={ask:.2f}")

        t_start = time.time()
        try:
            user = input(f"  → 可/警/不 ?: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。已保存当前进度。")
            return
        elapsed = (time.time() - t_start) * 1000
        total_time += elapsed

        if user == expected:
            correct += 1
            if elapsed < 3000:
                score += 3
            elif elapsed < 6000:
                score += 2
            else:
                score += 1
            print(f"  ✅ {elapsed/1000:.1f}s  {labels[expected]}  实际价差{actual_spread}%")
        else:
            print(f"  ❌ {elapsed/1000:.1f}s  你选{user}  实际{labels[expected]}  价差{actual_spread}%")

    accuracy = correct / n_rounds * 100
    avg_time = total_time / n_rounds
    save_session("B", score, accuracy, avg_time, n_rounds)

    print(f"\n  {'─'*40}")
    print(f"  训练B完成: {correct}/{n_rounds} 正确 ({accuracy:.0f}%)")
    print(f"  平均用时: {avg_time/1000:.1f}s/题  得分: {score}")
    rating = "⚡ 火眼金睛！" if accuracy >= 85 else ("👍 继续磨" if accuracy >= 65 else "🐢 多看真实链面")
    print(f"  {rating}")
    print()



# ═══════════════════════════════════════════
# 训练 C：天气→策略
# ═══════════════════════════════════════════

SCENARIOS_C = [
    {
        "desc": "玉米 IV 处于历史最低 12% 分位，未来 3 天 USDA 种植面积报告",
        "iv": "极低", "event": "高影响",
        "options": [
            ("买跨式 ATM Call+Put", True, "IV 低 + 事件将至 = 期权便宜 + 潜在跳空 → 买方有利"),
            ("卖出跨式收权利金", False, "IV 极低时卖出收的权利金太少，不值得"),
            ("虚值 Put 卖方", False, "IV 低时卖方优势弱"),
            ("不做", False, "虽然需要耐心，但这个场景优势明确"),
        ],
    },
    {
        "desc": "沪金 IV 处于历史最高 92% 分位，近期无重大事件，金价窄幅震荡",
        "iv": "极高", "event": "无",
        "options": [
            ("买入虚值 Put 等暴跌", False, "IV 极高 = 期权太贵，买不起"),
            ("卖出 ATM 跨式收 IV 回落 + Theta", True, "IV 极端高 + 无事件 = 均值回归概率大 → 卖方有利"),
            ("买跨式等方向", False, "IV 太贵，即使方向对了可能 Vega 亏更多"),
            ("不做", False, "IV 极端位置是难得的卖方窗口"),
        ],
    },
    {
        "desc": "豆粕 IV 处于中位 55%，USDA WASDE 报告 10 天后",
        "iv": "中等", "event": "较远",
        "options": [
            ("现在买入跨式", False, "报告还有10天，Theta 会蒸发掉不少"),
            ("卖出跨式", False, "IV 不高不低，卖也没多少肉"),
            ("先跟踪，D-3 再评估 IV 和事件风险", True, "时间还早，IV 也不极端，现在进场没有优势"),
            ("重仓卖出虚值 Put", False, "IV 中等卖方优势不足"),
        ],
    },
    {
        "desc": "PTA IV 处于 25% 分位（偏低），EIA 原油库存明天发布，原油近期波动大",
        "iv": "偏低", "event": "明天",
        "options": [
            ("买 ATM 跨式", True, "IV 偏低 + 明天事件 + 原油波动大 = 跳空概率 > IV 定价"),
            ("卖出跨式", False, "IV 低时卖方收的权利金太少"),
            ("买入虚值 Put", False, "虚值 Delta 太低，不如 ATM 直接赚方向"),
            ("不做", False, "场景有优势，值得小仓位博"),
        ],
    },
    {
        "desc": "300ETF IV 处于中位 48%，偏度极端（Put IV >> Call IV），无近期事件",
        "iv": "中等", "event": "无",
        "options": [
            ("买入 Call 价差（赌恐慌消退）", True, "偏度极端会回归，Put 溢价高 → 卖出 Put 价差 + 买 Call 价差"),
            ("买入跨式", False, "IV 不高不低，没事件驱动，跨式不值得"),
            ("卖出虚值 Put", False, "偏度极端说明市场还在恐慌，裸卖 Put 有尾部风险"),
            ("不做", False, "偏度极端是明确的套利信号"),
        ],
    },
    {
        "desc": "玉米 IV 处于中位 60%，基本面：美国中西部严重干旱预警，作物优良率连续 3 周下降",
        "iv": "中等", "event": "持续天气",
        "options": [
            ("买虚值 Call（赌减产涨价的尾部风险）", True, "基本面恶化 + 天气持续 = 上涨的概率和幅度都在累积"),
            ("卖出 Put 价差（赌不跌）", False, "天气风险下，尾部事件概率上升，卖方不利"),
            ("买跨式", False, "方向偏向上涨而非双向，Call 更直接"),
            ("不做", False, "基本面矛盾积累中，机会在酝酿"),
        ],
    },
    {
        "desc": "沪金 IV 处于 88% 分位，美联储 FOMC 决议明天凌晨",
        "iv": "极高", "event": "明天",
        "options": [
            ("会前买入跨式", False, "IV 已经很高，市场已经把波动预期定价进去了，即使跳空也不一定赚"),
            ("会前卖出跨式", False, "会议结果不可预测，裸卖有黑天鹅风险"),
            ("不做：IV 高 + 事件不透明 = 怎么做都没有优势", True, "两个方向的优势互相抵消。等待是最佳策略。"),
            ("买方向性期权赌鸽派", False, "方向赌博没有统计优势"),
        ],
    },
    {
        "desc": "甲醇 IV 处于 18% 分位（极低），无近期事件，价格在区间底部横盘 2 周",
        "iv": "极低", "event": "无",
        "options": [
            ("买 ATM Call（赌低 IV + 底部突破）", True, "IV 极低 + 区间底部 = 期权便宜 + 反弹可能，赔率高"),
            ("卖出 Put 价差", False, "IV 低时卖方收的权利金太少"),
            ("买跨式", False, "无事件驱动，跨式浪费 Theta"),
            ("不做", False, "虽然胜率不确定，但赔率有利"),
        ],
    },
]


def run_drill_c(quick=False):
    """训练 C：天气→策略匹配"""
    print(f"\n{'─'*60}")
    print(f"  训练 C — 天气→策略")
    print(f"  规则：看市场场景，5 秒内选最佳策略（单选）")
    print(f"  目标：正确率 > 85%")
    print(f"{'─'*60}")

    n_rounds = 3 if quick else 10
    score = 0
    total_time = 0
    correct = 0

    for round_num in range(1, n_rounds + 1):
        scenario = random.choice(SCENARIOS_C)
        random.shuffle(scenario["options"])

        print(f"\n  [{round_num}/{n_rounds}]")
        print(f"  📍 {scenario['desc']}")
        print(f"  IV 水平: {scenario['iv']}  │  事件: {scenario['event']}")
        print()
        for j, (opt_text, _, _) in enumerate(scenario["options"], 1):
            print(f"    {j}. {opt_text}")

        t_start = time.time()
        try:
            choice = int(input(f"  → 选哪个 (1-4): ").strip())
        except ValueError:
            choice = 0
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。已保存当前进度。")
            return
        elapsed = (time.time() - t_start) * 1000
        total_time += elapsed

        _, is_correct, explanation = scenario["options"][choice - 1] if 1 <= choice <= 4 else ("", False, "")

        if is_correct:
            correct += 1
            if elapsed < 5000:
                score += 3
            elif elapsed < 8000:
                score += 2
            else:
                score += 1
            print(f"  ✅ {elapsed/1000:.1f}s  {explanation}")
        else:
            # 找到正确答案的说明
            correct_expl = [o[2] for o in scenario["options"] if o[1]][0]
            print(f"  ❌ {elapsed/1000:.1f}s")
            print(f"  📝 {correct_expl}")

    accuracy = correct / n_rounds * 100
    avg_time = total_time / n_rounds
    save_session("C", score, accuracy, avg_time, n_rounds)

    print(f"\n  {'─'*40}")
    print(f"  训练C完成: {correct}/{n_rounds} 正确 ({accuracy:.0f}%)")
    print(f"  平均用时: {avg_time/1000:.1f}s/题  得分: {score}")
    ratings = ["⭐ 策略大师！", "👍 还不错", "📚 再看看分析文档", "🐢 需要加练"]
    idx = 0 if accuracy >= 90 else (1 if accuracy >= 70 else (2 if accuracy >= 50 else 3))
    print(f"  {ratings[idx]}")
    print()


# ═══════════════════════════════════════════
# 训练 D：Greek 场景直觉
# ═══════════════════════════════════════════
# 不再问知识选择题。给持仓 + 市场变化，判断 P&L 和主因 Greek。

SCENARIOS_D = [
    {
        "position": "卖豆粕虚值 Put 价差（卖 P2900 / 买 P2850），到期 25 天",
        "event": "豆粕期货突然跌了 4%，从 2966 跌到 2850",
        "q": "你的 P&L 大概变多少？主因是哪个 Greek？",
        "options": [
            ("浮亏 ¥150-300，主因 Delta + Gamma", True, "卖腿从虚值变平值 → Delta 从 0.15 跳到 0.50 → 浮亏。Gamma 加速了 Delta 变化"),
            ("浮亏 ¥50 以内，影响不大", False, "跌 4% 对虚值价差已经是事件级别"),
            ("浮盈 ¥100+，主因 Vega", False, "急跌时 IV 通常涨（恐慌），Vega 负 = 亏钱，不是赚钱"),
            ("浮亏 ¥500+，主因 Theta", False, "Theta 是每天慢慢赚的，不会造成急性亏损"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖玉米 Call 价差（卖 C2300 / 买 C2340），到期 30 天",
        "event": "USDA 报告利多，玉米期货跳涨 3% 到 2370",
        "q": "你的卖腿变实值了。现在怎么办？",
        "options": [
            ("立即平仓止损，亏损已到最大附近，等没有意义", True, "卖腿深实值 → 亏损封顶 → 持仓没有恢复空间，保证金还被占用"),
            ("继续持有，等期货跌回来", False, "深实值 Call 只剩内在价值，时间价值几乎为零，不可能跌回来"),
            ("加卖一张更虚的 Call 摊平成本", False, "亏损加仓 = 赌徒行为"),
            ("买入期货对冲 Delta", False, "已经在最大亏损了，对冲没有意义"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖菜粕 Put 价差（卖 P2275 / 买 P2250），到期 8 天，浮盈 ¥60（收了 ¥80）",
        "event": "还有 8 天到期，目前期货在 2310，远高于卖腿行权价",
        "q": "现在要不要提前平仓？",
        "options": [
            ("平仓锁利。赚了 75%，最后 8 天可能 Gamma 暴涨，不值得冒险", True, "到期临近 Gamma 大 + 利润已经拿了大部分。落袋为安。"),
            ("不平。反正快到期了，等归零全赚", False, "最后一周 Gamma 最大，万一暴跌会亏掉之前的浮盈"),
            ("不平。卖了更高行权价，利润更大", False, "这是在追利润，不是管理风险"),
            ("平掉一半", False, "信用价差两条腿，平一半 = 分腿 = 裸卖，不可以"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖豆粕 Put 价差，浮亏 ¥200（最大亏损 ¥350），到期 20 天",
        "event": "IV 突然大幅跳升（Vega 负 = 你亏），但期货没怎么动",
        "q": "亏损的主要来源是什么？该不该平？",
        "options": [
            ("Vega 亏损 + 暂时不平，IV 飙升后会回落，除非快到期", True, "期货没动 = Delta 没亏。IV 跳是暂时的，等均值回归。还剩 20 天够等。"),
            ("Delta 亏损 + 立即平仓", False, "期货没动，Delta 没亏"),
            ("Theta 亏损 + 不平", False, "卖方 Theta 是收益，不是亏损"),
            ("Gamma 亏损 + 平仓", False, "期货没动 → Gamma 没触发"),
        ],
        "correct_count": 1,
    },
    {
        "position": "持有菜粕信用价差 + 下周 USDA 报告",
        "event": "USDA 报告前的周五，IV 已经涨了 15%",
        "q": "报告前该不该平掉信用价差？",
        "options": [
            ("平掉。报告可能让 IV 继续涨或期货跳空。不想赌事件。", True, "信用价差 = 卖波动率。事件前平仓 = 不赌。等报告后 IV 回落再进。"),
            ("不平。信用价差封顶亏损，不怕", False, "封顶亏损不代表可以不考虑机会成本。保证金会在浮亏中被多占很久。"),
            ("加仓。IV 高是卖方好时机", False, "事件前 IV 高是对的——但事件后可能更高。只有事件后才确定 IV 是高点。"),
            ("不动。反正到期还早", False, "这是主动忽视风险，不是管理风险"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖玉米虚值 Put 价差，明天到期，期货离卖腿只差 0.5%",
        "event": "最后一天，期货在卖腿行权价附近徘徊",
        "q": "Gamma 最大的时刻。你该怎么做？",
        "options": [
            ("立即平仓。最后一天 Gamma 是平时的 10 倍+，0.5% 的移动就会造成巨大 P&L 跳动", True, "临到期 Gamma 爆炸。离行权价这么近 = 每一跳都是赌博。平掉。"),
            ("继续持有，等明天自动到期", False, "最后一天的 Gamma 风险不值得用一天的 Theta 去换"),
            ("买入期货对冲", False, "最后一天 Delta 变化太快，对冲跟不上"),
            ("什么都不做", False, "这是最危险的时刻，必须主动管理"),
        ],
        "correct_count": 1,
    },
    # ── Delta 方向 × 虚值/平值/实值 ──
    {
        "position": "卖出豆粕深度虚值 Put 价差（Delta -0.12），到期 30 天",
        "event": "豆粕期货从 2960 涨到 3020（+2%），你的卖腿离实值更远了",
        "q": "Delta 在这里的作用是什么？",
        "options": [
            ("Delta 变小 = 方向风险降低，是好事", True, "虚值 Put 的 Delta 随标的价格上涨而减小（绝对值趋向 0），你的方向性风险在降低"),
            ("Delta 变大 = 浮亏在扩大", False, "方向反了——标的上涨对 Put 卖方有利"),
            ("Delta 不受影响，只跟时间有关", False, "Delta 是标的价敏感度，不是时间衰减"),
            ("应该立即加仓", False, "浮盈扩大不代表应该加仓——事件前不加码"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖出玉米平值 Call 价差（Delta -0.48），到期 15 天",
        "event": "玉米期货从 2320 涨到 2350（+1.3%），你的卖腿从平值变轻度实值",
        "q": "Delta 变化意味着什么？",
        "options": [
            ("Delta 从 -0.48 降到 -0.65，方向风险加大", True, "标的上涨 → 实值 Call 的 Delta 从 0.5→0.65，卖方 Delta 负更多，浮亏加速"),
            ("Delta 不变，平值期权最稳定", False, "平值 Delta 在 0.5 附近，一旦变化很快"),
            ("Delta 变大是好事，意味着赚钱", False, "卖方的 Delta 变负更多 = 亏更多"),
            ("平仓止损，已经到最大亏损了", False, "接近平值 = 浮亏在扩大，但不等于该平——除非触发近值规则"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入棉花实值 Put（Delta -0.75），到期 40 天",
        "event": "棉花期货从 16100 跌到 15800（-1.9%），方向对了",
        "q": "Delta 的变化如何影响你的盈利？",
        "options": [
            ("Delta 从 -0.75 趋向 -1.0，盈利加速", True, "标的下跌 → 实值 Put Delta 绝对值增大，你的方向盈利在加速"),
            ("Delta 从 -0.75 趋向 -0.5，盈利减速", False, "方向反了"),
            ("Gamma 为负拖累你的利润", False, "买方 Gamma 为正，反而在加速盈利"),
            ("Delta 的变化不会影响已经赚到的钱", False, "Delta 的变化直接影响期权价格=你的 P&L"),
        ],
        "correct_count": 1,
    },
    # ── Gamma × 近到期/远到期/末日轮 ──
    {
        "position": "卖出豆粕 Put 价差，到期还有 3 天，卖腿离期货 2.5%",
        "event": "只剩 3 天了，Gamma 在快速上升",
        "q": "卖方负 Gamma 在到期前最危险的是什么？",
        "options": [
            ("Delta 会加速跳变，一旦不利方向会快速亏损", True, "到期前 Gamma 极大，标的动一两个点 Delta 可能从 -0.2 跳到 -0.6"),
            ("Theta 每天扣的更多了，浮盈缩水", False, "Theta 也大，但 Gamma 的风险 > Theta 的收益"),
            ("IV 会暴涨导致 Vega 亏钱", False, "到期只剩3天，Vega 已经很小了"),
            ("风险不大了，因为最大亏损封顶了", False, "封顶亏损保护还在，但被Gamma加速时实际亏损可能超过预期"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入豆粕远月 Call（Gamma 很小），到期 90 天",
        "event": "豆粕期货缓慢上涨 1%，持续了 5 天",
        "q": "远月 Call 的 Gamma 很小——这意味着什么？",
        "options": [
            ("价格缓慢上涨时，Delta 几乎不变，盈利线性增长", True, "远月 Gamma 近零，Delta 不会加速——你赚的是 Delta 的稳定平移，不是 Gamma 加速"),
            ("Gamma 小是坏事，应该换近月期权", False, "远月期权 Theta 也小，适合慢涨行情"),
            ("Gamma 小意味着期权价格不会变", False, "Delta 还在工作，只是加速效应弱"),
            ("买方应该越涨越加仓", False, "慢涨中远月 Call 线性盈利，不需要追"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖出玉米 Call 价差，明天到期，卖腿刚好在平值",
        "event": "末日轮——Gamma 趋近无穷。你在最后一天",
        "q": "负 Gamma 在末日轮该怎么做？",
        "options": [
            ("立即平仓。最后一天的 Gamma 风险不值得用一天的 Theta 去换", True, "到期日 Gamma 爆炸——标的动 0.5% 你的 Delta 可能跳 0.3。Theta 最后一天赚的一旦被跳就赚不回"),
            ("继续持有，等明天自动到期", False, "最后一天的风险/回报不对等"),
            ("加仓对冲", False, "到期日加仓 = 加更多负 Gamma"),
            ("买入期货对冲 Delta", False, "最后一天 Delta 跳太快，对冲跟不上"),
        ],
        "correct_count": 1,
    },
    # ── Theta × 买方/卖方/事件前 ──
    {
        "position": "买入菜粕 ATM 跨式，到期 10 天，IV 正常",
        "event": "还有 10 天到期，期货基本没动",
        "q": "Theta 对买方在做什么？",
        "options": [
            ("每天在扣你的时间价值，两条腿的 Theta 都在亏", True, "买方跨式 = 双倍负 Theta。10 天后如果还不跳，Theta 会吃掉成本的大半"),
            ("Theta 对买方也有利，因为时间越短期权越贵", False, "时间越短期权越便宜不是越贵"),
            ("Thet 的影响很小，可以忽略", False, "还剩 10 天 Theta 已经开始加速，不能忽略"),
            ("应该继续持有到到期", False, "10 天不动的买方跨式 = Theta 在消灭你的本金"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖出 PTA Put 价差，到期 35 天，浮盈 ¥80（收了 ¥265）",
        "event": "持仓 15 天了，Theta 每天都在给你赚",
        "q": "卖方正 Theta 在这个阶段在做什么？",
        "options": [
            ("每天赚一点，35 天后全部归零 = 赚满", True, "正 Theta 是卖方的自动引擎。每天都在往你的账户加微量利润，不需要你做任何事"),
            ("Theta 在加速，快到到期了应该提前平", False, "还有 35 天，Theta 还没加速。现在平浪费"),
            ("Theta 的贡献太小，不必关注", False, "60 笔交易的期望正是靠 Theta 堆起来的"),
            ("应该换到更近月的合约，Theta 更大", False, "近月 Gamma 也大，风险/回报不对等"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入玉米 Call，到期 5 天，下周一 USDA 报告",
        "event": "最后 5 天 + 事件前。Theta 在加速扣你的时间价值",
        "q": "买方在事件前最后几天该怎么想 Theta？",
        "options": [
            ("Theta 扣得很快，但 Gamma 可能爆发。赌的是 Gamma > Theta", True, "事件前买方的逻辑：付加速 Theta 换 Gamma 爆发机会。跳空够大 → Gamma 覆盖 Theta"),
            ("Theta 不大，因为远月期权", False, "还剩5天不是远月"),
            ("应该提前平仓，Theta 太贵了", False, "事件前平仓 = 放弃 Gamma 爆发——事件后才是最佳平仓窗口"),
            ("加仓另一组期权", False, "已经快到期，加仓 = 加更多负 Theta"),
        ],
        "correct_count": 1,
    },
    # ── Vega × IV 高/低/均值回归 ──
    {
        "position": "卖出豆粕 Put 价差，IV 在 88% 分位（极高）",
        "event": "IV 已经在历史极高位了，但还在缓慢下降",
        "q": "你在高位卖出的。Vega 在为你做什么？",
        "options": [
            ("Vega 正在回落 → 你的期权空头在赚钱", True, "IV 从极高位回落是卖方的黄金窗口。Vega 负 + IV 跌 = 双重收益"),
            ("Vega 高位 = 波动率还会涨，应该平仓", False, "IV 极高位反而意味着均值回归概率更大，不是更高"),
            ("Vega 不影响卖方，只影响买方", False, "卖方 Vegas 为负——IV 跌你赚，IV 涨你亏"),
            ("应该在 IV 高位加仓", False, "IV 已在高点，加仓即追顶。等确认回落再加"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入 PTA 宽跨式（OTM Call + OTM Put），IV 在 15% 分位（极低）",
        "event": "IV 在历史低位。下周 EIA 原油报告",
        "q": "低 IV 环境对买方意味着什么？",
        "options": [
            ("IV 低 + 事件催化 = 做多 Vega 的最佳时机", True, "IV 从低位上升的概率大。你花低价买保险，赌 IV 涨+Gamma 跳"),
            ("IV 低说明市场稳定，买方没机会", False, "IV 低意味着买方成本低，而事件可能推高 IV"),
            ("IV 低意味着 Theta 也低，不用急", False, "Theta 和 IV 正相关，低 IV → Theta 也低，买方等得起"),
            ("IV 低 = 期权便宜，应该卖", False, "便宜的时候买方进场才是对的"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖出菜粕 Put 价差，IV 在 55% 分位（正常），但浮亏 ¥90",
        "event": "期货跌了 2%，IV 涨了一点但不是爆炸",
        "q": "浮亏来自 Delta 还是 Vega？该不该平？",
        "options": [
            ("主要是 Delta——期货跌了，卖腿 Delta 负值变大 = 浮亏。IV 没跳，不急着平", True, "Delta 是主要亏损来源。IV 正常波动不是危机"),
            ("主要是 Vega——IV 涨了所以你亏，应该立即平", False, "IV 没跳。Vega 贡献小"),
            ("Delta 和 Vega 各一半", False, "2% 的标的波动对虚值卖腿 = Delta 占主导"),
            ("平仓止损，因为浮亏在扩大", False, "2% 在虚值价差的安全边际内。没触发止损条件"),
        ],
        "correct_count": 1,
    },
]


# 训练 E：虚值信用价差扫描
# ═══════════════════════════════════════════

def run_drill_e(quick=False):
    """训练 E：虚值信用价差 — 找卖腿买腿 + 心算净利"""
    print(f"\n{'─'*60}")
    print(f"  训练 E — 虚值信用价差扫描")
    print(f"  规则：从链面找出能做信用价差的行权价对，算净权利金。")
    print(f"  格式：卖腿行权价,买腿行权价,净权利金  （或'无'）")
    print(f"{'─'*60}")

    n_rounds = 3 if quick else 10
    score = 0
    total_time = 0
    correct = 0

    for round_num in range(1, n_rounds + 1):
        chain = generate_chain_segment()
        # 注入信用价差机会
        cs_pairs = []
        valid_strikes = [(i, chain["strikes"][i], chain["prices"][i])
                         for i in range(len(chain["strikes"]))
                         if chain["prices"][i]["bid"] > 0 and chain["prices"][i]["ask"] > 0
                         and (chain["prices"][i]["ask"] - chain["prices"][i]["bid"]) / chain["prices"][i]["bid"] < 0.10]

        # 随机注入 0-1 个可交易信用价差对（80% 概率，够 2 条合格腿就做）
        if len(valid_strikes) >= 2 and random.random() < 0.8:
            pair_indices = random.sample(valid_strikes, 2)
            pair_indices.sort(key=lambda x: x[0], reverse=True)  # 高行权价在前
            high, low = pair_indices[0], pair_indices[1]
            sell_bid = high[2]["bid"]
            buy_ask = low[2]["ask"]
            strike_width = high[1] - low[1]
            if sell_bid > buy_ask and strike_width <= chain['futures'] * 0.05:
                net = round(sell_bid - buy_ask, 1)
                cs_pairs.append({
                    "sell_strike": high[1], "buy_strike": low[1],
                    "net_premium": net,
                })

        print(f"\n  [{round_num}/{n_rounds}] {chain['product']} 期货≈{chain['futures']}")
        col_fmt = f"  {{:>6}} │ {{:>8}} {{:>8}} {{:>8}}"
        print(col_fmt.format('行权价', 'P买价(bid)', 'P卖价(ask)', '价差%'))
        print(f"  {'─'*6}─┼─{'─'*32}")

        for i, (s, p) in enumerate(zip(chain["strikes"], chain["prices"])):
            bid_str = f"{p['bid']:.2f}" if p['bid'] > 0 else "0.00"
            ask_str = f"{p['ask']:.2f}"
            if p['bid'] > 0 and p['ask'] > 0:
                sp = round((p['ask'] - p['bid']) / p['bid'] * 100, 1)
                flag = " ⚠️" if sp > 15 else ""
                spread_str = f"{sp}%{flag}"
            elif p['bid'] == 0:
                spread_str = "零买价 ❌"
            else:
                spread_str = "—"
            print(col_fmt.format(s, bid_str, ask_str, spread_str))

        print(f"  规则：卖高行权价(bid成交)，买低行权价(ask成交)。净利=卖bid-买ask")
        t_start = time.time()
        try:
            answer = input(f"  → 卖行权价,买行权价,净利（或'无'）: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。")
            return
        elapsed = (time.time() - t_start) * 1000
        total_time += elapsed

        if answer.lower() in ["无", "none", "n", ""]:
            user_pair = None
            user_net = 0
        else:
            parts = answer.replace("，", ",").split(",")
            try:
                user_pair = (int(parts[0]), int(parts[1]))
                user_net = float(parts[2]) if len(parts) >= 3 else 0
            except (ValueError, IndexError):
                user_pair = None
                user_net = 0

        has_cs = len(cs_pairs) > 0
        expected_pair = (cs_pairs[0]["sell_strike"], cs_pairs[0]["buy_strike"]) if has_cs else None
        expected_net = cs_pairs[0]["net_premium"] if has_cs else 0

        pair_ok = user_pair == expected_pair
        net_ok = abs(user_net - expected_net) < 0.15 if has_cs else True

        if not has_cs:
            if user_pair is None:
                correct += 1
                score += 3 if elapsed < 15000 else (2 if elapsed < 25000 else 1)
                print(f"  ✅ 正确！今日无信用价差机会 ({elapsed/1000:.1f}s)")
            else:
                sw = abs(user_pair[0] - user_pair[1])
                if sw > chain['futures'] * 0.05:
                    print(f"  ❌ 行权价间距{sw}点 > 期货{chain['futures']}的5%({int(chain['futures']*0.05)}点)，太大不做")
                else:
                    print(f"  ❌ 误报。今日无合格信用价差机会")
        elif pair_ok and net_ok:
            correct += 1
            score += 3 if elapsed < 20000 else (2 if elapsed < 30000 else 1)
            print(f"  ✅ 全对！卖P{expected_pair[0]}/买P{expected_pair[1]} 净收 ¥{expected_net} ({elapsed/1000:.1f}s)")
        elif pair_ok and not net_ok:
            print(f"  ⚠️ 行权价对正确，但净利算错。你算¥{user_net}，正确¥{expected_net}")
            print(f"     卖bid {cs_pairs[0]['sell_strike']}P, 买ask {cs_pairs[0]['buy_strike']}P")
            score += 1
        else:
            print(f"  ❌ 正确答案：卖P{expected_pair[0]}/买P{expected_pair[1]} 净收 ¥{expected_net}")
            score += 0

        if round_num < n_rounds:
            input(f"  (按回车继续)")

    accuracy = correct / n_rounds * 100
    avg_time = total_time / n_rounds
    save_session("E", score, accuracy, avg_time, n_rounds)

    print(f"\n  {'─'*40}")
    print(f"  训练E完成: {correct}/{n_rounds} 正确 ({accuracy:.0f}%)")
    print(f"  平均用时: {avg_time/1000:.1f}s/题  得分: {score}")
    rating = "⭐ 信用价差猎手！" if accuracy >= 85 else ("👍 继续磨" if accuracy >= 65 else "🐢 多跑几次扫描器")
    print(f"  {rating}")
    print()


# ═══════════════════════════════════════════
# 训练 F：持仓管理
# ═══════════════════════════════════════════

SCENARIOS_F = [
    {
        "position": "卖菜粕 Put 价差（P2275/P2250），净收 ¥80，最大亏损 ¥170，到期 20 天",
        "event": "菜粕期货从 2310 跌到 2285，你的卖腿离实值只剩 10 个点",
        "q": "浮亏在扩大。你该怎么做？",
        "options": [
            ("立即平仓。离行权价太近了，Gamma 开始变大，不值得冒", True, "只剩 10 点 = 0.4%。最后这点空间不能赌，锁亏离场。"),
            ("继续持有。期货没到行权价就不用动", False, "等到了行权价可能已经浮亏翻倍"),
            ("加卖一张看涨期权来对冲", False, "不对路——这是方向风险，不是波动率风险"),
            ("买入期货空单做 Delta 对冲", False, "Layer 2 才学这个。现在分腿加期货会乱"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖玉米 Call 价差（C2320/C2360），净收 ¥100，最大亏损 ¥300，到期 35 天",
        "event": "过去一周期货在 2300-2320 窄幅震荡，你的 Call 卖腿还安全",
        "q": "一切正常。你该做什么？",
        "options": [
            ("什么都不做。策略在按计划跑", True, "没触发止损条件 = 不管。这是持仓管理最难的事——不做。"),
            ("提前平仓锁利", False, "才过一周，Theta 只收了小部分。现在平亏手续费。"),
            ("加仓，多加一组价差", False, "窄幅震荡在卖腿附近 = 随时可能突破，加仓是加大风险"),
            ("每天盯着看几次", False, "盯没问题，但不能因为盯了就乱动"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖豆粕 Put 价差，收 ¥120，最大亏损 ¥380，到期 10 天，目前浮盈 ¥80",
        "event": "还有 10 天到期，IV 突然从 50% 分位跌到 20% 分位",
        "q": "IV 跌了 = Vega 让你赚了钱。现在该不该提前平仓？",
        "options": [
            ("平仓。10 天风险/回报不对等，赚了 67% 差不多了", True, "IV 回落是卖方最想看到的。已经赚了 2/3，最后几天 Gamma 大，不平可能吐回去。"),
            ("不平。等到期全赚", False, "最后 10 天 Gamma 最大，如果期货动一下浮盈可能蒸发"),
            ("不平。再卖一组价差", False, "IV 已经在低位了 = 不适合卖方进场"),
            ("平一半", False, "信用价差不能分腿平"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖豆粕虚值 Put 价差，刚开仓 3 天",
        "event": "期货在卖腿上方 3% 处正常运行，浮盈 ¥25",
        "q": "一切正常。但你觉得浮盈太少，想换一个更近行权价的价差来多赚。该换吗？",
        "options": [
            ("不换。频繁换仓 = 手续费吃掉利润。这个位置是安全的，等到期", True, "持仓管理的头号错误：因为无聊而改变正在赚钱的策略。"),
            ("换。更近行权价 = 更多权利金", False, "更近 = 更高 Delta = 更高风险 = 不是同一个策略了"),
            ("平掉一半，另一半留着", False, "又是分腿——做不到"),
            ("加仓另一组更近的价差", False, "可以，但不该以当前盈利为理由"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖菜粕 Put 价差 + 卖玉米 Put 价差，两个同时持仓",
        "event": "USDA 报告大幅利好，豆粕玉米双双暴涨。两个持仓都浮盈 ¥100+",
        "q": "两个持仓都在赚钱。你该做什么？",
        "options": [
            ("都放着。报告利好 = 方向在有利的一边。到期归零就行", False, "主要利润来自事件驱动的 IV 崩溃（Vega），已经兑现。剩下那点 Theta 不够补偿隔夜风险。"),
            ("平掉，落袋为安", True, "IV 崩掉后 Vega 已赚完。剩下的时间价值不够厚，机会成本不值得等。落袋 + 解放保证金。"),
            ("加仓第三组价差", False, "报告刚过 IV 在回落，卖家可以等确认后加仓——但不是因为涨了要追"),
            ("把止损收紧", False, "信用价差最大亏损是封顶的，收紧止损在这没意义"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖甲醇 Put 价差，刚开仓 2 天浮盈 ¥25",
        "event": "期货从 2400 跌到 2385。卖腿 P2375 离期货只差 10 点（0.4%）",
        "q": "卖腿突然离实值很近了。该不该平？",
        "options": [
            ("平。10 点差一天就能穿。现在小亏比明天大亏好", True, "卖腿 OTM<1%+期货还在跌 = 不做方向判断，平"),
            ("不平。还没到行权价", False, "到了就来不及了"),
            ("加仓一组对冲", False, "在风险上叠风险"),
            ("什么都不做，反正封顶了", False, "Gamma 正在加速，不是正常持有"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖 PTAPut 价差，OTM 0.7% 进场，现已深实值",
        "event": "三天跌 5.5%。亏损 ¥200/235，接近最大亏损",
        "q": "已到极限。继续等还是平？",
        "options": [
            ("平。亏到头了，继续等只锁保证金", True, "深实值无 Theta。释放保证金做新交易"),
            ("不平。万一反弹", False, "深实值反弹也回不到盈利区"),
            ("等到期，Theta 在赚", False, "深实值 Theta 近零，时间价值蒸发完了"),
            ("加仓反向价差", False, "亏损加仓不是对冲"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入玉米跨式，USDA 前 D-1 进场，成本 ¥675",
        "event": "报告后期货只涨 2 点。IV 微跌。浮亏 ¥80",
        "q": "Gamma 没触发，Vega 在亏。该不该平？",
        "options": [
            ("平。事件落地+IV跌+期货不动 = 三个平仓信号", True, "不确定性解除 = IV 继续跌。持仓每天亏 Theta"),
            ("不平。也许明天有行情", False, "在赌，不是在管理"),
            ("平掉一腿留一腿", False, "分腿=变策略性质"),
            ("亏损不大，再等等", False, "IV 还在跌，越等越亏"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖菜粕 Put 价差，持有 10 天浮盈 ¥50（收 ¥80）",
        "event": "还剩 15 天，期货在卖腿上方 3%，正常",
        "q": "赚了 62%。该不该提前平？",
        "options": [
            ("可平可不平。都合理", True, "利润已拿多数+安全距离够。平=释放保证金，不平=吃剩余 Theta"),
            ("必须平", False, "没有必须——持仓安全+时间有利"),
            ("加仓同款", False, "同品种加仓=风险集中"),
            ("平一半", False, "信用价差不能分腿"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖玉米 Put 信用价差（P2280/P2260），期货 2318",
        "event": "6 天后期货跌到 2294。卖腿只差 14 点（0.6%）",
        "q": "卖腿快被顶到。Gamma 在工作。怎么办？",
        "options": [
            ("平。14 点一天能穿，现在亏 ¥20 走", True, "近值+期货在跌+Gamma加速。看现在，别看当初"),
            ("不平。当初 OTM 2%，没问题", False, "当初条件不成立了。持仓管理看现在"),
            ("买期货对冲", False, "L2 才学。近值强对冲容易更乱"),
            ("不平。反正最大亏 ¥110", False, "明明可以 ¥20 走，别等 ¥110"),
        ],
        "correct_count": 1,
    },
]


def run_drill_f(quick=False):
    """训练 F：持仓管理 — 浮亏/浮盈时该不该平"""
    print(f"\n{'─'*60}")
    print(f"  训练 F — 持仓管理")
    print(f"  规则：你在持有信用价差。给场景，判断该不该动。")
    print(f"  目标：正确率 > 80%")
    print(f"{'─'*60}")

    n_rounds = 3 if quick else 10
    score = 0
    total_time = 0
    correct = 0

    for round_num in range(1, n_rounds + 1):
        scenario = random.choice(SCENARIOS_F)
        random.shuffle(scenario["options"])

        print(f"\n  [{round_num}/{n_rounds}]")
        print(f"  📍 持有: {scenario['position']}")
        print(f"  ⚡ 发生: {scenario['event']}")
        print(f"  ❓ {scenario['q']}")
        print(f"  （选{scenario['correct_count']}个正确答案）")
        print()
        for j, (opt_text, _, _) in enumerate(scenario["options"], 1):
            print(f"    {j}. {opt_text}")

        t_start = time.time()
        try:
            answers = input(f"  → 选哪几个 (数字，逗号分隔): ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。已保存当前进度。")
            return
        elapsed = (time.time() - t_start) * 1000
        total_time += elapsed

        try:
            user_choices = [int(x.strip()) for x in answers.split(",") if x.strip()]
        except ValueError:
            user_choices = []

        correct_choices = [j for j, (_, is_c, _) in enumerate(scenario["options"], 1) if is_c]
        matched = len(set(user_choices) & set(correct_choices))
        extra = len(set(user_choices) - set(correct_choices))
        missed = len(set(correct_choices) - set(user_choices))

        if matched == len(correct_choices) and extra == 0:
            correct += 1
            if elapsed < 8000:
                score += 3
            elif elapsed < 15000:
                score += 2
            else:
                score += 1
            print(f"  ✅ 完美！{elapsed/1000:.1f}s")
        elif matched > 0:
            print(f"  ⚠️ 部分正确 ({elapsed/1000:.1f}s)")
            if missed > 0:
                print(f"     漏了: {', '.join(str(c) for c in correct_choices if c not in user_choices)}")
            score += 1
        else:
            print(f"  ❌ ({elapsed/1000:.1f}s) 正确答案: {', '.join(str(c) for c in correct_choices)}")

    accuracy = correct / n_rounds * 100
    avg_time = total_time / n_rounds
    save_session("F", score, accuracy, avg_time, n_rounds)

    print(f"\n  {'─'*40}")
    print(f"  训练F完成: {correct}/{n_rounds} 正确 ({accuracy:.0f}%)")
    print(f"  平均用时: {avg_time/1000:.1f}s/题  得分: {score}")
    rating = "⚔️ 冷血持仓管理！" if accuracy >= 80 else ("👍 有判断意识" if accuracy >= 65 else "🐢 多复盘实盘持仓")
    print(f"  {rating}")
    print()


# ═══════════════════════════════════════════
# 主菜单
# ═══════════════════════════════════════════

def run_drill_g(quick=False):
    """训练 G：腿位判断 — 虚值/近值/实值"""
    print(f"\n{'─'*60}")
    print(f"  训练 G — 腿位判断")
    print(f"  规则：看期货现价+卖腿行权价，判断能不能做信用价差")
    print(f"  虚做 (OTM>2%) | 近平 (平仓离场) | 实不做 (ITM)")
    print(f"  目标：3秒/题，正确率>90%")
    print(f"{'─'*60}")

    n_rounds = 5 if quick else 15
    score = 0; total_time = 0; correct = 0
    labels = {"虚": "✅虚值可做", "近": "⚠️近值平仓", "实": "❌实值不做"}

    for r in range(1, n_rounds + 1):
        futures = random.randint(2200, 5800)
        sell_strike = futures + random.choice([-300, -200, -100, -50, -30, 0, 30, 50, 100, 200])
        spread_w = random.choice([20, 50, 100])
        buy_strike = sell_strike - spread_w if sell_strike > futures else sell_strike - spread_w

        pct_otm = (futures - sell_strike) / futures * 100
        if pct_otm > 2:
            expected = "虚"
        elif pct_otm >= 0:
            expected = "近"
        else:
            expected = "实"

        print(f"\n  [{r}/{n_rounds}]  期货={futures}  卖腿={sell_strike}  买腿={buy_strike}")
        t0 = time.time()
        try:
            u = input(f"  → 虚/近/实 ?: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。")
            return
        el = (time.time() - t0) * 1000; total_time += el
        if u == expected:
            correct += 1; score += 3 if el < 3000 else (2 if el < 6000 else 1)
            print(f"  ✅ {el/1000:.1f}s  {labels[expected]}  OTM={pct_otm:.1f}%")
        else:
            print(f"  ❌ {el/1000:.1f}s  你选{u}  实际{labels[expected]}  OTM={pct_otm:.1f}%")

    acc = correct / n_rounds * 100; avg = total_time / n_rounds
    save_session("G", score, acc, avg, n_rounds)
    print(f"\n  {'─'*40}")
    print(f"  训练G完成: {correct}/{n_rounds} 正确 ({acc:.0f}%)")
    print(f"  平均用时: {avg/1000:.1f}s/题  得分: {score}")
    print(f"  {'⚡ 腿位大师！' if acc >= 90 else ('👍 继续磨' if acc >= 70 else '🐢 菜粕教训牢记')}")
    print()


def run_drill_d(quick=False):
    """训练 D：Greek 场景直觉"""
    print(f"\n{'─'*60}")
    print(f"  训练 D — Greek 场景直觉")
    print(f"  规则：看持仓+事件，判断哪个 Greek 在驱动 P&L")
    print(f"  15 题题库随机抽 10 题。可能有多个正确答案")
    print(f"{'─'*60}")

    n_rounds = 5 if quick else 10
    score = 0; total_time = 0; correct = 0
    scenarios = random.sample(SCENARIOS_D, min(n_rounds, len(SCENARIOS_D)))

    for round_num, scenario in enumerate(scenarios, 1):
        opts = scenario["options"][:]
        random.shuffle(opts)

        print(f"\n  [{round_num}/{n_rounds}]")
        print(f"  📍 头寸: {scenario['position']}")
        if scenario.get('event'):
            print(f"  ⚡ 事件: {scenario['event']}")
        print(f"  ❓ {scenario['q']}")
        print(f"  （选{scenario['correct_count']}个正确答案）")
        print()
        for j, (opt_text, _, _) in enumerate(opts, 1):
            print(f"    {j}. {opt_text}")

        t0 = time.time()
        try:
            answers = input(f"  → 选哪几个 (数字，逗号分隔): ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。")
            return
        el = (time.time() - t0) * 1000; total_time += el

        try:
            user_choices = [int(x.strip()) for x in answers.split(",") if x.strip()]
        except ValueError:
            user_choices = []

        correct_choices = [j for j, (_, is_c, _) in enumerate(opts, 1) if is_c]
        matched = len(set(user_choices) & set(correct_choices))
        extra = len(set(user_choices) - set(correct_choices))
        missed = len(set(correct_choices) - set(user_choices))

        if matched == len(correct_choices) and extra == 0:
            correct += 1
            score += 3 if el < 8000 else (2 if el < 15000 else 1)
            print(f"  ✅ 完美！{el/1000:.1f}s")
        elif matched > 0:
            print(f"  ⚠️ 部分正确 ({el/1000:.1f}s)")
            if missed: print(f"     漏了")
            score += 1
        else:
            print(f"  ❌ ({el/1000:.1f}s)")

    acc = correct / n_rounds * 100; avg = total_time / n_rounds
    save_session("D", score, acc, avg, n_rounds)
    print(f"\n  {'─'*40}")
    print(f"  训练D完成: {correct}/{n_rounds} 正确 ({acc:.0f}%)")
    print(f"  平均用时: {avg/1000:.1f}s/题  得分: {score}")
    rating = "⭐ Greek 大师！" if acc >= 85 else ("👍 基础扎实" if acc >= 65 else "📚 重看第6章")
    print(f"  {rating}")
    print()


def today_recommendation():
    dow = date.today().weekday()  # 0=Mon
    return {0: "A", 1: "B", 2: "C", 3: "A", 4: "F", 5: "C", 6: "D"}[dow]


def main():
    parser = argparse.ArgumentParser(description="期权交易速度训练系统")
    parser.add_argument('module', nargs='?', default=None,
                        help='训练模块: A/B/C/D/auto/stats')
    parser.add_argument('--quick', action='store_true', help='快速模式: 题量缩减为5题')
    args = parser.parse_args()

    module = args.module
    if module is None or module == "auto":
        module = today_recommendation()
        names = {"A": "链面扫异常", "B": "价差判断", "C": "天气→策略", "D": "Greek场景", "E": "信用价差扫描", "F": "持仓管理", "G": "腿位判断"}
        print(f"\n  📅 今日推荐: 训练 {module} — {names[module]}")
        if args.quick:
            print(f"  ⚡ 快速模式(5题)")

    if module == "stats":
        show_progress()
        return

    if module == "A":
        run_drill_a(quick=args.quick)
    elif module == "B":
        run_drill_b(quick=args.quick)
    elif module == "C":
        run_drill_c(quick=args.quick)
    elif module == "D":
        run_drill_d(quick=args.quick)
    elif module == "E":
        run_drill_e(quick=args.quick)
    elif module == "F":
        run_drill_f(quick=args.quick)
    elif module == "G":
        run_drill_g(quick=args.quick)
    else:
        print(f"未知模块: {module}。请用 A/B/C/D/E/F/G/stats")
        return

    # 训练后显示简要统计
    h = load_history()
    recent = [s for s in h["sessions"] if s["module"] == module]
    if len(recent) >= 2:
        last_two = recent[-2:]
        print(f"  对比上次: 正确率 {last_two[0]['accuracy']:.0f}% → {last_two[1]['accuracy']:.0f}%  |  "
              f"速度 {last_two[0]['avg_time_ms']/1000:.1f}s → {last_two[1]['avg_time_ms']/1000:.1f}s")


if __name__ == '__main__':
    main()
