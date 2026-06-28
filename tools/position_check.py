#!/usr/bin/env python3
"""
仓位检查器 — 下单前必跑
────────────────────────
输入：本金、拟交易品种、合约、数量
输出：是否可以下单 + 风险指标

规则：
  虚值层: 总敞口 ≤ 5% 本金, 单笔 ≤ 2%
  事件层: 总敞口 ≤ 20% 本金, 单笔 ≤ 10%
  总风险敞口 ≤ 25% 本金
  已有持仓 + 拟开仓 不超上限

用法:
  python3 position_check.py --capital 10000
  python3 position_check.py --capital 10000 --action "买P2000@0.50x3手玉米"
  python3 position_check.py --capital 10000 --check-journal  # 读交易日志算当前敞口
"""

import sys
import os
import json
import argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL_DIR = os.path.join(SCRIPT_DIR, "journal")
POSITION_FILE = os.path.join(SCRIPT_DIR, "positions.json")

VARIETIES = {
    "au": {"name": "沪金",   "mult": 1000},
    "m":  {"name": "豆粕",   "mult": 10},
    "c":  {"name": "玉米",   "mult": 10},
    "cf": {"name": "棉花",   "mult": 5},
    "sr": {"name": "白糖",   "mult": 10},
    "ta": {"name": "PTA",    "mult": 5},
    "i":  {"name": "铁矿石", "mult": 100},
    "ru": {"name": "橡胶",   "mult": 10},
    "ma": {"name": "甲醇",   "mult": 10},
    "rm": {"name": "菜籽粕", "mult": 10},
}

# 风险参数
DEEP_OTM_MAX_PCT = 0.05    # 虚值层总敞口 ≤ 5%
DEEP_OTM_SINGLE_PCT = 0.02 # 虚值层单笔 ≤ 2%
EVENT_MAX_PCT = 0.20        # 事件层总敞口 ≤ 20%
EVENT_SINGLE_PCT = 0.10     # 事件层单笔 ≤ 10%
TOTAL_MAX_PCT = 0.25        # 总敞口 ≤ 25%


def load_positions():
    """加载当前持仓"""
    if os.path.exists(POSITION_FILE):
        with open(POSITION_FILE, 'r') as f:
            return json.load(f)
    return {"positions": [], "total_exposure_deep": 0, "total_exposure_event": 0}


def save_positions(data):
    with open(POSITION_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calculate_max_loss(variety_code, strike, premium, quantity, position_type="deep"):
    """计算单笔最大亏损"""
    mult = VARIETIES[variety_code]["mult"]
    if position_type == "deep":
        return premium * mult * quantity  # 买方：最大亏损 = 权利金
    else:
        # 事件跨式：两个腿都亏光
        return premium * mult * quantity


def check(action_str, capital, position_type="deep"):
    """检查是否可以开仓"""
    positions = load_positions()
    current_deep = positions.get("total_exposure_deep", 0)
    current_event = positions.get("total_exposure_event", 0)

    # 解析 action_str: "买P2000@0.50x3手玉米" 或 "P2000@0.50x3 c"
    import re
    match = re.match(r'(?:买)?P?(\d+)@([\d.]+)x(\d+)(?:手)?\s*(\w+)', action_str)
    if not match:
        return {"error": f"无法解析: {action_str}。格式: 'P2000@0.50x3 c' (行权价@单价x数量 品种)"}

    strike = int(match.group(1))
    premium = float(match.group(2))
    quantity = int(match.group(3))
    variety_code = match.group(4)

    if variety_code not in VARIETIES:
        return {"error": f"未知品种: {variety_code}"}

    name = VARIETIES[variety_code]["name"]
    mult = VARIETIES[variety_code]["mult"]
    total_cost = premium * mult * quantity
    max_loss = calculate_max_loss(variety_code, strike, premium, quantity, position_type)

    # 规则检查
    if position_type == "deep":
        single_limit = capital * DEEP_OTM_SINGLE_PCT
        total_limit = capital * DEEP_OTM_MAX_PCT
        current_exposure = current_deep
        layer_name = "虚值层"
    else:
        single_limit = capital * EVENT_SINGLE_PCT
        total_limit = capital * EVENT_MAX_PCT
        current_exposure = current_event
        layer_name = "事件层"

    new_exposure = current_exposure + max_loss
    all_exposure = (current_deep + current_event + max_loss
                    - (current_exposure if position_type == "deep" else current_deep))

    checks = {
        "单笔上限": {
            "limit": single_limit,
            "actual": max_loss,
            "pass": max_loss <= single_limit,
            "msg": f"{'✅' if max_loss <= single_limit else '❌'} 单笔 ¥{max_loss:.0f} / ¥{single_limit:.0f}"
        },
        "层级上限": {
            "limit": total_limit,
            "actual": new_exposure,
            "pass": new_exposure <= total_limit,
            "msg": f"{'✅' if new_exposure <= total_limit else '❌'} {layer_name}敞口 ¥{new_exposure:.0f} / ¥{total_limit:.0f}"
        },
        "总敞口": {
            "limit": capital * TOTAL_MAX_PCT,
            "actual": all_exposure,
            "pass": all_exposure <= capital * TOTAL_MAX_PCT,
            "msg": f"{'✅' if all_exposure <= capital * TOTAL_MAX_PCT else '❌'} 总敞口 ¥{all_exposure:.0f} / ¥{capital * TOTAL_MAX_PCT:.0f}"
        },
    }

    all_pass = all(c["pass"] for c in checks.values())

    return {
        "pass": all_pass,
        "action": f"买 {name} P{strike} @{premium} × {quantity}手",
        "cost": total_cost,
        "max_loss": max_loss,
        "layer": layer_name,
        "checks": checks,
        "current_deep_exposure": current_deep,
        "current_event_exposure": current_event,
    }


def print_check(result, capital):
    """打印仓位检查结果"""
    if "error" in result:
        print(f"\n  ❌ {result['error']}\n")
        return

    print(f"\n{'═'*60}")
    print(f"  📊 仓位检查 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*60}")
    print(f"\n  拟开仓: {result['action']}")
    print(f"  层级: {result['layer']}")
    print(f"  总成本: ¥{result['cost']:,.0f}")
    print(f"  最大亏损: ¥{result['max_loss']:,.0f}")

    print(f"\n  {'─'*50}")
    print(f"  {'检查项':<12} {'上限':>10} {'实际':>10} {'结果':>6}")
    print(f"  {'─'*50}")
    for name, check in result['checks'].items():
        print(f"  {name:<12} ¥{check['limit']:>9,.0f} ¥{check['actual']:>9,.0f} {'✅' if check['pass'] else '❌':>6}")

    print(f"\n  当前持仓:")
    print(f"    虚值层敞口: ¥{result['current_deep_exposure']:,.0f} / ¥{capital * DEEP_OTM_MAX_PCT:,.0f}")
    print(f"    事件层敞口: ¥{result['current_event_exposure']:,.0f} / ¥{capital * EVENT_MAX_PCT:,.0f}")

    if result['pass']:
        print(f"\n  ✅ 全部通过，可以下单")
    else:
        print(f"\n  🛑 不通过！调整数量或等现有仓位平掉")
    print()


def main():
    parser = argparse.ArgumentParser(description="仓位检查器")
    parser.add_argument('--capital', type=float, required=True, help='当前本金(元)')
    parser.add_argument('--action', type=str, default=None, help='拟交易: "P2000@0.50x3 c"')
    parser.add_argument('--type', type=str, default='deep', choices=['deep', 'event'],
                        help='策略层: deep=虚值倒挂, event=事件驱动')
    parser.add_argument('--close', type=str, default=None, help='平仓ID（从positions.json中移除）')
    parser.add_argument('--save', action='store_true', help='检查通过后自动保存到持仓文件')
    parser.add_argument('--show', action='store_true', help='显示当前持仓')
    args = parser.parse_args()

    if args.show:
        positions = load_positions()
        print(f"\n  📋 当前持仓:")
        if positions['positions']:
            for p in positions['positions']:
                print(f"    {p}")
        else:
            print(f"    (空仓)")
        print(f"  虚值层敞口: ¥{positions['total_exposure_deep']:,.0f}")
        print(f"  事件层敞口: ¥{positions['total_exposure_event']:,.0f}")
        print()
        return

    if args.action:
        result = check(args.action, args.capital, args.type)
        print_check(result, args.capital)

        if result.get('pass') and args.save:
            positions = load_positions()
            positions['positions'].append({
                "action": result['action'],
                "cost": result['cost'],
                "max_loss": result['max_loss'],
                "layer": result['layer'],
                "opened_at": datetime.now().strftime('%Y-%m-%d %H:%M'),
            })
            if result['layer'] == '虚值层':
                positions['total_exposure_deep'] += result['max_loss']
            else:
                positions['total_exposure_event'] += result['max_loss']
            save_positions(positions)
            print(f"  ✓ 已保存到持仓文件")


if __name__ == '__main__':
    main()
