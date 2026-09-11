#!/bin/bash
# PreToolUse hook：git commit / git add 前扫描敏感信息
# 触发条件：Bash 命令包含 git commit / git add
# 退出 2 = 阻断提交 | 退出 0 = 放行
#
# 2026-09-11 改造：本脚本不再自己写扫描逻辑，改为调用
#   tools/sensitive_guard.py       （唯一真相源）
# 原因：原版只扫 5 个硬编码路径、data/ 从未被看过、只看内容不看路径
#       （二进制 PDF 里 grep 不出姓名）——8/17 的 25 天泄漏就是这么来的。
#
# 注意：本 hook 只覆盖【教练】跑的 git commit。
#      用户自己在终端敲 git commit 走的是 tools/git-hooks/pre-commit
#      （由 git config core.hooksPath tools/git-hooks 启用）。
#      两个入口共用同一份扫描逻辑。

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)

# 不相关的命令直接放行
if ! echo "$COMMAND" | grep -qE '\bgit\s+(commit|add\b)'; then
    exit 0
fi

PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$PROJECT_DIR" ] || PROJECT_DIR="/Users/mm/Documents/AIcode/gold_option_tools"

OUT=$(python3 "$PROJECT_DIR/tools/sensitive_guard.py" 2>&1)
RC=$?

if [ "$RC" -ne 0 ]; then
    echo "$OUT" >&2
    exit 2   # 2 = 阻断，stderr 回给 Claude
fi

exit 0
