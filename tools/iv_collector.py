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
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import akshare as ak

# ── 配置 ──
DEFAULT_VARIETIES = {
    "m":  {"symbol": "豆粕期权",  "name": "豆粕"},
    "c":  {"symbol": "玉米期权",  "name": "玉米"},
    "rm": {"symbol": "菜籽粕期权", "name": "菜籽粕"},
    "ta": {"symbol": "PTA期权",   "name": "PTA"},
    "ma": {"symbol": "甲醇期权",  "name": "甲醇"},
}

OUTPUT_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "iv_history.csv")
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


def _safe(v):
    return v if not pd.isna(v) else 0


def collect_variety(vcode, vinfo):
    """拉取单个品种的主力合约 ATM 期权数据"""
    symbol = vinfo["symbol"]

    # 获取合约列表，选流动性最好的（前2个中 ATM 价差更紧的那个）
    contracts_df = ak.option_commodity_contract_sina(symbol=symbol)
    candidates = contracts_df["合约"].tolist()[:2]
    if not candidates:
        return None
    if len(candidates) == 1:
        main_contract = candidates[0]
    else:
        # 选 ATM 价差更紧的那个
        best_contract, best_spread = None, 999
        for c in candidates:
            try:
                tdf = ak.option_commodity_contract_table_sina(symbol=symbol, contract=c)
                tdf = tdf.rename(columns={"行权价": "strike", "看跌合约-买价": "p_bid", "看跌合约-卖价": "p_ask", "看涨合约-买价": "c_bid"})
                min_diff, atm_bid, atm_ask = float("inf"), 0, 0
                for _, r in tdf.iterrows():
                    pb = _safe(r["p_bid"]); cb = _safe(r["c_bid"])
                    if pb > 0 and cb > 0 and abs(pb - cb) < min_diff:
                        min_diff = abs(pb - cb); atm_bid = pb; atm_ask = _safe(r["p_ask"])
                sp = (atm_ask - atm_bid) / atm_bid * 100 if atm_bid > 0 else 999
                if sp < best_spread:
                    best_spread = sp; best_contract = c
            except Exception:
                continue
        main_contract = best_contract or candidates[0]

    # 拉期权链
    df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=main_contract)
    df = df.rename(columns={
        "行权价": "strike",
        "看涨合约-买价": "c_bid", "看涨合约-卖价": "c_ask",
        "看跌合约-买价": "p_bid", "看跌合约-卖价": "p_ask",
    })

    # 找 ATM：Call 和 Put bid 最接近的那个行权价
    best_strike, best_diff = None, float("inf")
    best_row = None
    for _, row in df.iterrows():
        p_bid = _safe(row["p_bid"])
        c_bid = _safe(row["c_bid"])
        if p_bid > 0 and c_bid > 0:
            diff = abs(p_bid - c_bid)
            if diff < best_diff:
                best_diff = diff
                best_strike = int(row["strike"])
                best_row = row

    if best_row is None:
        return None

    p_bid = _safe(best_row["p_bid"])
    p_ask = _safe(best_row["p_ask"])
    c_bid = _safe(best_row["c_bid"])
    c_ask = _safe(best_row["c_ask"])
    spread_pct = round((p_ask - p_bid) / p_bid * 100, 1) if p_bid > 0 else 999

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
                print(f"  {icon} {result['name']} {result['contract']} "
                      f"ATM={result['atm_strike']} "
                      f"P bid/ask={result['put_bid']}/{result['put_ask']} "
                      f"价差={result['spread_pct']}%")
            else:
                print(f"  ❌ {vinfo['name']}: 无有效 ATM 数据")
        except Exception as e:
            print(f"  ❌ {vinfo['name']}: {str(e)[:50]}")

    if not rows:
        print("\n  无数据，未写入 CSV\n")
        return

    # 追加写入 CSV
    fieldnames = list(rows[0].keys())
    file_exists = os.path.exists(OUTPUT_FILE)

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
