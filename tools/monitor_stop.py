#!/usr/bin/env python3
"""
实时平仓监控 — 信用价差止盈告警

只报警不自动下单。触发时三连：桌面弹窗 + 声音 + 飞书消息。

用法：
  开仓后更新 monitor_config.json（品种、腿、止盈净价）
  python3 tools/monitor_stop.py

停止：Ctrl+C
"""

import os
import sys
import json
import time
import requests
from tqsdk import TqApi, TqAuth

# ============================================================
# 配置 — 飞书 Webhook 和天勤账号
# ============================================================
***REMOVED***
***REMOVED***
***REMOVED***

# 监控配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_config.json")

# 轮询间隔（秒）
POLL_INTERVAL = 3

# 市场开盘时间段过滤（北京时间，粗略：9:00-15:00 + 21:00-23:00 夜盘）
# 全时段跑也行，这里不做时间过滤，靠人工启动/停止


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


def main():
    cfg = load_config()
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

    alerted = False  # 避免重复告警
    last_net = None

    try:
        while True:
            api.wait_update()

            # 卖腿 bid（我们卖平时打 bid）、买腿 ask（我们买平时打 ask）
            sell_bid = sell_quote.bid_price1
            buy_ask = buy_quote.ask_price1

            # 两腿都有有效报价才计算
            if sell_bid and buy_ask and sell_bid > 0 and buy_ask > 0:
                # 净价 = 买回价差的成本 = 买腿 ask − 卖腿 bid
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

                    # 告警一次后退出，避免一直轰炸
                    print("告警已发送，监控退出。需要继续监控请重新启动。")
                    break

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n⏹️  监控已手动停止。")
    finally:
        api.close()


if __name__ == "__main__":
    main()
