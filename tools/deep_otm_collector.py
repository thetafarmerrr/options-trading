#!/usr/bin/env python3
"""
deep_otm_collector.py — CTP MdApi 深虚期权 8 时点采集
─────────────────────────────────────────────────────
订阅沪金/豆粕/PTA 最虚 2-3 档 Call+Put，在袁永健 8 个决策时点
自动保存 bid/ask/量快照到 CSV。积累 ≥6 个月后可用分位数。

用法：
  python3 tools/deep_otm_collector.py --discover    # 发现深虚合约→写配置
  python3 tools/deep_otm_collector.py               # 订阅 + 8 时点采集
  python3 tools/deep_otm_collector.py --check       # 检查 CTP 连接+合约是否可订阅

原理：
  CTP MdApi → SubscribeMarketData(合约列表) → OnRtnDepthMarketData 持续推送
  → 在 8 个决策时点各存一次最新快照 → data/deep_otm_history.csv
"""

import os
import sys
import csv
import json
import time
import signal
import threading
import argparse
from datetime import datetime, date
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 全局退出信号
# ═══════════════════════════════════════════════════════════════
_shutdown = threading.Event()

# ═══════════════════════════════════════════════════════════════
# 路径
# ═══════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_DIR / "data" / "deep_otm_config.json"
OUTPUT_FILE = PROJECT_DIR / "data" / "deep_otm_history.csv"
ENV_FILE = PROJECT_DIR / ".env"

# ═══════════════════════════════════════════════════════════════
# 加载 .env
# ═══════════════════════════════════════════════════════════════
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

USER_ID = os.environ.get("CTP_USER_ID", "")
PASSWORD = os.environ.get("CTP_PASSWORD", "")
BROKER_ID = os.environ.get("CTP_BROKER_ID", "66666")
AUTH_CODE = os.environ.get("CTP_AUTH_CODE", "")
APP_ID = os.environ.get("CTP_APP_ID", "client_goldopt_1.0.0")
MD_ADDR = os.environ.get("CTP_MD_ADDR", "tcp://140.206.167.53:53213")
SYSTEM_INFO = f"macOS;goldopt/1.0.0;{APP_ID}"

# ═══════════════════════════════════════════════════════════════
# 品种参数：标的价格 + 行权价间隔 + 虚值深度
# ═══════════════════════════════════════════════════════════════
VARIETY_CONFIG = {
    "au": {
        "name": "沪金", "futures": 870, "interval": 8,
        "otm_call_pct": 0.10, "otm_put_pct": 0.10, "n_strikes": 5,
        "valid_months": [2, 4, 6, 8, 10, 12],
        "prefix": "au", "exchange": "SHFE",
        # SimNow 统一格式，无分隔符。2-digit year（已验证 ctp_farm.py）
        "ctp_fmt": "{prefix}{yymm}{cp}{strike}",
    },
    "m": {
        "name": "豆粕", "futures": 2800, "interval": 50,
        "otm_call_pct": 0.10, "otm_put_pct": 0.10, "n_strikes": 4,
        "valid_months": [1, 5, 9],
        "prefix": "m", "exchange": "DCE",
        "ctp_fmt": "{prefix}{yymm}{cp}{strike}",
    },
    "ta": {
        "name": "PTA", "futures": 4800, "interval": 50,
        "otm_call_pct": 0.10, "otm_put_pct": 0.10, "n_strikes": 4,
        "valid_months": [1, 5, 9],
        "prefix": "TA", "exchange": "CZCE",
        # SimNow 郑商所：1 位年份（TA609 = TA + 6(2026) + 09(9月)）已验证 ctp_farm.py
        "ctp_fmt": "{prefix}{y}{mm}{cp}{strike}",
    },
}

# 标的期货合约映射：每个品种额外订阅一份标的期货，用于实时标的价格
UNDERLYING_FUTURES = {
    "au": "au2610",   # 沪金主力期货（SimNow 格式）
    "m": "m2609",     # 豆粕主力期货（SimNow 格式）
    "ta": "TA609",    # PTA 主力期货（SimNow 格式，1位年份）
}

# SimNow CTP 合约命名（已验证 ctp_farm.py）
# 格式: {品种码}{YYMM}{C/P}{行权价}，无横杠，2 位年份
# SHFE: au2608C400  DCE: m2609C3400  CZCE: TA609C6200

# ═══════════════════════════════════════════════════════════════
# 袁永健 8 个关键决策时点
# ═══════════════════════════════════════════════════════════════
SNAPSHOT_TIMES = [
    ("09:00", "开盘"),
    ("09:30", "试仓结束"),
    ("10:00", "加仓窗口"),
    ("10:30", "第二节开盘"),
    ("11:00", "上午收盘前"),
    ("13:30", "下午开盘"),
    ("14:30", "谨慎窗口"),
    ("14:55", "强制平仓前"),
]

# ═══════════════════════════════════════════════════════════════
# CSV 字段
# ═══════════════════════════════════════════════════════════════
CSV_FIELDS = [
    "date", "time_slot", "time_label", "variety", "contract",
    "strike", "direction", "bid", "ask", "bid_vol", "ask_vol",
    "last", "volume", "open_interest", "underlying_price",
    "moneyness", "tick_time", "is_stale",
]


# ═══════════════════════════════════════════════════════════════
# 辅助：合约命名
# ═══════════════════════════════════════════════════════════════

def build_ctp_option_code(vcode: str, yy: int, mm: int, direction: str,
                          strike: int) -> str:
    """构造 CTP 期权合约代码。

    SimNow 统一格式，无分隔符。通过 VARIETY_CONFIG.ctp_fmt 定义每品种格式。
    示例: au2610C400, m2609C3400, TA609C6200
    """
    cfg = VARIETY_CONFIG[vcode]
    fmt = cfg.get("ctp_fmt", "{prefix}{yymm}{cp}{strike}")
    dir_char = "C" if direction.upper() == "C" else "P"
    return fmt.format(
        prefix=cfg["prefix"],
        y=yy % 10,                # 1 位年份（郑商所 SimNow）
        yy=f"{yy % 100:02d}",     # 2 位年份
        yymm=f"{yy % 100:02d}{mm:02d}",
        mm=f"{mm:02d}",
        cp=dir_char,
        strike=strike,
    )


def pick_active_month(vcode: str) -> tuple:
    """选当前活跃月份（近月）和次远月。"""
    cfg = VARIETY_CONFIG[vcode]
    valid = sorted(cfg["valid_months"])
    today = date.today()
    cur_month = today.month
    cur_year = today.year % 100

    # 跳过当月（可能已到期或临近到期）
    ordered = []
    for m in valid:
        if m >= cur_month + 1:
            ordered.append((m, cur_year))
    for m in valid:
        if m < cur_month + 1:
            ordered.append((m, cur_year + 1))

    near = ordered[0] if ordered else (cur_month + 1, cur_year)
    far = ordered[1] if len(ordered) > 1 else None
    return near, far


def calc_otm_strikes(vcode: str, futures_price: float, direction: str) -> list:
    """计算深虚 OTM 行权价列表（从最虚往近排）。"""
    cfg = VARIETY_CONFIG[vcode]
    interval = cfg["interval"]
    n = cfg["n_strikes"]

    if direction == "C":
        target = futures_price * (1 + cfg["otm_call_pct"])
    else:
        target = futures_price * (1 - cfg["otm_put_pct"])

    # 找到目标行权价
    base = round(target / interval) * interval

    # 往更虚的方向取 n 个
    strikes = []
    if direction == "C":
        for i in range(n):
            strikes.append(base + i * interval)
    else:
        for i in range(n):
            strikes.append(base - i * interval)

    return strikes


# ═══════════════════════════════════════════════════════════════
# 发现模式：用 akshare 查链 → 构造 CTP 代码 → 写配置
# ═══════════════════════════════════════════════════════════════

def discover_contracts():
    """用 akshare 拉取期权链数据，找出深虚合约，构造 CTP 代码。

    返回 list of dict，写入 CONFIG_FILE。
    """
    print("\n🔍 发现模式：扫描深虚合约…")
    print("   使用 akshare 新浪源获取期权链 → 计算深虚行权价 → 构造 CTP 代码\n")

    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from _ak_data import pick_two_contracts, fetch_option_chain
    except ImportError as e:
        print(f"❌ 无法导入 _ak_data: {e}")
        return None

    import akshare as ak

    # 品种 → akshare symbol 映射
    symbol_map = {
        "au": "黄金期权", "m": "豆粕期权", "ta": "PTA期权",
    }

    all_contracts = []
    today = date.today()

    for vcode in ["au", "m", "ta"]:
        cfg = VARIETY_CONFIG[vcode]
        name = cfg["name"]
        symbol = symbol_map[vcode]

        # 用 pick_two_contracts 选近月+次远月（akshare 格式）
        near_ak, far_ak = pick_two_contracts(symbol, vcode)
        if not near_ak:
            print(f"  ⚠️ {name}: pick_two_contracts 返回空")
            continue

        print(f"  📡 {name}: 拉取 {symbol} {near_ak} 期权链…")

        try:
            _, df, futures_price = fetch_option_chain(vcode, symbol, near_ak)
        except Exception as e:
            print(f"     ❌ 拉取失败: {e}")
            continue

        if df is None or df.empty:
            print(f"     ❌ 无数据")
            continue

        print(f"     标的 ≈ {futures_price:.0f}  | 共 {len(df)} 个行权价")

        # 解析近月合约的年月
        import re
        m = re.search(r'(\d{2})(\d{2})$', near_ak)
        if m:
            near_yy, near_mm = int(m.group(1)), int(m.group(2))
        else:
            near_yy, near_mm = today.year % 100, today.month + 1

        # 次远月
        far_yy = far_mm = None
        if far_ak:
            mf = re.search(r'(\d{2})(\d{2})$', far_ak)
            if mf:
                far_yy, far_mm = int(mf.group(1)), int(mf.group(2))

        # 计算深虚行权价
        call_strikes = calc_otm_strikes(vcode, futures_price, "C")
        put_strikes = calc_otm_strikes(vcode, futures_price, "P")
        avail_strikes = set(df["strike"].astype(int).tolist())

        for month_yy, month_mm, label in [(near_yy, near_mm, ""),
                                            (far_yy, far_mm, "[远月]")]:
            if month_yy is None:
                continue

            used_strikes = set()  # 去重：同一月份+方向下不重复取同一行权价
            for direction, strikes in [("C", call_strikes), ("P", put_strikes)]:
                for strike in strikes:
                    if strike not in avail_strikes:
                        diffs = [(abs(s - strike), s) for s in avail_strikes]
                        if diffs:
                            _, nearest = min(diffs)
                            strike = nearest
                        else:
                            continue

                    # 去重：同月份同方向同行权价只记一次
                    dedup_key = (month_yy, month_mm, direction, strike)
                    if dedup_key in used_strikes:
                        continue
                    used_strikes.add(dedup_key)

                    ctp_code = build_ctp_option_code(vcode, month_yy, month_mm,
                                                      direction, strike)
                    moneyness = (strike / futures_price
                                 if direction == "C"
                                 else futures_price / strike)
                    print(f"     ✅ {strike:<6} → {ctp_code:<16} {label} OTM {moneyness:.2%}")

                    all_contracts.append({
                        "ctp_code": ctp_code,
                        "variety": vcode,
                        "name": name,
                        "direction": direction,
                        "strike": strike,
                        "month": f"{month_yy:02d}{month_mm:02d}",
                        "moneyness": round(moneyness, 4),
                        "futures_est": round(futures_price, 0),
                    })

    if not all_contracts:
        print("\n❌ 未发现任何深虚合约")
        return None

    # 写配置
    config = {
        "discovered": date.today().isoformat(),
        "varieties": ["au", "m", "ta"],
        "futures_prices": {},
        "underlying_futures": UNDERLYING_FUTURES,
        "contracts": all_contracts,
    }

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2))

    print(f"\n✅ 发现 {len(all_contracts)} 个深虚合约 → {CONFIG_FILE}")
    print(f"   下一步：python3 tools/deep_otm_collector.py")

    # 汇总
    by_variety = {}
    for c in all_contracts:
        by_variety.setdefault(c["variety"], []).append(c)
    for vcode, contracts in by_variety.items():
        name = VARIETY_CONFIG[vcode]["name"]
        codes = [c["ctp_code"] for c in contracts]
        print(f"   {name}: {len(contracts)} 个 = {', '.join(codes)}")

    return config


# ═══════════════════════════════════════════════════════════════
# CTP MdApi 采集
# ═══════════════════════════════════════════════════════════════

class MdSpi:
    """CTP 行情回调。"""

    def __init__(self, underlying_map: dict = None):
        self.connected = False
        self.logged_in = False
        self.login_error = ""
        self.subscribed_count = 0
        self.sub_errors = []
        self._cond = threading.Condition()

        # 最新行情缓存: {InstrumentID: {bid, ask, ...}}
        self.snapshots = {}
        self.snap_lock = threading.Lock()

        # 标的期货价格: {futures_ctp_code: last_price}
        self.underlying_prices = {}
        # 期权合约→标的期货映射: {option_ctp_code: futures_ctp_code}
        self._opt_to_ul = underlying_map or {}

    def _signal(self, attr):
        with self._cond:
            setattr(self, attr, True)
            self._cond.notify_all()

    def _wait(self, attr, timeout=20):
        deadline = time.time() + timeout
        with self._cond:
            while not getattr(self, attr):
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
        return True

    # ── 连接 ──

    def OnFrontConnected(self):
        print("✅ MdApi 前置连接成功 → 登录…")
        self._api.ReqUserLogin(
            BROKER_ID, USER_ID, PASSWORD,
            len(SYSTEM_INFO), SYSTEM_INFO
        )

    def OnFrontDisconnected(self, nReason):
        reasons = {0x1001: "网络读失败", 0x1002: "网络写失败",
                   0x2001: "心跳超时", 0x2002: "发送心跳失败", 0x2003: "收到错误报文"}
        print(f"⚠️  MdApi 断开 (原因: {reasons.get(nReason, nReason)})")
        self._signal("connected")

    # ── 登录 ──

    def OnRspUserLogin(self, pRsp, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            self.login_error = f"[{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}"
            print(f"❌ MdApi 登录失败: {self.login_error}")
            self._signal("logged_in")
            return
        print(f"✅ MdApi 登录成功！交易日: {pRsp.TradingDay}")
        self._signal("logged_in")

    # ── 行情推送 ──

    def OnRtnDepthMarketData(self, pDepth):
        """每 500ms 推送一次。缓存最新数据 + 标的价格 + 时间戳。"""
        if not pDepth or not pDepth.InstrumentID:
            return

        instr = pDepth.InstrumentID

        def _v(x):
            """过滤无效值（CTP 无数据返回 DBL_MAX）。"""
            return x if (x > 0 and x < 1e10) else 0.0

        tick_time = f"{pDepth.UpdateTime}.{pDepth.UpdateMillisec:03d}"
        last = _v(pDepth.LastPrice)

        # 检测是否是标的期货
        if instr in self.underlying_prices or instr in UNDERLYING_FUTURES.values():
            if last > 0:
                self.underlying_prices[instr] = last
            return  # 标的期货不存入 snapshots

        snap = {
            "bid": _v(pDepth.BidPrice1),
            "ask": _v(pDepth.AskPrice1),
            "bid_vol": int(pDepth.BidVolume1) if pDepth.BidVolume1 > 0 else 0,
            "ask_vol": int(pDepth.AskVolume1) if pDepth.AskVolume1 > 0 else 0,
            "last": last,
            "volume": int(pDepth.Volume) if pDepth.Volume > 0 else 0,
            "oi": int(pDepth.OpenInterest) if pDepth.OpenInterest > 0 else 0,
            "tick_time": tick_time,
            "trading_day": pDepth.TradingDay,
        }
        with self.snap_lock:
            self.snapshots[instr] = snap

    # ── 订阅回调 ──

    def OnRspSubMarketData(self, pSpecificInstrument, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            err = f"[{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg} ({pSpecificInstrument.InstrumentID if pSpecificInstrument else '?'})"
            self.sub_errors.append(err)
            print(f"  ❌ 订阅失败: {err}")
        else:
            self.subscribed_count += 1
            name = pSpecificInstrument.InstrumentID if pSpecificInstrument else "?"
            print(f"  ✅ 订阅成功: {name}")

    # ── 错误 ──

    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"⚠️  MdApi 错误: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")


def connect_md(spi: MdSpi, contracts: list) -> tuple:
    """连接 MdApi → 登录 → 批量订阅合约（期权 + 标的期货）。返回 (api, success)。"""

    api_cls = __import__("openctp_ctp", fromlist=["mdapi"]).mdapi.CThostFtdcMdApi
    api = api_cls.CreateFtdcMdApi()
    spi._api = api
    api.RegisterSpi(spi)
    api.RegisterFront(MD_ADDR)
    api.Init()

    print(f"🔗 连接行情前置: {MD_ADDR}")
    print(f"   BrokerID: {BROKER_ID}  |  UserID: {USER_ID}")

    if not spi._wait("logged_in", timeout=15):
        print(f"\n❌ MdApi 登录超时: {spi.login_error}")
        api.Release()
        return None, False

    # 先订阅标的期货（获取实时标的价格）
    futures_codes = list(set(UNDERLYING_FUTURES.values()))
    print(f"\n📡 订阅 {len(futures_codes)} 个标的期货…")
    for code in futures_codes:
        api.SubscribeMarketData(code.encode(), 1)

    # 批量订阅期权
    codes = [c["ctp_code"] for c in contracts]
    print(f"📡 订阅 {len(codes)} 个深虚期权…")
    for code in codes:
        api.SubscribeMarketData(code.encode(), 1)

    # 等订阅回报
    time.sleep(3.0)

    total_subs = len(futures_codes) + len(codes)
    ok = spi.subscribed_count
    print(f"\n   订阅结果: {ok}/{total_subs} 成功")
    if spi.sub_errors:
        for err in spi.sub_errors[:5]:
            print(f"   {err}")

    if ok == 0:
        print(f"\n❌ 所有合约订阅失败，无法采集")
        api.Release()
        return None, False

    return api, True


# ═══════════════════════════════════════════════════════════════
# 时间检测与快照保存
# ═══════════════════════════════════════════════════════════════

def _time_matches(now: datetime, target: str) -> bool:
    """检测当前时间是否匹配目标时点（HH:MM）。在 ±30s 窗口内触发。"""
    th, tm = map(int, target.split(":"))
    target_minutes = th * 60 + tm
    current_minutes = now.hour * 60 + now.minute
    return abs(current_minutes - target_minutes) <= 0


def _time_passed(now: datetime, target: str) -> bool:
    """检测当前时间是否已超过目标时点。"""
    th, tm = map(int, target.split(":"))
    target_minutes = th * 60 + tm
    current_minutes = now.hour * 60 + now.minute
    return current_minutes > target_minutes


def save_snapshot(spi: MdSpi, contracts: list, time_slot: str, time_label: str):
    """保存当前所有订阅合约的最新行情到 CSV。

    自动计算：
    - underlying_price：从标的期货 tick 获取
    - moneyness：strike / underlying（C）或 underlying / strike（P）
    - is_stale：tick_time 距当前时间 > 120s 标记为 1
    """
    today_str = date.today().isoformat()
    now = time.time()

    rows = []
    with spi.snap_lock:
        for c in contracts:
            code = c["ctp_code"]
            snap = spi.snapshots.get(code)
            if snap is None:
                continue

            vcode = c["variety"]
            direction = c["direction"]
            strike = c["strike"]

            # 获取标的价格
            ul_code = spi._opt_to_ul.get(code, "")
            ul_price = spi.underlying_prices.get(ul_code, 0.0)

            # 计算虚值度
            if ul_price > 0 and strike > 0:
                moneyness = strike / ul_price if direction == "C" else ul_price / strike
            else:
                moneyness = 0.0

            # Stale 检测
            tick_time_str = snap.get("tick_time", "00:00:00.000")
            is_stale = 1  # 默认 stale
            try:
                # 解析 tick_time: HH:MM:SS.mmm
                parts = tick_time_str.split(":")
                if len(parts) >= 2:
                    tick_seconds = (int(parts[0]) * 3600 +
                                    int(parts[1]) * 60 +
                                    float(parts[2].split(".")[0]))
                    now_total = (datetime.now().hour * 3600 +
                                 datetime.now().minute * 60 +
                                 datetime.now().second)
                    age = abs(now_total - tick_seconds)
                    is_stale = 1 if age > 120 else 0
            except (ValueError, IndexError):
                pass

            rows.append({
                "date": today_str,
                "time_slot": time_slot,
                "time_label": time_label,
                "variety": vcode,
                "contract": code,
                "strike": strike,
                "direction": direction,
                "bid": snap["bid"],
                "ask": snap["ask"],
                "bid_vol": snap["bid_vol"],
                "ask_vol": snap["ask_vol"],
                "last": snap["last"],
                "volume": snap["volume"],
                "open_interest": snap["oi"],
                "underlying_price": round(ul_price, 2) if ul_price > 0 else "",
                "moneyness": round(moneyness, 4) if moneyness > 0 else "",
                "tick_time": tick_time_str,
                "is_stale": is_stale,
            })

    if not rows:
        print(f"  ⏰ {time_slot} ({time_label}): 无行情数据（可能合约尚未推送）")
        return

    # 追加写入 CSV
    file_exists = OUTPUT_FILE.exists()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    # 统计
    has_bid = sum(1 for r in rows if r["bid"] > 0)
    stale = sum(1 for r in rows if r["is_stale"])
    print(f"  ⏰ {time_slot} ({time_label}): {len(rows)} 条 "
          f"(有报价:{has_bid} stale:{stale})")


def run_collection(contracts: list):
    """主循环：连接 → 订阅 → 等待时点 → 保存快照 → 收盘退出。"""
    if not contracts:
        print("❌ 合约列表为空。请先运行 --discover")
        return

    # 构建期权→标的映射（用于 save_snapshot 查标的价格）
    opt_to_ul = {}
    for c in contracts:
        vcode = c["variety"]
        ul = UNDERLYING_FUTURES.get(vcode, "")
        if ul:
            opt_to_ul[c["ctp_code"]] = ul

    print(f"\n📊 深虚期权 8 时点采集")
    print(f"   品种: AU / M / TA")
    print(f"   期权: {len(contracts)} 个  |  标的期货: {len(set(UNDERLYING_FUTURES.values()))} 个")
    print(f"   时点: {', '.join(t for t, _ in SNAPSHOT_TIMES)}")
    print(f"   输出: {OUTPUT_FILE}\n")

    # ── 连接 MdApi ──
    spi = MdSpi(underlying_map=opt_to_ul)
    # 预填充 underlying_prices 的 key，方便 OnRtnDepthMarketData 判断
    for ul_code in UNDERLYING_FUTURES.values():
        spi.underlying_prices[ul_code] = 0.0

    api, ok = connect_md(spi, contracts)
    if not ok:
        return

    # ── 等待行情到达 ──
    print("\n⏳ 等待行情推送…")
    wait_start = time.time()
    while time.time() - wait_start < 30:
        with spi.snap_lock:
            count = len(spi.snapshots)
        if count > 0:
            print(f"   ✅ 已收到 {count} 个合约的行情")
            break
        time.sleep(1)
    else:
        print("   ⚠️ 30s 内未收到任何行情推送（可能非交易时段或网络问题）")

    # ── 时点列表：只保留还没到的 ──
    now = datetime.now()
    pending = [(t, l) for t, l in SNAPSHOT_TIMES if not _time_passed(now, t)]

    if not pending:
        print("\n⚠️ 当前时间已过所有采集时点（已收盘？）")
        # 保存当前快照作为收盘记录
        now_str = now.strftime("%H:%M")
        save_snapshot(spi, contracts, now_str, "手动收盘")
        api.Release()
        return

    print(f"\n📋 待采集时点: {len(pending)} 个")
    for t, l in pending:
        print(f"   {t} ({l})")

    # ── 主循环：等待时点触发 ──
    saved_slots = set()
    print(f"\n🔄 开始监控（Ctrl+C 退出）…")
    print(f"{'─'*50}")

    while not _shutdown.is_set():
        now = datetime.now()

        # 检查是否已过 15:05（收盘后自动退出）
        if now.hour >= 15 and now.minute >= 5:
            print(f"\n🛑 {now.strftime('%H:%M')} 已收盘，退出")
            break

        # 检查是否有未保存的时点
        for time_slot, time_label in pending:
            if time_slot in saved_slots:
                continue
            if _time_matches(now, time_slot):
                save_snapshot(spi, contracts, time_slot, time_label)
                saved_slots.add(time_slot)
                break

        # 全部时点已保存 → 退出
        if len(saved_slots) >= len(pending):
            print(f"\n✅ 所有时点已采集，退出")
            break

        time.sleep(5)  # 每 5 秒检查一次

    # ── 收盘后自动保存最后一条 ──
    now = datetime.now()
    last_slot = f"收盘-{now.strftime('%H:%M')}"
    if last_slot not in saved_slots:
        save_snapshot(spi, contracts, last_slot, "收盘")

    print(f"\n📊 本次采集完成: {len(saved_slots)} 个时点 → {OUTPUT_FILE}")

    # 统计今日采集
    today_str = date.today().isoformat()
    total_rows = 0
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r") as f:
            for row in csv.DictReader(f):
                if row["date"] == today_str:
                    total_rows += 1
    print(f"   今日累计: {total_rows} 行")

    api.Release()


# ═══════════════════════════════════════════════════════════════
# 检查模式：快速验证 CTP 连接 + 合约可订阅
# ═══════════════════════════════════════════════════════════════

def check_connection():
    """快速检查 MdApi 连接 + 订阅是否可用。"""
    if not CONFIG_FILE.exists():
        print(f"❌ 配置文件不存在: {CONFIG_FILE}")
        print(f"   请先运行: python3 tools/deep_otm_collector.py --discover")
        return

    config = json.loads(CONFIG_FILE.read_text())
    contracts = config["contracts"]
    first_5 = contracts[:5]

    print(f"🔍 检查模式：验证 CTP MdApi 连接…")
    print(f"   测试合约: {len(first_5)} 个（{', '.join(c['ctp_code'] for c in first_5)}）")

    spi = MdSpi()
    api_cls = __import__("openctp_ctp", fromlist=["mdapi"]).mdapi.CThostFtdcMdApi
    api = api_cls.CreateFtdcMdApi()
    spi._api = api
    api.RegisterSpi(spi)
    api.RegisterFront(MD_ADDR)
    api.Init()

    if not spi._wait("logged_in", timeout=15):
        print(f"❌ 登录失败: {spi.login_error}")
        api.Release()
        return

    # 订阅测试
    for c in first_5:
        api.SubscribeMarketData(c["ctp_code"].encode(), 1)

    time.sleep(3.0)
    print(f"\n   订阅: {spi.subscribed_count}/{len(first_5)} 成功")
    if spi.sub_errors:
        for e in spi.sub_errors:
            print(f"   错误: {e}")

    # 等待行情
    time.sleep(5)
    with spi.snap_lock:
        count = len(spi.snapshots)
    print(f"   行情: {count} 个合约有推送")

    if count > 0:
        print(f"\n✅ CTP MdApi 连接正常，可以运行采集")
    else:
        print(f"\n⚠️ 连接正常但无行情推送（非交易时段？）")

    api.Release()


# ═══════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="深虚期权 8 时点采集（CTP MdApi）")
    parser.add_argument("--discover", action="store_true",
                        help="发现深虚合约并写入配置文件")
    parser.add_argument("--check", action="store_true",
                        help="快速验证 CTP 连接+合约可订阅")
    args = parser.parse_args()

    # Ctrl+C 处理
    def _on_sigint(signum, frame):
        print("\n\n⚠️ 收到中断信号，正在退出…")
        _shutdown.set()
    signal.signal(signal.SIGINT, _on_sigint)

    if args.discover:
        discover_contracts()
    elif args.check:
        check_connection()
    else:
        # 正常采集模式
        if not CONFIG_FILE.exists():
            print(f"❌ 配置文件不存在: {CONFIG_FILE}")
            print(f"   请先运行: python3 tools/deep_otm_collector.py --discover")
            sys.exit(1)

        config = json.loads(CONFIG_FILE.read_text())
        contracts = config.get("contracts", [])
        if not contracts:
            print("❌ 配置文件中无合约")
            sys.exit(1)

        run_collection(contracts)


if __name__ == "__main__":
    main()
