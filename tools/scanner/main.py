#!/usr/bin/env python3
"""分层量化引擎 — 主入口

用法：
  python3 -m tools.scanner.main                      # 完整扫描
  python3 -m tools.scanner.main --capital 20000      # 含资金分配
  python3 -m tools.scanner.main --quick               # 快速版
  python3 -m tools.scanner.main --skip-otm            # 跳过虚值倒挂
  python3 -m tools.scanner.main --buyer               # 买方模式
"""

import sys
import os
import io
import argparse
import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional

# 确保 tools/ 在 path 中
_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from .models import OptionChain, Signal, ScanContext
from .config import (
    VARIETIES, MAX_SAME_DIRECTION, MAX_PORTFOLIO_DELTA_ABS,
    EVENT_PRICED_IV_PCT, EVENT_PRICED_DAYS, EVENT_SPREAD_MAX,
)
from .data_source import AKShareSource, CachedSource
from .volatility import (
    load_iv_history, load_all_iv_rows, iv_percentile,
    iv_hv_tier, _extract_variety,
)
from .events import EventEngine
from .strategies.credit_spread import CreditSpreadStrategy
from .strategies.otm_inversion import OTMInversionStrategy
from .strategies.buyer import BuyerStrategy
from .output import Reporter


def _build_iv_hv_panel(iv_hist: dict, iv_hist_rows: list, target: list) -> list:
    """构建全品种 IV-HV 面板数据。

    Returns: [{variety, iv_hv_spread, delta_5d, direction, notes}]
    """
    from .volatility import _extract_variety

    # 按品种算 5 日 IV 变动
    recent_by_variety = {}
    for r in sorted(iv_hist_rows, key=lambda x: x.get("date", "") + x.get("time", "")):
        v = r.get("variety") or _extract_variety(r.get("contract", ""))
        if v:
            recent_by_variety.setdefault(v, []).append(r.get("iv_est", 0))

    delta_5d_map = {}
    for v, ivs in recent_by_variety.items():
        if len(ivs) >= 2:
            # 最近一条 vs 5 条前（或最早）
            latest = ivs[-1]
            prev_idx = max(0, len(ivs) - 6)
            prev = ivs[prev_idx]
            delta_5d_map[v] = latest - prev
        else:
            delta_5d_map[v] = None

    panel = []
    for vcode in target:
        # 找该品种最新合约的 HV 数据
        hv_info = None
        for contract, info in iv_hist.items():
            v = _extract_variety(contract)
            if v == vcode:
                hv_info = info
                break

        spread = None
        hv20 = None
        if hv_info:
            iv_est = hv_info.get("iv_est")
            hv20 = hv_info.get("hv_20d")
            if iv_est and hv20 and hv20 > 0:
                spread = iv_est - hv20

        d5d = delta_5d_map.get(vcode)
        if d5d is not None and d5d > 0.005:
            direction = "→"
        elif d5d is not None and d5d < -0.005:
            direction = "←"
        else:
            direction = "—"

        notes = ""
        if spread is not None:
            if spread < -0.03:
                notes = "🔻折价"
            elif spread > 0.03:
                notes = "🔺溢价"

        panel.append({
            "variety": vcode,
            "iv_hv_spread": spread,
            "hv_20d": hv20,
            "delta_5d": d5d,
            "direction": direction,
            "notes": notes,
        })

    return panel


def fetch_futures_5d_change(vcode: str, source) -> Optional[float]:
    """拉取 5 日涨跌幅"""
    try:
        daily = source.fetch_futures_daily(vcode, 10)
        if daily is not None and len(daily) >= 6:
            daily = daily.sort_values("date")
            closes = daily["close"].astype(float)
            return (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100
    except Exception:
        pass
    return None


def load_weekly_scan() -> tuple:
    """加载每周非例行扫描 → (events_list, variety_map)"""
    scan_path = os.path.join(_TOOLS_DIR, "..", "data", "weekly_event_scan.json")
    events = []
    vmap = {}
    try:
        with open(scan_path) as f:
            data = json.load(f)
        today = date.today().isoformat()
        if data.get("valid_until", "") >= today:
            events = data.get("events", [])
    except Exception:
        pass

    ag_varieties = {"m", "c", "cf", "sr", "au"}
    for ev in events:
        vcode = ev.get("品种码", "")
        if vcode == "all_ag":
            for ag_code in ag_varieties:
                vmap.setdefault(ag_code, []).append(
                    ev.get("催化", "") if ev.get("买方窗口")
                    else ev.get("卖方预警", ev.get("催化", "")))
        elif vcode:
            vmap.setdefault(vcode, []).append(
                ev.get("催化", "") if ev.get("买方窗口")
                else ev.get("卖方预警", ev.get("催化", "")))

    return events, vmap


def check_portfolio_risk(signals: List[Signal], capital: float) -> List[str]:
    """简易组合风控：同方向 ≤2，组合 Delta ≤0.5"""
    warnings = []
    exec_signals = [s for s in signals if s.tier == "EXEC"]

    # 同方向计数
    put_signals = [s for s in exec_signals
                   if s.metadata.get("direction") == "put"]
    call_signals = [s for s in exec_signals
                    if s.metadata.get("direction") == "call"]

    if len(put_signals) > MAX_SAME_DIRECTION:
        warnings.append(
            f"⚠️ 组合风控: {len(put_signals)} 个 Put 卖方信号，超限 {MAX_SAME_DIRECTION}")
    if len(call_signals) > MAX_SAME_DIRECTION:
        warnings.append(
            f"⚠️ 组合风控: {len(call_signals)} 个 Call 卖方信号，超限 {MAX_SAME_DIRECTION}")

    # 组合 Delta（先求和再取绝对值——方向对冲应抵消）
    total_delta = sum(s.greeks.get("delta", 0) for s in exec_signals)
    if abs(total_delta) > MAX_PORTFOLIO_DELTA_ABS:
        warnings.append(
            f"⚠️ 组合风控: 总 Delta {total_delta:.3f} > {MAX_PORTFOLIO_DELTA_ABS}")

    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="分层扫描引擎: 虚值倒挂 + 信用价差/买方机会 + 事件 + IV 四合一")
    parser.add_argument("--capital", type=float, default=20000, help="本金(元)")
    parser.add_argument("--quick", action="store_true", help="快速模式")
    parser.add_argument("--variety", type=str, default="all", help="指定品种")
    parser.add_argument("--skip-otm", action="store_true", help="跳过虚值倒挂")
    parser.add_argument("--skip-cs", action="store_true", help="跳过信用价差")
    parser.add_argument("--buyer", action="store_true", help="买方模式")
    parser.add_argument("--show", type=int, default=10, help="信号详情数")
    parser.add_argument("--raw", action="store_true", help="不过滤")
    args = parser.parse_args()

    if args.variety == "all":
        target = list(VARIETIES.keys())
    else:
        target = [v.strip() for v in args.variety.split(",")]

    # ── 数据源 ──
    source = CachedSource(AKShareSource(), ttl_seconds=300)

    # ── 拉取全品种链 ──
    chains: Dict[str, Optional[OptionChain]] = {}
    for vcode in target:
        chain = source.fetch_chain(vcode)
        chains[vcode] = chain  # None if failed

    # ── 事件引擎 ──
    events_engine = EventEngine(days=14, varieties=target)
    event_vcodes = events_engine.get_event_vcodes(max_days=7)

    # ── IV 历史 + 非例行扫描（全程复用）──
    iv_hist_rows = load_all_iv_rows()
    iv_hist = load_iv_history()
    weekly_scan_events, weekly_map = load_weekly_scan()

    # ── 预计算 ScanContext ──
    contexts: Dict[str, ScanContext] = {}
    for vcode in target:
        chain = chains.get(vcode)
        if chain is None:
            contexts[vcode] = ScanContext(capital=args.capital)
            continue

        # 用 ATM 估算当前 IV
        iv_est = None
        try:
            atm_idx = (chain.puts["strike"] - chain.futures_price).abs().idxmin()
            p_bid = float(chain.puts.loc[atm_idx, "bid"])
            p_ask = float(chain.puts.loc[atm_idx, "ask"])
            strike_target = chain.puts.loc[atm_idx, "strike"]
            c_row = chain.calls.loc[(chain.calls["strike"] - strike_target).abs() < 0.01]
            if not c_row.empty:
                c_bid = float(c_row.iloc[0]["bid"])
                c_ask = float(c_row.iloc[0]["ask"])
                from .bsm import estimate_atm_iv
                iv_est = estimate_atm_iv(chain.futures_price, p_bid, p_ask, c_bid, c_ask, chain.dte)
        except Exception:
            pass

        # IV 分位（DTE 分组）
        iv_pct, iv_days = iv_percentile(
            iv_est or 0.20, chain.dte, chain.contract, iv_hist_rows)

        # HV
        hv_info = iv_hist.get(chain.contract, {})
        hv20 = hv_info.get("hv_20d")

        # 5日趋势
        change_5d = fetch_futures_5d_change(vcode, source)

        # 事件定价 shortcut
        variety_events = events_engine.for_variety(vcode, chain.name)
        event_priced = EventEngine.is_event_priced(
            iv_pct, variety_events, EVENT_PRICED_IV_PCT, EVENT_PRICED_DAYS)

        contexts[vcode] = ScanContext(
            events=variety_events,
            iv_percentile=iv_pct,
            iv_percentile_days=iv_days,
            change_5d=change_5d,
            hv_20d=hv20,
            iv_est=iv_est,
            weekly_scan_warnings=weekly_map.get(vcode, []),
            capital=args.capital,
            event_priced=event_priced,
        )

    # ── 策略扫描 ──
    all_signals: List[Signal] = []

    # 虚值倒挂
    if not args.skip_otm:
        otm_strategy = OTMInversionStrategy()
        for vcode in target:
            chain = chains.get(vcode)
            if chain is None:
                continue
            ctx = contexts.get(vcode, ScanContext(capital=args.capital))
            signals = otm_strategy.scan(chain, ctx)
            all_signals.extend(signals)

    # 信用价差（卖方）
    if not args.skip_cs:
        cs_strategy = CreditSpreadStrategy()
        for vcode in target:
            chain = chains.get(vcode)
            if chain is None:
                continue
            ctx = contexts.get(vcode, ScanContext(capital=args.capital))
            signals = cs_strategy.scan(chain, ctx)
            all_signals.extend(signals)

    # 买方
    buyer_strategy = BuyerStrategy(
        event_engine=events_engine, iv_history_rows=iv_hist_rows)
    for vcode in target:
        chain = chains.get(vcode)
        if chain is None:
            continue
        ctx = contexts.get(vcode, ScanContext(capital=args.capital))
        signals = buyer_strategy.scan(chain, ctx)
        all_signals.extend(signals)

    # ── 组合风控 ──
    risk_warnings = check_portfolio_risk(all_signals, args.capital)

    # ── 注入 IV Collector 分位（DTE 分组）──
    from .bsm import estimate_atm_iv
    for s in all_signals:
        chain = chains.get(s.variety)
        pct, days = None, 0
        if chain is not None and not chain.puts.empty and not chain.calls.empty:
            try:
                atm_idx = (chain.puts["strike"] - chain.futures_price).abs().idxmin()
                p_row = chain.puts.loc[atm_idx]
                strike_target = p_row["strike"]
                c_rows = chain.calls.loc[(chain.calls["strike"] - strike_target).abs() < 0.01]
                if not c_rows.empty:
                    current_iv = estimate_atm_iv(
                        chain.futures_price,
                        float(p_row["bid"]), float(p_row["ask"]),
                        float(c_rows.iloc[0]["bid"]), float(c_rows.iloc[0]["ask"]),
                        chain.dte,
                    )
                    if current_iv and current_iv > 0:
                        pct, days = iv_percentile(
                            current_iv, chain.dte, s.contract, iv_hist_rows)
            except Exception:
                pass
        s.metadata["_cl_pct"] = pct
        s.metadata["_cl_days"] = days

    # ── 输出 ──
    reporter = Reporter(capital=args.capital, show_limit=args.show)

    reporter.print_header()
    reporter.print_chain_status(chains)

    # 事件日历
    print(f"\n  ┌─ 事件日历")
    ongoing = events_engine.get_ongoing_events()
    for ev in ongoing:
        tag = "[例行]" if ev.get("routine", True) else "[⚠非例行]"
        print(f"  │ 🔥🔄 {tag} {ev['title']}  [{', '.join(ev['variety_names'])}]")

    high_events = events_engine.get_high_events(14)
    for ev in high_events[:5]:
        tag = "[例行]" if ev.get("routine", True) else "[⚠非例行]"
        time_label = ""
        if ev.get("time_edt") and ev.get("time_bjt"):
            time_label = f" 🕐 {ev['time_edt']} EDT / {ev['time_bjt']} 北京"
        print(f"  │ D-{ev['days_until']:<3} 🔥 {tag} {ev['title']}  "
              f"[{', '.join(ev['variety_names'])}]{time_label}")

    medium_events = events_engine.get_medium_events(5)
    for ev in medium_events[:3]:
        tag = "[例行]" if ev.get("routine", True) else "[⚠非例行]"
        print(f"  │ D-{ev['days_until']:<3} ⚡ {tag} {ev['title']}  "
              f"[{', '.join(ev['variety_names'])}]")

    if not ongoing and not high_events and not medium_events:
        print(f"  │ 无近期高影响事件")
    print(f"  └─ 共 {len(events_engine.events)} 个事件（含 {len(ongoing)} 个持续中）")

    # 非例行扫描
    if weekly_scan_events:
        try:
            scan_path = os.path.join(_TOOLS_DIR, "..", "data", "weekly_event_scan.json")
            with open(scan_path) as f:
                raw = json.load(f)
            valid_until = raw.get("valid_until", "")
        except Exception:
            valid_until = "?"
        print(f"\n  ┌─ 🔮 本周非例行扫描（至 {valid_until}）")
        for ev in weekly_scan_events:
            vname = ev.get("品种", "?")
            vcode = ev.get("品种码", "")
            catalyst = ev.get("催化", "?")
            buyer = "✅买方窗口" if ev.get("买方窗口") else "❌买方不进"
            seller = ev.get("卖方预警", "")
            prob = ev.get("概率", "")
            # 方案B：自动附当前 IV-HV（weekly JSON 里 IV 数值随换月过时，用 iv_history 最新合约值兜底）
            cur_note = ""
            best_key, best_iv, best_hv20 = "", None, None
            for contract, info in iv_hist.items():
                if _extract_variety(contract) == vcode:
                    key = info.get("date", "") + info.get("time", "")
                    if key >= best_key:
                        best_key = key
                        best_iv = info.get("iv_est")
                        best_hv20 = info.get("hv_20d")
            if best_iv:
                cur_note = f"  [当前 IV {best_iv:.1%}"
                if best_hv20 and best_hv20 > 0:
                    cur_note += f", HV₂₀ {best_hv20:.1%}"
                cur_note += "]"
            print(f"  │ 🟡 {vname}: {catalyst}  [{buyer}] [{seller}]  概率:{prob}{cur_note}")
        print(f"  └─ 手动扫描，Scanner 仅显示上下文——不参与判据")

    # IV 采样
    if not args.quick:
        print(f"\n  ┌─ IV/流动性采样 (关键品种ATM)")
        key_varieties = [v for v in target if v in ("c", "m", "ta", "au", "rm")]
        for vcode in key_varieties[:5]:
            chain = chains.get(vcode)
            if chain is None:
                continue
            vinfo = VARIETIES.get(vcode, {})
            try:
                atm_idx = (chain.puts["strike"] - chain.futures_price).abs().idxmin()
                p_bid = float(chain.puts.loc[atm_idx, "bid"])
                p_ask = float(chain.puts.loc[atm_idx, "ask"])
                if p_bid > 0:
                    sp = round((p_ask - p_bid) / p_bid * 100, 1)
                else:
                    sp = 999
                icon = "✅" if sp < EVENT_SPREAD_MAX else ("⚠️" if sp < 20 else "❌")
                print(f"  │ {icon} {vinfo.get('name', vcode):6s}: ATM价差 {sp}%")
            except Exception as e:
                print(f"  │ ❌ {vinfo.get('name', vcode):6s}: 采样失败 ({str(e)[:30]})")
        print(f"  └─")

    # 三层信号
    print(f"\n{'═'*70}")
    print(f"  📊 三层信号汇总")
    print(f"  {'═'*70}")

    reporter.print_exec_section(
        all_signals, event_vcodes, iv_hist, weekly_map)
    reporter.print_near_section(all_signals)
    reporter.print_buyer_sections(all_signals, weekly_map)

    # OBSERVE
    observe_count = 0
    print(f"\n  ⚪ [OBSERVE] 高级策略 — 仅计数，S2 解锁")
    print(f"    铁秃鹰 · 铁蝴蝶 · 蝶式 · 比率价差 · 日历价差")
    print(f"    → 共 {observe_count} 个机会。仅计数，不做。")

    # IGNORE
    print(f"\n  🔘 [IGNORE] 未扫描（需额外数据或S2+解锁）")
    print(f"    合成期货 · 备兑Call · 品种间价差 · 对角价差 · 跨市场套利 · 期货对冲")

    # 组合风控警告
    if risk_warnings:
        print(f"\n  ⚠️ 组合风控警告：")
        for w in risk_warnings:
            print(f"    {w}")

    # 汇总
    exec_n = len([s for s in all_signals if s.tier == "EXEC" and "credit" in s.strategy])
    paper_n = len([s for s in all_signals if s.tier == "PAPER"])
    reporter.print_summary(exec_n, paper_n, observe_count, iv_hist)

    # IV-HV 全品种面板
    panel_data = _build_iv_hv_panel(iv_hist, iv_hist_rows, target)
    reporter.print_iv_hv_panel(panel_data)

    return all_signals, chains


if __name__ == "__main__":
    import io
    from pathlib import Path

    # 保存输出
    log_dir = Path(__file__).parent.parent.parent / "data" / "scanner_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    log_path = log_dir / f"{today}.md"

    buf = io.StringIO()
    orig_stdout = sys.stdout
    sys.stdout = buf

    all_signals = []
    chains = {}
    try:
        all_signals, chains = main()
    finally:
        sys.stdout = orig_stdout
        output = buf.getvalue()
        print(output, end="")

        # 保存 Markdown
        log_path.write_text(output, encoding="utf-8")
        print(f"  📁 已存: {log_path}")

        # 保存 JSON（仅当 main() 成功时）
        if all_signals or chains:
            reporter = Reporter()
            reporter.save_json(all_signals, chains)
