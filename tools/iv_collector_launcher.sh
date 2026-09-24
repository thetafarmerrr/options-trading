#!/bin/bash
# IV Collector 自动调度 wrapper
# 由 ~/Library/LaunchAgents/com.goldopt.iv-collector.plist 在 09:15 / 09:30 / 14:50 调用
#（9/5 从 09:30/14:56 改为三采，对齐 --watch：独立短进程逐点触发，避开常驻被休眠冻结）
# 前提：/bin/bash 需在系统设置→隐私与安全性→完全磁盘访问权限 内授权，
# 否则 launchd 读不到 ~/Documents 下本脚本（EPERM/exit 126，9/5 根因）。
#
# 职责：跳过周末 + 跳过休市日 + 日志记录。窗口判定由 iv_collector.py 的 _detect_window() 自动完成。
#
# ── 9/24 加：交易日历守卫 ──────────────────────────────────────────────
# 原守卫只看星期（DAY>5）→ 9/25 中秋是周五会被放行，launchd 会在休市日采三次、
# 污染 Data 门的数据源 data/iv_history.csv。
# 实测 7/13–9/24 共 54 个日期 0 污染（该窗口无工作日假期，原守卫从未被真正考验）。
# 日历源 = akshare tool_trade_date_hist_sina（自更新）。落本地缓存，正常路径纯 grep 不联网。
# 等价性：商品期货休市日历 = A 股日历（各交易所均依证监会通知、证监会依国务院安排 → 日期一致，
#         差异仅在每日交易时段）。2026 各交易所公告已核对：中秋 9/25–9/27、国庆 10/1–10/7。
# ⚠️ 日历当前覆盖至 2026-12-31。走到边界会走下方 🔴 fail-open 分支并留日志（不静默停采）。
# 缓存缺失 / 超 30 天 / 今天超出覆盖 → 自动重拉。

set -e

PROJECT_DIR="/Users/mm/Documents/AIcode/gold_option_tools"
LOG_FILE="$PROJECT_DIR/data/iv_collector_scheduler.log"
CAL_FILE="$PROJECT_DIR/data/trade_calendar.txt"   # akshare 交易日历缓存，一行一个日期
TODAY=$(date '+%Y-%m-%d')

# ── 1. 周末 ──
if [ "$(date +%u)" -gt 5 ]; then
    exit 0
fi

# ── 2. 日历按需刷新（正常路径不联网）──
need_refresh=0
if [ ! -s "$CAL_FILE" ]; then
    need_refresh=1
else
    if [ -n "$(find "$CAL_FILE" -mtime +30 2>/dev/null)" ]; then
        need_refresh=1
    fi
    if [ "$TODAY" \> "$(tail -1 "$CAL_FILE")" ]; then
        need_refresh=1
    fi
fi

if [ "$need_refresh" -eq 1 ]; then
    if /opt/miniconda3/bin/python3 -c "
import akshare as ak
print('\n'.join(sorted(str(x) for x in ak.tool_trade_date_hist_sina()['trade_date'])))
" > "$CAL_FILE.tmp" 2>/dev/null; then
        if [ -s "$CAL_FILE.tmp" ]; then
            mv "$CAL_FILE.tmp" "$CAL_FILE"
        else
            rm -f "$CAL_FILE.tmp"
        fi
    else
        rm -f "$CAL_FILE.tmp"
    fi
fi

# ── 3. 交易日判定 ──
if [ ! -s "$CAL_FILE" ]; then
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') ⚠️ 无交易日历且刷新失败 → 放行采集（fail-open）===" >> "$LOG_FILE"
elif grep -qx "$TODAY" "$CAL_FILE"; then
    :   # 交易日 → 继续
elif [ "$TODAY" \> "$(tail -1 "$CAL_FILE")" ]; then
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') 🔴 日历覆盖不到今天（覆盖至 $(tail -1 "$CAL_FILE")）→ 无法判定，放行采集（fail-open）===" >> "$LOG_FILE"
else
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') 非交易日（休市）→ 跳过 ===" >> "$LOG_FILE"
    exit 0
fi

# ── 4. 采集 ──
cd "$PROJECT_DIR"

{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
    /opt/miniconda3/bin/python3 tools/iv_collector.py
    echo ""
} >> "$LOG_FILE" 2>&1
