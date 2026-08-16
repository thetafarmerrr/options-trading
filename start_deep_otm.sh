#!/usr/bin/env bash
# 盘前一条命令：换月 discover → 启动采集（#15 换月机制闭环）
# 用法：./start_deep_otm.sh
# set -e：discover 失败（akshare 网络异常）→ 中止，不用旧 config 硬跑
set -euo pipefail
cd "$(dirname "$0")"

echo "📡 [1/2] discover 换月（拉当前期权链总持仓，重选活跃月/最虚档）…"
python3 tools/deep_otm_collector.py --discover

echo "📡 [2/2] 启动 8 时点采集…"
python3 tools/deep_otm_collector.py
