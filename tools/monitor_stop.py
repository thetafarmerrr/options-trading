#!/usr/bin/env python3
"""
实时平仓监控 — 信用价差止盈告警

只报警不自动下单。触发时三连：桌面弹窗 + 声音 + 飞书消息。

用法：
  python3 tools/monitor_stop.py                 # 连续监控（手动启停）
  python3 tools/monitor_stop.py --once          # 单次检查（launchd 定时调用）
  python3 tools/monitor_stop.py --dry-run       # 验证配置不实际连接
  python3 tools/monitor_stop.py --once --quiet  # 单次检查，无仓位时不输出

停止：Ctrl+C（连续模式）
"""

import os
import re
import sys
import json
import time
import requests
from datetime import datetime
from tqsdk import TqApi, TqAuth

# ============================================================
# .env 加载（凭据不硬编码；绝对路径定位，launchd 定时跑也能找到）
# ============================================================
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_TOOLS_DIR)
_ENV_FILE = os.path.join(_PROJECT_DIR, ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# ============================================================
# 配置 — 飞书 Webhook 和天勤账号（来自 .env）
# ============================================================
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")
TQ_USER = os.environ.get("TQ_USER", "")
TQ_PASS = os.environ.get("TQ_PASS", "")

if not TQ_USER or not TQ_PASS:
    sys.exit("❌ .env 缺 TQ_USER/TQ_PASS，天勤凭据未配置。监控拒绝启动（宁可不跑，不带空凭据）")
if not FEISHU_WEBHOOK:
    print("⚠️ .env 缺 FEISHU_WEBHOOK，飞书告警失效（监控继续，桌面弹窗+声音不受影响）")

# 监控配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_config.json")

# 轮询间隔（秒）— 连续模式用
POLL_INTERVAL = 3

# 交易时段（北京时间，日盘两段含午休，夜盘一段）
# 注意：每段必须是 (start, end) 二元组，嵌套结构写错会在盘中崩 is_trading_time（8/17 教训：夜盘少套一层）
TRADING_HOURS = (
    ((9, 0), (11, 30)),
    ((13, 30), (15, 0)),
    ((21, 0), (23, 0)),
)
# 加载时自检：结构必须全是「两个二元组」，结构错误 → 启动即崩，不等到 11:30 才炸
assert all(len(r) == 2 and all(isinstance(x, tuple) and len(x) == 2 for x in r) for r in TRADING_HOURS), \
    f"❌ TRADING_HOURS 结构错误: {TRADING_HOURS}"


def is_trading_time():
    """当前是否在交易时段内"""
    now = datetime.now()
    t = (now.hour, now.minute)
    for start, end in TRADING_HOURS:
        if start <= t < end:
            return True
    return False


def load_config():
    """加载监控配置，文件不存在返回 None"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("active") and cfg.get("sell_leg") and cfg.get("buy_leg"):
            return cfg
    return None


def send_alert(title: str, body: str):
    """三连告警：桌面弹窗 + 系统声音 + 飞书机器人"""
    # 1. macOS 桌面弹窗
    os.system(
        f'''osascript -e 'display notification "{body}" with title "{title}"' '''
    )
    # 2. 系统声音
    os.system("afplay /System/Library/Sounds/Ping.aiff")
    # 3. 飞书
    payload = {"msg_type": "text", "content": {"text": f"🚨 {title}\n{body}"}}
    try:
        requests.post(FEISHU_WEBHOOK, json=payload, timeout=5)
    except Exception:
        pass


# ============================================================
# 离场六步 —— 第 2/3/4/5 条（2026-09-11 补）
#
# 背景：原版只监控第 1 条（止盈 50%）+ 第 6 条（事件缓冲），六步只覆盖 2 步。
# 实盘证据：cf2701 期货 17200 → 16330，一路走进 ⛔ 撤离区（卖腿入水 70 点），
#          monitor_stop 全程在跑，**零告警**。因为它只会报喜——
#          net_cost = 卖腿ask − 买腿bid，只有赚钱方向才可能 ≤ stop_net，
#          亏钱方向一路涨到全亏也一声不响。
#
# 规则出处 docs/monitoring-rules.md：
#   2. 期货触及买腿行权价 → 平（开仓前定的硬线）
#   3. 剩余 ≤ 2 个交易日   → 平（末日 Gamma + 指派风险）
#   4. 两腿都实值          → 平（亏损已封顶，持仓无意义）
#   5. OTM < 1% + 期货向卖腿方向移动 → 平（撤离区）
#   三档体系（:128-133）：🟢>3% / 🟡2-3% / 🔴1-2% / ⛔<1%
#
# ⚠️ 口径冲突 —— 用户 2026-09-11 裁定「取并集」：
#   :133 ⛔ <1% 写「无条件｜立刻平。不等。不犹豫」
#   :259 第 5 条写「<1% **+** 期货向卖腿方向移动」
#   两者矛盾 → 取并集：**<1% 一律告警**，方向只作附注，不因方向不符而压掉告警。
#   理由：漏报的代价是「零告警进撤离区」（就是今天 cf 那次），
#         误报的代价只是你看一眼然后判断「方向还没到，继续持有」。
# ============================================================

# 卖腿代码 "CZCE.CF701P16400" → 品种字母 + 合约月 + C/P + 行权价
# 例：CZCE.CF701P16400 / SHFE.au2607C560 / DCE.m2701P3150
_LEG_RE = re.compile(r"^[A-Za-z]+\.[A-Za-z]+\d+([CP])(\d+(?:\.\d+)?)$")


def parse_leg(code):
    """解析期权腿代码 → (kind, strike)。解析失败返回 (None, None)。"""
    m = _LEG_RE.match(str(code or "").strip())
    if not m:
        return None, None
    return m.group(1).upper(), float(m.group(2))


def spread_geometry(cfg):
    """从配置解出卖方价差几何 → (kind, sell_strike, buy_strike, width)

    kind='P'（卖 Put 价差，危险方向=期货下跌）/ 'C'（卖 Call 价差，危险方向=期货上涨）
    两腿期权类型不一致 → 返回 None（不是本监控覆盖的结构）
    """
    sk, ss = parse_leg(cfg.get("sell_leg"))
    bk, bs = parse_leg(cfg.get("buy_leg"))
    if sk is None or bk is None or sk != bk:
        return None
    return sk, ss, bs, abs(ss - bs)


def sell_otm_pct(kind, fut, strike):
    """卖腿虚值百分比。正 = 虚值（安全），负 = 实值（已入水）。

    与 journal 9/11 口径一致：卖 P16400、期货 16330 → (16330−16400)/16400 = −0.43%
    """
    if not strike:
        return None
    return (fut - strike) / strike if kind == "P" else (strike - fut) / strike


def trading_days_left(expire_ns):
    """距到期的剩余【工作日】数。

    ⚠️ 近似：只按周一~周五计数，**不含法定节假日** → 会高估 1-2 天。
    宁可早报一天，不可晚报 —— 第 3 条是「剩 ≤2 交易日」，晚报等于失效。
    """
    from datetime import date, timedelta
    if not expire_ns:
        return None
    try:
        exp = datetime.fromtimestamp(expire_ns / 1e9).date()
    except (OSError, ValueError, OverflowError):
        return None
    today = date.today()
    if exp <= today:
        return 0
    n, d = 0, today
    while d < exp:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def check_exit_steps(cfg, fut_price, expire_ns, already_fired):
    """离场六步第 2/3/4/5 条 → [(step_no, level, title, body), ...]

    already_fired：已报过的 step 号集合（本轮内不重报）。
    期货价缺失 → 返回空（不猜，宁可不报也不编一个价）。
    """
    geo = spread_geometry(cfg)
    if not geo or not fut_price or fut_price <= 0:
        return []

    kind, sell_strike, buy_strike, width = geo
    out = []

    # 方向参考：优先开仓时的期货价（跨日移动才看得见），缺则用昨收（当日方向）
    ref, ref_src = None, ""
    entry_fut = cfg.get("entry_futures")
    if entry_fut and float(entry_fut) > 0:
        ref, ref_src = float(entry_fut), "开仓价"
    move = None if ref is None else fut_price - ref
    if move is None:
        dir_txt = "（无参考价，方向未判——请填 entry_futures）"
    else:
        # 卖 Put 价差：期货下跌 = 朝卖腿走；卖 Call 价差：期货上涨 = 朝卖腿走
        toward = (move < 0) if kind == "P" else (move > 0)
        arrow = "↓" if move < 0 else ("↑" if move > 0 else "→")
        dir_txt = (f"期货 {fut_price:.0f}（{ref_src} {ref:.0f} 起 {arrow}{abs(move):.0f}）"
                   f" → {'✅ 朝卖腿方向' if toward else '⚠️ 未朝卖腿方向'}")

    otm = sell_otm_pct(kind, fut_price, sell_strike)
    otm_pct = otm * 100 if otm is not None else None

    # ── 第 5 条 + 三档体系 ──
    # 并集口径：<1% 与 1~3% 都报，方向只作附注（三档原规则要求方向，此处不据此压掉）
    if otm_pct is not None and otm_pct < 1.0:
        out.append((5, "⛔",
                    f"撤离区触发 — {cfg['name']}",
                    f"卖腿 OTM {otm_pct:+.2f}%  < 1%（第 5 条 · 无条件档）\n"
                    f"卖腿行权 {sell_strike:.0f}  期货 {fut_price:.0f}\n"
                    f"{dir_txt}\n"
                    f"→ 规则：⛔ 立刻平，不等。方向仅供参考，不改变本条触发。"))
    elif otm_pct is not None and otm_pct < 2.0:
        out.append((5, "🔴",
                    f"高危档 — {cfg['name']}",
                    f"卖腿 OTM {otm_pct:+.2f}%  在 🔴 1-2% 高危区\n"
                    f"卖腿行权 {sell_strike:.0f}  期货 {fut_price:.0f}\n"
                    f"{dir_txt}\n"
                    f"→ 规则：期货向卖腿移动 + 任何到期日 → 平（除非 >45 天且已止跌反弹）"))
    elif otm_pct is not None and otm_pct < 3.0:
        out.append((5, "🟡",
                    f"警戒档 — {cfg['name']}",
                    f"卖腿 OTM {otm_pct:+.2f}%  在 🟡 2-3% 警戒区\n"
                    f"卖腿行权 {sell_strike:.0f}  期货 {fut_price:.0f}\n"
                    f"{dir_txt}\n"
                    f"→ 规则：期货向卖腿移动 + 到期 <30 天 → 评估平仓成本；亏 <30% 最大亏损可平"))

    # ── 第 2 条：期货触及买腿行权价 ──
    reached_buy = (fut_price <= buy_strike) if kind == "P" else (fut_price >= buy_strike)
    if reached_buy:
        out.append((2, "🔴",
                    f"期货触及买腿 — {cfg['name']}",
                    f"期货 {fut_price:.0f} 已触及买腿行权价 {buy_strike:.0f}\n"
                    f"卖腿 OTM {otm_pct:+.2f}%\n"
                    f"→ 规则：第 2 条，开仓前定的硬线 → 平"))

    # ── 第 4 条：两腿都实值（亏损已封顶）──
    both_itm = (fut_price < buy_strike) if kind == "P" else (fut_price > buy_strike)
    if both_itm:
        out.append((4, "⛔",
                    f"两腿都实值 — {cfg['name']}",
                    f"期货 {fut_price:.0f} 已越过买腿行权价 {buy_strike:.0f}\n"
                    f"两腿均实值 → 亏损已封顶，持仓无意义\n"
                    f"→ 规则：第 4 条 → 平仓释放保证金"
                    f"（第 2 条『触及买腿』此时已被本条覆盖）"))

    # ── 第 3 条：剩余 ≤ 2 个交易日 ──
    dte = trading_days_left(expire_ns)
    if dte is not None and dte <= 2:
        out.append((3, "🔴",
                    f"临期告警 — {cfg['name']}",
                    f"剩余 ≈{dte} 个工作日（近似，未扣节假日）≤ 2\n"
                    f"卖腿 OTM {otm_pct:+.2f}%\n"
                    f"→ 规则：第 3 条，末日 Gamma + 指派风险 → 平，不赚最后一个硬币"))

    return [(s, lv, t, b) for (s, lv, t, b) in out if s not in already_fired]


def check_once(cfg):
    """单次检查（供 launchd 定时调用）"""
    api = TqApi(auth=TqAuth(TQ_USER, TQ_PASS))
    try:
        sell_quote = api.get_quote(cfg["sell_leg"])
        buy_quote = api.get_quote(cfg["buy_leg"])
        fut_quote = _subscribe_futures(api, cfg)
        api.wait_update()

        sell_ask = sell_quote.ask_price1
        buy_bid = buy_quote.bid_price1
        fut_price = fut_quote.last_price if fut_quote else None
        fired = set()   # once 模式无状态，每次都是全新一轮

        hit = False

        # ── 第 1 条：止盈（原逻辑，只报喜那一侧）──
        if sell_ask and buy_bid and sell_ask > 0 and buy_bid > 0:
            net_cost = sell_ask - buy_bid
            if net_cost <= cfg["stop_net"]:
                title = f"止盈触发 — {cfg['name']}"
                body = (
                    f"净价 {net_cost:.1f} ≤ 止盈线 {cfg['stop_net']}\n"
                    f"卖腿ask={sell_ask:.1f}  买腿bid={buy_bid:.1f}\n"
                    f"利润 ≈ {(cfg.get('credit', 0) - net_cost):.1f}（已扣净成本）"
                )
                send_alert(title, body)
                print(f"🚨 {title}")
                hit = True

        # ── 第 2/3/4/5 条：离场告警（2026-09-11 补）──
        for step, level, title, body in check_exit_steps(
                cfg, fut_price, getattr(sell_quote, "expire_datetime", None), fired):
            fired.add(step)
            send_alert(f"{level} {title}", body)
            print(f"{level} {title}\n{body}")
            hit = True

        return hit
    finally:
        api.close()


def check_event_buffer(cfg, futures_price=None):
    """事件缓冲检查（#14）：持仓品种未来2天有事件时，比「缓冲 vs 事件预期波动」。

    只报不平。数据源：
    - 事件：event_calendar.get_upcoming_events(days=2)，跳过 category=expiry（8/14 修复）
    - 预期波动：IV × √(1/242) × 2（单日 2σ，iv_history 数据可追溯，非 event_calendar 估算字段）
    - 缓冲：卖腿行权价 → 期货价 OTM%（futures_price 由调用方 tqsdk 现拉）

    判断（对应 monitoring-rules 离场六步第 6 条）：
      缓冲 > 2σ → 持有（打不穿）
      缓冲 < 1σ → 平（大概率打穿）
      1σ ≤ 缓冲 ≤ 2σ → 缩仓减半（多手生效）+ D-1 重估

    返回 (has_event, message)。无事件或无需提示返回 (False, "")。
    """
    import math
    import re as _re

    try:
        sys.path.insert(0, _TOOLS_DIR)
        from event_calendar import get_upcoming_events
        from scanner.volatility import load_iv_history, _extract_variety, latest_healthy_iv
    except Exception as exc:
        return False, f"⚠️ 事件检查不可用：{exc}"

    # 品种码：卖腿 "CZCE.CF701P16400" → "cf"
    sell_leg = cfg.get("sell_leg", "")
    vcode = _extract_variety(sell_leg)
    if not vcode:
        return False, ""

    # 未来2天事件（跳过到期）
    try:
        events = [e for e in get_upcoming_events(days=2, varieties=[vcode])
                  if e.get("category") != "expiry"
                  and e.get("impact") in ("high", "medium")]
    except Exception:
        return False, ""

    if not events:
        return False, ""

    # 事件预期波动：IV × √(1/242) × 2（单日2σ，取品种最新健康合约）
    iv_hist = load_iv_history()
    hv_info, _ = latest_healthy_iv(iv_hist, vcode)
    if not hv_info or hv_info.get("iv_est") is None:
        return True, f"⚠️ [{vcode}] 有事件（{events[0]['title']}）但无 IV 数据，无法算缓冲。"

    iv = hv_info["iv_est"]
    exp_move = iv * math.sqrt(1 / 242) * 2

    # 卖腿行权价：卖腿 "CZCE.CF701P16400" → 16400
    sell_strike = None
    m = _re.search(r"[CP](\d+(?:\.\d+)?)$", sell_leg)
    if m:
        sell_strike = float(m.group(1))

    # 无期货价或卖腿行权价 → 只报事件+预期波动，不做缓冲判断
    if futures_price is None or sell_strike is None or futures_price <= 0:
        return True, f"有事件 {events[0]['title']}，IV={iv*100:.1f}% 单日2σ={exp_move*100:.2f}%（缓冲判断需期货价）"

    # 缓冲（卖 Put：缓冲 = 期货在卖腿之上多少；卖 Call 同式看距离）
    buffer_pct = abs(futures_price - sell_strike) / futures_price
    one_sigma = exp_move / 2  # 2σ → 1σ

    if buffer_pct > exp_move:
        action = "✅ 缓冲 > 2σ，事件打不穿，持有"
    elif buffer_pct < one_sigma:
        action = "⛔ 缓冲 < 1σ，D-0 建议平仓"
    else:
        action = "⚠️ 1σ≤缓冲≤2σ，缩仓减半（多手生效）+ D-1 重估"

    return True, (f"事件 {events[0]['title']}：缓冲 {buffer_pct*100:.1f}% vs 预期2σ {exp_move*100:.2f}%"
                  f" → {action}")


def dry_run(cfg):
    """验证配置，不实际连接"""
    print("🔍 配置验证：")
    print(f"   品种: {cfg['name']}")
    print(f"   卖腿: {cfg['sell_leg']}")
    print(f"   买腿: {cfg['buy_leg']}")
    print(f"   收入 credit: {cfg.get('credit', '?')}")
    print(f"   止盈净价 ≤ {cfg.get('stop_net', '?')}")

    # ── 最大亏损（2026-09-11 修）──
    # 旧式：stop_net × 2 − credit。错在 stop_net 是【止盈线】(= credit × 50%)，
    # 不是价差宽度 —— 两个不相干的数凑出 "0.0"。cf2701（宽 200 / credit 69）
    # 打印「最大亏损 ≈ 0.0」，让一个 655 元风险的仓位看起来无风险。
    # 正确：宽度 = |卖腿行权 − 买腿行权|，最大亏损 = (宽度 − credit) × 乘数。
    geo = spread_geometry(cfg)
    if geo:
        kind, ss, bs, width = geo
        credit = cfg.get("credit", 0)
        mult = cfg.get("multiplier")
        print(f"   结构: 卖{kind}{ss:.0f} / 买{kind}{bs:.0f}   宽度 = {width:.0f} 点")
        if mult:
            print(f"   最大亏损 = ({width:.0f} − {credit}) × {mult} = {(width - credit) * float(mult):.0f}")
        else:
            print(f"   最大亏损 = ({width:.0f} − {credit}) × 乘数 = ?"
                  f"   ⚠️ 配置缺 multiplier，算不出——补上它（各品种不同）")
    else:
        print("   ⚠️ 腿代码解析失败 → 算不出价差宽度/最大亏损（检查 leg 格式）")

    # 离场告警所需字段
    if cfg.get("entry_futures"):
        print(f"   开仓时期货 = {cfg['entry_futures']}（离场方向参考）")
    else:
        print("   ⚠️ 缺 entry_futures → 离场方向只能退回当日涨跌判，跨日移动看不见")
    print()
    # 基础校验
    errors = []
    if not cfg.get('name'): errors.append("名称未填")
    if not cfg.get('sell_leg'): errors.append("卖腿代码未填")
    if not cfg.get('buy_leg'): errors.append("买腿代码未填")
    if cfg.get('stop_net', 0) <= 0: errors.append("止盈净价未填或 ≤0")
    if cfg.get('credit', 0) <= 0: errors.append("credit 未填或 ≤0")
    if errors:
        print("❌ 配置问题：")
        for e in errors: print(f"   - {e}")
        return False
    else:
        print("✅ 配置校验通过。可以启动监控。")
        return True


def _subscribe_futures(api, cfg):
    """订阅卖腿对应的期货合约。卖腿 "CZCE.CF701P16400" → 期货 "CZCE.CF701"。

    8/17 bug 修复：旧正则漏了合约月份数字，得到不存在的 "CZCE.CF"
    → get_quote 报错 → 坏订阅污染连接 → wait_update 静默卡死。
    失败返回 None（不抛），调用方需容忍 fut_quote 为 None。
    """
    m = re.match(r"([A-Za-z]+\.[A-Za-z]+\d+)", cfg.get("sell_leg", ""))
    if not m:
        return None
    try:
        return api.get_quote(m.group(1))
    except Exception:
        return None


def _connect_quotes(cfg):
    """建立连接并订阅卖腿/买腿/期货报价。返回 (api, sell_quote, buy_quote, fut_quote)。"""
    api = TqApi(auth=TqAuth(TQ_USER, TQ_PASS))
    sell_quote = api.get_quote(cfg["sell_leg"])
    buy_quote = api.get_quote(cfg["buy_leg"])
    fut_quote = _subscribe_futures(api, cfg)
    return api, sell_quote, buy_quote, fut_quote


def main():
    args = sys.argv[1:]
    once = "--once" in args
    dry = "--dry-run" in args
    quiet = "--quiet" in args

    cfg = load_config()

    # ── dry-run：只验证，不连接 ──
    if dry:
        if not cfg:
            print("⏸️  无活跃监控任务（active=false 或腿未填）。")
            sys.exit(0)
        ok = dry_run(cfg)
        sys.exit(0 if ok else 1)

    # ── once：单次检查（launchd 用）──
    if once:
        if not cfg:
            if not quiet:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 无活跃仓位，跳过。")
            return
        # 非交易时段跳过（省天勤连接）
        if not is_trading_time():
            if not quiet:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 非交易时段，跳过。")
            return
        if not quiet:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查 {cfg['name']}...")
        triggered = check_once(cfg)
        if not triggered and not quiet:
            print("   ⏳ 未触发止盈。")
        # #14 事件缓冲检查（只报不平，非止盈检查的一部分）
        has_ev, ev_msg = check_event_buffer(cfg)
        if has_ev and not quiet:
            print(f"   📅 {ev_msg}")
        return

    # ── 连续模式（手动启动）──
    if not cfg:
        print("⏸️  无活跃监控任务。")
        print("   开仓后编辑 tools/monitor_config.json 填入腿代码和止盈净价。")
        return

    print(f"🔭 监控启动：{cfg['name']}")
    print(f"   卖腿: {cfg['sell_leg']}  买腿: {cfg['buy_leg']}")
    print(f"   止盈净价 ≤ {cfg['stop_net']}（credit={cfg.get('credit','?')}，50%={cfg.get('stop_net','?')}）")
    print(f"   轮询间隔: {POLL_INTERVAL}s")
    print()

    alerted = False
    last_net = None
    ev_last_report = None  # 事件检查：只在一轮报告一次（有事件变化才重报）

    try:
        # 外层循环：连接失败/报价停更 → 重建连接，绝不静默死掉（8/17 加固）
        while True:
            try:
                api, sell_quote, buy_quote, fut_quote = _connect_quotes(cfg)
            except Exception as exc:
                print(f"⚠️ [{time.strftime('%H:%M:%S')}] 连接失败: {exc}")
                print("   5 秒后重试...")
                time.sleep(5)
                continue

            last_activity = time.time()   # 最近一次报价流动的墙钟时间
            last_q_dt = None              # 上一次看到的报价 datetime
            last_heartbeat = time.time()
            exit_fired = set()            # 已报过的离场 step 号（条件解除后移除，可重报）
            exit_err_reported = None      # 离场检查异常只打一次，不刷屏

            try:
                while True:
                    try:
                        api.wait_update(deadline=time.time() + 5)
                    except Exception:
                        pass

                    # 报价健康信号：sell_quote.datetime 前进 = 行情还在流动
                    q_dt = str(sell_quote.datetime)
                    if q_dt and q_dt != last_q_dt:
                        last_q_dt = q_dt
                        last_activity = time.time()

                    # #14 事件缓冲检查（只报不平；无事件返回 False 不打扰）
                    try:
                        fut_price = fut_quote.last_price if fut_quote else None
                        has_ev, ev_msg = check_event_buffer(cfg, futures_price=fut_price)
                        if has_ev and ev_msg != ev_last_report:
                            print(f"\n📅 {ev_msg}\n")
                            ev_last_report = ev_msg
                    except Exception:
                        pass

                    sell_ask = sell_quote.ask_price1
                    buy_bid = buy_quote.bid_price1

                    # ── 离场六步第 2/3/4/5 条（2026-09-11 补）──
                    # 条件解除的 step 从 fired 里移除 → 再次触发会重报
                    try:
                        fut_price = fut_quote.last_price if fut_quote else None
                        trig = check_exit_steps(
                            cfg, fut_price,
                            getattr(sell_quote, "expire_datetime", None), set())
                        for step, level, title, body in trig:
                            if step not in exit_fired:
                                exit_fired.add(step)
                                send_alert(f"{level} {title}", body)
                                print(f"\n{level} {title}\n{body}\n")
                        exit_fired &= {s for (s, _, _, _) in trig}
                    except Exception as exc:
                        if exit_err_reported is None:
                            print(f"⚠️ 离场检查异常（不致命，继续监控）：{exc}")
                            exit_err_reported = str(exc)

                    if sell_ask and buy_bid and sell_ask > 0 and buy_bid > 0:
                        net_cost = sell_ask - buy_bid

                        if net_cost != last_net:
                            print(f"  [{time.strftime('%H:%M:%S')}] 净价={net_cost:.1f}  "
                                  f"卖腿ask={sell_ask:.1f} 买腿bid={buy_bid:.1f}  "
                                  f"({'✅ 止盈' if net_cost <= cfg['stop_net'] else '⏳ 等待'})")
                            last_net = net_cost

                        if net_cost <= cfg["stop_net"] and not alerted:
                            title = f"止盈触发 — {cfg['name']}"
                            body = (
                                f"净价 {net_cost:.1f} ≤ 止盈线 {cfg['stop_net']}\n"
                                f"卖腿ask={sell_ask:.1f}  买腿bid={buy_bid:.1f}\n"
                                f"利润 ≈ {(cfg.get('credit', 0) - net_cost):.1f}（已扣净成本）"
                            )
                            send_alert(title, body)
                            print(f"\n🚨 {title}\n{body}\n")
                            alerted = True
                            break

                    # 看门狗：交易时段内报价 5 分钟不流动 → 重建连接
                    now = time.time()
                    if is_trading_time() and now - last_activity > 300:
                        print(f"⚠️ [{time.strftime('%H:%M:%S')}] 报价 5 分钟未流动"
                              f"（最近更新 {time.strftime('%H:%M:%S', time.localtime(last_activity))}）")
                        print("   重建连接...")
                        break

                    # 心跳：静默但有心跳（交易时段 10 分钟，非交易时段 30 分钟）
                    hb_interval = 600 if is_trading_time() else 1800
                    if now - last_heartbeat > hb_interval:
                        net_disp = f"{last_net:.1f}" if last_net is not None else "?"
                        print(f"  [{time.strftime('%H:%M:%S')}] 仍在监控 净价={net_disp} "
                              f"最近更新={time.strftime('%H:%M:%S', time.localtime(last_activity))}")
                        last_heartbeat = now

                    time.sleep(POLL_INTERVAL)
            finally:
                try:
                    api.close()
                except Exception:
                    pass

            if alerted:
                print("告警已发送，监控退出。需要继续监控请重新启动。")
                break

    except KeyboardInterrupt:
        print("\n⏹️  监控已手动停止。")


if __name__ == "__main__":
    main()
