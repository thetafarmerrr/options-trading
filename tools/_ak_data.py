"""akshare 数据层 — scanner + iv_collector 共享（日频 REST，不挂）"""
import re
import math
import pandas as pd
from datetime import datetime

import akshare as ak

VALID_MONTHS = {
    'm': [1, 5, 9], 'rm': [1, 5, 9], 'sr': [1, 5, 9], 'cf': [1, 5, 9],
    'c': [1, 3, 5, 7, 9, 11],
    'ta': [1, 5, 9], 'ma': [1, 5, 9], 'ru': [1, 5, 9],
    'i': [1, 5, 9], 'au': [2, 4, 6, 8, 10, 12],
}

DEFAULT_FUTURES = {"au": 870, "m": 2800, "c": 2300, "cf": 13500, "sr": 5600,
                   "ta": 4800, "i": 780, "ru": 17000, "ma": 2450, "rm": 2500}

STRIKE_INTERVAL = {"au": 8, "m": 50, "c": 40, "cf": 200, "sr": 100,
                   "ta": 50, "ma": 50, "i": 20, "ru": 500, "rm": 50}


def pick_best_contract(symbol, vcode=None):
    """选主力合约：L0 指向当前周期 → L1 流动性验证"""
    today = datetime.now()
    cur_month = today.month
    cur_year = today.year % 100

    try:
        cdf = ak.option_commodity_contract_sina(symbol=symbol)
        all_contracts = cdf['合约'].tolist()
    except Exception:
        return None
    if not all_contracts:
        return None

    if vcode and vcode in VALID_MONTHS:
        valid = sorted(VALID_MONTHS[vcode])
        ordered = [m for m in valid if m >= cur_month + 1] + [m for m in valid if m < cur_month + 1]
        target_codes = []
        for m in ordered:
            yr = cur_year if m > cur_month else cur_year + 1
            target_codes.append(f"{yr:02d}{m:02d}")
        candidates = []
        for tc in target_codes[:3]:
            match = next((c for c in all_contracts if c.endswith(tc)), None)
            if match:
                candidates.append(match)
        if not candidates:
            return all_contracts[0] if all_contracts else None
    else:
        candidates = all_contracts[:2]

    def _check_quality(contract):
        try:
            df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=contract)
            df = df.rename(columns={
                '行权价': 'strike',
                '看跌合约-买价': 'p_bid', '看涨合约-买价': 'c_bid',
            })
            df = df.sort_values('strike').reset_index(drop=True)
            atm_idx = (df['p_bid'] - df['c_bid']).abs().idxmin()
            if pd.isna(atm_idx):
                return False
            start, end = max(0, atm_idx - 5), min(len(df) - 1, atm_idx + 5)
            if end - start < 5:
                return False
            window = df.iloc[start:end + 1]
            ok = sum(1 for _, r in window.iterrows()
                     if (r['p_bid'] if not pd.isna(r['p_bid']) else 0) > 0
                     or (r['c_bid'] if not pd.isna(r['c_bid']) else 0) > 0)
            return ok / len(window) >= 0.5
        except Exception:
            return False

    for c in candidates:
        if _check_quality(c):
            return c
    return candidates[0] if candidates else None


def _safe(v):
    return v if not pd.isna(v) else 0


def fetch_option_chain(vcode, symbol, contract=None):
    """用 akshare 拉完整期权链，返回 (contract_code, DataFrame, futures_price)"""
    if contract is None:
        contract = pick_best_contract(symbol, vcode)
    if not contract:
        return None, pd.DataFrame(), DEFAULT_FUTURES.get(vcode, 3000)

    df = ak.option_commodity_contract_table_sina(symbol=symbol, contract=contract)
    # 新浪不同交易所列名不统一，统一映射
    col_map = {}
    for col in df.columns:
        if '行权' in col or 'strike' in col.lower():
            col_map[col] = 'strike'
        elif '看跌' in col and '买价' in col:
            col_map[col] = 'p_bid'
        elif '看跌' in col and '卖价' in col:
            col_map[col] = 'p_ask'
        elif '看跌' in col and '买量' in col:
            col_map[col] = 'p_bid_vol'
        elif '看跌' in col and '最新价' in col:
            col_map[col] = 'p_last'
        elif '看跌' in col and '持仓' in col:
            col_map[col] = 'p_oi'
        elif '看涨' in col and '买价' in col:
            col_map[col] = 'c_bid'
        elif '看涨' in col and '卖价' in col:
            col_map[col] = 'c_ask'
    df = df.rename(columns=col_map)
    if 'strike' not in df.columns:
        # 最后兜底：第一列当行权价
        first_col = df.columns[0]
        df = df.rename(columns={first_col: 'strike'})

    df['strike'] = df['strike'].astype(float)

    # 推断期货价：ATM Put/Call bid 最接近且流动性好的行权价
    best_strike, best_diff = None, float('inf')
    for _, row in df.iterrows():
        p_bid = _safe(row.get('p_bid', 0))
        c_bid = _safe(row.get('c_bid', 0))
        p_ask = _safe(row.get('p_ask', 0))
        c_ask = _safe(row.get('c_ask', 0))
        if p_bid > 0 and c_bid > 0:
            diff = abs(p_bid - c_bid)
            # 过滤明显流动性差的：Put 或 Call 价差 > 50%（假 ATM）
            p_sp = (p_ask - p_bid) / p_bid if p_bid > 0 else 999
            c_sp = (c_ask - c_bid) / c_bid if c_bid > 0 else 999
            if p_sp > 0.50 or c_sp > 0.50:
                continue
            if diff < best_diff:
                best_diff = diff
                best_strike = row['strike']
    if best_strike:
        df_default = DEFAULT_FUTURES.get(vcode, 3000)
        # 安全网：推断价偏离默认价超过 25%，取默认价
        if abs(best_strike - df_default) / df_default > 0.25:
            futures_price = df_default
        else:
            futures_price = best_strike
    else:
        futures_price = DEFAULT_FUTURES.get(vcode, 3000)

    return contract, df, futures_price


def fetch_futures_daily(vcode, days=120):
    """拉期货日线（Parkinson HV），akshare 新浪源"""
    # 需要知道 akshare 合约代码 → 用 pick_best_contract 的近月
    # 这里用最简单的方式：从 iv_collector 的合约代码转成 akshare 期货代码
    try:
        # 用 DEFAULT_VARIETIES 里的品种名推断
        symbol_map = {
            "m": "豆粕", "c": "玉米", "rm": "菜籽粕", "ta": "PTA", "ma": "甲醇",
            "au": "黄金", "cf": "棉花", "sr": "白糖", "i": "铁矿石", "ru": "橡胶",
        }
        # 查对应品种的最近合约
        symbol = symbol_map.get(vcode, vcode) + "期权"
        contract = pick_best_contract(symbol, vcode)
        if contract:
            df = ak.futures_zh_daily_sina(contract.upper())
            if df is not None and len(df) > 0:
                df = df.rename(columns={
                    "日期": "date", "开盘价": "open", "最高价": "high",
                    "最低价": "low", "收盘价": "close", "成交量": "volume",
                })
                return df
    except Exception:
        pass
    return None


def _est_dte(contract):
    try:
        m = re.search(r'(\d{4})$', contract)
        if m:
            yy, mm = int(m.group(1)[:2]), int(m.group(1)[2:])
            expiry = datetime(2000 + yy, mm, 1)
            return max((expiry - datetime.now()).days - 5, 5)
    except Exception:
        pass
    return 30


def estimate_iv_from_chain(df, futures_price, contract):
    """从 ATM 跨式估算 IV"""
    atm_idx = (df['strike'] - futures_price).abs().idxmin()
    atm_row = df.loc[atm_idx]
    p_bid = _safe(atm_row.get('p_bid', 0))
    p_ask = _safe(atm_row.get('p_ask', 0))
    c_bid = _safe(atm_row.get('c_bid', 0))
    c_ask = _safe(atm_row.get('c_ask', 0))
    straddle = (p_bid + p_ask + c_bid + c_ask) / 2
    dte = _est_dte(contract)
    if futures_price > 0 and straddle > 0:
        return round(float(straddle / (0.8 * futures_price * math.sqrt(max(dte, 1) / 365))), 4), dte
    return None, dte
