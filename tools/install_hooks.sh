#!/bin/sh
# 启用敏感信息闸的 git 原生钩子。
#
# 为什么需要这一步：core.hooksPath 存在【本地 .git/config】里，不进 git。
# 换机器 / 重新克隆后必须重跑本脚本，否则闸是哑的。
# 新建仓库或迁移后，第一件事跑这个。
#
# 用法：sh tools/install_hooks.sh

set -e
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

chmod +x tools/git-hooks/pre-commit
git config core.hooksPath tools/git-hooks

echo "✅ 敏感信息闸已启用"
echo "   core.hooksPath = $(git config --get core.hooksPath)"
echo "   钩子本体       = tools/git-hooks/pre-commit"
echo "   扫描逻辑       = tools/sensitive_guard.py"
echo ""
echo "   自测：sh tools/git-hooks/pre-commit ; echo \$?   （空暂存区应为 0）"
echo "   体检：python3 tools/sensitive_guard.py --audit"
echo "   逃生：git commit --no-verify"
