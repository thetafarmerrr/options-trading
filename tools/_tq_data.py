"""天勤数据层 v2 — 批量订阅 + 超时 + 分批"""
from datetime import datetime
import os
import time
import pandas as pd
from tqsdk import TqApi, TqAuth
from tqsdk.exceptions import TqTimeoutError

# 凭据来自 .env（不硬编码）
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists(os.path.join(_PROJECT_DIR, ".env")):
    with open(os.path.join(_PROJECT_DIR, ".env")) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

TQ_USER = os.environ.get("TQ_USER", "")
TQ_PASS = os.environ.get("TQ_PASS", "")

VALID_MONTHS = {
    'm': [1, 5, 9], 'rm': [1, 5, 9], 'sr': [1, 5, 9], 'cf': [1, 5, 9],
    'c': [1, 3, 5, 7, 9, 11],
    'ta': [1, 5, 9], 'ma': [1, 5, 9], 'ru': [1, 5, 9],
    'i': [1, 5, 9], 'au': [2, 4, 6, 8, 10, 12],
}

EXCHANGE_MAP = {
    "au": "SHFE", "ru": "SHFE",
    "m": "DCE", "c": "DCE", "i": "DCE",
    "ta": "CZCE", "ma": "CZCE", "cf": "CZCE", "sr": "CZCE", "rm": "CZCE",
}

TQ_CODE = {
    "au": "au", "m": "m", "c": "c", "cf": "CF", "sr": "SR",
    "ta": "TA", "ma": "MA", "i": "i", "ru": "ru", "rm": "RM",
}

STRIKE_INTERVAL = {"au": 8, "m": 50, "c": 40, "cf": 200, "sr": 100,
                   "ta": 50, "ma": 50, "i": 20, "ru": 500, "rm": 50}

DEFAULT_FUTURES = {"au": 870, "m": 2800, "c": 2300, "cf": 13500, "sr": 5600,
                   "ta": 4800, "i": 780, "ru": 17000, "ma": 2450, "rm": 2500}

BATCH_SIZE = 4          # 每批品种数（免费版配额友好）
QUOTE_TIMEOUT = 15      # 单品种超时秒数
BATCH_COOLDOWN = 3      # 批次间隔秒数


def tq_contract_month(vcode):
    today = datetime.now()
    cur_month = today.month
    cur_year = today.year % 100
    valid = sorted(VALID_MONTHS.get(vcode, [1, 5, 9]))
    ordered = [m for m in valid if m >= cur_month + 1] + [m for m in valid if m < cur_month + 1]
    m = ordered[0] if ordered else cur_month + 1
    yr = cur_year if m > cur_month else cur_year + 1
    return f"{EXCHANGE_MAP.get(vcode, 'DCE')}.{TQ_CODE.get(vcode, vcode)}{yr:02d}{m:02d}"


def fetch_option_chain(api, vcode, timeout=QUOTE_TIMEOUT):
    """v2：query_options 发现合约 + get_quote_list 批量订阅 + 15s 超时"""
    exch = EXCHANGE_MAP.get(vcode, "DCE")
    tq = TQ_CODE.get(vcode, vcode)
    underlying = tq_contract_month(vcode)
    month_suffix = underlying[-4:]

    # 1. 用天勤 query_options 发现真实存在的期权合约（不订阅，不挂）
    try:
        calls = api.query_options(underlying, option_class="CALL", expired=False)
        puts = api.query_options(underlying, option_class="PUT", expired=False)
        all_codes = calls + puts
    except Exception:
        # query_options 不可用 → 回退到手工拼接
        fp = DEFAULT_FUTURES.get(vcode, 3000)
        interval = STRIKE_INTERVAL.get(vcode, 50)
        lo = int((fp * 0.90) // interval) * interval
        hi = int((fp * 1.10) // interval + 1) * interval
        strikes = list(range(lo, hi + interval, interval))
        all_codes = [f"{exch}.{tq}{month_suffix}P{int(s)}" for s in strikes]
        all_codes += [f"{exch}.{tq}{month_suffix}C{int(s)}" for s in strikes]

    if not all_codes:
        return underlying, pd.DataFrame(), DEFAULT_FUTURES.get(vcode, 3000)

    # 2. 批量订阅（一次调用，50→1 次请求）
    deadline = time.time() + timeout
    quotes = api.get_quote_list(all_codes)
    try:
        api.wait_update(deadline=deadline)
    except TqTimeoutError:
        pass  # 部分合约可能没数据，能拿多少拿多少

    # 3. 读取期货价
    try:
        fut_q = api.get_quote(underlying)
        fp = fut_q.last_price
        futures_price = float(fp) if fp and fp > 0 else DEFAULT_FUTURES.get(vcode, 3000)
    except Exception:
        futures_price = DEFAULT_FUTURES.get(vcode, 3000)

    # 4. 组装 DataFrame（QuoteList 对象用下标取，和 dict 一样）
    rows = []
    for code in all_codes:
        try:
            q = quotes[code]
            b = float(q.bid_price1) if q.bid_price1 and float(q.bid_price1) > 0 else 0
            a = float(q.ask_price1) if q.ask_price1 and float(q.ask_price1) > 0 else 0
            oi = float(q.open_interest) if q.open_interest else 0
        except (KeyError, IndexError):
            try:
                q = api.get_quote(code)
                b = float(q.bid_price1) if q.bid_price1 and float(q.bid_price1) > 0 else 0
                a = float(q.ask_price1) if q.ask_price1 and float(q.ask_price1) > 0 else 0
                oi = float(q.open_interest) if q.open_interest else 0
            except Exception:
                b, a, oi = 0, 0, 0
        except Exception:
            b, a, oi = 0, 0, 0
        suffix = code.replace(f"{exch}.{tq}{month_suffix}", "")
        if not suffix or len(suffix) < 2:
            continue
        opt_type = suffix[0]
        try:
            strike = int(suffix[1:])
        except ValueError:
            continue
        rows.append({"strike": strike, "type": opt_type, "bid": b, "ask": a, "oi": oi})

    if not rows:
        return underlying, pd.DataFrame(), futures_price

    df_raw = pd.DataFrame(rows)
    result_rows = []
    for strike in sorted(df_raw["strike"].unique()):
        p_r = df_raw[(df_raw["strike"] == strike) & (df_raw["type"] == "P")]
        c_r = df_raw[(df_raw["strike"] == strike) & (df_raw["type"] == "C")]
        result_rows.append({
            "strike": strike,
            "p_bid": float(p_r.iloc[0]["bid"]) if not p_r.empty else 0,
            "p_ask": float(p_r.iloc[0]["ask"]) if not p_r.empty else 0,
            "p_oi":  float(p_r.iloc[0]["oi"]) if not p_r.empty else 0,
            "c_bid": float(c_r.iloc[0]["bid"]) if not c_r.empty else 0,
            "c_ask": float(c_r.iloc[0]["ask"]) if not c_r.empty else 0,
        })
    df = pd.DataFrame(result_rows).sort_values("strike").reset_index(drop=True)
    return underlying, df, futures_price


def fetch_futures_daily(api, vcode, days=120):
    """拉期货日线（Parkinson HV）"""
    try:
        underlying = tq_contract_month(vcode)
        kline = api.get_kline_serial(underlying, 86400, data_length=days)
        df = pd.DataFrame({
            "date": pd.to_datetime(kline["datetime"]),
            "open": kline["open"], "high": kline["high"],
            "low": kline["low"], "close": kline["close"],
            "volume": kline["volume"],
        })
        return df
    except Exception:
        return None


def tq_api():
    return TqApi(auth=TqAuth(TQ_USER, TQ_PASS))


def scan_all_varieties(vcodes, scanner_fn, verbose=True):
    """分批跑所有品种，带重连+异常隔离。scanner_fn(api, vcode) → result"""
    results = {}
    for i in range(0, len(vcodes), BATCH_SIZE):
        batch = vcodes[i:i + BATCH_SIZE]
        api = tq_api()
        for vcode in batch:
            try:
                results[vcode] = scanner_fn(api, vcode)
            except Exception as e:
                if verbose:
                    print(f"     ❌ {vcode} → {str(e)[:40]}（跳过）")
        api.close()
        if i + BATCH_SIZE < len(vcodes):
            time.sleep(BATCH_COOLDOWN)
    return results
