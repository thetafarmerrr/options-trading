#!/bin/bash
# 安装教练飞书轰炸定时任务（macOS launchd）
# 用法：bash tools/install_coach_cron.sh
# 卸载：bash tools/install_coach_cron.sh --uninstall

set -e

AGENT_DIR="$HOME/Library/LaunchAgents"
PREFIX="com.manman.coach-nudge"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/coach_nudge.py"
PYTHON="$(which python3)"

# 定时表：slot hour minute
# 每行格式："slot hour minute"
SLOT_LINES=(
    "morning       9 30"
    "scanner_miss  9 30"
    "drill_b   10 30"
    "sinclair  11  0"
    "afternoon 14  0"
    "d_drill   15  0"
    "english   16  0"
    "wrapup    17  0"
    "evening   20  0"
    "d_check   21  0"
)

install_one() {
    local slot="$1" hour="$2" minute="$3"
    local plist="$AGENT_DIR/${PREFIX}.${slot}.plist"

    cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PREFIX}.${slot}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT}</string>
        <string>${slot}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${hour}</integer>
        <key>Minute</key>
        <integer>${minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/${PREFIX}.${slot}.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/${PREFIX}.${slot}.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

    launchctl bootstrap gui/$(id -u) "$plist" 2>/dev/null || true
    printf "   ✅ %-12s → 每天 %02d:%02d\n" "$slot" "$hour" "$minute"
}

uninstall_one() {
    local slot="$1"
    local plist="$AGENT_DIR/${PREFIX}.${slot}.plist"
    launchctl bootout gui/$(id -u) "$plist" 2>/dev/null || true
    rm -f "$plist"
    echo "   ❌ ${slot}"
}

status_one() {
    local slot="$1"
    local plist="$AGENT_DIR/${PREFIX}.${slot}.plist"
    if [ -f "$plist" ]; then
        echo "   ✅ ${slot}  — 已安装"
    else
        echo "   ⬚ ${slot}  — 未安装"
    fi
}

install() {
    echo "📦 安装教练飞书定时任务..."
    echo "   Python: $PYTHON"
    echo "   脚本:   $SCRIPT"
    echo ""

    mkdir -p "$AGENT_DIR"

    for line in "${SLOT_LINES[@]}"; do
        read -r slot hour minute <<< "$line"
        install_one "$slot" "$hour" "$minute"
    done

    echo ""
    echo "🎯 全部安装完成。10 个定时任务已就位。"
    echo "   bash tools/install_coach_cron.sh --status   查看状态"
    echo "   bash tools/install_coach_cron.sh --uninstall  卸载"
    echo ""
    echo "测试发送：python3 tools/coach_nudge.py morning"
}

do_uninstall() {
    echo "🗑️  卸载所有教练定时任务..."
    for line in "${SLOT_LINES[@]}"; do
        read -r slot _ _ <<< "$line"
        uninstall_one "$slot"
    done
    echo ""
    echo "🗑️  全部卸载完成。"
}

do_status() {
    echo "📋 教练定时任务状态："
    echo ""
    for line in "${SLOT_LINES[@]}"; do
        read -r slot _ _ <<< "$line"
        status_one "$slot"
    done
}

case "${1:-}" in
    --uninstall)
        do_uninstall
        ;;
    --status)
        do_status
        ;;
    *)
        install
        ;;
esac
