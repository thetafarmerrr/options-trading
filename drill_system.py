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
STATE_DIR = SCRIPT_DIR / "drill_state"
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
    modules = ["A", "B", "C", "D"]
    module_names = {"A": "链面扫异常", "B": "心算价差", "C": "天气→策略", "D": "Greek直觉"}

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
        # 真实市场：bid/ask 随机跳动
        theo += random.uniform(-0.15, 0.15)
        bid = round(theo * random.uniform(0.85, 0.96), 2)
        ask = round(theo * random.uniform(1.04, 1.15), 2)
        # 随机零买价
        otm_pct = (fut - strikes[i]) / fut
        if otm_pct > 0.25 and random.random() < 0.08:
            bid = 0.0
        prices.append({
            "theo": max(prices[i-1]["theo"] + 0.01, theo),
            "bid": max(0.01, bid) if bid > 0 else 0.0,
            "ask": ask,
        })

    # 注入 0-3 个混合异常
    tradeable_strikes = []
    all_anomalies = []
    n_anomalies = random.randint(0, 3)
    candidates = list(range(2, len(strikes) - 2))
    random.shuffle(candidates)

    for idx in candidates[:n_anomalies]:
        anomaly_type = random.choice(["inversion_tradeable", "inversion_untradeable",
                                       "zero_bid", "wide_spread"])
        if anomaly_type == "inversion_tradeable":
            prices[idx]["theo"] = round(prices[idx-1]["theo"] * random.uniform(0.5, 0.8), 2)
            prices[idx]["bid"] = round(prices[idx]["theo"] * random.uniform(0.88, 0.94), 2)
            prices[idx]["ask"] = round(prices[idx]["bid"] * random.uniform(1.03, 1.10), 2)
            tradeable_strikes.append(strikes[idx])
            all_anomalies.append({"strike": strikes[idx], "type": "可交易倒挂",
                                   "detail": f"行权价{strikes[idx]}：更高但更便宜，买价{prices[idx]['bid']:.2f}存在，价差合理"})
        elif anomaly_type == "inversion_untradeable":
            prices[idx]["theo"] = round(prices[idx-1]["theo"] * random.uniform(0.5, 0.8), 2)
            if random.random() < 0.5:
                prices[idx]["bid"] = 0.0
                prices[idx]["ask"] = round(prices[idx]["theo"] * 1.5, 2)
                detail = f"行权价{strikes[idx]}：价格倒挂了但买价为零 → 无法平仓，不能做"
            else:
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
                spread_str = f"{round((p['ask'] - p['bid']) / p['bid'] * 100, 1)}%"
            elif p['bid'] == 0:
                spread_str = "零买价"
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
    """训练 B：心算价差百分比"""
    print(f"\n{'─'*60}")
    print(f"  训练 B — 心算价差")
    print(f"  规则：看 bid/ask，心算价差百分比，输入答案")
    print(f"  公式：(卖价-买价)÷买价×100。目标：3秒/题，误差<2%，正确率>90%")
    print(f"{'─'*60}")

    n_rounds = 5 if quick else 25
    score = 0
    total_time = 0
    correct = 0

    for round_num in range(1, n_rounds + 1):
        # 生成逼真的 bid/ask 对
        scenario_type = random.choice(["deep_otm", "atm", "itm", "wide", "tight"])
        if scenario_type == "deep_otm":
            bid = round(random.uniform(0.10, 2.00), 2)
            ask = round(bid * random.uniform(1.10, 2.50), 2)
        elif scenario_type == "atm":
            bid = round(random.uniform(5.00, 50.00), 2)
            ask = round(bid * random.uniform(1.01, 1.10), 2)
        elif scenario_type == "itm":
            bid = round(random.uniform(30.00, 200.00), 2)
            ask = round(bid * random.uniform(1.01, 1.08), 2)
        elif scenario_type == "wide":
            bid = round(random.uniform(0.20, 3.00), 2)
            ask = round(bid * random.uniform(2.00, 5.00), 2)
        else:
            bid = round(random.uniform(1.00, 20.00), 2)
            ask = round(bid * random.uniform(1.02, 1.06), 2)

        actual_spread = round((ask - bid) / bid * 100, 1)

        print(f"\n  [{round_num}/{n_rounds}]  买价={bid:.2f}  卖价={ask:.2f}")

        t_start = time.time()
        try:
            user_answer = float(input(f"  → 价差 = ?%: ").strip())
        except ValueError:
            user_answer = -999
        except (EOFError, KeyboardInterrupt):
            print(f"\n  训练中断。已保存当前进度。")
            return
        elapsed = (time.time() - t_start) * 1000
        total_time += elapsed

        error = abs(user_answer - actual_spread)
        if error <= 2.0:
            correct += 1
            # 速度加分
            if elapsed < 3000:
                score += 3
            elif elapsed < 6000:
                score += 2
            else:
                score += 1
            print(f"  ✅ {elapsed/1000:.1f}s  你:{user_answer}%  实际:{actual_spread}%  (误差{error:.1f}%)")
        else:
            print(f"  ❌ {elapsed/1000:.1f}s  你:{user_answer}%  实际:{actual_spread}%  (误差{error:.1f}%，超过2%)")

    accuracy = correct / n_rounds * 100
    avg_time = total_time / n_rounds
    save_session("B", score, accuracy, avg_time, n_rounds)

    print(f"\n  {'─'*40}")
    print(f"  训练B完成: {correct}/{n_rounds} 正确 ({accuracy:.0f}%)")
    print(f"  平均用时: {avg_time/1000:.1f}s/题  得分: {score}")
    rating = "⭐ 心算天才！" if avg_time < 3000 else ("👍 不错" if avg_time < 6000 else "🐢 多练，价差判断是赚钱的关键")
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
# 训练 D：Greek 直觉
# ═══════════════════════════════════════════

SCENARIOS_D = [
    {
        "position": "买入 ATM Call，到期还有 30 天",
        "q": "最有利的 Greek 是什么？",
        "options": [
            ("Delta — 方向对了就赚钱", False, "Delta 只是 1:1 平移，真正的加速器是 Gamma"),
            ("Gamma — 方向对了越赚越快", True, "ATM 期权 Gamma 最大，标的涨 1 块 → Delta 也变大 → 利润加速"),
            ("Theta — 时间价值增长", False, "买方 Theta 每天在亏钱"),
            ("Vega — 波动率上升赚钱", True, "ATM Vega 也大，IV 上升时直接拉动期权价格"),
        ],
        "correct_count": 2,
    },
    {
        "position": "卖出深度虚值 Put，到期还有 5 天",
        "q": "最危险的 Greek 是什么？",
        "options": [
            ("Delta — 方向风险", False, "虚值 Put 的 Delta 很小（0.05-0.15），方向不致命"),
            ("Gamma — 快速变实值后 Delta 爆炸", True, "到期临近 + 虚值 = Gamma 极高，一旦方向不利，期权迅速变实值，亏损非线性放大"),
            ("Theta — 时间损耗太快", False, "卖方 Theta 是朋友"),
            ("Vega — IV 突然飙升", False, "只剩5天，Vega 已经很小了"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入深度虚值 Put，到期还有 60 天",
        "q": "最大的敌人是什么？",
        "options": [
            ("Theta — 每天蒸发时间价值", True, "虽然远月 Theta 小，但虚值期权没有内在价值 = 全由时间价值组成 = Theta 是最大敌人"),
            ("Gamma — 波动加速", False, "远月虚值 Gamma 很小，加速效应弱"),
            ("Delta — 方向性亏损", False, "虚值 Delta 小，标的微涨微跌影响不大"),
            ("Rho — 利率变动", False, "商品期权短期利率影响可忽略"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖出 ATM 跨式（Call+Put），到期还有 14 天",
        "q": "你赌的是什么？",
        "options": [
            ("标的窄幅震荡 + IV 下跌", True, "跨式卖方赚两份 Theta + Vega 回落，需要标的不动 + 波动率下降"),
            ("标的单边暴涨", False, "卖方最怕这个"),
            ("标的暴跌", False, "另一腿 Put 也会亏"),
            ("利率大幅变动", False, "Rho 不是主要风险"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入宽跨式（OTM Call + OTM Put），到期还有 3 天，下周 USDA 报告",
        "q": "持有到期最可能的结果？",
        "options": [
            ("两腿都归零，亏光权利金", True, "宽跨式两腿都虚值 + 只剩3天 = 大概率归零。除非报告造成远超预期的跳空。"),
            ("至少一腿赚钱", False, "两腿都是虚值，都需大跳空才变实值。3天时间太短。"),
            ("Theta 每天补偿权利金", False, "买方 Theta 是负的"),
            ("Delta 对冲自动获利", False, "未做 Delta 对冲"),
        ],
        "correct_count": 1,
    },
    {
        "position": "买入远月 ITM Put（Delta -0.85），作为期货空单替代品",
        "q": "相比直接做空期货，优势是？",
        "options": [
            ("亏损上限锁定在权利金", True, "买方最大亏损 = 权利金，期货理论上无上限（对空单来说也无下限）"),
            ("手续费更低", False, "期权手续费通常更高"),
            ("杠杆更高", False, "ITM 期权的杠杆通常低于期货"),
            ("不受时间损耗影响", False, "即使 ITM 也有 Theta，只是较小"),
        ],
        "correct_count": 1,
    },
    {
        "position": "卖出 NTM（近值）Put，同时买入更低行权价 Put（Bull Put Spread），到期 30 天",
        "q": "和裸卖 Put 相比，这个结构有什么不同？",
        "options": [
            ("最大亏损封顶了", True, "牛市看跌价差 = 裸卖 Put 的最大亏损被买入的更低行权 Put 截断了"),
            ("胜率提高了", True, "盈亏平衡点更低（净收入降低了成本基础）→ 胜率确实更高"),
            ("Vega 敞口更大", False, "两腿 Vega 对冲，净 Vega 变小"),
            ("不需要保证金", False, "仍需保证金"),
        ],
        "correct_count": 2,
    },
    {
        "position": "持有期货多头 + 买入 OTM Put 保护",
        "q": "这个组合本质上等于什么？",
        "options": [
            ("买入 Call（合成看涨）", True, "期货多 + 买 Put = 买 Call（Put-Call Parity）。锁了下方风险 + 保留上方空间。"),
            ("卖出 Put", False, "方向反了"),
            ("卖出跨式", False, "完全不同的结构"),
            ("裸做多期货", False, "多了 Put 保护后变成了合成期权"),
        ],
        "correct_count": 1,
    },
]


def run_drill_d(quick=False):
    """训练 D：Greek 直觉"""
    print(f"\n{'─'*60}")
    print(f"  训练 D — Greek 直觉")
    print(f"  规则：看期权头寸场景，回答 Greek 相关问题")
    print(f"  可能有多个正确答案。目标：正确率 > 85%")
    print(f"{'─'*60}")

    n_rounds = 3 if quick else 12
    score = 0
    total_time = 0
    correct = 0

    for round_num in range(1, n_rounds + 1):
        scenario = random.choice(SCENARIOS_D)
        random.shuffle(scenario["options"])

        print(f"\n  [{round_num}/{n_rounds}]")
        print(f"  📍 头寸: {scenario['position']}")
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

        # 解析答案
        try:
            user_choices = [int(x.strip()) for x in answers.split(",") if x.strip()]
        except ValueError:
            user_choices = []

        correct_choices = [j for j, (_, is_c, _) in enumerate(scenario["options"], 1) if is_c]

        # 部分正确给部分分
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
            if extra > 0:
                print(f"     多了: {', '.join(str(c) for c in user_choices if c not in correct_choices)}")
            score += 1
        else:
            print(f"  ❌ ({elapsed/1000:.1f}s) 正确答案: {', '.join(str(c) for c in correct_choices)}")
            for j, (t, _, _) in enumerate(scenario["options"], 1):
                if j in correct_choices:
                    print(f"     {j}. {t}")

    accuracy = correct / n_rounds * 100
    avg_time = total_time / n_rounds
    save_session("D", score, accuracy, avg_time, n_rounds)

    print(f"\n  {'─'*40}")
    print(f"  训练D完成: {correct}/{n_rounds} 全对 ({accuracy:.0f}%)")
    print(f"  平均用时: {avg_time/1000:.1f}s/题  得分: {score}")
    ratings = ["⭐ Greek 大师！", "👍 基础扎实", "📚 重看 Natenberg 第4-5章", "🐢 从头来过"]
    idx = 0 if accuracy >= 85 else (1 if accuracy >= 65 else (2 if accuracy >= 40 else 3))
    print(f"  {ratings[idx]}")
    print()


# ═══════════════════════════════════════════
# 主菜单
# ═══════════════════════════════════════════

def today_recommendation():
    dow = date.today().weekday()  # 0=Mon
    return {0: "A", 1: "B", 2: "C", 3: "A", 4: "B", 5: "C", 6: "D"}[dow]


def main():
    parser = argparse.ArgumentParser(description="期权交易速度训练系统")
    parser.add_argument('module', nargs='?', default=None,
                        help='训练模块: A/B/C/D/auto/stats')
    parser.add_argument('--quick', action='store_true', help='快速模式: 题量缩减为5题')
    args = parser.parse_args()

    module = args.module
    if module is None or module == "auto":
        module = today_recommendation()
        names = {"A": "链面扫异常", "B": "心算价差", "C": "天气→策略", "D": "Greek直觉"}
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
    else:
        print(f"未知模块: {module}。请用 A/B/C/D/stats")
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
