#!/usr/bin/env bash
# view_csv.sh — 安全查看 data/ 下的 CSV
#
# 为什么需要它：Excel/Numbers/WPS 打开 CSV 后「保存」写的是它内存里的图，
# 不是硬盘上的文件——来回一次会静默抹掉别处写入的数据。
# 9/16 事故：124 格已回填数据被这么抹掉（见 mistakes.md）。
#
# 这个脚本做三件事：
#   1. 把原文件拷一份到 /tmp（带时间戳，不覆盖任何东西）
#   2. 把副本设成只读（chmod 444）→ Excel 打不进去，物理上存不回来
#   3. 用表格软件打开那个副本
# 原文件全程只被「读」，一个字节都不会变。
#
# 用法:
#   ./tools/view_csv.sh                              # 列出 data/ 下所有 csv
#   ./tools/view_csv.sh data/iv_direction_pred.csv   # 只读打开副本

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$REPO/data"

if [ $# -eq 0 ]; then
  echo "data/ 下的 CSV："
  ls -1 "$DATA_DIR"/*.csv 2>/dev/null | sed "s|$REPO/||" || echo "  （没有）"
  echo
  echo "用法：$0 data/<文件名>.csv"
  exit 0
fi

SRC="$1"
[ -f "$SRC" ] || SRC="$REPO/$1"
if [ ! -f "$SRC" ]; then
  echo "❌ 找不到文件：$1" >&2
  exit 1
fi

# 安全：只允许操作仓库内 data/ 下的文件
SRC_ABS="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"
case "$SRC_ABS" in
  "$DATA_DIR"/*) ;;
  *) echo "❌ 只允许查看 $DATA_DIR 下的文件，收到：$SRC_ABS" >&2; exit 1 ;;
esac

TS="$(date +%Y%m%d_%H%M%S)"
BASE="$(basename "$SRC_ABS" .csv)"
COPY="/tmp/${BASE}__副本_${TS}.csv"

cp "$SRC_ABS" "$COPY"
chmod 444 "$COPY"

echo "✅ 已拷贝副本（原文件未被触碰）"
echo "   原文件 : $SRC_ABS"
echo "   副本   : $COPY   ← 只读，Excel 存不回去"
echo

# 优先用 Excel，没有就用系统默认程序
if open -a "Microsoft Excel" "$COPY" 2>/dev/null; then
  echo "已在 Excel 打开副本。想改内容 → 别改这个，发给我用脚本写。"
elif open -a "Numbers" "$COPY" 2>/dev/null; then
  echo "已在 Numbers 打开副本。想改内容 → 别改这个，发给我用脚本写。"
else
  open "$COPY"
  echo "已用默认程序打开副本。想改内容 → 别改这个，发给我用脚本写。"
fi
