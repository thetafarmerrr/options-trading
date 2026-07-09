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

import akshare as ak
from unified_scanner import pick_best_contract

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
PARKINSON_WINDOW = 20
MIN_VALID_DAYS = 15

OUTPUT_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "iv_history.csv")
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


def _safe(v):
    return v if not pd.isna(v) else 0


def calc_parkinson_hv(contract, window=PARKINSON_WINDOW):
    """用 Parkinson 估计量计算历史波动率（替代收盘价法）。

    Parkinson 比收盘价法效率高 5 倍，用最高/最低价捕捉日内波动。
    跳空时低估——Yang-Zhang 会修正这个问题，Phase 3 切换。
    """
    try:
        # 拉单一合约日线（无换月跳空）
        df = ak.futures_zh_daily_sina(contract.upper())
        if df is None or len(df) == 0:
            return None

        # 统一列名
        df = df.rename(columns={
            "日期": "date", "开盘价": "open", "最高价": "high",
            "最低价": "low", "收盘价": "close",
        })

        # 取最近 window 根日线，按日期排序
        df = df.sort_values("date").tail(window)

        # 过滤异常 K 线：停牌、涨跌停无成交、数据异常
        valid = df[(df["high"] > df["low"]) & (df["high"] / df["low"] > 1.0005)]
        n = len(valid)

        if n < MIN_VALID_DAYS:
            return None  # 数据不足，不输出不可靠的 HV

        high = valid["high"].values.astype(float)
        low = valid["low"].values.astype(float)

        # Parkinson 公式
        ln_ratio = np.log(high / low)
        sigma_daily = np.sqrt(np.sum(ln_ratio ** 2) / (4 * n * np.log(2)))
        hv = sigma_daily * np.sqrt(TRADING_DAYS)  # 年化（√242）

        return round(float(hv), 4)

    except Exception:
        return None


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
    """拉取单个品种的主力合约 ATM 期权数据"""
    symbol = vinfo["symbol"]

    # 与 scanner 同套逻辑选主力合约。优先沿用历史合约保证连续性
    main_contract = get_last_contract(vcode)
    best_contract = pick_best_contract(symbol, vcode)
    if best_contract and best_contract != main_contract:
        print(f"  🔄 {vinfo['name']} 合约切换: {main_contract} → {best_contract}")
    main_contract = best_contract or main_contract
    if not main_contract:
        return None

    # 拉期权链
    df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=main_contract)
    df = df.rename(columns={
        "行权价": "strike",
        "看涨合约-买价": "c_bid", "看涨合约-卖价": "c_ask",
        "看跌合约-买价": "p_bid", "看跌合约-卖价": "p_ask",
    })

    # 找 ATM：加权评分 = 交易活跃度 / Call-Put偏差
    # 远端行权价（如玉米2640）绝对差值小但bid也极小→活跃度低→评分低
    best_strike, best_score, best_row = None, -1, None
    for _, row in df.iterrows():
        p_bid = _safe(row["p_bid"])
        c_bid = _safe(row["c_bid"])
        if p_bid > 0 and c_bid > 0:
            diff = abs(p_bid - c_bid)
            activity = (p_bid + c_bid) / 2  # 平均bid = 市场参与度
            score = activity / max(diff, 0.01)  # 活跃度高 + 偏差小 = 高分
            if score > best_score:
                best_score = score
                best_strike = int(row["strike"])
                best_row = row

    if best_row is None:
        return None

    # 安全网：如果 ATM 偏离昨天 5% 以上 → 用昨天的（开盘流动性假象）
    yesterday_atm = get_last_atm(vcode)
    if yesterday_atm and yesterday_atm > 0:
        deviation = abs(best_strike - yesterday_atm) / yesterday_atm
        if deviation > 0.05:
            best_strike = yesterday_atm
            # 从链面找最近的行权价行
            closest = df.iloc[(df["strike"] - yesterday_atm).abs().argsort()[:1]]
            best_row = closest.iloc[0] if len(closest) > 0 else best_row

    p_bid = _safe(best_row["p_bid"])
    p_ask = _safe(best_row["p_ask"])
    c_bid = _safe(best_row["c_bid"])
    c_ask = _safe(best_row["c_ask"])
    spread_pct = round((p_ask - p_bid) / p_bid * 100, 1) if p_bid > 0 else 999

    # 估算 IV（ATM 跨式反推，近似值）
    dte = _est_dte(main_contract)
    iv = _est_iv(float(best_strike), p_bid, p_ask, c_bid, c_ask, dte)
    hv = calc_parkinson_hv(main_contract)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M"),
        "variety": vcode,
        "name": vinfo["name"],
        "contract": main_contract,
        "atm_strike": best_strike,
        "call_bid": round(float(c_bid), 2),
        "call_ask": round(float(c_ask), 2),
        "put_bid": round(float(p_bid), 2),
        "put_ask": round(float(p_ask), 2),
        "spread_pct": spread_pct,
        "iv_est": iv,
        "hv_parkinson": hv,
        "dte": dte,
        "inferred_futures": best_strike,
    }


def main():
    parser = argparse.ArgumentParser(description="每日 IV 数据采集")
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
                hv_str = f"{result['hv_parkinson']:.1%}" if result['hv_parkinson'] else "N/A"
                print(f"  {icon} {result['name']} {result['contract']} "
                      f"ATM={result['atm_strike']} DTE={result['dte']}d "
                      f"P bid/ask={result['put_bid']}/{result['put_ask']} "
                      f"价差={result['spread_pct']}% "
                      f"IV≈{iv_str} HV={hv_str}")
            else:
                print(f"  ❌ {vinfo['name']}: 无有效 ATM 数据")
        except Exception as e:
            print(f"  ❌ {vinfo['name']}: {str(e)[:50]}")

    if not rows:
        print("\n  无数据，未写入 CSV\n")
        return

    # 追加写入 CSV（兼容旧文件无 hv_parkinson 列）
    fieldnames = list(rows[0].keys())
    file_exists = os.path.exists(OUTPUT_FILE)

    # 如果旧 CSV 缺少 hv_parkinson 列，补齐头部
    if file_exists:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing_fields = f.readline().strip().split(",")
        missing = [f for f in fieldnames if f not in existing_fields]
        if missing:
            # 重写头部，插入缺失列（放在 inferred_futures 之前）
            insert_pos = existing_fields.index("inferred_futures")
            new_header = existing_fields[:insert_pos] + missing + existing_fields[insert_pos:]
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                old_rows = f.readlines()[1:]
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(",".join(new_header) + "\n")
                f.writelines(old_rows)

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"\n  💾 已写入 {len(rows)} 条 → {OUTPUT_FILE}")
    if not file_exists:
        print(f"  🆕 新文件已创建。连续跑 4 周后 iv_ranker.py 可用。")
    print()


if __name__ == "__main__":
    main()
