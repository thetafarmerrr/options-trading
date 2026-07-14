#!/usr/bin/env python3
"""
surface_viewer.py — 波动率曲面可视化原型
────────────────────────────────────────
从 iv_history.csv 读取数据，生成 3D 波动率曲面图 + skew/term structure 标注。
等 IV 数据积累到 30 天以上开始有意义。

当前状态：骨架已建，数据够了一行命令出图。

用法：
  python3 tools/surface_viewer.py              # 默认品种
  python3 tools/surface_viewer.py --variety m  # 指定品种
"""

import sys, os, argparse
from pathlib import Path
import csv
import numpy as np

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_FILE = PROJECT_DIR / "data" / "iv_history.csv"
OUTPUT_DIR = PROJECT_DIR / "reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

VARIETY_NAMES = {"m": "豆粕", "c": "玉米", "rm": "菜籽粕", "ta": "PTA", "ma": "甲醇"}

# 尝试导入 matplotlib，没有就告诉用户装
try:
    import matplotlib
    matplotlib.use("Agg")  # 非交互模式
    import matplotlib.pyplot as plt
    from matplotlib import cm
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def load_iv_data(variety=None):
    """从 iv_history.csv 加载数据，返回按品种分组的 dict"""
    if not DATA_FILE.exists():
        print(f"  ⚠️ {DATA_FILE} 不存在。先跑 iv_collector.py 攒数据。")
        return None

    data = {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vcode = row.get("variety", "")
            if variety and vcode != variety:
                continue
            if vcode not in data:
                data[vcode] = []
            try:
                iv = float(row.get("iv_est", 0) or 0)
                hv20 = float(row.get("hv_20d", 0) or 0)
                hv60 = float(row.get("hv_60d", 0) or 0)
                dte = int(row.get("dte", 0) or 0)
                if 0.001 < iv < 5.0:
                    data[vcode].append({
                        "date": row.get("date", ""),
                        "iv": iv,
                        "hv20": hv20 if 0.001 < hv20 < 5.0 else None,
                        "hv60": hv60 if 0.001 < hv60 < 5.0 else None,
                        "dte": dte,
                    })
            except (ValueError, TypeError):
                pass

    return {k: v for k, v in data.items() if v}


def print_summary(data):
    """打印文本摘要（不依赖 matplotlib）"""
    print(f"\n{'═'*60}")
    print(f"  波动率曲面数据摘要")
    print(f"{'═'*60}")

    for vcode, rows in data.items():
        name = VARIETY_NAMES.get(vcode, vcode)
        ivs = [r["iv"] for r in rows]
        hv20s = [r["hv20"] for r in rows if r["hv20"]]
        hv60s = [r["hv60"] for r in rows if r["hv60"]]

        iv_current = ivs[-1] if ivs else None
        iv_min, iv_max = min(ivs), max(ivs)
        iv_mean = np.mean(ivs)
        iv_pct = sum(1 for v in ivs if v <= iv_current) / len(ivs) * 100 if iv_current else 0

        hv20_current = hv20s[-1] if hv20s else None
        hv60_current = hv60s[-1] if hv60s else None

        # Term structure (HV20 vs HV60)
        if hv20_current and hv60_current:
            gap = hv20_current - hv60_current
            if gap > 0.03:
                ts = "⚡ 近期剧烈（contango型）"
            elif gap < -0.03:
                ts = "😴 近期异常安静"
            else:
                ts = "➡ 平坦"
        else:
            ts = "❓ 数据不足"

        # Skew approximation: IV vs HV
        if iv_current and hv20_current:
            iv_hv_gap = iv_current - hv20_current
            if iv_hv_gap > 0.05:
                skew_note = f"IV>HV ({iv_hv_gap:.1%}) → 卖方有利"
            elif iv_hv_gap < -0.05:
                skew_note = f"IV<HV ({abs(iv_hv_gap):.1%}) → 买方有利"
            else:
                skew_note = f"IV≈HV → 均衡"
        else:
            skew_note = "❓"

        print(f"\n  {name} ({vcode}) — {len(rows)} 天数据")
        print(f"    IV: 当前 {iv_current:.1%} | 区间 [{iv_min:.1%}, {iv_max:.1%}] | 均值 {iv_mean:.1%} | 分位 {iv_pct:.0f}%")
        print(f"    HV: 20d={hv20_current:.1%} 60d={hv60_current:.1%}" if hv20_current else f"    HV: 数据不足")
        print(f"    期限结构: {ts}")
        print(f"    IV-HV 偏差: {skew_note}")

    # Cross-variety comparison
    print(f"\n  ── 跨品种对比 ──")
    iv_pcts = []
    for vcode, rows in data.items():
        ivs = [r["iv"] for r in rows]
        if len(ivs) >= 5:
            name = VARIETY_NAMES.get(vcode, vcode)
            current = ivs[-1]
            pct = sum(1 for v in ivs if v <= current) / len(ivs) * 100
            iv_pcts.append((name, current, pct))

    iv_pcts.sort(key=lambda x: x[2], reverse=True)
    for name, iv, pct in iv_pcts:
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        tag = "🟢 卖方" if pct > 60 else ("🔵 买方" if pct < 30 else "⚪ 中性")
        print(f"    {name:6s}  IV={iv:.1%}  分位 {pct:.0f}%  [{bar}]  {tag}")

    print(f"\n  ⚠️ 数据 < 30 天 → 分位仅供参考。满 60 天后分位可信。")
    print()


def plot_surface(data):
    """生成 3D 曲面图（需要 matplotlib）"""
    if not HAS_MATPLOTLIB:
        print("  ⚠️ 未安装 matplotlib。运行：pip install matplotlib")
        print("  文本摘要已在上方输出。")
        return

    for vcode, rows in data.items():
        name = VARIETY_NAMES.get(vcode, vcode)
        dates = [r["date"] for r in rows]
        ivs = [r["iv"] * 100 for r in rows]  # 转为百分比
        hv20s = [r["hv20"] * 100 if r["hv20"] else None for r in rows]
        hv60s = [r["hv60"] * 100 if r["hv60"] else None for r in rows]

        fig, axes = plt.subplots(2, 1, figsize=(12, 10))
        fig.suptitle(f"{name} ({vcode}) 波动率结构", fontsize=14, fontweight="bold")

        # Top: IV vs HV time series
        ax1 = axes[0]
        x = range(len(dates))
        ax1.plot(x, ivs, "b-", linewidth=2, label="IV (隐含)")
        hv20_valid = [(i, v) for i, v in enumerate(hv20s) if v]
        hv60_valid = [(i, v) for i, v in enumerate(hv60s) if v]
        if hv20_valid:
            ax1.plot([i for i, _ in hv20_valid], [v for _, v in hv20_valid],
                     "orange", linestyle="--", linewidth=1.5, label="HV 20d")
        if hv60_valid:
            ax1.plot([i for i, _ in hv60_valid], [v for _, v in hv60_valid],
                     "green", linestyle=":", linewidth=1.5, label="HV 60d")

        ax1.set_ylabel("波动率 (%)")
        ax1.set_title("IV vs HV 时间序列")
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)

        # Highlight IV-HV gap zones
        for i, (iv, hv20) in enumerate(zip(ivs, hv20s)):
            if hv20 and iv < hv20:
                ax1.axvspan(i - 0.3, i + 0.3, color="blue", alpha=0.1)
        if any(iv < (hv or 0) for iv, hv in zip(ivs, hv20s)):
            ax1.text(0.02, 0.95, "蓝色阴影 = IV<HV（买方有利）", transform=ax1.transAxes,
                     fontsize=9, color="blue", alpha=0.7)

        # Bottom: IV Percentile bar
        ax2 = axes[1]
        iv_arr = np.array(ivs)
        current = iv_arr[-1]
        pct = sum(1 for v in iv_arr if v <= current) / len(iv_arr) * 100
        colors = ["red" if v > current else "lightgray" for v in iv_arr]
        ax2.bar(range(len(iv_arr)), iv_arr, color=colors, alpha=0.7)
        ax2.axhline(y=current, color="blue", linewidth=2, label=f"当前 IV={current:.1f}% (分位 {pct:.0f}%)")
        ax2.set_ylabel("IV (%)")
        ax2.set_title(f"IV 历史分布（当前分位 {pct:.0f}%）")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)

        # Annotate buyer/seller zones
        ax2.axhline(y=np.percentile(iv_arr, 30), color="blue", linestyle="--", alpha=0.3)
        ax2.axhline(y=np.percentile(iv_arr, 70), color="red", linestyle="--", alpha=0.3)
        ax2.text(len(iv_arr) - 1, np.percentile(iv_arr, 30), "买方区", fontsize=8, color="blue")
        ax2.text(len(iv_arr) - 1, np.percentile(iv_arr, 70), "卖方区", fontsize=8, color="red")

        plt.tight_layout()
        out_path = OUTPUT_DIR / f"surface_{vcode}_{dates[-1]}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  📊 {name} 曲面图 → {out_path}")


def main():
    parser = argparse.ArgumentParser(description="波动率曲面可视化原型")
    parser.add_argument("--variety", type=str, default=None,
                        help="品种代码：m/c/rm/ta/ma。默认全部。")
    parser.add_argument("--plot", action="store_true",
                        help="生成 3D 曲面图（需 matplotlib）")
    args = parser.parse_args()

    data = load_iv_data(args.variety)
    if not data:
        print("  ⚠️ 数据不足。至少需要 5 天 IV 数据。")
        print(f"  当前数据文件：{DATA_FILE}")
        return

    print_summary(data)

    if args.plot and HAS_MATPLOTLIB:
        plot_surface(data)
    elif args.plot:
        print("  ⚠️ matplotlib 未安装，无法出图。")


if __name__ == "__main__":
    main()
