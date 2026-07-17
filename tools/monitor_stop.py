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
import sys
import json
import time
import requests
from datetime import datetime
from tqsdk import TqApi, TqAuth

# ============================================================
# 配置 — 飞书 Webhook 和天勤账号
# ============================================================
***REMOVED***
***REMOVED***
***REMOVED***

# 监控配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_config.json")

# 轮询间隔（秒）— 连续模式用
POLL_INTERVAL = 3

# 交易时段（北京时间）
TRADING_HOURS_DAY = (9, 0), (15, 0)     # 日盘 9:00-15:00
TRADING_HOURS_NIGHT = (21, 0), (23, 0)  # 夜盘 21:00-23:00（简化，实际到 23:00）


def is_trading_time():
    """当前是否在交易时段内"""
    now = datetime.now()
    t = (now.hour, now.minute)
    d_start, d_end = TRADING_HOURS_DAY
    n_start, n_end = TRADING_HOURS_NIGHT
    return (d_start <= t < d_end) or (n_start <= t < n_end)


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


def check_once(cfg):
    """单次检查（供 launchd 定时调用）"""
    api = TqApi(auth=TqAuth(TQ_USER, TQ_PASS))
    try:
        sell_quote = api.get_quote(cfg["sell_leg"])
        buy_quote = api.get_quote(cfg["buy_leg"])
        api.wait_update()

        sell_bid = sell_quote.bid_price1
        buy_ask = buy_quote.ask_price1

        if sell_bid and buy_ask and sell_bid > 0 and buy_ask > 0:
            net_cost = buy_ask - sell_bid
            if net_cost <= cfg["stop_net"]:
                title = f"止盈触发 — {cfg['name']}"
                body = (
                    f"净价 {net_cost:.1f} ≤ 止盈线 {cfg['stop_net']}\n"
                    f"卖腿bid={sell_bid:.1f}  买腿ask={buy_ask:.1f}\n"
                    f"利润 ≈ {(cfg.get('credit', 0) - net_cost):.1f}（已扣净成本）"
                )
                send_alert(title, body)
                print(f"🚨 {title}")
                return True
        return False
    finally:
        api.close()


def dry_run(cfg):
    """验证配置，不实际连接"""
    print("🔍 配置验证：")
    print(f"   品种: {cfg['name']}")
    print(f"   卖腿: {cfg['sell_leg']}")
    print(f"   买腿: {cfg['buy_leg']}")
    print(f"   收入 credit: {cfg.get('credit', '?')}")
    print(f"   止盈净价 ≤ {cfg.get('stop_net', '?')}")
    print(f"   最大亏损 ≈ {cfg.get('stop_net', 0) * 2 - cfg.get('credit', 0):.1f}" if cfg.get('stop_net') and cfg.get('credit') else "")
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

    api = TqApi(auth=TqAuth(TQ_USER, TQ_PASS))
    sell_quote = api.get_quote(cfg["sell_leg"])
    buy_quote = api.get_quote(cfg["buy_leg"])

    alerted = False
    last_net = None

    try:
        while True:
            api.wait_update()

            sell_bid = sell_quote.bid_price1
            buy_ask = buy_quote.ask_price1

            if sell_bid and buy_ask and sell_bid > 0 and buy_ask > 0:
                net_cost = buy_ask - sell_bid

                if net_cost != last_net:
                    print(f"  [{time.strftime('%H:%M:%S')}] 净价={net_cost:.1f}  "
                          f"卖腿bid={sell_bid:.1f} 买腿ask={buy_ask:.1f}  "
                          f"({'✅ 止盈' if net_cost <= cfg['stop_net'] else '⏳ 等待'})")
                    last_net = net_cost

                if net_cost <= cfg["stop_net"] and not alerted:
                    title = f"止盈触发 — {cfg['name']}"
                    body = (
                        f"净价 {net_cost:.1f} ≤ 止盈线 {cfg['stop_net']}\n"
                        f"卖腿bid={sell_bid:.1f}  买腿ask={buy_ask:.1f}\n"
                        f"利润 ≈ {(cfg.get('credit', 0) - net_cost):.1f}（已扣净成本）"
                    )
                    send_alert(title, body)
                    print(f"\n🚨 {title}\n{body}\n")
                    alerted = True

                    print("告警已发送，监控退出。需要继续监控请重新启动。")
                    break

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n⏹️  监控已手动停止。")
    finally:
        api.close()


if __name__ == "__main__":
    main()
