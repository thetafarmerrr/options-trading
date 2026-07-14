#!/usr/bin/env python3
"""
iv_collector.py — 每日 IV 数据采集
─────────────────────────────────
每天拉取关键品种 ATM 期权数据，存入 CSV。
攒够 4 周数据后，iv_ranker.py 就能算 IV 分位数。

用法：
  python3 iv_collector.py                     # 默认品种
  python3 iv_collector.py --variety m,c,rm    # 指定品种
"""

import sys, os, csv, argparse
from datetime import datetime
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from _ak_data import (pick_best_contract, fetch_option_chain, fetch_futures_daily,
                      estimate_iv_from_chain, DEFAULT_FUTURES, STRIKE_INTERVAL)

# ── 配置 ──
DEFAULT_VARIETIES = {
    "m":  {"symbol": "豆粕期权",  "name": "豆粕"},
    "c":  {"symbol": "玉米期权",  "name": "玉米"},
    "rm": {"symbol": "菜籽粕期权", "name": "菜籽粕"},
    "ta": {"symbol": "PTA期权",   "name": "PTA"},
    "ma": {"symbol": "甲醇期权",  "name": "甲醇"},
}

# 中国商品期货年交易日数 ≈ 242
TRADING_DAYS = 242
PARKINSON_WINDOW = 60
MIN_VALID_DAYS = 15

OUTPUT_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "iv_history.csv")
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


def _safe(v):
    return v if not pd.isna(v) else 0


def calc_parkinson_hv(vcode, window=PARKINSON_WINDOW):
    """用 Parkinson 估计量计算历史波动率。akshare 日线。"""
    df = fetch_futures_daily(vcode, window + 10)
    if df is None or len(df) == 0:
        return None
    df = df.sort_values("date").tail(window)
    valid = df[(df["high"] > df["low"]) & (df["high"] / df["low"] > 1.0005)]
    n = len(valid)
    if n < MIN_VALID_DAYS:
        return None
    high = valid["high"].values.astype(float)
    low = valid["low"].values.astype(float)
    ln_ratio = np.log(high / low)
    sigma_daily = np.sqrt(np.sum(ln_ratio ** 2) / (4 * n * np.log(2)))
    hv = sigma_daily * np.sqrt(TRADING_DAYS)
    return round(float(hv), 4)


def get_last_atm(vcode):
    """从 CSV 历史中读出该品种最近一次记录的 ATM 行权价"""
    if not os.path.exists(OUTPUT_FILE):
        return None
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            last = None
            for row in reader:
                if row.get("variety") == vcode:
                    last = row.get("atm_strike")
            return int(last) if last else None
    except Exception:
        return None


def calc_iv_slope(vcode):
    """从 CSV 历史算该品种近 3 天 IV 斜率。正=加速涨，负=回落，0=数据不足"""
    if not os.path.exists(OUTPUT_FILE):
        return None
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            vals = []
            for row in reader:
                if row.get("variety") == vcode:
                    try:
                        v = float(row.get("iv_est", 0) or 0)
                        if 0.001 < v < 5.0:  # 过滤行权价等脏数据
                            vals.append(v)
                    except (ValueError, TypeError):
                        pass
        # 去重取最后 3 天（同一天可能多次采集）
        # 4 位小数：IV 约 10% 时 0.0001 ≈ 0.1 个 IV 点，足够分辨
        unique_vals = []
        seen = set()
        for v in vals:
            key = f"{v:.4f}"
            if key not in seen:
                seen.add(key)
                unique_vals.append(v)
        if len(unique_vals) < 3:
            return None
        recent = unique_vals[-3:]
        x = np.arange(3)
        slope = np.polyfit(x, recent, 1)[0]
        return slope
    except Exception:
        return None


def get_last_contract(vcode):
    """从 CSV 历史中读出该品种最近一次用的合约"""
    if not os.path.exists(OUTPUT_FILE):
        return None
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            last = None
            for row in reader:
                if row.get("variety") == vcode:
                    last = row.get("contract")
            return last
    except Exception:
        return None


def _est_dte(contract):
    """估算期权距到期天数（商品期权通常为标的月份前一个月到期）"""
    try:
        month = int(contract[-2:])
        year = 2000 + int(contract[-4:-2])
        expiry = datetime(year, month, 1)
        dte = (expiry - datetime.now()).days - 5  # 到期月首日前 5 天
        return max(dte, 5)
    except Exception:
        return 30


def _est_iv(S, p_bid, p_ask, c_bid, c_ask, dte):
    """用 ATM 跨式价格近似反推隐含波动率。

    ATM 跨式 ≈ 0.8 × S × σ × √(T/365) → σ ≈ 跨式 / (0.8 × S × √(T/365))
    这个方法精确度有限，但 IV-HV 对比够用。Phase 3 可换精确求解器。
    """
    p_mid = (p_bid + p_ask) / 2
    c_mid = (c_bid + c_ask) / 2
    straddle = p_mid + c_mid
    if S <= 0 or straddle <= 0:
        return None
    iv = straddle / (0.8 * S * (dte / 365) ** 0.5)
    return round(float(iv), 4)


def collect_variety(vcode, vinfo):
    """用 akshare 拉取单个品种的主力合约 ATM 期权数据"""
    symbol = vinfo["symbol"]
    main_contract = get_last_contract(vcode)
    best_contract = pick_best_contract(symbol, vcode)
    if best_contract and best_contract != main_contract:
        print(f"  🔄 {vinfo['name']} 合约切换: {main_contract} → {best_contract}")
    main_contract = best_contract or main_contract
    if not main_contract:
        return None

    fut_contract, df, futures_price = fetch_option_chain(vcode, symbol, main_contract)
    if df.empty:
        return None

    best_strike, best_score, best_row = None, -1, None
    for _, row in df.iterrows():
        p_bid = _safe(row["p_bid"])
        c_bid = _safe(row["c_bid"])
        if p_bid > 0 and c_bid > 0:
            diff = abs(p_bid - c_bid)
            activity = (p_bid + c_bid) / 2
            score = activity / max(diff, 0.01)
            if score > best_score:
                best_score = score
                best_strike = int(row["strike"])
                best_row = row
    if best_row is None:
        return None

    yesterday_atm = get_last_atm(vcode)
    if yesterday_atm and yesterday_atm > 0:
        deviation = abs(best_strike - yesterday_atm) / yesterday_atm
        if deviation > 0.05:
            best_strike = yesterday_atm
            closest = df.iloc[(df["strike"] - yesterday_atm).abs().argsort()[:1]]
            best_row = closest.iloc[0] if len(closest) > 0 else best_row

    p_bid = _safe(best_row["p_bid"])
    p_ask = _safe(best_row["p_ask"])
    c_bid = _safe(best_row["c_bid"])
    c_ask = _safe(best_row["c_ask"])
    spread_pct = round((p_ask - p_bid) / p_bid * 100, 1) if p_bid > 0 else 999

    dte = _est_dte(fut_contract)
    iv = _est_iv(float(best_strike), p_bid, p_ask, c_bid, c_ask, dte)
    hv_20 = calc_parkinson_hv(vcode, window=20)
    hv_60 = calc_parkinson_hv(vcode, window=60)
    iv_slope = calc_iv_slope(vcode)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M"),
        "variety": vcode,
        "name": vinfo["name"],
        "contract": fut_contract,
        "atm_strike": best_strike,
        "call_bid": round(float(c_bid), 2),
        "call_ask": round(float(c_ask), 2),
        "put_bid": round(float(p_bid), 2),
        "put_ask": round(float(p_ask), 2),
        "spread_pct": spread_pct,
        "iv_est": iv,
        "hv_20d": hv_20,
        "hv_60d": hv_60,
        "iv_slope": round(iv_slope, 6) if iv_slope is not None else None,
        "dte": dte,
        "inferred_futures": best_strike,
    }


# ═══════════════════════════════════════════════════════════════
# 开盘环境定性 helper 函数
# ═══════════════════════════════════════════════════════════════

MIN_IV_DAYS = 3


def _clean_vol_vals(rows, field):
    vals = []
    for r in rows:
        try:
            v = float(r.get(field, 0) or 0)
            if 0.001 < v < 5.0:
                vals.append(v)
        except (ValueError, TypeError):
            pass
    return vals


def _load_iv_history(vcode):
    if not os.path.exists(OUTPUT_FILE):
        return None
    rows = []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["variety"] == vcode:
                rows.append(row)
    return rows if len(rows) >= 5 else None


def _hv_trend(rows):
    vals = _clean_vol_vals(rows[-20:], "hv_20d")
    if len(vals) < 5:
        return None, f"有效HV不足（{len(vals)}天）"
    vals = vals[-5:]
    x = np.arange(len(vals))
    slope = np.polyfit(x, vals, 1)[0]
    direction = "⬇ 退潮" if slope < 0 else "⬆ 聚集"
    return slope < 0, f"斜率={slope:.4f} {direction}"


def _hv_regime(rows):
    vals = _clean_vol_vals(rows[-30:], "hv_20d")
    if len(vals) < 5:
        return None, f"有效HV不足（{len(vals)}天）"
    current = vals[-1]
    mean_20 = np.mean(vals)
    ratio = current / mean_20 if mean_20 > 0 else 1
    if ratio > 1.25:
        return False, f"高波动期（{ratio:.1f}x 均值）"
    elif ratio < 0.85:
        return True, f"低波动期（{ratio:.1f}x 均值）"
    else:
        return True, f"正常（{ratio:.1f}x 均值）"


def _leverage_effect(vcode):
    try:
        df = fetch_futures_daily(vcode, 60)
        if df is None or len(df) < 30:
            return None, "日线不足"
        df = df.sort_values("date").tail(60)
        df["return"] = df["close"].astype(float).pct_change()
        df = df.dropna()
        up_days = df[df["return"] > 0]
        down_days = df[df["return"] < 0]
        if len(down_days) < 5:
            return None, "下跌日不足"
        avg_down = abs(down_days["return"].mean())
        avg_up = abs(up_days["return"].mean()) if len(up_days) > 0 else avg_down
        asymmetry = avg_down / avg_up if avg_up > 0 else 999
        if asymmetry > 1.3:
            return False, f"不对称明显（跌{avg_down:.2%} vs 涨{avg_up:.2%}，×{asymmetry:.1f}）"
        return True, f"对称（跌{avg_down:.2%} vs 涨{avg_up:.2%}）"
    except Exception as e:
        return None, f"拉取失败: {e}"


def _vol_hv_cross(rows):
    hv20_vals = _clean_vol_vals(rows[-5:], "hv_20d")
    hv60_vals = _clean_vol_vals(rows[-5:], "hv_60d")
    hv20 = hv20_vals[-1] if hv20_vals else None
    hv60 = hv60_vals[-1] if hv60_vals else None
    vcode = rows[-1].get("variety", "")
    if not vcode:
        return None, "无品种代码"
    df = fetch_futures_daily(vcode, 100)
    if df is None or len(df) < 10:
        return None, "日线不足"
    df = df.sort_values("date")
    recent_vol = df["volume"].astype(float).tail(5).mean()
    ma20_vol = df["volume"].astype(float).tail(20).mean()
    vol_ratio = recent_vol / ma20_vol if ma20_vol > 0 else 1
    expanding = hv20 and hv60 and hv20 > hv60
    vol_high = vol_ratio > 1.2
    vol_low = vol_ratio < 0.8
    if expanding and vol_high:
        return False, f"HV扩张+放量{vol_ratio:.1f}x → 信号真实强烈"
    elif expanding and vol_low:
        return True, f"HV扩张+缩量{vol_ratio:.1f}x → 虚张声势，可小仓试"
    elif not expanding and vol_high:
        return True, f"HV收缩+放量{vol_ratio:.1f}x → 波动退潮，卖方有利"
    elif not expanding and vol_low:
        return True, f"HV收缩+缩量{vol_ratio:.1f}x → 安静收租"
    return True, f"正常 {vol_ratio:.1f}x"


def _iv_rank_volume(rows):
    vals = _clean_vol_vals(rows, "iv_est")
    if len(vals) < MIN_IV_DAYS:
        return None, f"有效IV不足（{len(vals)}天，需≥{MIN_IV_DAYS}）"
    current = vals[-1]
    percentile = sum(1 for v in vals if v <= current) / len(vals) * 100
    iv_high = percentile > 70
    warn = " ⚠️刚起步" if len(vals) < 5 else (" ⚠️样本偏少" if len(vals) < 10 else "")
    recent = vals[-3:]
    if len(recent) >= 3:
        x = np.arange(3)
        slope = np.polyfit(x, recent, 1)[0]
        if slope > 0.005:
            direction = "⬆ 加速涨"
            favorable = False
        elif slope < -0.005:
            direction = "⬇ 回落"
            favorable = True
        else:
            direction = "➡ 企稳"
            favorable = iv_high
    else:
        direction, favorable = "?", iv_high
    vol_tag = ""
    vcode = rows[-1].get("variety", "")
    if vcode:
        df = fetch_futures_daily(vcode, 100)
        if df is not None and len(df) >= 10:
            df = df.sort_values("date")
            recent_v = df["volume"].astype(float).tail(5).mean()
            ma20_v = df["volume"].astype(float).tail(20).mean()
            vol_ratio = recent_v / ma20_v if ma20_v > 0 else 1
            if iv_high:
                if vol_ratio > 1.2:
                    vol_tag = " 放量→真贵慎卖"
                    favorable = False
                elif vol_ratio < 0.8:
                    vol_tag = " 缩量→虚高可卖"
                    favorable = True
    return (favorable, f"分位 {percentile:.0f}% {direction}（{len(vals)}天）{warn}{vol_tag}")


# ═══════════════════════════════════════════════════════════════


def _run_premarket_check(target_vcodes):
    """对指定品种跑五条检查并输出"""

    # 复用 DEFAULT_VARIETIES
    if not os.path.exists(OUTPUT_FILE):
        print("  ⚠️ iv_history.csv 不存在，跳过低风险查")
        return

    print(f"\n{'='*50}")
    print(f"  开盘环境定性（Sinclair 第 3 章）")
    print(f"  {'='*50}")

    scores = {}
    for vcode in target_vcodes:
        vinfo = DEFAULT_VARIETIES.get(vcode)
        if not vinfo:
            continue
        name = vinfo["name"]

        rows = _load_iv_history(vcode)
        if not rows:
            print(f"  ⚠️ {name}: iv_history.csv 数据不足（需至少 5 天）")
            continue

        contract_code = rows[-1].get("contract", "")
        if not contract_code:
            print(f"  ⚠️ {name}: 无合约代码")
            continue

        results = {}
        total_favorable = 0
        total_checked = 0

        print(f"\n{'─'*50}")
        print(f"  {name} ({vcode}) | 合约={contract_code}")
        print(f"  {'─'*50}")

        for num, (label, func, args) in enumerate([
            ("HV 趋势(5d)", _hv_trend, [rows]),
            ("波动环境(vs20d)", _hv_regime, [rows]),
            ("杠杆效应", _leverage_effect, [vcode]),
            ("量×HV方向", _vol_hv_cross, [rows]),
            ("IV分位+量价", _iv_rank_volume, [rows]),
        ], 1):
            try:
                favorable, detail = func(*args)
            except Exception as e:
                print(f"  [{num}] {label}: ❓ 计算异常 {e}")
                continue

            if favorable is None:
                print(f"  [{num}] {label}: ❓ {detail}")
                continue

            icon = "🟢" if favorable else "🔴"
            results[num] = favorable
            total_checked += 1
            if favorable:
                total_favorable += 1
            print(f"  [{num}] {icon} {label}: {detail}")

        results["total"] = total_favorable
        results["checked"] = total_checked

        if total_checked >= 3:
            if total_favorable >= 3:
                verdict = "🟢 开仓"
            elif total_favorable <= 1:
                verdict = "🔴 旁观"
            else:
                verdict = "🟡 谨慎"
        else:
            verdict = "❓ 数据不足"

        print(f"  {'─'*50}")
        print(f"  → {verdict}（{total_favorable}/{total_checked}）")

        scores[vcode] = results

    if scores:
        print(f"\n  ── 卖方全局汇总 ──")
        buyer_opportunities = []
        for vcode, s in scores.items():
            name = DEFAULT_VARIETIES[vcode]["name"]
            checked = s.get("checked", 0)
            fav = s.get("total", 0)
            bar = "🟢" * fav + "🔴" * (checked - fav) if checked else "❓"
            print(f"  {name:6s}  {bar}  {fav}/{checked}")

            # ── 买方视角：IV 低 = 买方有利 ──
            rows = _load_iv_history(vcode)
            if rows:
                vals = _clean_vol_vals(rows, "iv_est")
                if len(vals) >= MIN_IV_DAYS:
                    current_iv = vals[-1]
                    iv_pct = sum(1 for v in vals if v <= current_iv) / len(vals) * 100
                    if iv_pct < 30:
                        buyer_opportunities.append((vcode, name, iv_pct, "🟢 买方黄金窗口"))
                    elif iv_pct < 50:
                        buyer_opportunities.append((vcode, name, iv_pct, "🟡 买方可关注"))
                    else:
                        buyer_opportunities.append((vcode, name, iv_pct, "🔴 买方不利"))

        if buyer_opportunities:
            print(f"\n  ── 买方视角（IV 低位=期权便宜，买方有利）──")
            for vcode, name, iv_pct, tag in buyer_opportunities:
                print(f"  {name:6s}  IV 分位 {iv_pct:.0f}%  {tag}")
            active = [b for b in buyer_opportunities if "🟢" in b[3] or "🟡" in b[3]]
            if active:
                print(f"  → 买方可关注品种：{', '.join(b[1] for b in active)}")
            else:
                print(f"  → 所有品种 IV 偏高，买方无优势。继续卖方或旁观。")

    print()


def main():
    parser = argparse.ArgumentParser(description="每日 IV 数据采集 + 开盘环境定性")
    parser.add_argument("--variety", type=str, default="m,c,rm,ta,ma",
                        help="品种代码，逗号分隔。默认 m,c,rm,ta,ma")
    args = parser.parse_args()

    target = [v.strip() for v in args.variety.split(",")]

    print(f"\n📊 iv_collector — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   品种: {', '.join(target)}")
    print()

    rows = []
    for vcode in target:
        vinfo = DEFAULT_VARIETIES.get(vcode)
        if not vinfo:
            print(f"  ⚠️ 未知品种: {vcode}")
            continue
        try:
            result = collect_variety(vcode, vinfo)
            if result:
                rows.append(result)
                icon = "✅" if result["spread_pct"] < 10 else "⚠️"
                iv_str = f"{result['iv_est']:.1%}" if result['iv_est'] else "N/A"
                hv20_str = f"{result['hv_20d']:.1%}" if result['hv_20d'] else "N/A"
                hv60_str = f"{result['hv_60d']:.1%}" if result['hv_60d'] else "N/A"
                # 20d vs 60d 差距标记
                hv_gap = ""
                if result['hv_20d'] and result['hv_60d']:
                    gap = result['hv_20d'] - result['hv_60d']
                    if gap > 0.03:
                        hv_gap = "⚡"  # 近期剧烈
                    elif gap < -0.03:
                        hv_gap = "😴"  # 近期安静
                slope = calc_iv_slope(vcode)
                if slope is not None:
                    if slope > 0.003:
                        iv_dir = "⬆"
                    elif slope < -0.003:
                        iv_dir = "⬇"
                    else:
                        iv_dir = "➡"
                else:
                    iv_dir = "?"
                print(f"  {icon} {result['name']} {result['contract']} "
                      f"ATM={result['atm_strike']} DTE={result['dte']}d "
                      f"P bid/ask={result['put_bid']}/{result['put_ask']} "
                      f"价差={result['spread_pct']}% "
                      f"IV≈{iv_str}{iv_dir} HV₂₀={hv20_str} HV₆₀={hv60_str} {hv_gap}")
            else:
                print(f"  ❌ {vinfo['name']}: 无有效 ATM 数据")
        except Exception as e:
            print(f"  ❌ {vinfo['name']}: {str(e)[:50]}")

    if not rows:
        print("\n  无数据，未写入 CSV\n")
        return

    # 追加写入 CSV
    file_exists = os.path.exists(OUTPUT_FILE)

    if file_exists:
        # 以现有头部为准，新列自动追加到末尾
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fields = list(reader.fieldnames)
        new_fields = [f for f in rows[0].keys() if f not in existing_fields]
        fieldnames = existing_fields + new_fields
        if new_fields:
            # 重写头部追加新列
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                old_rows = f.readlines()[1:]
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(",".join(fieldnames) + "\n")
                f.writelines(old_rows)
    else:
        fieldnames = list(rows[0].keys())

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"\n  💾 已写入 {len(rows)} 条 → {OUTPUT_FILE}")
    if not file_exists:
        print(f"  🆕 新文件已创建。连续跑 4 周后 iv_ranker.py 可用。")

    # ── 自动跑开盘环境定性 ──
    try:
        _run_premarket_check(target)
    except Exception:
        pass  # 环境检查挂了不影响采集

    print()


if __name__ == "__main__":
    main()
