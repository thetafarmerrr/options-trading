#!/bin/bash
# 每日快速扫描 — 别名: daily
# 用法: ./daily.sh 或 ./daily.sh 10000 (指定本金)

CAPITAL=${1:-10000}
cd /Users/mm/Documents/AIcode/gold_option_tools
python3 unified_scanner.py --capital "$CAPITAL" --quick
