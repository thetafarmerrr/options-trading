#!/bin/bash
# IV Collector 自动调度 wrapper
# 由 ~/Library/LaunchAgents/com.goldopt.iv-collector.plist 在 09:15 / 09:30 / 14:50 调用
#（9/5 从 09:30/14:56 改为三采，对齐 --watch：独立短进程逐点触发，避开常驻被休眠冻结）
# 前提：/bin/bash 需在系统设置→隐私与安全性→完全磁盘访问权限 内授权，
# 否则 launchd 读不到 ~/Documents 下本脚本（EPERM/exit 126，9/5 根因）。
#
# 职责：跳过周末 + 日志记录。窗口判定由 iv_collector.py 的 _detect_window() 自动完成。

set -e

DAY=$(date +%u)  # 1=Mon ... 7=Sun
if [ "$DAY" -gt 5 ]; then
    exit 0
fi

PROJECT_DIR="/Users/mm/Documents/AIcode/gold_option_tools"
LOG_FILE="$PROJECT_DIR/data/iv_collector_scheduler.log"

cd "$PROJECT_DIR"

{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
    /opt/miniconda3/bin/python3 tools/iv_collector.py
    echo ""
} >> "$LOG_FILE" 2>&1
