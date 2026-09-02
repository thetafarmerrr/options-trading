"""三层输出：控制台 + Markdown 日志 + JSON 日志

保留旧方案全部输出格式：
- 🟢 [EXEC] 卖方信用价差（含 IV-HV 分层 + 止盈/止损）
- 🟠 [NEAR] 接近但盈亏比不足
- 🟡 [PAPER] 买方三区
- ⚪ [OBSERVE] 高级策略仅计数
- 🔘 [IGNORE] 未扫描策略
- 📊 IV-HV 全品种面板 + 💧 干旱总结 + 🔮 非例行扫描
"""

import json
import os
import re
import csv
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

from .models import Signal, OptionChain
from .config import VARIETIES, RR_MIN, EXEC_RR_MIN, EVENT_SPREAD_MAX


def _cl_str(signal: Signal) -> str:
    """格式化 IV Collector 分位字符串"""
    pct = signal.metadata.get("_cl_pct")
    if pct is not None:
        days = signal.metadata.get("_cl_days", 0)
        return f" Cl{pct}%({days}d)"
    return " ClN/A"


class Reporter:
    """统一报告器：控制台 + 文件输出"""

    def __init__(self, capital: float = 20000.0, show_limit: int = 10):
        self.capital = capital
        self.show_limit = show_limit

    def print_header(self):
        """打印头部横幅"""
        now = datetime.now()
        print(f"\n{'█'*70}")
        print(f"  🔭 全策略扫描 v4 — {now.strftime('%Y-%m-%d %H:%M')}")
        print(f"  {'█'*70}")

    def print_chain_status(self, chains: Dict[str, Optional[OptionChain]]):
        """打印期权链拉取状态"""
        print(f"\n  📡 akshare 拉取期权链中...")
        for vcode, chain in chains.items():
            vinfo = VARIETIES.get(vcode, {})
            vname = vinfo.get("name", vcode)
            if chain is None:
                print(f"     ❌ {vname:6s} → 拉取失败")
            else:
                print(f"     ✅ {vname:6s} {chain.contract} → "
                      f"期货 {chain.futures_price} | 链 {len(chain.puts)} 档")

    # ── EXEC 卖方 ──

    def print_exec_section(self, all_signals: List[Signal],
                           event_vcodes: set,
                           iv_hv: dict,
                           weekly_scan_map: dict):
        """打印 [EXEC] 卖方信用价差"""
        # 计算实际 IV 历史天数（从全量行取不重复日期）
        from .volatility import load_all_iv_rows
        iv_dates = set(r.get("date", "") for r in load_all_iv_rows() if r.get("date"))
        iv_day_count = len(iv_dates)
        iv_note = f"已攒{iv_day_count}天" if iv_day_count < 30 else f"已攒{iv_day_count}天✅"
        print(f"\n  ⚠️ IV分位：Scanner=工程近似 | Collector=DTE分组 | {iv_note}")
        print(f"\n  🟢 [EXEC] 卖方信用价差 — 可执行")

        cs_ok = [s for s in all_signals
                 if s.tier == "EXEC"
                 and s.rr_ratio >= EXEC_RR_MIN
                 and "credit" in s.strategy]

        # #12 IV-HV 拦截：腿质量达标但 IV-HV<1% 的信号（tier 已降为 INTERCEPTED）
        intercepted = [s for s in all_signals
                       if s.tier == "INTERCEPTED" and "credit" in s.strategy]

        if not cs_ok:
            if intercepted:
                # 环境拦截日：有达标腿但被 IV-HV 拦，非干旱
                print(f"  ⛔ [INTERCEPTED] 环境拦截（{len(intercepted)} 个）：腿达标但 IV-HV < 1%，非干旱")
                for s in intercepted[:5]:
                    reason = s.metadata.get("intercept_reason", "")
                    print(f"      {s.name} {s.contract} 卖{s.metadata.get('sell_strike','?')}"
                          f"/{s.metadata.get('buy_strike','?')}  {reason}")
                # 卖方窗口补充
                seller_windows = []
                for contract, hv_info in iv_hv.items():
                    spread = hv_info.get("iv_est", 0) - hv_info.get("hv_20d", 0)
                    if spread >= 0.03:
                        vcode_match = re.match(r'([a-z]+)', contract)
                        if vcode_match:
                            name = VARIETIES.get(vcode_match.group(1), {}).get("name", contract)
                            seller_windows.append(f"{name}({spread*100:+.1f}%)")
                if seller_windows:
                    print(f"    卖方窗口：{', '.join(seller_windows)}，但被 IV-HV 拦截。")
            else:
                # 真·干旱
                seller_windows = []
                for contract, hv_info in iv_hv.items():
                    spread = hv_info.get("iv_est", 0) - hv_info.get("hv_20d", 0)
                    if spread >= 0.03:
                        vcode_match = re.match(r'([a-z]+)', contract)
                        if vcode_match:
                            name = VARIETIES.get(vcode_match.group(1), {}).get("name", contract)
                            seller_windows.append(f"{name}({spread*100:+.1f}%)")
                if seller_windows:
                    print(f"    卖方窗口：{', '.join(seller_windows)}，但无可执行腿组合。")
                    print(f"    系统在拦，不在漏。")
                else:
                    print(f"    今日无卖方窗口（IV-HV ≥3% 品种=0）。")
            return

        # 去重 + 排序
        seen = {}
        for s in sorted(cs_ok, key=lambda x: x.rr_ratio, reverse=True):
            key = f"{s.variety}_{s.contract}"
            if key not in seen:
                seen[key] = s
                # 注入 IV-HV + 事件标签（取品种最新健康合约，防换月污染 #16）
                from .volatility import latest_healthy_iv
                hv_info, _ = latest_healthy_iv(iv_hv, s.variety)
                if hv_info:
                    from .volatility import iv_hv_tier
                    spread, tier_str, action = iv_hv_tier(
                        hv_info.get("iv_est"), hv_info.get("hv_20d"))
                    s.metadata["_iv_hv_spread"] = spread
                    s.metadata["_iv_hv_tier"] = tier_str
                    s.metadata["_iv_hv_action"] = action
                else:
                    s.metadata["_iv_hv_spread"] = None
                    s.metadata["_iv_hv_tier"] = "⚠️无HV数据"
                    s.metadata["_iv_hv_action"] = ""
                s.metadata["_event_warning"] = s.variety in event_vcodes

        filtered = list(seen.values())
        limit = min(self.show_limit, len(filtered)) if self.show_limit > 0 else len(filtered)

        for i, s in enumerate(filtered[:limit], 1):
            inv_note = ""
            if s.metadata.get("inversion"):
                inv_msg = s.metadata.get("inversion_msg", "")
                inv_note = f" ⚠️倒挂·法则①禁卖方({inv_msg})"
            warn = " ⚠️有事件" if s.metadata.get("_event_warning") else ""
            nr_note = ""
            if s.variety in weekly_scan_map:
                nr_note = f" 🔮[非例行: {weekly_scan_map[s.variety][0][:20]}]"

            tier_color = s.metadata.get("tier_color")
            if tier_color == "green":
                tier_icon = "🟢"
            elif tier_color == "yellow":
                tier_icon = "🟡"
            elif tier_color == "red":
                tier_icon = "🔴"
            else:
                # fallback: OTM inversion 等策略不设 tier_color
                tier_icon = {"EXEC": "🟢", "PAPER": "🟡", "OBSERVE": "⚪"}.get(s.tier, "⚪")
            opt_type = s.metadata.get("direction", "?")
            opt_type_short = "C" if opt_type == "call" else "P"

            spread_val = s.metadata.get("_iv_hv_spread")
            spread_str = f"IV-HV {spread_val*100:+.1f}% " if spread_val is not None else ""
            tier_label = s.metadata.get("_iv_hv_tier", "?")
            action_label = s.metadata.get("_iv_hv_action", "")
            tier_str = (f"[{spread_str}| {tier_label} · {action_label}]"
                        if action_label else f"[{tier_label}]")

            sell_strike = s.metadata.get("sell_strike", "?")
            buy_strike = s.metadata.get("buy_strike", "?")
            net_premium = s.metadata.get("net_premium", "?")
            sell_bid = s.metadata.get("sell_bid", "?")
            buy_ask = s.metadata.get("buy_ask", "?")

            print(f"    [{i}] {tier_icon} {s.name} {s.contract} "
                  f"卖{opt_type_short}{sell_strike}/{buy_strike}  "
                  f"净收 ¥{net_premium}  卖bid ¥{sell_bid} 买ask ¥{buy_ask}  "
                  f"盈亏比 {s.rr_ratio}:1  OTM {s.metadata.get('otm_pct','?')}%"
                  f"{inv_note}{warn}{nr_note}")
            print(f"        {tier_str}")

            tp = round(s.max_profit * 0.5, 0)
            print(f"        止盈 ¥{tp:.0f}/手  止损预警: {opt_type_short}{buy_strike}")

        # #12 拦截信号（EXEC 有信号时也显示，不埋没）
        if intercepted:
            print(f"\n  ⛔ [INTERCEPTED] IV-HV<1% 拦截（{len(intercepted)} 个，非干旱）：")
            for s in intercepted[:5]:
                reason = s.metadata.get("intercept_reason", "")
                opt_t = "C" if s.metadata.get("direction") == "call" else "P"
                print(f"      {s.name} {s.contract} 卖{opt_t}{s.metadata.get('sell_strike','?')}"
                      f"/{s.metadata.get('buy_strike','?')}  {reason}")

    # ── NEAR 近失 ──

    def print_near_section(self, all_signals: List[Signal]):
        """打印接近 EXEC 但盈亏比不足的信号"""
        near_miss = [s for s in all_signals
                     if s.tier == "EXEC"
                     and RR_MIN <= s.rr_ratio < EXEC_RR_MIN
                     and "credit" in s.strategy]

        if not near_miss:
            return

        print(f"\n  🟠 [NEAR] 接近 EXEC 但盈亏比不足（{RR_MIN}≤rr<{EXEC_RR_MIN}）：")
        for s in sorted(near_miss, key=lambda x: x.rr_ratio, reverse=True)[:3]:
            opt_t = "C" if s.metadata.get("direction") == "call" else "P"
            print(f"    {s.name} {s.contract} "
                  f"卖{opt_t}{s.metadata.get('sell_strike','?')}/"
                  f"{s.metadata.get('buy_strike','?')}  "
                  f"净收 ¥{s.metadata.get('net_premium','?')}  "
                  f"rr={s.rr_ratio}  OTM {s.metadata.get('otm_pct','?')}%")

    # ── PAPER 买方 ──

    def print_buyer_sections(self, all_signals: List[Signal],
                             weekly_scan_map: dict):
        """打印所有 PAPER 买方信号"""
        # 分三类
        spreads = [s for s in all_signals if "spread" in s.strategy and s.tier == "PAPER"]
        straddles = [s for s in all_signals
                     if s.strategy in ("long_straddle", "long_strangle")
                     and s.tier == "PAPER"]
        single_events = [s for s in all_signals
                         if s.strategy in ("buy_call_event", "buy_put_event")
                         and s.tier == "PAPER"]
        single_trends = [s for s in all_signals
                         if s.strategy in ("buy_call_trend", "buy_put_trend")
                         and s.tier == "PAPER"]

        # 买方价差
        if spreads:
            print(f"\n  🟡 [PAPER] 买方价差（2腿·封顶亏损）— 纸面跟踪")
            seen = {}
            for s in sorted(spreads, key=lambda x: (
                x.metadata.get("color") == "green", x.rr_ratio), reverse=True):
                buy_s = s.metadata.get('buy_strike', s.metadata.get('strike', '?'))
                sell_s = s.metadata.get('sell_strike', '?')
                key = f"{s.variety}_{s.contract}_{s.strategy}_{buy_s}_{sell_s}"
                if key not in seen:
                    seen[key] = s
            for s in list(seen.values())[:self.show_limit or 5]:
                color = "🟢" if s.metadata.get("color") == "green" else "🟡"
                opt_t = "C" if "call" in s.strategy else "P"
                ev_str = f"D-{s.metadata.get('event_days','?')}" if s.metadata.get("event_days") else ""
                buyer_nr = ""
                if s.variety in weekly_scan_map:
                    buyer_nr = f" 🔮[催化: {weekly_scan_map[s.variety][0][:15]}]"
                print(f"    {color} {s.name} {s.contract} "
                      f"买{opt_t}{s.metadata.get('buy_strike','?')}/"
                      f"卖{opt_t}{s.metadata.get('sell_strike','?')}  "
                      f"成本≈¥{s.metadata.get('net_debit','?')}  "
                      f"盈亏比 {s.rr_ratio}:1  "
                      f"ScP{s.metadata.get('iv_percentile','?')}{_cl_str(s)}  "
                      f"{ev_str}{buyer_nr}")
            print(f"    ⚠️ 共 {len(seen)} 个。不执行，仅纸面。")
        else:
            print(f"\n  🟡 [PAPER] 买方价差（2腿·封顶亏损）— 今日无")

        # 跨式/宽跨式
        if straddles:
            print(f"\n  🟡 [PAPER] 买方跨式/宽跨式（2腿·赌波动）— 纸面跟踪")
            for s in straddles[:self.show_limit or 3]:
                color = "🟢" if s.metadata.get("color") == "green" else "🟡"
                ev_str = f"D-{s.metadata.get('event_days','?')}" if s.metadata.get("event_days") else ""
                if s.metadata.get("call_strike") is not None:
                    legs = f"C{s.metadata.get('call_strike')}/P{s.metadata.get('put_strike')}"
                else:
                    legs = f"ATM {s.metadata.get('strike','?')}"
                em = s.metadata.get("expected_move_pct", "?")
                print(f"    {color} {s.name} {s.contract} {s.strategy} {legs}  "
                      f"成本≈¥{s.metadata.get('net_cost','?')}  "
                      f"预期波动 ±{em}%  {ev_str}")
            print(f"    ⚠️ 共 {len(straddles)} 个。不执行，仅纸面。")
        else:
            print(f"\n  🟡 [PAPER] 买方跨式/宽跨式（2腿·赌波动）— 今日无（缺IV<30%+事件）")

        # 单腿·事件
        if single_events:
            print(f"\n  🟡 [PAPER] 买单腿·事件触发 — 纸面跟踪")
            for s in single_events[:5]:
                color = "🟢" if s.metadata.get("color") == "green" else "🟡"
                opt_t = "Call" if "call" in s.strategy else "Put"
                print(f"    {color} {s.name} 买{opt_t} {s.metadata.get('strike','?')}  "
                      f"OTM {s.metadata.get('otm_pct','?')}%  "
                      f"权利金≈¥{s.metadata.get('cost','?')}  "
                      f"ScP{s.metadata.get('iv_percentile','?')}{_cl_str(s)}")
            print(f"    ⚠️ {len(single_events)} 个事件触发。不执行，仅纸面。")
        else:
            print(f"\n  🟡 [PAPER] 买单腿·事件触发 — 今日无（日历无D-2~D-7事件）")

        # 单腿·趋势
        if single_trends:
            print(f"\n  🟡 [PAPER] 买单腿·趋势触发 — 纸面跟踪")
            for s in single_trends[:5]:
                color = "🟢" if s.metadata.get("color") == "green" else "🟡"
                opt_t = "Call" if "call" in s.strategy else "Put"
                print(f"    {color} {s.name} 买{opt_t} {s.metadata.get('strike','?')}  "
                      f"OTM {s.metadata.get('otm_pct','?')}%  "
                      f"权利金≈¥{s.metadata.get('cost','?')}  "
                      f"{s.metadata.get('trigger','')}  "
                      f"ScP{s.metadata.get('iv_percentile','?')}{_cl_str(s)}")
            print(f"    ⚠️ {len(single_trends)} 个趋势触发。不执行，仅纸面。")

    # ── 汇总行 ──

    def print_summary(self, exec_count: int, paper_count: int,
                      observe_count: int, iv_hv: dict,
                      intercepted_count: int = 0):
        """打印汇总行（#12：有被 IV-HV 拦截的信号 → 环境拦截日，非干旱）"""
        print(f"\n  {'─'*70}")
        intercept_note = f" + {intercepted_count} 拦截" if intercepted_count else ""
        print(f"  📊 {exec_count} 可执行 + {paper_count} 纸面 + {observe_count} 观察"
              f"{intercept_note} + 6 未扫描")
        if exec_count == 0:
            if intercepted_count > 0:
                # 环境拦截日：有达标腿但被 IV-HV 拦 → 非干旱，不触发无信号日操作
                print(f"  🌵 环境拦截日：{intercepted_count} 个腿达标但 IV-HV<1%。")
                print(f"  📖 非干旱——不计入干旱天数（按 monitoring-rules.md 正常规程）。")
            elif paper_count > 0:
                print(f"  📋 买方/单腿纸面窗口已标出（共 {paper_count} 个），不执行仅跟踪。")
                print(f"  📖 无信号日操作规程 → monitoring-rules.md「无信号日操作规程」")
            else:
                print(f"  📖 无信号日操作规程 → monitoring-rules.md「无信号日操作规程」")
        print(f"  {'═'*70}\n")

    # ── IV-HV 全品种面板 ──

    @staticmethod
    def print_iv_hv_panel(panel_data: list):
        """打印全品种 IV-HV 一览表"""
        if not panel_data:
            return

        from .config import VARIETIES

        print(f"  ┌─ 📊 全品种 IV-HV 一览（iv_history 最新）")
        print(f"  │ {'品种':6s}  {'IV-HV':>8s}  {'5dΔ':>7s}  方向    标注      IV数据点")
        for row in panel_data:
            vc = row["variety"]
            name = VARIETIES.get(vc, {}).get("name", vc)
            spread = row.get("iv_hv_spread")
            sp_str = f"{spread*100:+.1f}%" if spread is not None else "N/A"
            d5d = row.get("delta_5d")
            d5d_str = f"{d5d*100:+.1f}pp" if d5d is not None else "N/A"
            direction = row.get("direction", "—")
            notes = row.get("notes", "")
            point = row.get("iv_point") or "—"
            print(f"  │ {name:6s}  {sp_str:>8s}  {d5d_str:>7s}      {direction}         {notes:<6s}  @{point}")
        print(f"  └─ 5dΔ = IV 近 5 日变动。数据点 = 该品种最新健康 IV 的日期时间（旧日期/⚠️失真 = 盘前快照，决策前 9:15 重跑）\n")

    # ── 保存日志 ──

    def save_logs(self, output_text: str):
        """保存 Markdown + JSON 日志"""
        log_dir = Path(__file__).parent.parent.parent / "data" / "scanner_log"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()

        # Markdown
        md_path = log_dir / f"{today}.md"
        md_path.write_text(output_text, encoding="utf-8")
        print(f"  📁 已存: {md_path}")

    def save_json(self, all_signals: List[Signal],
                  chains: Dict[str, Optional[OptionChain]]):
        """保存 JSON 格式（供回测/分析用）"""
        log_dir = Path(__file__).parent.parent.parent / "data" / "scanner_log"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()

        signals_json = []
        for s in all_signals:
            signals_json.append({
                "strategy": s.strategy,
                "variety": s.variety,
                "name": s.name,
                "contract": s.contract,
                "tier": s.tier,
                "rr_ratio": s.rr_ratio,
                "max_profit": s.max_profit,
                "max_loss": s.max_loss,
                "greeks": s.greeks,
                "edge_score": s.edge_score,
                "liquidity_score": s.liquidity_score,
                "metadata": {k: v for k, v in s.metadata.items()
                            if not k.startswith("_")},
            })

        json_path = log_dir / f"{today}.json"
        json_path.write_text(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "chains": {vc: {"contract": c.contract, "futures": c.futures_price, "dte": c.dte}
                      for vc, c in chains.items() if c},
            "signals": signals_json,
            "summary": {
                "exec": len([s for s in all_signals if s.tier == "EXEC"]),
                "paper": len([s for s in all_signals if s.tier == "PAPER"]),
                "observe": len([s for s in all_signals if s.tier == "OBSERVE"]),
            },
        }, ensure_ascii=False, indent=2), encoding="utf-8")
