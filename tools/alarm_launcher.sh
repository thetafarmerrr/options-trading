#!/bin/bash
# 早起闹钟 wrapper —— 由 ~/Library/LaunchAgents/com.goldopt.alarm.plist 在每天 8:10 调用
# 职责：语音 + 弹窗提醒起床。不依赖 Claude 会话、不依赖终端，纯 launchd 到点触发。
# 前提：同 iv_collector_launcher.sh —— /bin/bash 需在 系统设置→隐私与安全性→完全磁盘访问 授权，
#       否则 launchd 读不到 ~/Documents 下本脚本（EPERM/exit 126）。

LOG_FILE="$HOME/Library/Logs/goldopt_alarm.log"
mkdir -p "$(dirname "$LOG_FILE")"

# 要改时间：改 plist 的 StartCalendarInterval，重载即可（见收尾说明）
{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') 闹钟触发 ==="
    # 语音提醒 ×5（Meijia 美佳·台湾腔女声）
    for i in 1 2 3 4 5; do
        say -v Meijia "早上八点十分，起床了。拉开窗帘见光，今天不要睡午觉。"
        sleep 4
    done
    # 弹窗通知（声音 Glass）
    osascript -e 'display notification "8:10 起床锚：拉开窗帘见光 10 分钟，午觉只许 14:00 前 20 分钟" with title "🌅 起床闹钟" sound name "Glass"'
    echo "say×5 + notification 已触发"
} >> "$LOG_FILE" 2>&1
