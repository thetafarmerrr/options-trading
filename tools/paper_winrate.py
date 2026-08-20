#!/usr/bin/env python3
"""paper-tracker.md 纸面信号胜率统计（8/20 首次落地）

用法: python3 tools/paper_winrate.py
读取 docs/paper-tracker.md，解析主条目 + 追踪盈亏，输出胜率统计。
格式可解析的前提：主条目以 `2026-xx-xx|` 开头，追踪行含盈亏数字。
"""
import re
import sys
from pathlib import Path

MD = Path(__file__).resolve().parent.parent / "docs" / "paper-tracker.md"

# 主条目行：日期| 开头（兼容 | 和 ｜）
ENTRY = re.compile(r"^(2026-\d\d-\d\d)\s*[|｜]")
# 盈亏格式：三种
PAT_NEG = re.compile(r"如果平仓 亏([\d.]+)")          # 亏3.5
PAT_EQ = re.compile(r"(?:=|→)\s*([+\-\d.]+)\s*$")    # 平仓模拟：...=3 / ...→ +3.5
PAT_CONS = re.compile(r"亏([\d.]+)\s*$")             # 平仓 亏1.5
PAT_DONE = re.compile(r"已交割|已到期|无法平仓|无报价")


def parse():
    signals, cur = [], None
    for line in MD.read_text().split("\n"):
        m = ENTRY.match(line.strip())
        if m:
            if cur:
                signals.append(cur)
            cur = {"date": m.group(1), "desc": line.strip()[:70], "pnls": [], "done": False}
            continue
        if cur is None:
            continue
        if "追踪" in line or "平仓" in line:
            v = None
            mm = PAT_NEG.search(line)
            if mm:
                v = -float(mm.group(1))
            if v is None:
                mm = PAT_EQ.search(line)
                if mm:
                    v = float(mm.group(1))
            if v is None:
                mm = PAT_CONS.search(line)
                if mm and "平仓" in line:
                    v = -float(mm.group(1))
            if v is not None:
                cur["pnls"].append(v)
        if PAT_DONE.search(line):
            cur["done"] = True
    if cur:
        signals.append(cur)
    return signals


def main():
    signals = parse()
    settled = [s for s in signals if s["pnls"]]
    pending = [s for s in signals if not s["pnls"]]
    wins = [s for s in settled if s["pnls"][-1] > 0]
    losses = [s for s in settled if s["pnls"][-1] < 0]

    print(f"paper-tracker.md 解析: {len(signals)} 条信号")
    print(f"已结算: {len(settled)}  在途/未结算: {len(pending)}")
    print(f"盈利: {len(wins)}  亏损: {len(losses)}")
    if settled:
        print(f"胜率: {len(wins)}/{len(settled)} = {len(wins)/len(settled)*100:.0f}%")

    if len(sys.argv) > 1 and sys.argv[1] == "--detail":
        print("\n各笔最终盈亏:")
        for s in settled:
            print(f"  {s['date']} → {s['pnls'][-1]:+.1f}  {s['desc'][:50]}")


if __name__ == "__main__":
    main()
