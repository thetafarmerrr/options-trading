"""Black-Scholes-Merton 定价 + Greeks + IV 反解

纯函数，零外部依赖（仅 math）。Newton-Raphson IV 反解，
初值用 ATM 跨式近似（非硬编码 0.2），商品期权高 IV 场景收敛更快。
"""

import math
from typing import Optional


def _norm_cdf(x: float) -> float:
    """标准正态 CDF — erf 实现"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """标准正态 PDF"""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """BS d1"""
    if sigma <= 0 or T <= 0:
        return 0.0
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))


def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """BS d2"""
    d1_val = d1(S, K, T, r, sigma)
    return d1_val - sigma * math.sqrt(T)


# ── 定价 ──

def price(S: float, K: float, T: float, r: float, sigma: float,
          option_type: str) -> float:
    """BSM 期权价格"""
    if T <= 0:
        # 到期：仅内在价值
        if option_type.upper() == "C":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)

    d1_val = d1(S, K, T, r, sigma)
    d2_val = d2(S, K, T, r, sigma)

    if option_type.upper() == "C":
        return S * _norm_cdf(d1_val) - K * math.exp(-r * T) * _norm_cdf(d2_val)
    else:
        return K * math.exp(-r * T) * _norm_cdf(-d2_val) - S * _norm_cdf(-d1_val)


# ── Greeks ──

def delta(S: float, K: float, T: float, r: float, sigma: float,
          option_type: str) -> float:
    """BSM Delta — Call: N(d1), Put: N(d1)-1"""
    if T <= 0:
        if option_type.upper() == "C":
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0
    d1_val = d1(S, K, T, r, sigma)
    if option_type.upper() == "C":
        return _norm_cdf(d1_val)
    else:
        return _norm_cdf(d1_val) - 1.0


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """BSM Gamma"""
    if sigma <= 0 or T <= 0 or S <= 0:
        return 0.0
    d1_val = d1(S, K, T, r, sigma)
    return _norm_pdf(d1_val) / (S * sigma * math.sqrt(T))


def theta(S: float, K: float, T: float, r: float, sigma: float,
          option_type: str) -> float:
    """BSM Theta（每天的时间衰减）"""
    if T <= 0:
        return 0.0
    d1_val = d1(S, K, T, r, sigma)
    d2_val = d2(S, K, T, r, sigma)
    term1 = -(S * _norm_pdf(d1_val) * sigma) / (2.0 * math.sqrt(T))
    if option_type.upper() == "C":
        term2 = -r * K * math.exp(-r * T) * _norm_cdf(d2_val)
    else:
        term2 = r * K * math.exp(-r * T) * _norm_cdf(-d2_val)
    return (term1 + term2) / 365.0  # 每天


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """BSM Vega（每 1% IV 变动）"""
    if T <= 0 or S <= 0:
        return 0.0
    d1_val = d1(S, K, T, r, sigma)
    return S * _norm_pdf(d1_val) * math.sqrt(T) / 100.0


# ── IV 反解（Newton-Raphson）──

def iv(market_price: float, S: float, K: float, T: float, r: float,
       option_type: str, iv_initial: Optional[float] = None,
       max_iter: int = 20, tol: float = 1e-6) -> Optional[float]:
    """Newton-Raphson IV 反解。

    Args:
        market_price: 市场价格
        S, K, T, r: 标的价格、行权价、到期时间（年）、无风险利率
        option_type: "C" 或 "P"
        iv_initial: 初值。None 时自动用 straddle 估算（推荐传入）
        max_iter: 最大迭代次数
        tol: 收敛容差

    Returns:
        IV（小数，如 0.25 = 25%），或 None（不收敛）
    """
    if market_price <= 0 or T <= 0:
        return None

    # 内在价值边界：期权价格不能低于内在价值
    intrinsic = max(0.0, S - K) if option_type.upper() == "C" else max(0.0, K - S)
    if market_price <= intrinsic:
        return 0.01  # 几乎无时间价值

    # 初值：建议调用方传 ATM 跨式估算，这里用 fallback
    sigma = iv_initial if iv_initial and 0.01 < iv_initial < 5.0 else 0.25

    for _ in range(max_iter):
        p = price(S, K, T, r, sigma, option_type)
        v = vega(S, K, T, r, sigma) * 100.0  # vega 返回每 1%，转回原始单位
        if v <= 0:
            # Vega 太小 —— 用二分 fallback
            break

        diff = p - market_price
        if abs(diff) < tol:
            return round(sigma, 6)

        # Newton step
        sigma_new = sigma - diff / v
        # 边界保护：IV ∈ [0.1%, 500%]
        sigma_new = max(0.001, min(5.0, sigma_new))

        if abs(sigma_new - sigma) < tol:
            return round(sigma_new, 6)

        sigma = sigma_new

    # Newton 失败 → 简单二分 fallback（确保收敛）
    lo, hi = 0.001, 5.0
    for _ in range(30):
        mid = (lo + hi) / 2.0
        p = price(S, K, T, r, mid, option_type)
        if abs(p - market_price) < tol:
            return round(mid, 6)
        if p > market_price:
            hi = mid
        else:
            lo = mid

    return round((lo + hi) / 2.0, 6)


def estimate_atm_iv(S: float, p_bid: float, p_ask: float,
                    c_bid: float, c_ask: float, dte: int) -> Optional[float]:
    """用 ATM 跨式成本估算 IV（商品期权经验公式）

    返回 IV 小数（如 0.25 = 25%），用于 bsm_iv 的初值。
    与 _ak_data.estimate_iv_from_chain 的公式一致。
    """
    if S <= 0 or dte <= 0:
        return None
    straddle = (p_bid + p_ask + c_bid + c_ask) / 2.0
    if straddle <= 0:
        return None
    T = max(dte / 365.0, 1.0 / 365.0)
    iv = straddle / (0.8 * S * math.sqrt(T))
    return iv if 0.01 < iv < 5.0 else None
