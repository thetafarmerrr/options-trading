#!/usr/bin/env python3
"""解码快期 V2(RAE) 的 order.dat / match.dat —— 给剥头皮跟踪表的 ③ 成交损耗供数。

编码：文件里每个字节都是 **ASCII 左移 1 位**（防复制伪装）。
      ord(b) 是真实字符 → 文件存 chr(b)<<1。解码 = 逐字节 >>1。

用法:
    python3 tools/decode_q7_dat.py <目录> [合约,默认 m2701] [日期 YYYYMMDD]
    python3 tools/decode_q7_dat.py ~/Downloads/ToDesk/1 m2701 20261009
    不给日期 → 用目录里最新的那一天。

配套: 交割单 .xls 用来补 买/卖·开/平·平仓盈亏（match.dat 里是二进制标志位,不解）。
"""
import glob, os, re, sys, datetime, statistics

def decode(path):
    """逐字节 >>1 还原成文本；填充位（0x00）换成空格，好让 \\s 类正则吃得下。"""
    return "".join(chr(b >> 1) if 32 <= b >> 1 < 127 else " "
                   for b in open(path, "rb").read())

def records(path, contract):
    """按 HH:MM:SS 切记录，只留含目标合约的。"""
    s = decode(path)
    hits = list(re.finditer(r"\d\d:\d\d:\d\d", s))
    out = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(s)
        seg = s[m.end():end]
        if contract in seg:
            out.append((m.group(0), seg))
    return out

def orders(path, contract):
    """委托: 时间 / 价格 / 委托序号"""
    d = {}
    for t, seg in records(path, contract):
        no = re.search(r"\s2\s+(\d{9})", seg)
        px = re.findall(r"(?<![\d.])(\d{4})\.0(?![.\d])", seg)
        if no:
            d[no.group(1)] = (t, px[-1] if px else None)
    return d

def matches(path, contract):
    """成交: (时间, 委托序号, 成交价)。成交价是 委托序号 前面那个整数。"""
    out = []
    for t, seg in records(path, contract):
        no = re.search(r"\s2\s+(\d{9})", seg)
        if not no:
            continue
        head = seg[:no.start()]
        px = re.findall(r"(?<![\d.])(\d{4})(?![\d.])", head)
        out.append((t, no.group(1), px[-1] if px else None))
    return out

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = os.path.expanduser(sys.argv[1])
    ctr = sys.argv[2] if len(sys.argv) > 2 else "m2701"
    # 文件名里 合约 和 日期 紧挨着（...-m270120261009order.dat），
    # 不能用裸 \d{8}——文件名前缀那串哈希里也有 8 位数字。
    dates = sorted({m.group(1) for f in os.listdir(d)
                    for m in [re.search(re.escape(ctr) + r"(\d{8})", f)]
                    if m and f.endswith(("order.dat", "match.dat"))})
    if not dates:
        sys.exit(f"目录 {d} 里没有 {ctr} 的 order/match.dat")
    date = sys.argv[3] if len(sys.argv) > 3 else dates[-1]
    if date not in dates:
        sys.exit(f"没这天的数据。{ctr} 可用: {', '.join(dates)}")
    pick = lambda kind: glob.glob(os.path.join(d, f"*{ctr}{date}{kind}.dat"))[0]
    print(f"# {ctr} {date}\n")
    ORD = orders(pick("order"), ctr)
    T = lambda x: datetime.datetime.strptime(x, "%H:%M:%S")
    rows = []
    for mt, ono, mpx in matches(pick("match"), ctr):
        op = ORD.get(ono)
        if not op:
            rows.append((None, mt, None, mpx, ono)); continue
        rows.append((op[0], mt, op[1], mpx, ono))
    rows.sort(key=lambda r: r[1])
    print(f"委托 {len(ORD)} 条 | 成交 {len(rows)} 条\n")
    print(f"{'委托时间':<10}{'成交时间':<10}{'延迟s':>6} {'委托价':>6}{'成交价':>6}{'滑点':>5}  委托序号")
    lat, slip, disc = [], 0, 0
    for ot, mt, op, mp, ono in rows:
        if ot is None:
            print(f"{'—':<10}{mt:<10}{'—':>6} {'—':>6}{mp or '—':>6}{'—':>5}  {ono}  ⚠️未配委托")
            disc += 1; continue
        dt = int((T(mt) - T(ot)).total_seconds()); lat.append(dt)
        sl = (int(mp) - int(op)) if (mp and op) else None
        if sl is not None: slip += sl
        print(f"{ot:<10}{mt:<10}{dt:>6} {op or '—':>6}{mp or '—':>6}{'' if sl is None else f'{sl:+d}':>5}  {ono}")
    if lat:
        print(f"\n★ 滑点合计 {slip:+d} 点 = {slip*10:+d} 元")
        print(f"★ 委托→成交 延迟: min {min(lat)} / 中位 {statistics.median(lat):.0f} / "
              f"均值 {statistics.mean(lat):.0f} / max {max(lat)} 秒  (n={len(lat)})")
        for lo, hi, lab in ((0,1,'0s'),(1,5,'1-5s'),(5,15,'5-15s'),(15,60,'15-60s'),(60,10**9,'>60s')):
            g = [x for x in lat if lo <= x < hi]
            if g: print(f"   {lab:<7}: {len(g):>2} 笔")
    if disc:
        print(f"\n⚠️ {disc} 条成交未配上委托（成交序号/委托序号跨文件对不上），已列出")

if __name__ == "__main__":
    main()
