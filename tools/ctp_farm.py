#!/usr/bin/env python3
"""CTP 仿真刷单工具 — 侦察 + 自动刷期权交易记录

用法：
  python3 tools/ctp_farm.py --probe              # 侦察：列出可交易期权合约
  python3 tools/ctp_farm.py --farm               # 刷单：2轮买卖=4笔交易
  python3 tools/ctp_farm.py --farm --symbol MA609C2550  # 指定合约

设计：
  每轮 = 查行情→买1手@ask→等成交→查行情→卖1手@bid→等成交
  每天 2 轮 = 4 笔交易。不设总笔数上限——多跑几天自然超额。

凭证：读 .env，与 ctp_connect.py 共享。
"""

import os
import sys
import time
import signal
import json
import threading
from collections import defaultdict
from pathlib import Path

try:
    from openctp_ctp import tdapi
except ImportError:
    print("❌ 需要安装 openctp-ctp: pip3 install openctp-ctp")
    sys.exit(1)

# ── 加载 .env ────────────────────────────────────────────────────────
ENV_FILE = Path(__file__).parent.parent / ".env"
CTP_LOG_FILE = Path(__file__).parent.parent / "data" / "ctp_farm_log.json"
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
TRADING_ADDR = os.environ.get("CTP_TRADING_ADDR", "tcp://140.206.167.53:53205")
SYSTEM_INFO = f"macOS;goldopt/1.0.0;{APP_ID}"

# ── 默认刷单合约（按日期轮换，优先流动性好的）───────────────
DEFAULT_SYMBOLS = [
    "RM701P2300",   # 菜籽粕 2701 Put 2300（8/13 实测跑通，spread 1.7%）
    "RM701C2300",   # 菜籽粕 2701 Call 2300（spread 1.9%）
    "MA701P2600",   # 甲醇 2701 Put 2600（spread 2.5%）
    "MA701P2500",   # 甲醇 2701 Put 2500（spread 3.2%）
    "CF701P15000",  # 棉花 2701 Put 15000（spread 1.9%）
]

EXCHANGE_NAMES = {
    "SHFE": "上期所", "DCE": "大商所", "CZCE": "郑商所",
    "CFFEX": "中金所", "INE": "上期能源",
}
OUR_UNDERLYING_CODES = {
    "au": "沪金", "m": "豆粕", "c": "玉米", "CF": "棉花",
    "SR": "白糖", "TA": "PTA", "MA": "甲醇", "i": "铁矿石",
    "ru": "橡胶", "RM": "菜籽粕",
}
OPTION_CLASSES = {"2", "6", "7", "8"}


def strip_month(contract_id: str) -> str:
    import re
    m = re.match(r'^([A-Za-z]+)', contract_id)
    return m.group(1) if m else contract_id


# ── SPI 回调（侦察 + 刷单 共用）────────────────────────────────────
class FarmSpi(tdapi.CThostFtdcTraderSpi):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.request_id = 0
        self.logged_in = False
        self.confirmed = False
        self.last_error = ""
        self._cond = threading.Condition()

        # 侦察数据
        self.instruments = []
        self.query_done = False

        # 刷单数据
        self.depth_bid = 0.0       # 最新买一价
        self.depth_ask = 0.0       # 最新卖一价
        self.depth_last = 0.0      # 最新成交价
        self.depth_avg = 0.0       # 均价
        self.depth_ready = False
        self.trade_price = 0.0
        self.trade_volume = 0
        self.trade_filled = False
        self.order_error = ""

        # 查询数据（--query）
        self.trades = []            # 当日成交
        self.trade_query_done = False
        self.settlement_chunks = [] # 结算单内容片段
        self.settlement_done = False

    def _next_id(self):
        self.request_id += 1
        return self.request_id

    def _wait_for(self, attr: str, timeout: float = 30.0):
        deadline = time.time() + timeout
        with self._cond:
            while not getattr(self, attr):
                remaining = deadline - time.time()
                if remaining <= 0:
                    print(f"\n⏰ 超时：等待 {attr} 超过 {timeout}s")
                    return False
                self._cond.wait(timeout=remaining)
        return True

    def _reset_depth(self):
        """重置行情标志。"""
        self.depth_bid = 0.0
        self.depth_ask = 0.0
        self.depth_last = 0.0
        self.depth_avg = 0.0
        self.depth_ready = False

    def _reset_trade_state(self):
        """重置下单/成交标志。"""
        self.trade_price = 0.0
        self.trade_volume = 0
        self.trade_filled = False
        self.order_error = ""

    # ═══════════════════════════════════════════════════════════════
    #  连接 / 认证 / 登录
    # ═══════════════════════════════════════════════════════════════

    def OnFrontConnected(self):
        print("✅ 前置连接成功 → 正在认证…")
        req = tdapi.CThostFtdcReqAuthenticateField()
        req.BrokerID = BROKER_ID
        req.UserID = USER_ID
        req.AuthCode = AUTH_CODE
        req.AppID = APP_ID
        self.api.ReqAuthenticate(req, self._next_id())

    def OnFrontDisconnected(self, nReason):
        reasons = {0x1001: "网络读失败", 0x1002: "网络写失败", 0x2001: "心跳超时", 0x2002: "发送心跳失败", 0x2003: "收到错误报文"}
        print(f"⚠️  前置断开 (原因: {reasons.get(nReason, nReason)})")

    def OnRspAuthenticate(self, pRsp, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"❌ 认证失败: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
            with self._cond:
                self.last_error = f"认证失败: {pRspInfo.ErrorMsg}"
                self._cond.notify_all()
            return
        print("✅ 认证成功 → 正在登录…")
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = BROKER_ID
        req.UserID = USER_ID
        req.Password = PASSWORD
        req.UserProductInfo = "goldopt"
        self.api.ReqUserLogin(req, self._next_id(), len(SYSTEM_INFO), SYSTEM_INFO)

    def OnRspUserLogin(self, pRsp, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"❌ 登录失败: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
            with self._cond:
                self.last_error = f"登录失败: {pRspInfo.ErrorMsg}"
                self._cond.notify_all()
            return
        print(f"✅ 登录成功！交易日: {pRsp.TradingDay}")
        with self._cond:
            self.logged_in = True
            self._cond.notify_all()
        settle = tdapi.CThostFtdcSettlementInfoConfirmField()
        settle.BrokerID = BROKER_ID
        settle.InvestorID = USER_ID
        self.api.ReqSettlementInfoConfirm(settle, self._next_id())

    def OnRspSettlementInfoConfirm(self, pSettlementInfoConfirm, pRspInfo, nRequestID, bIsLast):
        status = "✅" if (not pRspInfo or pRspInfo.ErrorID == 0) else f"⚠️ [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}"
        print(f"{status} 结算单确认")
        with self._cond:
            self.confirmed = True
            self._cond.notify_all()

    # ═══════════════════════════════════════════════════════════════
    #  成交 / 结算单查询（--query 用）
    # ═══════════════════════════════════════════════════════════════

    def OnRspQryTrade(self, pTrade, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"⚠️  成交查询: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
            return
        if pTrade:
            self.trades.append({
                "合约": pTrade.InstrumentID,
                "方向": "买入" if pTrade.Direction == "0" else "卖出",
                "开平": {"0": "开仓", "1": "平仓", "3": "平今"}.get(pTrade.OffsetFlag, pTrade.OffsetFlag),
                "价格": pTrade.Price,
                "数量": pTrade.Volume,
                "时间": pTrade.TradeTime,
                "交易日": pTrade.TradeDate,
            })
        if bIsLast:
            with self._cond:
                self.trade_query_done = True
                self._cond.notify_all()

    def OnRspQrySettlementInfo(self, pSettlementInfo, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"⚠️  结算单查询: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
            return
        if pSettlementInfo and pSettlementInfo.Content:
            content = pSettlementInfo.Content
            if isinstance(content, bytes):
                content = content.decode("gbk", errors="ignore")
            self.settlement_chunks.append(content)
        if bIsLast:
            with self._cond:
                self.settlement_done = True
                self._cond.notify_all()

    # ═══════════════════════════════════════════════════════════════
    #  合约查询（侦察用）
    # ═══════════════════════════════════════════════════════════════

    def OnRspQryInstrument(self, pInstrument, pRspInfo, nRequestID, bIsLast):
        if pInstrument and pInstrument.InstrumentID:
            self.instruments.append({
                "合约代码": pInstrument.InstrumentID,
                "名称": pInstrument.InstrumentName,
                "交易所": pInstrument.ExchangeID,
                "品种": pInstrument.ProductID,
                "类别": pInstrument.ProductClass,
                "行权价": pInstrument.StrikePrice,
                "到期日": pInstrument.ExpireDate,
                "标的": pInstrument.UnderlyingInstrID,
                "乘数": pInstrument.VolumeMultiple,
                "最小变动": pInstrument.PriceTick,
                "是否交易": pInstrument.IsTrading,
                "期权类型": pInstrument.OptionsType,
            })
        if bIsLast:
            with self._cond:
                self.query_done = True
                self._cond.notify_all()

    # ═══════════════════════════════════════════════════════════════
    #  行情查询（刷单用）
    # ═══════════════════════════════════════════════════════════════

    def OnRspQryDepthMarketData(self, pDepth, pRspInfo, nRequestID, bIsLast):
        if pDepth and pDepth.InstrumentID:
            raw_bid = pDepth.BidPrice1
            raw_ask = pDepth.AskPrice1
            # CTP 无数据返回 DBL_MAX
            self.depth_bid = raw_bid if (raw_bid > 0 and raw_bid < 1e10) else 0.0
            self.depth_ask = raw_ask if (raw_ask > 0 and raw_ask < 1e10) else 0.0
            self.depth_last = pDepth.LastPrice if (pDepth.LastPrice > 0 and pDepth.LastPrice < 1e10) else 0.0
            self.depth_avg = pDepth.AveragePrice if (pDepth.AveragePrice > 0 and pDepth.AveragePrice < 1e10) else 0.0
            self.depth_ready = True
            with self._cond:
                self._cond.notify_all()
        elif pRspInfo and pRspInfo.ErrorID != 0:
            print(f"⚠️  行情查询失败: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
            self.depth_ready = True
            with self._cond:
                self._cond.notify_all()

    # ═══════════════════════════════════════════════════════════════
    #  下单回调（刷单用）
    # ═══════════════════════════════════════════════════════════════

    def OnRspOrderInsert(self, pInputOrder, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            self.order_error = f"[{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}"
            print(f"❌ 下单被拒: {self.order_error}")
            with self._cond:
                self._cond.notify_all()

    def OnRtnOrder(self, pOrder):
        status_map = {"0": "全部成交", "1": "部分成交", "2": "未成交",
                      "3": "未成交队列中", "4": "未成交不在队列", "5": "已撤单"}
        status = status_map.get(pOrder.OrderStatus, pOrder.OrderStatus)
        direction = "买" if pOrder.Direction == "0" else "卖"
        offset = {"0": "开", "1": "平", "3": "平今"}.get(pOrder.CombOffsetFlag, pOrder.CombOffsetFlag)
        print(f"  📋 报单: {pOrder.InstrumentID} {direction}{offset} "
              f"{pOrder.VolumeTotalOriginal}手 @ {pOrder.LimitPrice} | {status}")

    def OnRtnTrade(self, pTrade):
        self.trade_price = pTrade.Price
        self.trade_volume = pTrade.Volume
        self.trade_filled = True
        direction = "买" if pTrade.Direction == "0" else "卖"
        offset = {"0": "开", "1": "平", "3": "平今"}.get(pTrade.OffsetFlag, pTrade.OffsetFlag)
        print(f"  💰 成交: {pTrade.InstrumentID} {direction}{offset} "
              f"{pTrade.Volume}手 @ {pTrade.Price} | 编号:{pTrade.TradeID}")
        with self._cond:
            self._cond.notify_all()

    # ═══════════════════════════════════════════════════════════════
    #  错误
    # ═══════════════════════════════════════════════════════════════

    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"⚠️  CTP 错误: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg} (req={nRequestID})")


# ── 连接 + 登录 ─────────────────────────────────────────────────────
def connect_and_login() -> tuple:
    api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi()
    spi = FarmSpi(api)
    api.RegisterSpi(spi)
    api.SubscribePrivateTopic(tdapi.THOST_TERT_QUICK)
    api.SubscribePublicTopic(tdapi.THOST_TERT_QUICK)
    api.RegisterFront(TRADING_ADDR)
    api.Init()

    print(f"🔗 连接 {TRADING_ADDR}")
    print(f"   BrokerID: {BROKER_ID}  |  UserID: {USER_ID}")

    if not spi._wait_for("logged_in", timeout=15):
        print(f"\n❌ 登录失败: {spi.last_error}")
        api.Release()
        return None, None, False

    spi._wait_for("confirmed", timeout=5)
    return api, spi, True


# ── 查询行情 ────────────────────────────────────────────────────────
def query_depth(api, spi, symbol: str, timeout: float = 5.0) -> tuple:
    """查询合约深度行情，返回 (bid, ask, last, avg)。"""
    spi._reset_depth()
    qry = tdapi.CThostFtdcQryDepthMarketDataField()
    qry.InstrumentID = symbol
    api.ReqQryDepthMarketData(qry, spi._next_id())

    if not spi._wait_for("depth_ready", timeout=timeout):
        return 0.0, 0.0, 0.0, 0.0

    bid, ask, last, avg = spi.depth_bid, spi.depth_ask, spi.depth_last, spi.depth_avg
    if ask <= 0 or ask > 1e10:
        return 0.0, 0.0, 0.0, 0.0

    return bid, ask, last, avg


# ── 飞行前检查：挑流动性最好的合约 ─────────────────────────────────
def pick_best_symbol(api, spi) -> str:
    """扫描所有候选合约，返回 bid>0 且价差最窄的那个。"""
    best_symbol = None
    best_spread_pct = float("inf")
    best_bid = best_ask = 0.0

    print(f"\n🔍 飞行前检查：扫描 {len(DEFAULT_SYMBOLS)} 个候选合约…")
    for sym in DEFAULT_SYMBOLS:
        bid, ask, last, avg = query_depth(api, spi, sym, timeout=3.0)
        if bid <= 0 or ask <= 0:
            print(f"   ❌ {sym:16s}  bid={bid} ask={ask} → 跳过（无对手盘）")
            continue
        spread_pct = (ask - bid) / ask * 100
        marker = "⭐" if spread_pct < best_spread_pct else "  "
        print(f"   {marker} {sym:16s}  bid={bid:<8} ask={ask:<8} 价差 {spread_pct:.1f}%")
        if spread_pct < best_spread_pct:
            best_spread_pct = spread_pct
            best_symbol = sym
            best_bid, best_ask = bid, ask

    if best_symbol is None:
        print(f"\n❌ 所有候选合约均无对手盘（bid=0 或 ask=0），无法刷单")
        print(f"   建议：换到交易时段重试，或 --probe 找活跃合约手动指定")
        return ""

    print(f"\n✅ 选中 {best_symbol}（bid={best_bid} ask={best_ask} 价差 {best_spread_pct:.1f}%）")
    return best_symbol


# ── 下单并等待成交 ──────────────────────────────────────────────────
def place_and_wait(api, spi, symbol: str, direction: str, offset: str,
                   price: float, volume: int = 1, timeout: float = 10.0) -> bool:
    """下一笔限价单并等待成交。返回是否成交。"""
    spi._reset_trade_state()

    req = tdapi.CThostFtdcInputOrderField()
    req.BrokerID = BROKER_ID
    req.InvestorID = USER_ID
    req.InstrumentID = symbol
    req.OrderRef = str(spi._next_id()).zfill(10)
    req.Direction = direction          # "0"=买 "1"=卖
    req.CombOffsetFlag = offset        # "0"=开 "1"=平 "3"=平今
    req.CombHedgeFlag = "1"            # 投机
    req.LimitPrice = price
    req.VolumeTotalOriginal = volume
    req.OrderPriceType = "2"           # 限价
    req.TimeCondition = "3"            # 当日有效
    req.VolumeCondition = "1"          # 任何数量
    req.MinVolume = 1
    req.ContingentCondition = "1"      # 立即
    req.ForceCloseReason = "0"         # 非强平
    req.IsAutoSuspend = 0
    req.UserForceClose = 0

    direction_cn = "买" if direction == "0" else "卖"
    offset_cn = {"0": "开", "1": "平", "3": "平今"}.get(offset, offset)
    print(f"  📝 {direction_cn}{offset_cn}: {symbol} {volume}手 @ {price}")

    api.ReqOrderInsert(req, spi._next_id())

    # 等成交或报错
    if not spi._wait_for("trade_filled", timeout=timeout):
        if spi.order_error:
            print(f"  ❌ 下单失败: {spi.order_error}")
        else:
            print(f"  ⏰ 等待成交超时 ({timeout}s)")
        return False

    return True


# ── 一轮买卖 ─────────────────────────────────────────────────────────
def do_round(api, spi, symbol: str) -> bool:
    """一轮：买 @ask → 卖 @bid。SimNow 仿真盘差价是刷单成本。"""
    print(f"\n{'─'*50}")
    print(f"  🔄 标的: {symbol}")

    # 1. 查行情 → 买
    bid, ask, last, avg = query_depth(api, spi, symbol)
    if ask <= 0:
        print(f"  ⚠️  无卖一价，跳过")
        return False
    print(f"  行情: bid={bid} ask={ask} last={last}")

    if not place_and_wait(api, spi, symbol, "0", "0", ask):
        return False

    # 2. 查行情 → 卖。逐级追价：bid → ask → last → trade_price
    time.sleep(1.0)
    bid, ask, last, avg = query_depth(api, spi, symbol)
    # 优先对面价（bid），bid 死了追 ask（跨价差），再死追 last/成交价
    sell_price = bid if bid > 0 else (ask if ask > 0 else (last if last > 0 else spi.trade_price))
    strategy = "bid" if bid > 0 else ("ask" if ask > 0 else ("last" if last > 0 else "成交价"))
    if sell_price <= 0:
        print(f"  ⚠️  无可用卖出价（bid={bid} ask={ask} last={last}）")
        return False
    print(f"  行情: bid={bid} ask={ask} last={last}  → 卖出价={sell_price} ({'✅对面价' if bid > 0 else '⚡追价'+strategy})")

    if not place_and_wait(api, spi, symbol, "1", "1", sell_price):
        return False

    return True


# ── 刷单模式 ────────────────────────────────────────────────────────
def farm(api, spi):
    """每天 2 轮买卖 = 4 笔交易。飞行前检查自动挑流动性最好的合约。"""
    # 允许 --symbol 覆盖
    symbol = ""
    for i, arg in enumerate(sys.argv):
        if arg == "--symbol" and i + 1 < len(sys.argv):
            symbol = sys.argv[i + 1]

    if not symbol:
        symbol = pick_best_symbol(api, spi)
        if not symbol:
            return

    print(f"\n🚜 刷单模式 · 合约: {symbol}")
    print(f"   每轮 1 买 1 卖 = 2 笔 × 2 轮 = 每天 4 笔")
    print(f"   不设总笔数上限——多跑几天自然超额\n")

    ok_count = 0
    for rnd in range(1, 3):
        print(f"\n{'='*50}")
        print(f"  🎯 第 {rnd}/2 轮")
        print(f"{'='*50}")
        if do_round(api, spi, symbol):
            ok_count += 1
            print(f"  ✅ 第 {rnd} 轮完成")
        else:
            print(f"  ❌ 第 {rnd} 轮失败，跳过")
        if rnd < 2:
            time.sleep(2.0)  # 轮间冷却

    trades_today = ok_count * 2

    print(f"\n{'='*50}")
    print(f"  完成: {ok_count}/2 轮成功 = {trades_today} 笔交易")
    print(f"{'='*50}")

    # 写日志：累加交易天数+笔数
    log = {"runs": [], "total_trades": 0, "total_days": 0}
    if CTP_LOG_FILE.exists():
        try:
            log = json.loads(CTP_LOG_FILE.read_text())
        except json.JSONDecodeError:
            pass

    today_str = time.strftime("%Y-%m-%d")
    today_trades = trades_today
    # 如果今天已经跑过（叠加轮次），合并
    already_today = sum(r["trades"] for r in log["runs"] if r["date"] == today_str)
    if already_today:
        today_trades += already_today
        log["runs"] = [r for r in log["runs"] if r["date"] != today_str]

    log["runs"].append({
        "date": today_str,
        "trades": today_trades,
        "symbol": symbol,
        "rounds_ok": ok_count,
    })
    log["total_trades"] = sum(r["trades"] for r in log["runs"])
    log["total_days"] = len(set(r["date"] for r in log["runs"]))

    CTP_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CTP_LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2))
    print(f"  📋 累计: {log['total_days']} 天 / {log['total_trades']} 笔 → data/ctp_farm_log.json")


# ── 侦察模式 ────────────────────────────────────────────────────────
def probe(api, spi):
    print("\n📡 查询全市场合约…（SimNow 可能返回数百条，请耐心等 30s）")

    qry = tdapi.CThostFtdcQryInstrumentField()
    api.ReqQryInstrument(qry, spi._next_id())

    if not spi._wait_for("query_done", timeout=60):
        print("❌ 合约查询超时")
        return

    total = len(spi.instruments)
    options = [i for i in spi.instruments if i["类别"] in OPTION_CLASSES]
    futures = [i for i in spi.instruments if i["类别"] == "1"]
    print(f"\n📦 共返回 {total} 个合约")
    print(f"   期权: {len(options)} 个  |  期货: {len(futures)} 个  |  其他: {total - len(options) - len(futures)} 个\n")

    by_prefix = defaultdict(lambda: defaultdict(list))
    for opt in options:
        ul = opt["标的"] or "??"
        prefix = strip_month(ul)
        by_prefix[prefix][ul].append(opt)

    ours = {k: v for k, v in by_prefix.items() if k in OUR_UNDERLYING_CODES}

    for prefix, months in sorted(ours.items()):
        label = OUR_UNDERLYING_CODES.get(prefix, "")
        for ul, opts in sorted(months.items()):
            trading = [o for o in opts if o["是否交易"] == 1]
            if not trading:
                continue
            calls = [o for o in trading if o["期权类型"] == "1"]
            puts = [o for o in trading if o["期权类型"] == "2"]
            exp = trading[0]["到期日"]
            exchange = EXCHANGE_NAMES.get(trading[0]["交易所"], trading[0]["交易所"])
            strikes = sorted(set(o["行权价"] for o in trading))
            print(f"  📌 {prefix} {label} → {ul} | {exchange} | 到期 {exp}")
            print(f"     C:{len(calls)} P:{len(puts)} 行权价 {strikes[0]}~{strikes[-1]} ({len(strikes)}档)")

    our_trading = sum(
        1 for prefix, months in by_prefix.items() if prefix in OUR_UNDERLYING_CODES
        for ul, opts in months.items() for o in opts if o["是否交易"] == 1
    )
    print(f"\n  汇总: 我们品种共 {our_trading} 个可交易期权合约")


# ── 查询成交 + 结算单（开权限凭证）──────────────────────────────────
def query_records(api, spi):
    import json

    # 1. 当日成交
    spi.trade_query_done = False
    qry = tdapi.CThostFtdcQryTradeField()
    qry.BrokerID = BROKER_ID
    qry.InvestorID = USER_ID
    api.ReqQryTrade(qry, spi._next_id())
    spi._wait_for("trade_query_done", timeout=10)

    print(f"\n📊 当日成交（{len(spi.trades)} 笔）")
    for t in spi.trades:
        print(f"   {t['交易日']} {t['时间']} {t['合约']} {t['方向']}{t['开平']} {t['数量']}手 @ {t['价格']}")

    # 2. 历史结算单（逐日，从本地日志读有成交的交易日）
    log_path = Path(__file__).parent.parent / "data" / "ctp_farm_log.json"
    days = []
    if log_path.exists():
        data = json.loads(log_path.read_text())
        for run in data.get("runs", []):
            if run.get("trades", 0) > 0:
                days.append(run["date"].replace("-", ""))

    print(f"\n📄 拉取 {len(days)} 天结算单（开权限凭证）")
    saved = []
    for d in days:
        spi.settlement_chunks = []
        spi.settlement_done = False
        q = tdapi.CThostFtdcQrySettlementInfoField()
        q.BrokerID = BROKER_ID
        q.InvestorID = USER_ID
        q.TradingDay = d
        api.ReqQrySettlementInfo(q, spi._next_id())
        spi._wait_for("settlement_done", timeout=10)
        content = "".join(spi.settlement_chunks)
        if not content:  # 错误90=查询未就绪，sleep后重试一次
            time.sleep(2)
            spi.settlement_done = False
            api.ReqQrySettlementInfo(q, spi._next_id())
            spi._wait_for("settlement_done", timeout=10)
            content = "".join(spi.settlement_chunks)
        if content:
            out = Path(__file__).parent.parent / "data" / f"settlement_{d}.txt"
            out.write_text(content)
            saved.append(out.name)
            print(f"   {d}: {len(content)} 字 → {out.name}")
        else:
            print(f"   {d}: ⚠️ 无结算单（柜台可能不保留或非交易日）")

    if saved:
        print(f"\n✅ 已存 {len(saved)} 份结算单到 data/。当日成交 + 结算单 = 开权限凭证。")


# ── main ─────────────────────────────────────────────────────────────
def main():
    if not USER_ID or not PASSWORD:
        print("❌ 缺少 CTP_USER_ID / CTP_PASSWORD。请在 .env 中设置。")
        sys.exit(1)

    api, spi, ok = connect_and_login()
    if not ok:
        sys.exit(1)

    if "--probe" in sys.argv:
        probe(api, spi)
    elif "--farm" in sys.argv:
        farm(api, spi)
    elif "--query" in sys.argv:
        query_records(api, spi)
    else:
        print("用法:")
        print("  python3 tools/ctp_farm.py --probe             侦察可交易期权")
        print("  python3 tools/ctp_farm.py --farm              每天2轮=4笔交易")
        print("  python3 tools/ctp_farm.py --query             拉成交+结算单（开权限）")
        print("  python3 tools/ctp_farm.py --farm --symbol X   指定合约刷单")

    print("\n👋 释放连接…")
    api.Release()
    print("完成。")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    main()
