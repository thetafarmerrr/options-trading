#!/usr/bin/env python3
"""exchange_ltd.py — 三家商品交易所期权「最后交易日」规则 · 单一真相源

═══ 规则原文出处（2026-09-27 逐条抓取核对，**原文，非转述**）═══

  ▸ 上期所 SHFE（黄金 au / 橡胶 ru）
    https://www.shfe.com.cn/products/option/ferrousandpreciousmetal/au_o/standard_au_o/202401/t20240103_331332.html
    原文：「最后交易日：标的期货合约交割月前第一月的倒数第五个交易日，
            交易所可以根据国家法定节假日等调整最后交易日」

  ▸ 郑商所 CZCE（棉花 cf / 白糖 sr / PTA ta / 甲醇 ma / 菜粕 rm）
    《白糖期货品种手册》表10 + 第4节「到期月份与最后交易日」
    https://www.czce.com.cn/cn/content_file/sspz/bt/pzjs/qh/2026/7/1988e8c935d84b258bd838174a114d1c.pdf
    原文（常规期权）：「标的期货合约交割月份前一个月第15个日历日之前（含该日）的倒数第3个交易日」
    原文（系列期权）：「标的期货合约交割月份前两个月第15个日历日之前（含该日）的倒数第3个交易日」
    合约代码：常规 `SR2611C5000` ｜ 系列 `SR2611MSC5000`（多一个 MS 段）

  ▸ 大商所 DCE（豆粕 m / 玉米 c / 铁矿石 i）
    《关于大商所2610常规期权及系列期权合约到期日相关事宜的通知》
    https://58.23.237.247/content/show/31/206328 （dce.com.cn 有 WAF，此条取自交易所通知的券商镜像）
    原文：「…铁矿石…2610**常规期权**最后交易日、最后行权日均为标的期货合约交割月份
            前一个月的第12个交易日；…豆粕2611**系列期权**…为标的期货合约交割月份
            前二个月的第12个交易日，即2026年9月16日」
    系列期权于 2026-02-02 才挂牌，代码带 MS 标识。

═══ 规则表回测：4/4 精确命中（到期日为外部独立核实值）═══
    i2610=2026-09-16    au2610=2026-09-23    cf2607=2026-06-11    cf2609=2026-08-12
  该回测同时验证了 data/trade_calendar.txt 的可靠性（规则要算对，日历必须对）。

═══ 为什么要有这个模块 ═══
原先同一套「到期月首日 - 5 天」近似式被复制在 4 处，且其中 2/3 的规则注释是过期的：
    tools/iv_collector.py:_est_dte              （注释：大商所前月第5个 → M2501 前旧规）
    tools/_ak_data.py:_est_dte                  （无注释）
    tools/scanner/data_source.py (DTE 计算段)    （无注释）
    tools/scanner/volatility.py (ref_dte)       （注释：同旧规）
实测偏差 3~15 天，且方向恒为「记长了」→ IV 被系统性低估。
四份副本已合并到本模块。**改动代码请只改这里，不要再复制。**

═══ ⚠️ 已知边界（不是 bug，是范围）═══
1. 日历覆盖 `data/trade_calendar.txt` 至 2026-12-31。远期合约（前月 ≥ 2027-01，
   如 au2702 / cf2705）算不出，`dte()` 回落到旧近似式**并打一次警告**。
   真正的修复见 MASTER_PLAN 搁置项「交易日历缓存覆盖边界」。
2. 原文那句「交易所可以根据国家法定节假日等调整最后交易日」保留条款——
   **已过去的月份**已由上述 4 个实点验证；**未来含长假（国庆/春节）的月份未验证**。
   出现偏差时以交易所当期通知为准。
3. 系列期权规则：郑商所取自合约手册原文（可靠）；大商所取自到期日通知（次一级）。
   当前 `iv_history.csv` 内 MS 合约为 0 个，此分支尚未被真实数据走过。
"""

import os
import re
import sys
from datetime import date, datetime

# ── 交易日历（akshare 缓存，一行一个 ISO 日期）──
_CAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "trade_calendar.txt",
)
_CAL = None
_CAL_SPAN = None          # (first, last) 覆盖区间，用于判断某月能不能算

# ── 品种 → 交易所规则 ──
_DCE = {"m", "c", "i"}          # 前月第12个交易日
_SHFE = {"au", "ru"}            # 前月倒数第5个交易日
# 其余（cf/sr/ta/ma/rm 及其它郑商所品种）走郑商所规则

# 合约代码形如：m2701 / TA610 / SR2611MS / MS2611 / au2610
_RE_TAIL = re.compile(r"^([A-Z]{1,3})(\d{3,4})(MS)?$")     # SR2611MS
_RE_HEAD = re.compile(r"^(MS)([A-Z]{1,3})(\d{3,4})$")      # MS2611

_FALLBACK_SEEN = set()


def load_calendar():
    """读交易日历，进程内缓存。返回排序后的 date 列表。"""
    global _CAL, _CAL_SPAN
    if _CAL is None:
        try:
            with open(_CAL_PATH, encoding="utf-8") as f:
                _CAL = sorted({date.fromisoformat(l.strip()) for l in f if l.strip()})
        except Exception as e:
            print(f"⚠️  exchange_ltd: 交易日历读取失败 {_CAL_PATH}: {e}", file=sys.stderr)
            _CAL = []
        _CAL_SPAN = (_CAL[0], _CAL[-1]) if _CAL else None
    return _CAL


def reload_calendar():
    """日历文件更新后强制重载（长驻进程用；采集器每次新起进程，不需要）。"""
    global _CAL
    _CAL = None
    return load_calendar()


def calendar_span():
    load_calendar()
    return _CAL_SPAN


def parse_contract(code):
    """合约代码 → (variety, year, month, is_series)；不认识 → None。

    支持三种形态：`m2701`（四位数 YYMM）、`TA610`（三位数 YMM，郑商所）、
    `SR2611MS` / `MS2611`（系列期权）。不认识的形态返回 None —— 不猜。
    """
    if not code:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", str(code)).upper()
    m = _RE_TAIL.match(s)
    if m:
        v, num, ms = m.group(1), m.group(2), m.group(3)
    else:
        m = _RE_HEAD.match(s)
        if not m:
            return None
        v, num, ms = m.group(2), m.group(3), "MS"
    if len(num) == 3:                 # 三位 = 年个位 + 月
        y, mo = 2000 + int(num[0]), int(num[1:])
    else:
        y, mo = 2000 + int(num[:2]), int(num[2:])
    if not (1 <= mo <= 12):
        return None
    return v.lower(), y, mo, bool(ms)


def _shift_month(y, m, back):
    """往回退 back 个月 → (y, m)"""
    idx = y * 12 + (m - 1) - back
    return idx // 12, idx % 12 + 1


def _month_days(y, m):
    return [d for d in load_calendar() if d.year == y and d.month == m]


def last_trading_day(code):
    """期权最后交易日（date）；日历覆盖不到或代码不认识 → None。

    规则逐条对应文首原文，见各分支注释。
    """
    p = parse_contract(code)
    if not p:
        return None
    v, y, mo, series = p
    py, pm = _shift_month(y, mo, 2 if series else 1)
    ds = _month_days(py, pm)
    if not ds:
        return None                   # 该月不在日历覆盖内

    if v in _DCE:
        # 大商所：常规「前月第12个交易日」；系列「前两个月第12个交易日」
        return ds[11] if len(ds) >= 12 else None
    if v in _SHFE:
        # 上期所：前月倒数第5个交易日（上期所无系列期权）
        if series:
            return None
        return ds[-5] if len(ds) >= 5 else None
    # 郑商所：常规「前月15日(含)前倒数第3个交易日」；系列「前两个月…」
    d15 = [d for d in ds if d.day <= 15]
    return d15[-3] if len(d15) >= 3 else None


def _coerce_asof(asof):
    """asof 接受 None / date / datetime / 'YYYY-MM-DD'（CSV 里就是字符串）。"""
    if asof is None:
        return date.today()
    if isinstance(asof, datetime):
        return asof.date()
    if isinstance(asof, date):
        return asof
    try:
        return date.fromisoformat(str(asof).strip()[:10])
    except ValueError:
        return date.today()


def dte_exact(code, asof=None):
    """真实剩余天数（可为负 = 已到期）；算不出 → None。

    要「知道算不算得出」时用这个；只要一个数时用 `dte()`。
    """
    L = last_trading_day(code)
    if L is None:
        return None
    return (L - _coerce_asof(asof)).days


def _legacy_approx(code, asof=None):
    """旧「到期月首日 - 5 天」近似式。**本身就是错的**，只作日历覆盖不到的兜底。

    保留它是为了「不改今天就有的行为」——远期合约今天也是这么算的，
    换成 None 会让下游 `> dte_min` 比较直接 TypeError。
    """
    p = parse_contract(code)
    a = _coerce_asof(asof)
    if not p:
        return 30
    _, y, mo, _ = p
    try:
        return max((date(y, mo, 1) - a).days - 5, 5)
    except ValueError:
        return 30


def dte(code, asof=None):
    """剩余天数 —— **直接替换旧 `_est_dte` 用这个**，签名兼容，永不抛。

    能按规则算 → 真实值（可为负，表示已到期，交给调用方判）；
    算不出（日历不够 / 代码不认识）→ 回落旧近似式，并对每个合约**打一次警告**。
    """
    v = dte_exact(code, asof)
    if v is not None:
        return v
    key = str(code)
    if key not in _FALLBACK_SEEN:
        _FALLBACK_SEEN.add(key)
        sp = calendar_span()
        print(f"⚠️  exchange_ltd: {key} 无法按规则算 DTE（日历覆盖 "
              f"{sp[0] if sp else '?'} ~ {sp[1] if sp else '?'}），回落旧近似式",
              file=sys.stderr)
    return _legacy_approx(code, asof)


if __name__ == "__main__":
    # 自检：把文首那 4 个外部核实点重跑一遍
    _EXT = {"i2610": date(2026, 9, 16), "au2610": date(2026, 9, 23),
            "cf2607": date(2026, 6, 11), "cf2609": date(2026, 8, 12)}
    print(f"日历覆盖：{calendar_span()}")
    ok = 0
    for c, want in _EXT.items():
        got = last_trading_day(c)
        hit = got == want
        ok += hit
        print(f"  {c:8s} 外部核实 {want} ｜ 规则算出 {got}  {'✅' if hit else '🔴'}")
    print(f"  回测 {ok}/{len(_EXT)}")
