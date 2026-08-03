#!/bin/bash
# PreToolUse hook：git commit 前扫描敏感信息
# 触发条件：Bash 命令包含 "git commit"
# 退出 2 = 阻断提交 | 退出 0 = 放行

# 从 stdin 读 tool call JSON
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)

# 只拦截 git commit / git add
if ! echo "$COMMAND" | grep -qE '\bgit\s+(commit|add\b)'; then
    exit 0
fi

PROJECT_DIR="/Users/mm/Documents/AIcode/gold_option_tools"
FOUND=0

# 匹配 key=value 形式的真实凭据值（不拦 BrokerID 66666 等公开值）
# AuthCode=xxx / CTP_PASSWORD: yyy / api_key=zzz / CTP_USER_ID=数字
PATTERNS='(AuthCode|CTP_PASSWORD)\s*[:=]\s*\S+|CTP_USER_ID\s*[:=]\s*[0-9]{5,}|(api[_-]?key|token|secret)\s*[:=]\s*\S+'

for FILE in "$PROJECT_DIR/docs/conversation-log.md" "$PROJECT_DIR"/journal/*.md "$PROJECT_DIR"/docs/ctp-config.md "$PROJECT_DIR"/trade_log.md; do
    [ -f "$FILE" ] || continue
    HITS=$(grep -inE "$PATTERNS" "$FILE" 2>/dev/null)
    if [ -n "$HITS" ]; then
        echo ""
        echo "⛔ 敏感信息在 $FILE :"
        echo "$HITS"
        echo "   提交前移除 AuthCode/密码/账号/Token 的实际值。"
        echo "   允许保留'已脱敏'等说明性文字。"
        FOUND=1
    fi
done

if [ "$FOUND" -eq 1 ]; then
    exit 2
fi

exit 0
