#!/usr/bin/env python3
"""backfill_dte_20260927.py — 一次性迁移：把 iv_history.csv 的 dte/iv_est/ref_iv
换到「交易所规则真尺」（tools/exchange_ltd.py）。

═══ 为什么 ═══
2026-09-27 之前，`dte` 由「到期月首日 − 5 天」近似式算出，比真实到期日长 3~15 天
（上期所只差 1 天，郑商所差 13~16 天）。`iv = 跨式/(0.8·S·√(dte/365))` 对 dte 敏感，
所以**全部历史 IV 都被系统性低估**。代码已于 2026-09-27 修（见 exchange_ltd.py），
但历史行仍是旧尺 → 修复上线后新旧行不可比（尤其 50 行待回填预测的 compare_date
落在 9/28 之后，会跨尺）。本脚本把历史拉齐到同一把尺。

═══ 改哪几列 ═══
  dte      旧近似值 → exchange_ltd.dte(contract, 该行自己的 date)
  iv_est   = 跨式 / (0.8 · S · √(dte/365))，用**新 dte** 重算
           （跨式与 S 都还在 CSV 里：call_bid/ask + put_bid/ask + inferred_futures）
  ref_iv   参照合约的跨式价没存 → 只能按比例换算：
           ref_iv_new = ref_iv_old × √(实际旧 dte_ref / 精确新 dte_ref)
           ⚠️ 分母必须是 `_legacy_collector`（当年真写进 CSV 的），不是 `_legacy_approx`
              —— 后者多 1 天（见该函数 docstring），用它会系统性抬高 ref_iv。
  iv_slope 派生于 iv_est，按 calc_iv_slope 的原逻辑逐行重放
  dte_src  新增列：exact（按规则算出）| legacy（日历覆盖不到，回落旧近似）| expired
  ref_iv_src 新增列：exact（已换算到新尺）| legacy（参照月超日历·**留在旧尺原值**）
                     | 空（本行无 ref_iv）

═══ 不动 ═══
  hv_parkinson / hv_20d / hv_60d —— 纯期货高低价，与 dte 无关
  spread_pct / liquidity_ok / ref_liquidity_ok —— 盘口质量，与 dte 无关
  atm_strike / 各 bid·ask / inferred_futures —— 原始观测

═══ 用法 ═══
  python3 tools/backfill_dte_20260927.py            # 干跑（默认，不落盘）
  python3 tools/backfill_dte_20260927.py --write    # 落盘
"""

import csv
import math
import os
import sys
from datetime import date

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "tools"))

from exchange_ltd import dte as true_dte, dte_exact, _legacy_approx  # noqa: E402

CSV_PATH = os.path.join(_REPO, "data", "iv_history.csv")
NEW_COL = "dte_src"
REF_COL = "ref_iv_src"


def _legacy_collector(code, asof):
    """**采集器当年真正写进 CSV 的那个 dte** —— 比 `_legacy_approx` 少 1。

    旧式是 `(date(y,mo,1) - datetime.now()).days - 5`，`now` 带时分而月初是零点，
    `timedelta.days` 向下取整 → 只要不在零点整采数就少 1 天。下限 5 也照旧。

    **已全量验证**：旧文件 1128 行 dte 列 == 本函数，1128/1128 相符（2026-09-27）。
    ref 合约的跨式价没存，所以 ref_iv 只能按 `√(旧dte/新dte)` 比例换算 —— 分母用
    本函数（**实际用过的**值）才准；用 `_legacy_approx` 会高估 ref_iv。

    ⚠️ 已知边界：旧 `_est_dte` 是 `int(contract[-2:])`，对 `SR2611MS` 会抛异常回落 30。
    本库 0 个 MS 合约，暂不影响。
    """
    return max(_legacy_approx(code, asof) - 1, 5)


def _f(v):
    try:
        x = float(v)
        return x
    except (TypeError, ValueError):
        return None


def _recompute_slopes(rows):
    """按 calc_iv_slope 的原逻辑（全历史按值去重 → 取最后 3 个 → 线性回归）
    逐行重放，写回每行的 iv_slope。返回被改动的行数。

    注意：原函数是按「格式化成 4 位小数后的值」去重的，这里照抄，不改语义。
    """
    import numpy as np
    by_var = {}
    changed = 0
    for r in rows:
        v = r.get("variety")
        iv = _f(r.get("iv_est"))
        if not v or iv is None or not (0.001 < iv < 5.0):
            continue
        seq = by_var.setdefault(v, [])
        key = "%.4f" % iv
        if key not in seq[1:]:            # 值级去重（同 calc_iv_slope）
            seq.append((key, iv))
        if len(seq) < 3:
            continue
        recent = [x[1] for x in seq[-3:]]
        slope = float(np.polyfit(np.arange(3), recent, 1)[0])
        new = round(slope, 6)
        if r.get("iv_slope") != str(new) and _f(r.get("iv_slope")) != new:
            changed += 1
        r["iv_slope"] = new
    return changed


def main(write=False):
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = list(reader)
    for _c in (NEW_COL, REF_COL):
        if _c not in fields:
            fields.append(_c)

    repro_ok = repro_bad = 0
    repro_samples = []
    n_dte_chg = n_iv_chg = 0
    n_no_price = n_nonpos = n_legacy = 0
    dte_deltas = []
    iv_ratios = []
    ref_touched = 0
    n_ref_legacy = 0
    leg_ok = leg_bad = 0

    for r in rows:
        c = r.get("contract") or ""
        d = r.get("date") or ""
        old_dte = _f(r.get("dte"))
        old_iv = _f(r.get("iv_est"))
        S = _f(r.get("inferred_futures"))
        cb, ca = _f(r.get("call_bid")), _f(r.get("call_ask"))
        pb, pa = _f(r.get("put_bid")), _f(r.get("put_ask"))

        # ── ⓪ 先证明「旧尺公式」认得对：CSV 里的旧 dte 必须 == _legacy_collector ──
        # （ref_iv 的换算因子全靠这个函数，认错了整列都偏 → 先验再加权）
        if c and d and old_dte:
            if int(old_dte) == _legacy_collector(c, d):
                leg_ok += 1
            else:
                leg_bad += 1

        # ── ① 复现旧值：用 CSV 里的旧 dte 反算，必须等于 CSV 里的 iv_est ──
        if None not in (S, cb, ca, pb, pa) and S > 0 and old_dte and old_dte > 0:
            straddle = (pb + pa) / 2 + (cb + ca) / 2
            if straddle > 0:
                repro = round(straddle / (0.8 * S * math.sqrt(old_dte / 365)), 4)
                if old_iv is not None and abs(repro - old_iv) < 1e-9:
                    repro_ok += 1
                else:
                    repro_bad += 1
                    if len(repro_samples) < 5:
                        repro_samples.append((d, c, old_dte, old_iv, repro))

        # ── ② 新 dte ──
        if not c or not d:
            continue
        exact = dte_exact(c, d)
        if exact is None:
            src, new_dte = "legacy", true_dte(c, d)
            n_legacy += 1
        elif exact <= 0:
            # 合约在采集当天已在/过了最后交易日 —— dte 存真值（0 或负），
            # 但 IV 公式在 dte≤0 无定义，**这一行的 iv_est 只能保留旧值**，
            # 用 dte_src='expired' 标出来。不删行、不假装算得出。
            src, new_dte = "expired", exact
            n_nonpos += 1
        else:
            src, new_dte = "exact", exact
        r[NEW_COL] = src
        r["dte"] = new_dte
        if old_dte is not None and new_dte != old_dte:
            n_dte_chg += 1
        if old_dte:
            dte_deltas.append(new_dte - old_dte)

        # ── ③ 新 iv_est（只在 dte>0 时重算）──
        if None in (S, cb, ca, pb, pa) or not S or S <= 0:
            n_no_price += 1
        elif src == "expired":
            pass                      # 已在 ② 记数并标记，iv_est 保持旧值
        else:
            straddle = (pb + pa) / 2 + (cb + ca) / 2
            if straddle > 0:
                new_iv = round(straddle / (0.8 * S * math.sqrt(new_dte / 365)), 4)
                if old_iv is not None:
                    iv_ratios.append(new_iv / old_iv if old_iv else float("nan"))
                if new_iv != old_iv:
                    n_iv_chg += 1
                r["iv_est"] = new_iv

        # ── ④ 新 ref_iv（按比例换算，跨式价没存）──
        # 换算因子用 `_legacy_collector`（**实际写进 CSV 的**旧 dte），不是
        # `_legacy_approx` —— 后者多 1 天，会把 ref_iv 系统性抬高（2026-09-27 修）。
        rc = r.get("ref_contract") or ""
        r_old = _f(r.get("ref_iv"))
        if not (rc and r_old):
            r[REF_COL] = ""
        else:
            r_exact = dte_exact(rc, d)
            old_r = _legacy_collector(rc, d)
            if r_exact is None or r_exact <= 0:
                # 参照月的最后交易日在日历覆盖之外（当前日历止于 2026-12-31，
                # 所以 2027 年到期的参照月都落这里，ru/au 为主）。
                # **不假装算得出** → ref_iv 留在旧尺原值不动，只标记来源。
                r[REF_COL] = "legacy"
                n_ref_legacy += 1
            elif old_r and old_r > 0:
                r["ref_iv"] = round(r_old * math.sqrt(old_r / r_exact), 4)
                r[REF_COL] = "exact"
                ref_touched += 1
            else:
                r[REF_COL] = "legacy"
                n_ref_legacy += 1

                n_ref_legacy += 1

    n_slope = _recompute_slopes(rows)

    # ── 第三步 · 自洽校验（落盘前最后一道）──
    # 用**将要写盘的 dte 列**反算 iv_est，必须等于**将要写盘的 iv_est**。
    # 9/27 第一版漏了这个：干跑里 dte 只被计数、忘了 `r["dte"] = new_dte`，
    # 而 iv_est 用的是局部变量 new_dte 所以照改了 —— 落盘后文件自相矛盾
    # （iv_est 是新尺、dte 是旧尺，拿 dte 反算不出 iv_est）。
    # 这一步就是为了让那类「算了但没写回」的 bug 逃不过去。
    self_ok = self_bad = 0
    self_samples = []
    for r in rows:
        new_dte = _f(r.get("dte"))
        iv = _f(r.get("iv_est"))
        S = _f(r.get("inferred_futures"))
        cb, ca = _f(r.get("call_bid")), _f(r.get("call_ask"))
        pb, pa = _f(r.get("put_bid")), _f(r.get("put_ask"))
        if r.get(NEW_COL) == "expired":
            continue          # iv_est 有意保留旧值，不参与自洽
        if None in (S, cb, ca, pb, pa) or not S or S <= 0 or iv is None:
            continue
        if not new_dte or new_dte <= 0:
            continue
        straddle = (pb + pa) / 2 + (cb + ca) / 2
        if straddle <= 0:
            continue
        back = round(straddle / (0.8 * S * math.sqrt(new_dte / 365)), 4)
        if abs(back - iv) < 1e-9:
            self_ok += 1
        else:
            self_bad += 1
            if len(self_samples) < 5:
                self_samples.append((r.get("date"), r.get("contract"), new_dte, iv, back))

    # ── 打印回核 ──
    print("=" * 80)
    print("回填干跑 · data/iv_history.csv  （%d 行）" % len(rows))
    print("=" * 80)
    print("\n【第零步 · 认旧尺】CSV 里的旧 dte 必须 == _legacy_collector(contract, date)")
    print("  ✅ 相符 %d 行 ｜ 🔴 不符 %d 行" % (leg_ok, leg_bad))
    if leg_bad:
        print("  ⚠️ 旧尺认错 → ref_iv 的换算因子不可信，**先别落盘**")

    print("\n【第一步 · 复现旧值】用 CSV 里的旧 dte 反算 iv_est，必须等于 CSV 里的值")
    print("  ✅ 精确复现 %d 行 ｜ 🔴 对不上 %d 行" % (repro_ok, repro_bad))
    for s in repro_samples:
        print("      %s %-8s 旧dte=%s  存=%s  复现=%s" % s)
    if repro_bad:
        print("  ⚠️ 有对不上的行 → 说明 iv_est 不是这条公式写的，**先别落盘**")
    print("\n【第二步 · 新值将改动什么】")
    print("  dte      改动 %d 行" % n_dte_chg)
    if dte_deltas:
        print("           偏差 min %+d / 中位 %+d / max %+d 天" % (
            min(dte_deltas), sorted(dte_deltas)[len(dte_deltas) // 2], max(dte_deltas)))
    print("  iv_est   改动 %d 行" % n_iv_chg)
    if iv_ratios:
        fin = sorted(x for x in iv_ratios if x == x)
        print("           倍数 min %.3f / 中位 %.3f / max %.3f" % (
            fin[0], fin[len(fin) // 2], fin[-1]))
    print("  ref_iv   改动 %d 行（换算因子 = √(实际旧dte / 精确新dte)）" % ref_touched)
    print("  ref_iv_src 新增列：exact %d 行 ｜ legacy %d 行（超日历·留在旧尺·不改值）"
          % (ref_touched, n_ref_legacy))
    print("  iv_slope 改动 %d 行（按原逻辑逐行重放）" % n_slope)
    n_src = {}
    for r in rows:
        n_src[r.get(NEW_COL, "")] = n_src.get(r.get(NEW_COL, ""), 0) + 1
    print("  dte_src  新增列：%s" % " ｜ ".join(
        "%s %d 行" % (k, v) for k, v in sorted(n_src.items())))
    print("\n【第三步 · 自洽校验】拿**将要写盘的 dte 列**反算 iv_est，必须等于**将要写盘的 iv_est**")
    print("  ✅ 自洽 %d 行 ｜ 🔴 不自洽 %d 行" % (self_ok, self_bad))
    for s in self_samples:
        print("      %s %-8s 新dte=%s  存=%s  反算=%s" % s)
    if self_bad:
        print("  ⚠️ 不自洽 → 说明「算了新 dte 但没写回 dte 列」这类 bug → **拒绝落盘**")
    print("\n【未改动】hv_* / spread_pct / liquidity_ok / 各 bid·ask / inferred_futures")
    if n_no_price:
        print("  ⚠️ 无价格跳过 %d 行" % n_no_price)
    if n_nonpos:
        print("  ⚠️ dte_src='expired' %d 行 —— dte 存真值(0或负)，iv_est 保留旧值" % n_nonpos)

    if not write:
        print("\n（干跑，未落盘。确认无误后加 --write）")
        return 0

    if leg_bad:
        print("\n🔴 旧尺认错 %d 行 → 拒绝落盘" % leg_bad)
        return 1
    if repro_bad:
        print("\n🔴 复现失败 %d 行 → 拒绝落盘" % repro_bad)
        return 1
    if self_bad:
        print("\n🔴 自洽校验失败 %d 行 → 拒绝落盘" % self_bad)
        return 1

    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    os.replace(tmp, CSV_PATH)
    print("\n✅ 已落盘 %s（%d 行，%d 列）" % (CSV_PATH, len(rows), len(fields)))
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--write" in sys.argv))
