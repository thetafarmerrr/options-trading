#!/usr/bin/env python3
"""CTP 仿真连接 + 下单工具（Mac → 中信期货仿真环境）

依赖：pip3 install openctp-ctp
用法：
  python3 tools/ctp_connect.py              # 交互式：连接→查账户→可选下单
  python3 tools/ctp_connect.py --dry-run    # 只连接+登录+查账户，不下单
  python3 tools/ctp_connect.py --order      # 连接后直接进下单提示

凭证：设环境变量 CTP_USER_ID / CTP_PASSWORD / CTP_BROKER_ID
      未设则交互式提示输入。
"""

import os
import sys
import time
import signal
import threading
from pathlib import Path

try:
    from openctp_ctp import tdapi
except ImportError:
    print("❌ 需要安装 openctp-ctp: pip3 install openctp-ctp")
    sys.exit(1)

# ── 加载 .env 文件（如果存在）────────────────────────────────────
ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# ── CTP 仿真地址（中信期货）───────────────────────────────────────
CTP_ADDRESSES = {
    "电信交易": "tcp://101.226.254.149:53205",
    "电信行情": "tcp://101.226.254.149:53213",
    "联通交易": "tcp://140.206.167.53:53205",
    "联通行情": "tcp://140.206.167.53:53213",
}

DEFAULT_BROKER = "66666"
TRADING_ADDR = CTP_ADDRESSES["联通交易"]

# ── 凭证 ──────────────────────────────────────────────────────────
USER_ID = os.environ.get("CTP_USER_ID", "")
PASSWORD = os.environ.get("CTP_PASSWORD", "")
BROKER_ID = os.environ.get("CTP_BROKER_ID", DEFAULT_BROKER)
AUTH_CODE = os.environ.get("CTP_AUTH_CODE", "")
APP_ID = os.environ.get("CTP_APP_ID", "client_goldopt_1.0.0")


def get_credentials():
    """确保有凭证，没有就交互式输入。"""
    global USER_ID, PASSWORD, BROKER_ID

    if USER_ID and PASSWORD:
        return

    print("\n📝 请输入 CTP 仿真账户信息（中信期货提供）：")
    print("   （之后可设环境变量 CTP_USER_ID / CTP_PASSWORD 跳过此步）\n")
    if not USER_ID:
        USER_ID = input("   UserID（资金账号）: ").strip()
    if not PASSWORD:
        PASSWORD = input("   Password: ").strip()
    if not BROKER_ID or BROKER_ID == DEFAULT_BROKER:
        b = input(f"   BrokerID [{DEFAULT_BROKER}]: ").strip()
        BROKER_ID = b or DEFAULT_BROKER


# ── CTP 回调 SPI ──────────────────────────────────────────────────
class TraderSpi(tdapi.CThostFtdcTraderSpi):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.request_id = 0
        self.connected = False
        self.logged_in = False
        self.confirmed = False
        self.account_ready = False
        self.last_error = ""
        self._cond = threading.Condition()

        # 账户信息
        self.account_info = {}
        self.positions = []

    def _next_id(self):
        self.request_id += 1
        return self.request_id

    # ── 等待辅助 ────────────────────────────────────────────────
    def _wait_for(self, attr: str, timeout: float = 10.0):
        """阻塞等待直到 self.<attr> == True 或超时。"""
        deadline = time.time() + timeout
        with self._cond:
            while not getattr(self, attr):
                remaining = deadline - time.time()
                if remaining <= 0:
                    print(f"\n⏰ 超时：等待 {attr} 超过 {timeout}s")
                    return False
                self._cond.wait(timeout=remaining)
        return True

    # ── 连接回调 ────────────────────────────────────────────────
    def OnFrontConnected(self):
        print("✅ 前置连接成功 → 正在认证…")
        # 先认证
        req = tdapi.CThostFtdcReqAuthenticateField()
        req.BrokerID = BROKER_ID
        req.UserID = USER_ID
        req.AuthCode = AUTH_CODE
        req.AppID = APP_ID
        self.api.ReqAuthenticate(req, self._next_id())

    def OnFrontDisconnected(self, nReason):
        reasons = {0x1001: "网络读失败", 0x1002: "网络写失败", 0x2001: "心跳超时", 0x2002: "发送心跳失败", 0x2003: "收到错误报文"}
        print(f"⚠️  前置断开 (原因: {reasons.get(nReason, nReason)})")
        with self._cond:
            self.connected = False
            self._cond.notify_all()

    # ── 认证回调 ────────────────────────────────────────────────
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
        # 看穿式监管：ReqUserLogin 6.7.7+ 需要传客户端系统信息
        sys_info = f"macOS;goldopt/1.0.0;{APP_ID}"
        self.api.ReqUserLogin(req, self._next_id(), len(sys_info), sys_info)

    # ── 登录回调 ────────────────────────────────────────────────
    def OnRspUserLogin(self, pRsp, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"❌ 登录失败: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
            with self._cond:
                self.last_error = f"登录失败: {pRspInfo.ErrorMsg}"
                self._cond.notify_all()
            return

        print(f"✅ 登录成功！")
        print(f"   交易日: {pRsp.TradingDay}  |  前置: {pRsp.FrontID}  |  会话: {pRsp.SessionID}")
        print(f"   最大报单引用: {pRsp.MaxOrderRef}  |  SHFE时间: {pRsp.SHFETime}")
        with self._cond:
            self.logged_in = True
            self._cond.notify_all()

        # 确认结算单
        print("→ 确认结算单…")
        settle = tdapi.CThostFtdcSettlementInfoConfirmField()
        settle.BrokerID = BROKER_ID
        settle.InvestorID = USER_ID
        self.api.ReqSettlementInfoConfirm(settle, self._next_id())

    def OnRspSettlementInfoConfirm(self, pSettlementInfoConfirm, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"⚠️  结算单确认失败: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
        else:
            print("✅ 结算单已确认")
        with self._cond:
            self.confirmed = True
            self._cond.notify_all()

    # ── 账户查询回调 ────────────────────────────────────────────
    def OnRspQryTradingAccount(self, pTradingAccount, pRspInfo, nRequestID, bIsLast):
        if pTradingAccount and pTradingAccount.BrokerID:
            self.account_info = {
                "可用资金": pTradingAccount.Available,
                "持仓保证金": pTradingAccount.CurrMargin,
                "冻结保证金": pTradingAccount.FrozenMargin,
                "手续费": pTradingAccount.Commission,
                "平仓盈亏": pTradingAccount.CloseProfit,
                "持仓盈亏": pTradingAccount.PositionProfit,
                "动态权益": pTradingAccount.Balance,
            }
        if bIsLast:
            with self._cond:
                self.account_ready = True
                self._cond.notify_all()

    def OnRspQryInvestorPosition(self, pInvestorPosition, pRspInfo, nRequestID, bIsLast):
        if pInvestorPosition and pInvestorPosition.InstrumentID:
            self.positions.append({
                "合约": pInvestorPosition.InstrumentID,
                "方向": "买" if pInvestorPosition.PosiDirection == "2" else "卖",
                "持仓": pInvestorPosition.Position,
                "今仓": pInvestorPosition.TodayPosition,
                "昨仓": pInvestorPosition.YdPosition,
                "开仓价": pInvestorPosition.OpenAmount / max(pInvestorPosition.Position, 1),
                "盈亏": pInvestorPosition.PositionProfit,
            })
        if bIsLast:
            with self._cond:
                self.account_ready = True
                self._cond.notify_all()

    # ── 下单回调 ────────────────────────────────────────────────
    def OnRspOrderInsert(self, pInputOrder, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"❌ 下单失败: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")
        else:
            print(f"✅ 报单已提交: {pInputOrder.InstrumentID} {pInputOrder.Direction} {pInputOrder.Volume}手")

    def OnRtnOrder(self, pOrder):
        status_map = {
            "0": "全部成交", "1": "部分成交", "2": "未成交",
            "3": "未成交队列中", "4": "未成交不在队列", "5": "已撤单",
        }
        status = status_map.get(pOrder.OrderStatus, pOrder.OrderStatus)
        print(f"📋 报单回报: {pOrder.InstrumentID} {pOrder.Direction}{pOrder.CombOffsetFlag} "
              f"{pOrder.Volume}手 | 状态: {status} | 编号: {pOrder.OrderSysID}")

    def OnRtnTrade(self, pTrade):
        print(f"💰 成交: {pTrade.InstrumentID} {pTrade.Direction}{pTrade.OffsetFlag} "
              f"{pTrade.Volume}手 @ {pTrade.Price} | 编号: {pTrade.TradeID}")

    # ── 错误回调 ────────────────────────────────────────────────
    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"⚠️  CTP 错误: [{pRspInfo.ErrorID}] {pRspInfo.ErrorMsg}")


# ── 主流程 ────────────────────────────────────────────────────────

def connect_and_login() -> tuple:
    """连接 CTP + 登录，返回 (api, spi, success)。"""
    api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi()
    spi = TraderSpi(api)
    api.RegisterSpi(spi)
    api.SubscribePrivateTopic(tdapi.THOST_TERT_QUICK)
    api.SubscribePublicTopic(tdapi.THOST_TERT_QUICK)
    api.RegisterFront(TRADING_ADDR)
    api.Init()

    print(f"🔗 连接 {TRADING_ADDR} …")
    print(f"   BrokerID: {BROKER_ID}  |  UserID: {USER_ID}")

    if not spi._wait_for("logged_in", timeout=15):
        print(f"\n❌ 登录失败或超时: {spi.last_error}")
        api.Release()
        return None, None, False

    # 等结算确认完成
    spi._wait_for("confirmed", timeout=5)

    # 查询账户
    print("→ 查询账户信息…")
    spi.account_ready = False
    qry = tdapi.CThostFtdcQryTradingAccountField()
    qry.BrokerID = BROKER_ID
    qry.InvestorID = USER_ID
    api.ReqQryTradingAccount(qry, spi._next_id())
    if spi._wait_for("account_ready", timeout=5):
        print("\n📊 账户信息:")
        for k, v in spi.account_info.items():
            print(f"   {k}: {v}")

    # 查询持仓
    print("\n→ 查询持仓…")
    spi.account_ready = False
    qry = tdapi.CThostFtdcQryInvestorPositionField()
    qry.BrokerID = BROKER_ID
    qry.InvestorID = USER_ID
    api.ReqQryInvestorPosition(qry, spi._next_id())
    spi._wait_for("account_ready", timeout=5)
    if spi.positions:
        print(f"   当前持仓 {len(spi.positions)} 笔:")
        for pos in spi.positions:
            print(f"   {pos['合约']} {pos['方向']}{pos['持仓']}手 "
                  f"(今{pos['今仓']}/昨{pos['昨仓']}) 盈亏:{pos['盈亏']}")
    else:
        print("   当前无持仓")

    return api, spi, True


def place_order(api: "tdapi.CThostFtdcTraderApi", spi: TraderSpi, instr: str,
                direction: str, offset: str, price: float, volume: int = 1):
    """下一笔限价单。

    Args:
        api: CTP trader API
        spi: 回调 SPI
        instr: 合约代码，如 "MA609"（甲醇 2609）
        direction: "0"=买 "1"=卖
        offset: "0"=开仓 "1"=平仓 "3"=平今
        price: 限价
        volume: 手数
    """
    req = tdapi.CThostFtdcInputOrderField()
    req.BrokerID = BROKER_ID
    req.InvestorID = USER_ID
    req.InstrumentID = instr
    req.OrderRef = str(spi._next_id()).zfill(10)
    req.Direction = direction
    req.CombOffsetFlag = offset
    req.CombHedgeFlag = "1"  # 投机
    req.LimitPrice = price
    req.VolumeTotalOriginal = volume
    req.OrderPriceType = "2"  # 限价
    req.TimeCondition = "3"   # 当日有效
    req.VolumeCondition = "1" # 任何数量
    req.MinVolume = 1
    req.ContingentCondition = "1" # 立即
    req.ForceCloseReason = "0"     # 非强平
    req.IsAutoSuspend = 0
    req.UserForceClose = 0

    print(f"\n📝 下单: {instr} {'买' if direction=='0' else '卖'}"
          f"{'开' if offset=='0' else '平' if offset=='1' else '平今'} "
          f"{volume}手 @ {price}")
    api.ReqOrderInsert(req, spi._next_id())


def interactive_order(api, spi):
    """交互式下单。"""
    print("\n" + "=" * 50)
    print("📝 下单模式")
    print("   合约代码示例: MA609（甲醇2609）, TA609（PTA2609）, rb2610（螺纹钢2610）")
    print("   方向: 买=0 / 卖=1 | 开平: 开=0 / 平=1 / 平今=3")
    print("   输入 'q' 退出\n")

    while True:
        instr = input("   合约代码: ").strip().upper()
        if instr.lower() == "q":
            break

        direction = input("   方向 (0=买 1=卖): ").strip()
        if direction.lower() == "q":
            break

        offset = input("   开平 (0=开 1=平 3=平今): ").strip()
        if offset.lower() == "q":
            break

        price_str = input("   价格: ").strip()
        if price_str.lower() == "q":
            break

        volume_str = input("   手数 [1]: ").strip()
        volume = int(volume_str) if volume_str else 1

        try:
            price = float(price_str)
        except ValueError:
            print("   ❌ 价格格式错误")
            continue

        place_order(api, spi, instr, direction, offset, price, volume)
        time.sleep(1)  # 等回报


def login_with_retry(api, spi, max_retries=3):
    """登录，如果未认证则跳过认证步骤。"""
    pass  # CTP 仿真通常直接登录即可


# ── main ────────────────────────────────────────────────────────
def main():
    get_credentials()

    if not USER_ID or not PASSWORD:
        print("❌ 缺少 UserID 或 Password。设 CTP_USER_ID / CTP_PASSWORD 环境变量或交互输入。")
        sys.exit(1)

    # 连接 + 登录
    api, spi, ok = connect_and_login()
    if not ok:
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("\n✅ --dry-run 模式：连接+登录成功，不下单。")
    else:
        interactive_order(api, spi)

    print("\n👋 释放连接…")
    api.Release()
    print("完成。")


if __name__ == "__main__":
    # 确保 Ctrl+C 能正常释放
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    main()
