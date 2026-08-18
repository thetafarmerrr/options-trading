#!/usr/bin/env python3
"""
deep_otm_collector.py — 天勤(tqsdk) 深虚期权 8 时点采集
─────────────────────────────────────────────────────
订阅沪金/豆粕/PTA 最虚 2-3 档 Call+Put，在袁永健 8 个决策时点
自动保存 bid/ask/量快照到 CSV。积累 ≥6 个月后可用分位数。

【用途：袁永健买方策略数据搜集器 —— 深度虚值"买彩票"】
  深虚权利金标准化价格 < 自身历史 P25（不含今日）→ 便宜彩票可埋伏（买方，低成
  本小仓位博尾部行情，占总资金 ≤5%）。不是卖方扫描器，数据不用于"卖它收权利
  金"判断。8/18 标记：曾被误当卖方工具，特此注明。

用法：
  python3 tools/deep_otm_collector.py --discover    # 发现深虚合约→写配置
  python3 tools/deep_otm_collector.py               # 订阅 + 8 时点采集
  python3 tools/deep_otm_collector.py --check       # 检查天勤连接+合约是否可订阅

原理：
  天勤 tqsdk → TqApi.get_quote(合约) → wait_update 轮询快照
  → 在 8 个决策时点各存一次最新快照 → data/deep_otm_history.csv
  8/17 换源：SimNow 无深虚盘口（m 全天 0、au 深虚空、ta 只有 last），
  天勤有真实深虚行情且 78 合约并发 4.2s 全订阅、全有数据。
"""

import os
import sys
import re
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
OUTPUT_TRADING = PROJECT_DIR / "data" / "deep_otm_trading.csv"
OUTPUT_EOD = PROJECT_DIR / "data" / "deep_otm_eod.csv"
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

# 天勤行情源账号（8/17 换源后使用，monitor_stop 同源）
TQ_USER = os.environ.get("TQ_USER", "")
TQ_PASS = os.environ.get("TQ_PASS", "")

# ═══════════════════════════════════════════════════════════════
# 品种参数：标的价格 + 行权价间隔 + 虚值深度
# ═══════════════════════════════════════════════════════════════
# otm_call_pct/otm_put_pct：已废弃（8/15 #15 改造后无引用），保留壳勿删 n_strikes
VARIETY_CONFIG = {
    "au": {
        "name": "沪金", "futures": 870, "interval": 8,
        "otm_call_pct": 0.30, "otm_put_pct": 0.30, "n_strikes": 5,
        "valid_months": [2, 4, 6, 8, 10, 12],
        "prefix": "au", "exchange": "SHFE",
        # SimNow 统一格式，无分隔符。2-digit year（已验证 ctp_farm.py）
        "ctp_fmt": "{prefix}{yymm}{cp}{strike}",
    },
    "m": {
        "name": "豆粕", "futures": 2800, "interval": 50,
        "otm_call_pct": 0.30, "otm_put_pct": 0.30, "n_strikes": 4,
        "valid_months": [1, 5, 9],
        "prefix": "m", "exchange": "DCE",
        "ctp_fmt": "{prefix}{yymm}{cp}{strike}",
    },
    "ta": {
        "name": "PTA", "futures": 4800, "interval": 50,
        "otm_call_pct": 0.30, "otm_put_pct": 0.30, "n_strikes": 4,
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
    "moneyness", "tick_time", "is_stale", "is_eod_proxy",
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


def build_ctp_futures_code(vcode: str, yy: int, mm: int) -> str:
    """构造 CTP 标的期货代码。格式同 build_ctp_option_code，但无 C/P + 行权价。"""
    cfg = VARIETY_CONFIG[vcode]
    fmt = cfg.get("ctp_fmt", "{prefix}{yymm}")
    return fmt.format(
        prefix=cfg["prefix"],
        y=yy % 10,
        yy=f"{yy % 100:02d}",
        yymm=f"{yy % 100:02d}{mm:02d}",
        mm=f"{mm:02d}",
        cp="",
        strike="",
    )


# 品种 → 天勤交易所前缀
EXCHANGE_MAP = {"au": "SHFE", "m": "DCE", "ta": "CZCE"}


def ctp_to_tq_code(code: str, vcode: str) -> str:
    """CTP 合约代码 → 天勤代码（8/17 换源）。

    DCE 必须带连字符，SHFE/CZCE 不带（8/17 实测 DCE.m2609C3400 报"不存在"）：
      au2610C1512  → SHFE.au2610C1512
      TA611P4800   → CZCE.TA611P4800
      m2609C3400   → DCE.m2609-C-3400
    """
    ex = EXCHANGE_MAP.get(vcode, "")
    if vcode == "m":
        m = re.match(r"^([a-zA-Z]+)(\d{4})([CP])(\d+)$", code)
        if m:
            return f"DCE.{m.group(1)}{m.group(2)}-{m.group(3)}-{m.group(4)}"
    return f"{ex}.{code}"

def futures_price_fallback(vcode: str) -> float:
    """标的期货价兜底：优先 VARIETY_CONFIG.futures，否则 0（select_boundary 会空）。"""
    return float(VARIETY_CONFIG[vcode].get("futures", 0) or 0)


def select_boundary_strikes(avail: set, futures_price: float, direction: str,
                            n: int, max_moneyness: float = 3.0) -> list:
    """有效边界法：从挂牌链最虚端往近扫，取最虚 n 档。

    只做结构选档（strike 列存在性），不做价格/流动性判断——
    0.5 门槛 + 流动性留在采集/P0 层（yuan-yongjian-strategy.md §3.1 分层）。
    僵尸剔除也在采集层（CTP 实测）：akshare 深虚档 bid/ask/last 常空，
    discover 阶段无法可靠判僵尸（8/14 已确认沪金 P648 全空是常态）。
    max_moneyness: 仅作异常剔除安全网（防 akshare 脏数据出现 3 倍价档）。
    不设硬门槛——最虚档由挂牌链决定，非系数拍（8/15 实测 C1512
    moneyness 1.60 曾被 1.6 误挡，P648 同理，硬上限会漏最虚档）。
    """
    strikes = sorted(avail)
    if direction == "C":
        ordered = list(reversed(strikes))  # 从高（最虚）往低扫
        edge = [s for s in ordered
                if futures_price > 0 and s / futures_price <= max_moneyness]
    else:
        ordered = strikes  # 从低（最虚）往高扫
        edge = [s for s in ordered
                if futures_price > 0 and futures_price / s <= max_moneyness]
    return edge[:n]


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
        from _ak_data import pick_active_months, fetch_option_chain
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

        # 选活跃月：按期权链总持仓排序取前 n 个月（近月+次近+远月）。
        # discover 层只筛活跃度，不排 DTE/临近交割——真门槛（流动性/0.5）在
        # 采集层 CTP 实测（yuan-yongjian-strategy.md §3.1 分层，8/15 定案）。
        # refresh=True：手动 discover 总是强制重拉，不吃 scanner/iv_collector 的缓存。
        active_months = pick_active_months(symbol, vcode, n=3, refresh=True)
        if not active_months:
            print(f"  ⚠️ {name}: 无活跃月份")
            continue

        months_desc = ", ".join(f"{c}({oi/1000:.0f}K)" for c, oi in active_months)
        print(f"  📡 {name}: 活跃月（总持仓降序）= {months_desc}")

        # 有效边界法选档：从各月份挂牌链最虚端往近扫，取最虚 n 档（纯结构，不含 0.5/流动性）
        # 注意：每个月份独立拉链选档——远月链更宽（如 m2701 有 3600，近月 m2609 只有 3500），
        # 复用近月 edge_map 会漏掉远月独有的更虚档（8/15 瞒瞒指出，已验证远月链含 3600）。
        edge_map = {}          # ak -> {"C": [...], "P": [...]}
        month_fpx = {}         # ak -> 该月独立期货价
        month_yy_mm = {}       # ak -> (yy, mm)
        month_oi = {c: oi for c, oi in active_months}

        for month_idx, (month_ak, _oi) in enumerate(active_months):
            label = "" if month_idx == 0 else f"[{month_idx + 1}月]"
            try:
                _, mdf, mfpx = fetch_option_chain(vcode, symbol, month_ak)
            except Exception as e:
                print(f"     ⚠️ {month_ak} 拉取失败（跳过）: {e}")
                continue
            if mdf is None or mdf.empty:
                print(f"     ⚠️ {month_ak} 无数据（跳过）")
                continue

            mfpx = mfpx if mfpx > 0 else futures_price_fallback(vcode)
            month_fpx[month_ak] = mfpx

            # 解析合约年月（兼容 1 位年份 TA609 / 2 位 m2609）
            m2 = re.search(r'(\d{1,2})(\d{2})$', month_ak)
            if m2:
                myy, mm_ = int(m2.group(1)), int(m2.group(2))
                if myy < 10:
                    myy = 20 + myy
            else:
                myy, mm_ = today.year % 100, today.month + 1
            month_yy_mm[month_ak] = (myy, mm_)

            avail = set(mdf["strike"].astype(int).tolist())
            edge_map[month_ak] = {
                "C": select_boundary_strikes(avail, mfpx, "C", cfg["n_strikes"]),
                "P": select_boundary_strikes(avail, mfpx, "P", cfg["n_strikes"]),
            }
            print(f"     {label}{month_ak}: 标的 ≈ {mfpx:.0f} | "
                  f"共 {len(mdf)} 档 | 总持仓 {month_oi[month_ak]/1000:.0f}K")

        for month_ak, strikes_map in edge_map.items():
            myy, mm_ = month_yy_mm[month_ak]
            fpx_this = month_fpx[month_ak]
            label = "" if month_ak == active_months[0][0] else "[次月+]"

            used_strikes = set()  # 去重：同一月份+方向下不重复取同一行权价
            for direction, strikes in strikes_map.items():
                for strike in strikes:
                    # select_boundary_strikes 输出必然在 avail 内，无需再校准

                    # 去重：同月份同方向同行权价只记一次
                    dedup_key = (myy, mm_, direction, strike)
                    if dedup_key in used_strikes:
                        continue
                    used_strikes.add(dedup_key)

                    ctp_code = build_ctp_option_code(vcode, myy, mm_,
                                                      direction, strike)
                    moneyness = (strike / fpx_this
                                 if direction == "C"
                                 else fpx_this / strike)
                    print(f"     ✅ {strike:<6} → {ctp_code:<16} {label} OTM {moneyness:.2%}")

                    all_contracts.append({
                        "ctp_code": ctp_code,
                        "variety": vcode,
                        "name": name,
                        "direction": direction,
                        "strike": strike,
                        "month": f"{myy:02d}{mm_:02d}",
                        "moneyness": round(moneyness, 4),
                        "futures_est": round(fpx_this, 0),
                    })

    if not all_contracts:
        print("\n❌ 未发现任何深虚合约")
        return None

    # 写配置
    # 动态标的期货映射（从本次发现的合约月份反推）
    underlying_futures_dynamic = {}
    for vcode in ["au", "m", "ta"]:
        contracts_for_vcode = [c for c in all_contracts if c["variety"] == vcode]
        if contracts_for_vcode:
            # 取近月（month 最短的）作为标的期货月份
            near_month = min(int(c["month"]) for c in contracts_for_vcode)
            near_yy = near_month // 100
            near_mm = near_month % 100
            underlying_futures_dynamic[vcode] = build_ctp_futures_code(vcode, near_yy, near_mm)

    config = {
        "discovered": date.today().isoformat(),
        "varieties": ["au", "m", "ta"],
        "futures_prices": {},
        "underlying_futures": underlying_futures_dynamic,
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
# 天勤行情源（8/17 换源，替代 CTP MdApi）
# ═══════════════════════════════════════════════════════════════

class TqQuotes:
    """天勤行情源（8/17 换源，替代 CTP MdSpi）。

    保持对外接口：snapshots / underlying_prices / snap_lock / _opt_to_ul，
    save_snapshot 与 8 时点逻辑无需改动。
    数据获取：TqApi.get_quote 批量订阅 → refresh() 内 wait_update 轮询刷新。
    """

    def __init__(self, underlying_map: dict = None):
        self.subscribed_count = 0
        self.sub_errors = []

        # 最新行情缓存: {ctp_code: {bid, ask, ...}}（与 MdSpi 同构）
        self.snapshots = {}
        self.snap_lock = threading.Lock()

        # 标的期货价格: {futures_ctp_code: last_price}
        self.underlying_prices = {}
        # 期权合约→标的期货映射: {option_ctp_code: futures_ctp_code}
        self._opt_to_ul = underlying_map or {}

        self.api = None          # TqApi 实例
        self._quotes = {}        # {tq_symbol: Quote 对象}
        self._code_to_tq = {}    # {option_ctp_code: tq_symbol}
        self._ul_to_tq = {}      # {futures_ctp_code: tq_symbol}

    @staticmethod
    def _i(x) -> int:
        """安全转 int（天勤无数据时可能返回 nan/None）。"""
        try:
            return int(float(x)) if x is not None and float(x) == float(x) else 0
        except (ValueError, TypeError):
            return 0

    def connect(self, contracts: list, underlying_futures: dict = None) -> bool:
        """连接天勤并批量订阅期权 + 标的期货。返回是否至少部分订阅成功。"""
        if underlying_futures is None:
            underlying_futures = UNDERLYING_FUTURES
        if not TQ_USER or not TQ_PASS:
            print("❌ .env 缺 TQ_USER/TQ_PASS，天勤凭据未配置")
            return False

        try:
            from tqsdk import TqApi, TqAuth
            print(f"🔗 连接天勤行情源…")
            self.api = TqApi(auth=TqAuth(TQ_USER, TQ_PASS))
        except Exception as e:
            print(f"❌ 天勤连接失败: {e}")
            return False

        # 标的期货（天勤代码 = 交易所前缀 + CTP 代码）
        for vcode, fut_code in underlying_futures.items():
            tq = f"{EXCHANGE_MAP.get(vcode, '')}.{fut_code}"
            self._ul_to_tq[fut_code] = tq
            try:
                self._quotes[tq] = self.api.get_quote(tq)
                self.underlying_prices[fut_code] = 0.0
                self.subscribed_count += 1
            except Exception as e:
                self.sub_errors.append(f"期货 {tq}: {str(e)[:60]}")

        # 期权（DCE 需连字符格式）
        codes = [c["ctp_code"] for c in contracts]
        for c in contracts:
            code = c["ctp_code"]
            tq = ctp_to_tq_code(code, c["variety"])
            self._code_to_tq[code] = tq
            try:
                self._quotes[tq] = self.api.get_quote(tq)
                self.subscribed_count += 1
            except Exception as e:
                self.sub_errors.append(f"{code}: {str(e)[:60]}")

        total = len(underlying_futures) + len(codes)
        print(f"\n   订阅结果: {self.subscribed_count}/{total} 成功")
        if self.sub_errors:
            for err in self.sub_errors[:5]:
                print(f"   {err}")
        return self.subscribed_count > 0

    def refresh(self):
        """主循环轮询：wait_update 后用最新行情刷新 snapshots（与 MdSpi 同构）。"""
        if self.api is None:
            return
        self.api.wait_update(deadline=time.time() + 1)
        with self.snap_lock:
            for code, tq in self._code_to_tq.items():
                q = self._quotes.get(tq)
                if q is None:
                    continue
                bid = float(q.bid_price1) if q.bid_price1 and q.bid_price1 > 0 else 0.0
                ask = float(q.ask_price1) if q.ask_price1 and q.ask_price1 > 0 else 0.0
                last = float(q.last_price) if q.last_price and q.last_price > 0 else 0.0
                tick_time = ""
                if q.datetime:
                    s = str(q.datetime)
                    tick_time = s.split(" ")[1] if " " in s else s
                self.snapshots[code] = {
                    "bid": bid,
                    "ask": ask,
                    "bid_vol": self._i(q.bid_volume1),
                    "ask_vol": self._i(q.ask_volume1),
                    "last": last,
                    "volume": self._i(q.volume),
                    "oi": self._i(q.open_interest),
                    "tick_time": tick_time,
                    "trading_day": str(q.datetime)[:10].replace("-", "") if q.datetime else "",
                }
            for fut_code, tq in self._ul_to_tq.items():
                q = self._quotes.get(tq)
                if q and q.last_price and q.last_price > 0:
                    self.underlying_prices[fut_code] = float(q.last_price)

    def close(self):
        if self.api is not None:
            try:
                self.api.close()
            except Exception:
                pass
            self.api = None


# ═══════════════════════════════════════════════════════════════
# 时间检测与快照保存
# ═══════════════════════════════════════════════════════════════

def _time_matches(now: datetime, target: str) -> bool:
    """检测当前时间是否匹配目标时点（HH:MM）。在 ±30s 窗口内触发。"""
    th, tm = map(int, target.split(":"))
    target_minutes = th * 60 + tm
    current_minutes = now.hour * 60 + now.minute
    return abs(current_minutes - target_minutes) <= 1


def _time_passed(now: datetime, target: str) -> bool:
    """检测当前时间是否已超过目标时点。"""
    th, tm = map(int, target.split(":"))
    target_minutes = th * 60 + tm
    current_minutes = now.hour * 60 + now.minute
    return current_minutes > target_minutes


def save_snapshot(spi, contracts: list, time_slot: str, time_label: str,
                  output_path: Path = None, is_eod_proxy: int = 0):
    """保存当前所有订阅合约的最新行情到 CSV。

    自动计算：
    - underlying_price：从标的期货 tick 获取
    - moneyness：strike / underlying（C）或 underlying / strike（P）
    - is_stale：tick_time 距当前时间 > 120s 标记为 1
    - is_eod_proxy：是否为日终代理采集（非真 15:00）
    """
    if output_path is None:
        output_path = OUTPUT_TRADING
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
                "is_eod_proxy": is_eod_proxy,
            })

    if not rows:
        print(f"  ⏰ {time_slot} ({time_label}): 无行情数据（可能合约尚未推送）")
        return

    # 追加写入 CSV
    file_exists = output_path.exists()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    # 统计
    has_bid = sum(1 for r in rows if r["bid"] > 0)
    stale = sum(1 for r in rows if r["is_stale"])
    print(f"  ⏰ {time_slot} ({time_label}): {len(rows)} 条 "
          f"(有报价:{has_bid} stale:{stale})")


def _save_eod(spi, contracts):
    """日终归档——退出前必跑，兜底保护。即使无行情也建空文件防丢失。"""
    try:
        now = datetime.now()
        if now.hour == 15 and now.minute == 0 and now.second <= 10:
            is_proxy = 0
        else:
            is_proxy = 1
        time_slot = now.strftime("%H:%M")
        save_snapshot(spi, contracts, time_slot, "日终", OUTPUT_EOD, is_proxy)
        print(f"📊 自动日终归档 → {OUTPUT_EOD} (proxy={is_proxy})")
    except Exception as e:
        # 兜底：即使异常也至少建空文件，保证收尾检查能通过
        print(f"⚠️ EOD 保存异常: {e}，创建空记录")
        try:
            OUTPUT_EOD.parent.mkdir(parents=True, exist_ok=True)
            if not OUTPUT_EOD.exists():
                with open(OUTPUT_EOD, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                    writer.writeheader()
        except Exception:
            pass  # 连这都失败就放弃了


def run_collection(contracts: list, underlying_futures: dict = None,
                   output_path: Path = None):
    """主循环：连接 → 订阅 → 等待时点 → 保存快照 → 收盘退出。"""
    if not contracts:
        print("❌ 合约列表为空。请先运行 --discover")
        return

    if underlying_futures is None:
        underlying_futures = UNDERLYING_FUTURES
    if output_path is None:
        output_path = OUTPUT_TRADING

    # 构建期权→标的映射（用于 save_snapshot 查标的价格）
    opt_to_ul = {}
    for c in contracts:
        vcode = c["variety"]
        ul = underlying_futures.get(vcode, "")
        if ul:
            opt_to_ul[c["ctp_code"]] = ul

    print(f"\n📊 深虚期权 8 时点采集")
    print(f"   品种: AU / M / TA")
    print(f"   期权: {len(contracts)} 个  |  标的期货: {len(set(underlying_futures.values()))} 个")
    print(f"   时点: {', '.join(t for t, _ in SNAPSHOT_TIMES)}")
    print(f"   输出: {output_path}\n")

    # ── 连接天勤 ──
    spi = TqQuotes(underlying_map=opt_to_ul)
    # 预填充 underlying_prices 的 key
    for ul_code in underlying_futures.values():
        spi.underlying_prices[ul_code] = 0.0

    ok = spi.connect(contracts, underlying_futures)
    if not ok:
        return

    # ── 等待行情到达（天勤需 refresh 才填充 snapshots）──
    print("\n⏳ 等待行情推送…")
    wait_start = time.time()
    while time.time() - wait_start < 30:
        spi.refresh()
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
        save_snapshot(spi, contracts, now_str, "手动收盘", output_path)
        _save_eod(spi, contracts)
        spi.close()
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

        # 刷新行情（天勤轮询）
        try:
            spi.refresh()
        except Exception as e:
            print(f"⚠️ [{time.strftime('%H:%M:%S')}] 行情刷新失败: {e}，3 秒后重试")
            time.sleep(3)
            continue

        # 检查是否有未保存的时点
        for time_slot, time_label in pending:
            if time_slot in saved_slots:
                continue
            if _time_matches(now, time_slot):
                save_snapshot(spi, contracts, time_slot, time_label, output_path)
                saved_slots.add(time_slot)
                break

        # 全部时点已保存 → 退出
        if len(saved_slots) >= len(pending):
            print(f"\n✅ 所有时点已采集，退出")
            break

        time.sleep(5)  # 每 5 秒检查一次

    # ── 采集完成 ──

    # ── 自动日终归档（退出前必跑，兜底保护）──
    _save_eod(spi, contracts)

    print(f"\n📊 本次采集完成: {len(saved_slots)} 个时点 → {output_path}")

    # 统计今日采集
    today_str = date.today().isoformat()
    total_rows = 0
    if output_path.exists():
        with open(output_path, "r") as f:
            for row in csv.DictReader(f):
                if row["date"] == today_str:
                    total_rows += 1
    print(f"   今日累计: {total_rows} 行")

    spi.close()


# ═══════════════════════════════════════════════════════════════
# 检查模式：快速验证天勤连接 + 合约可订阅
# ═══════════════════════════════════════════════════════════════

def check_connection():
    """快速检查天勤连接 + 订阅是否可用（8/17 换源）。"""
    if not CONFIG_FILE.exists():
        print(f"❌ 配置文件不存在: {CONFIG_FILE}")
        print(f"   请先运行: python3 tools/deep_otm_collector.py --discover")
        return

    config = json.loads(CONFIG_FILE.read_text())
    contracts = config["contracts"]
    underlying = config.get("underlying_futures", UNDERLYING_FUTURES)
    first_5 = contracts[:5]

    print(f"🔍 检查模式：验证天勤连接…")
    print(f"   测试: {len(first_5)} 个期权 + {len(underlying)} 个标的期货")

    spi = TqQuotes()
    ok = spi.connect(first_5, underlying)
    if not ok:
        print(f"❌ 天勤订阅失败")
        if spi.sub_errors:
            for e in spi.sub_errors[:5]:
                print(f"   错误: {e}")
        return

    # 等待行情
    time.sleep(5)
    spi.refresh()
    with spi.snap_lock:
        count = len(spi.snapshots)
    print(f"   行情: {count} 个合约有推送")

    if count > 0:
        print(f"\n✅ 天勤连接正常，可以运行采集")
    else:
        print(f"\n⚠️ 连接正常但无行情推送（非交易时段？）")

    spi.close()


# ═══════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════

def needs_rediscover(config: dict) -> bool:
    """判断是否需要重新发现合约。"""
    if not config or not config.get("contracts"):
        return True

    discovered = config.get("discovered", "")
    if discovered:
        try:
            d = datetime.strptime(discovered, "%Y-%m-%d").date()
            if (date.today() - d).days > 7:
                return True
        except ValueError:
            return True
    else:
        return True

    if len(config.get("contracts", [])) < 6:
        return True

    return False


def load_or_discover_config(force: bool = False) -> dict:
    """加载配置，过期则自动重新发现。返回 config dict，失败返回 None。"""
    config = None
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            config = None

    if force or needs_rediscover(config):
        print("⚠️ 合约配置过期或不存在，自动执行发现…")
        config = discover_contracts()
        if not config:
            print("❌ 自动发现失败，请检查网络或手动运行 --discover")
            return None

    return config


def main():
    parser = argparse.ArgumentParser(
        description="深虚期权 8 时点采集（天勤行情源）")
    parser.add_argument("--discover", action="store_true",
                        help="发现深虚合约并写入配置文件")
    parser.add_argument("--check", action="store_true",
                        help="快速验证天勤连接+合约可订阅")
    parser.add_argument("--eod", action="store_true",
                        help="日终归档（兜底）：盘中模式已自动追加日终，此参数仅在进程崩溃后补采")
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
    elif args.eod:
        # ── 日终归档模式（兜底）──
        config = load_or_discover_config()
        if not config:
            sys.exit(1)
        contracts = config["contracts"]
        underlying = config.get("underlying_futures", UNDERLYING_FUTURES)

        # 构建映射
        opt_to_ul = {}
        for c in contracts:
            vcode = c["variety"]
            ul = underlying.get(vcode, "")
            if ul:
                opt_to_ul[c["ctp_code"]] = ul

        print(f"\n📊 深虚期权 日终归档（EOD）")
        print(f"   品种: AU / M / TA")
        print(f"   期权: {len(contracts)} 个  |  标的期货: {len(set(underlying.values()))} 个")
        print(f"   输出: {OUTPUT_EOD}\n")

        spi = TqQuotes(underlying_map=opt_to_ul)
        for ul_code in underlying.values():
            spi.underlying_prices[ul_code] = 0.0

        ok = spi.connect(contracts, underlying)
        if not ok:
            sys.exit(1)

        # 等待行情（天勤需 refresh）
        print("\n⏳ 等待行情推送…")
        wait_start = time.time()
        while time.time() - wait_start < 30:
            spi.refresh()
            with spi.snap_lock:
                count = len(spi.snapshots)
            if count > 0:
                print(f"   ✅ 已收到 {count} 个合约的行情")
                break
            time.sleep(1)
        else:
            print("   ⚠️ 30s 内未收到任何行情推送")

        # 日终单次采集
        now = datetime.now()
        # 仅允许 14:55 之后运行
        if now.hour < 14 or (now.hour == 14 and now.minute < 55):
            print("❌ 日终模式只能在 14:55 后运行")
            spi.close()
            sys.exit(1)

        if now.hour == 15 and now.minute == 0 and now.second <= 10:
            # 15:00:00–15:00:10：SimNow 大概率还连着，真日终
            time_slot = "15:00"
            is_proxy = 0
        else:
            # 14:55–14:59 或 15:00:10+：代理
            time_slot = "14:59:50"
            is_proxy = 1

        save_snapshot(spi, contracts, time_slot, "日终", OUTPUT_EOD, is_proxy)
        spi.close()
        print(f"\n📊 日终归档完成 → {OUTPUT_EOD}")
    else:
        # ── 正常采集模式（自动发现 + 8 时点 + 日终归档）──
        config = load_or_discover_config()
        if not config:
            sys.exit(1)
        contracts = config["contracts"]
        underlying = config.get("underlying_futures", UNDERLYING_FUTURES)
        run_collection(contracts, underlying, OUTPUT_TRADING)


if __name__ == "__main__":
    main()
