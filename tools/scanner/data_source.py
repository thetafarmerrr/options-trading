"""数据源层：抽象 + 缓存 + 校验

包装 tools/_ak_data.py，不改原有逻辑。
加标准化校验 + 垂直价差无套利边界检查。
"""

import os
import sys
import math
import re
from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
import pandas as pd

# 确保能 import 同级的 _ak_data
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.dirname(_SCRIPT_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from _ak_data import (fetch_option_chain as _ak_fetch_chain,
                       estimate_iv_from_chain as _ak_est_iv,
                       fetch_futures_daily as _ak_futures_daily,
                       pick_best_contract as _ak_pick_contract)

from .models import OptionChain
from .config import VARIETIES, MAX_SPREAD_PCT


class DataSource(ABC):
    """数据源抽象基类"""

    @abstractmethod
    def fetch_chain(self, vcode: str) -> Optional[OptionChain]:
        """拉取单个品种期权链 → OptionChain 或 None"""
        ...

    @abstractmethod
    def fetch_futures_daily(self, vcode: str, days: int = 10) -> Optional[pd.DataFrame]:
        """拉取期货日线"""
        ...


class AKShareSource(DataSource):
    """akshare 数据源 — 包装 _ak_data 函数"""

    AK_SYMBOLS = {
        "沪金": "黄金期权", "铁矿石": "铁矿石期权", "橡胶": "橡胶期权"
    }

    def fetch_chain(self, vcode: str) -> Optional[OptionChain]:
        """拉取期权链 → OptionChain，或 None（失败时）"""
        if vcode not in VARIETIES:
            print(f"     ⚠️ 未知品种 {vcode}")
            return None

        vinfo = VARIETIES[vcode]
        vname = vinfo["name"]
        symbol = self.AK_SYMBOLS.get(vname, vname + "期权")

        try:
            contract, df, futures_price = _ak_fetch_chain(vcode, symbol)

            if df is None or df.empty:
                return None

            # ── 标准化校验 ──
            df = self._normalize(df, futures_price)

            # ── 无套利边界检查 ──
            block_errors, warnings = self._check_arbitrage(df, futures_price)
            for w in warnings:
                print(f"     {w}")
            if block_errors:
                for err in block_errors[:3]:
                    print(f"     ⚠️ 无套利【拦截】: {vname} {contract} {err}")
                return None  # ATM 附近垂直价差倒挂 → 数据不可信

            # ── DTE 计算 ──
            dte = 30
            try:
                m = re.search(r'(\d{4})$', contract)
                if m:
                    yy, mm = int(m.group(1)[:2]), int(m.group(1)[2:])
                    expiry = datetime(2000 + yy, mm, 1)
                    dte = max((expiry - datetime.now()).days - 5, 5)
            except Exception:
                pass

            # ── 分离 Put/Call ──
            put_cols = [c for c in df.columns if c.startswith("p_")]
            call_cols = [c for c in df.columns if c.startswith("c_") and c != "contract"]
            common_cols = [c for c in df.columns if c in ("strike",) or c not in put_cols and c not in call_cols]

            # 构建 puts/calls DataFrame
            puts = df[["strike"] + [c for c in put_cols if c in df.columns]].copy()
            calls = df[["strike"] + [c for c in call_cols if c in df.columns]].copy()

            # 重命名去掉前缀，统一为 bid/ask/last/volume/oi
            def _rename_side(side_df, prefix):
                renames = {}
                for c in side_df.columns:
                    if c.startswith(prefix):
                        new = c[len(prefix):]  # "p_bid" → "bid"
                        renames[c] = new
                return side_df.rename(columns=renames)

            puts = _rename_side(puts, "p_")
            calls = _rename_side(calls, "c_")

            # 确保必需列存在
            for side_df, name in [(puts, "puts"), (calls, "calls")]:
                for col in ["bid", "ask"]:
                    if col not in side_df.columns:
                        side_df[col] = 0.0

            return OptionChain(
                variety=vcode,
                name=vname,
                contract=contract,
                futures_price=futures_price,
                multiplier=vinfo["multiplier"],
                expiry=datetime.now().date() + timedelta(days=dte),
                dte=dte,
                puts=puts,
                calls=calls,
            )

        except Exception as e:
            print(f"     ❌ {vname:6s} → {str(e)[:60]}")
            return None

    def fetch_futures_daily(self, vcode: str, days: int = 10) -> Optional[pd.DataFrame]:
        """拉取期货日线"""
        try:
            return _ak_futures_daily(vcode, days)
        except Exception:
            return None

    @staticmethod
    def _normalize(df: pd.DataFrame, futures_price: float) -> pd.DataFrame:
        """标准化清洗"""
        df = df.copy()
        # 确保数值列
        for col in df.columns:
            if col == "strike":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif any(col.startswith(p) for p in ("p_", "c_")):
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        # 过滤无效行权价
        df = df[df["strike"] > 0].copy()

        # 过滤极端偏离的行权价（>3x 期货价格 或 <0.3x）
        if futures_price > 0:
            df = df[(df["strike"] > futures_price * 0.3) &
                    (df["strike"] < futures_price * 3.0)]

        return df

    @staticmethod
    def _check_arbitrage(df: pd.DataFrame, futures_price: float) -> tuple:
        """分层无套利检查。

        Returns: (block_errors, warnings)
          block_errors: ATM ±5% 垂直价差倒挂 → 拦截品种
          warnings: ATM ±15% bid>ask → 只打印不拦截
        """
        block_errors = []
        warnings = []
        lo, hi = futures_price * 0.85, futures_price * 1.15

        # ── P1（预警）: bid > ask ──
        # ≥20% 档位系统性交叉 → 升级为 P0 拦截
        for prefix, side_name in [("p_", "Put"), ("c_", "Call")]:
            bid_col, ask_col = f"{prefix}bid", f"{prefix}ask"
            if bid_col not in df.columns or ask_col not in df.columns:
                continue
            core = df[(df["strike"] >= lo) & (df["strike"] <= hi)]
            if len(core) == 0:
                continue
            bad = core[(core[bid_col] > core[ask_col]) & (core[bid_col] > 1.0)]
            n_bad = len(bad)
            if n_bad == 0:
                continue
            ratio = n_bad / len(core)
            if ratio > 0.25 and n_bad >= 5:
                block_errors.append(
                    f"{side_name} 系统性报价交叉: {n_bad}/{len(core)}={ratio:.0%}")
            else:
                warnings.append(
                    f"  ⚡ {side_name} bid>ask: {n_bad} 档（不拦截）")

        # ── P0（拦截）: 垂直价差倒挂（仅 OTM 区：策略实际交易区）──
        # ITM 期权近 ATM 也有做市商，但报价逻辑不同（内在价值主导），
        # 轻微 ITM 的 bid 倒挂不一定是数据错误。
        for prefix, side_name, strike_range in [
            ("p_", "Put",   (futures_price * 0.95, futures_price)),        # OTM Put
            ("c_", "Call",  (futures_price, futures_price * 1.05)),        # OTM Call
        ]:
            bid_col = f"{prefix}bid"
            if bid_col not in df.columns:
                continue

            lo_s, hi_s = strike_range
            subset = df[[bid_col, "strike"]].copy()
            subset = subset[subset[bid_col] > 0]
            subset = subset[(subset["strike"] >= lo_s) & (subset["strike"] <= hi_s)]
            if len(subset) < 2:
                continue
            subset = subset.sort_values("strike")

            for i in range(len(subset) - 1):
                k1 = float(subset.iloc[i]["strike"])
                k2 = float(subset.iloc[i + 1]["strike"])
                b1 = float(subset.iloc[i][bid_col])
                b2 = float(subset.iloc[i + 1][bid_col])

                if side_name == "Put" and b1 > b2 * 1.15:
                    block_errors.append(f"{side_name} 倒挂: {k1}@{b1:.2f} > {k2}@{b2:.2f}")
                elif side_name == "Call" and b2 > b1 * 1.15:
                    block_errors.append(f"{side_name} 倒挂: {k2}@{b2:.2f} > {k1}@{b1:.2f}")

        return block_errors, warnings


class CachedSource(DataSource):
    """缓存装饰器 — 同一次 scanner 运行内复用，TTL 5 分钟"""

    def __init__(self, source: DataSource, ttl_seconds: int = 300):
        self._source = source
        self._ttl = ttl_seconds
        self._cache: Dict[str, tuple] = {}  # vcode → (OptionChain, timestamp)

    def fetch_chain(self, vcode: str) -> Optional[OptionChain]:
        now = datetime.now()
        if vcode in self._cache:
            chain, cached_at = self._cache[vcode]
            if (now - cached_at).total_seconds() < self._ttl:
                return chain

        chain = self._source.fetch_chain(vcode)
        if chain is not None:
            self._cache[vcode] = (chain, now)
        return chain

    def fetch_futures_daily(self, vcode: str, days: int = 10) -> Optional[pd.DataFrame]:
        return self._source.fetch_futures_daily(vcode, days)
