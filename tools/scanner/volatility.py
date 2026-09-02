"""波动率分析：IV 分位（DTE 分组）+ expected_move + HV 加载

核心修正：
- IV 分位按 DTE 分组计算（旧方案混同所有 DTE → 扭曲分位）
- expected_move 按 F×IV×√T 算百分比（旧方案 net_cost 元 → P0 bug）
- 品种提取：m2609 → m 正则映射（换月时数据连续）
"""

import csv
import math
import re
import os
from collections import defaultdict
from datetime import date
from typing import Optional, Tuple, Dict, List


def _extract_variety(contract: str) -> Optional[str]:
    """从合约代码提取品种码：'m2609' → 'm', 'au2610' → 'au', 'TA609' → 'ta'"""
    m = re.match(r'([a-zA-Z]+)', contract)
    return m.group(1).lower() if m else None


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_iv_history() -> dict:
    """读 data/iv_history.csv → {contract: {iv_est, hv_20d, hv_60d, dte, date, time}}

    返回每个合约的最新一条记录。
    """
    csv_path = os.path.join(_REPO_ROOT, "data", "iv_history.csv")
    if not os.path.exists(csv_path):
        return {}

    hist = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c = row.get("contract", "")
            if not c:
                continue
            try:
                iv = float(row.get("iv_est", 0) or 0)
                hv20 = float(row.get("hv_20d", 0) or 0)
                hv60 = float(row.get("hv_60d", 0) or 0)
                dte = int(row.get("dte", 30) or 30)
                far_iv_raw = row.get("far_iv", "")
                hist[c] = {
                    "iv_est": iv,
                    "hv_20d": hv20,
                    "hv_60d": hv60,
                    "dte": dte,
                    "date": row.get("date", ""),
                    "time": row.get("time", ""),
                    "liquidity_ok": row.get("liquidity_ok", "1"),
                    "spread_pct": row.get("spread_pct", ""),
                    "far_iv": float(far_iv_raw) if far_iv_raw not in (None, "") else None,
                    "far_contract": row.get("far_contract", ""),
                }
            except (ValueError, TypeError):
                continue
    return hist


def latest_healthy_iv(iv_hist: dict, vcode: str):
    """选某品种 date+time 最新且盘口健康的合约信息（换月防污染 #16）。

    iv_hist: load_iv_history() 结果 {contract: info}
    无健康数据时回退最新一条并返回 is_healthy=False（调用方标 ⚠️失真）。
    健康 = liquidity_ok 且 spread≤10%。
    Returns: (info_or_None, is_healthy)
    """
    best_any, best_key = None, ""
    best_ok, ok_key = None, ""
    for contract, info in iv_hist.items():
        if _extract_variety(contract) != vcode:
            continue
        key = (info.get("date", ""), info.get("time", ""))
        if best_any is None or key > best_key:
            best_any, best_key = info, key
        ok = info.get("liquidity_ok", "1") not in ("0", "False")
        try:
            sp = float(info.get("spread_pct", 0) or 0)
        except (ValueError, TypeError):
            sp = 0.0
        if ok and sp <= 10 and (best_ok is None or key > ok_key):
            best_ok, ok_key = info, key
    if best_ok is not None:
        return best_ok, True
    return best_any, False


def detect_term_structure_inversion(info: dict) -> Optional[dict]:
    """期限结构倒挂检测（法则①）：近月 IV > 远月 IV = 倒挂。

    输入：latest_healthy_iv() 返回的单品种最新健康合约 info（含 far_iv/far_contract）。
    有效性闸（9/2 立，吸取 9/1 c 坏数据教训）：
      - far_iv 缺失/空/<5%（物理不可能）→ 不判（None）
      - far_contract 无法解析月份 → 不判
    返回 None（无倒挂/数据不可判）或 {near_iv, far_iv, near_dte, msg}。
    """
    try:
        main_iv = float(info.get("iv_est") or 0)
        far_iv = info.get("far_iv")
        far_iv = float(far_iv) if far_iv is not None else 0.0
    except (ValueError, TypeError):
        return None
    if main_iv <= 0 or far_iv < 0.05:          # far_iv <5% = 坏数据不判
        return None
    far_contract = info.get("far_contract", "") or ""
    try:
        main_dte = int(info.get("dte") or 0)
    except (ValueError, TypeError):
        main_dte = 0
    if main_dte <= 0 or not far_contract:
        return None
    m = re.search(r"(\d{4})$", far_contract)   # far 合约月份 YYMM
    if not m:
        return None
    yy, mm = int(m.group(1)[:2]), int(m.group(1)[2:])
    try:
        far_dte = max((date(2000 + yy, mm, 1) - date.today()).days - 5, 5)
    except ValueError:
        return None
    # 谁 DTE 短谁是近月
    if main_dte < far_dte:                      # 主采=近月
        near_iv, far_iv_v = main_iv, far_iv
    else:                                       # far=近月（主采为远月，如 m2701 vs m2611）
        near_iv, far_iv_v = far_iv, main_iv
    if near_iv > far_iv_v:
        return {
            "near_iv": near_iv,
            "far_iv": far_iv_v,
            "near_dte": min(main_dte, far_dte),
            "msg": f"近{near_iv:.1%} > 远{far_iv_v:.1%}",
        }
    return None


def load_all_iv_rows() -> List[dict]:
    """读 iv_history.csv 全部行 → [{contract, iv_est, dte, date, ...}]"""
    csv_path = os.path.join(_REPO_ROOT, "data", "iv_history.csv")
    rows = []
    if not os.path.exists(csv_path):
        return rows
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "contract": row.get("contract", ""),
                    "variety": _extract_variety(row.get("contract", "")),
                    "iv_est": float(row.get("iv_est", 0) or 0),
                    "dte": int(row.get("dte", 30) or 30),
                    "date": row.get("date", ""),
                })
            except (ValueError, TypeError):
                continue
    return rows


def iv_percentile(current_iv: float, dte: int, contract: str,
                  history_rows: List[dict] = None,
                  min_samples: int = 10) -> Tuple[Optional[float], int]:
    """按 DTE 分组计算 IV 分位。

    Args:
        current_iv: 当前 IV（小数，如 0.25 = 25%）
        dte: 当前到期天数
        contract: 当前合约代码（用于品种映射）
        history_rows: 全量历史行列表。None 时自动加载。
        min_samples: 最少样本数，不足返回 (None, n)

    Returns:
        (percentile: 0-100 or None, sample_count: int)
    """
    if current_iv <= 0:
        return None, 0

    if history_rows is None:
        history_rows = load_all_iv_rows()

    variety = _extract_variety(contract)
    if not variety:
        return None, 0

    # DTE 分组：当前 DTE ± 40%
    dte_lo = int(dte * 0.6)
    dte_hi = int(dte * 1.4)

    # 同品种 + DTE 窗口
    subset = [
        r for r in history_rows
        if r.get("variety") == variety
        and dte_lo <= r.get("dte", 0) <= dte_hi
        and r.get("iv_est", 0) > 0
    ]

    n = len(subset)
    if n < min_samples:
        return None, n

    ivs = [r["iv_est"] for r in subset]
    below = sum(1 for v in ivs if v < current_iv)
    pct = round(below / n * 100)
    return pct, n


def expected_move_pct(futures_price: float, iv: float, dte: int) -> float:
    """预期波动（1σ，百分比）。

    修正旧方案 expected_move = net_cost（元）的错误。
    公式：F × IV × √(DTE/365)

    Args:
        futures_price: 标的价格
        iv: 隐含波动率（小数）
        dte: 到期天数

    Returns:
        1σ 预期波动百分比（如 2.5 = ±2.5%）
    """
    if futures_price <= 0 or iv <= 0 or dte <= 0:
        return 0.0
    return round(iv * math.sqrt(dte / 365.0) * 100, 2)


def expected_move_price(futures_price: float, iv: float, dte: int) -> float:
    """预期波动（1σ，价格单位）。

    Returns:
        预期波动点数
    """
    if futures_price <= 0 or iv <= 0 or dte <= 0:
        return 0.0
    return round(futures_price * iv * math.sqrt(dte / 365.0), 2)


def iv_hv_tier(iv_est: Optional[float], hv_20d: Optional[float]
               ) -> Tuple[Optional[float], str, str]:
    """IV-HV 价差分层。

    Returns:
        (spread_float, tier_str, action_str)
    """
    if iv_est is None or hv_20d is None or hv_20d == 0:
        return None, "⚠️无HV数据", ""

    spread = iv_est - hv_20d

    if spread >= 0.05:
        return spread, "≥5%", "重仓/裸卖"
    elif spread >= 0.03:
        return spread, "3-5%", "正常仓位"
    elif spread >= 0.01:
        return spread, "1-3%", "减半仓位"
    elif spread >= 0:
        return spread, "<1%", "不执行"
    else:
        return spread, "<0% · 折价", "不执行"


def hv_trend(contract: str, history_rows: List[dict] = None,
             window: int = 5) -> Optional[float]:
    """近 N 条 HV 趋势（斜率，用于 IV-HV 面板 5dΔ）。"""
    if history_rows is None:
        history_rows = load_all_iv_rows()

    variety = _extract_variety(contract)
    if not variety:
        return None

    subset = [r for r in history_rows if r.get("variety") == variety and r.get("iv_est", 0) > 0]
    if len(subset) < window:
        return None

    # 取最后 window 条和 window 天前的 IV
    recent = subset[-1].get("iv_est", 0)
    earlier = subset[-min(window, len(subset))].get("iv_est", 0)
    return (recent - earlier) * 100  # 百分点
