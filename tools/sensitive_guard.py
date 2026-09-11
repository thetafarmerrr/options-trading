#!/usr/bin/env python3
"""提交前敏感信息闸 —— 单一真相源，被两个 hook 共用。

立：2026-09-11（结算单 PDF 在公开仓库躺了 25 天的事故后）
背景：旧 hook 有三个洞 —— ① 只扫 5 个硬编码路径，data/ 从未被看过
      ② 只看内容不看路径，二进制 PDF 里 grep 不出「曹迪」
      ③ 挂在 Claude Code 上，只挡教练，用户自己在终端敲 git commit 不生效
本脚本同时修三个洞，并让两个入口共用同一份逻辑，杜绝两处飘移。

被谁调用：
    tools/git-hooks/pre-commit            git 原生钩子（对任何人任何方式生效）
    .claude/hooks/check-sensitive.sh      Claude Code PreToolUse（管教练）

用法：
    python3 tools/sensitive_guard.py              扫暂存区（commit 时，默认）
    python3 tools/sensitive_guard.py --files a b  扫指定文件
    python3 tools/sensitive_guard.py --audit      全量体检：扫全部已跟踪文件 + 报告长期不一致

退出码：0 放行 / 1 命中拒绝
逃生舱：git commit --no-verify（明确知道自己要放行时才用，别当默认）
"""

import os
import re
import subprocess
import sys

# ── 闸 1：路径黑名单 ────────────────────────────────────────────────
# 为什么按路径拦：二进制内容无法文本扫描，grep 不出里面的姓名/账号，
# 只能按「这类文件根本不该进 git」来拦。8/17 的 PDF 就是这么漏的。
PATH_BLOCK = [
    (r"(^|/)settlement",              "结算单：真实姓名+客户号+资金账号+交易编码"),
    (r"\.(pdf|png|jpe?g|gif|zip|tar|gz|xlsx?|docx?|pptx?)$",
                                      "二进制文件：内容无法扫描，一律不进 git"),
    (r"(^|/)\.env",                   "环境变量文件：凭据"),
    (r"credential",                   "凭据文件"),
    (r"ctp-config",                   "CTP 配置：账号/AuthCode"),
    (r"\.con$",                       "CTP 连接配置"),
    (r"yuan-yongjian",                "第三方付费策略文档"),
    (r"(^|/)mistakes\.md$",           "私有：错误记录（本意不进公开库）"),
    (r"conversation-log\.md$",        "私有：完整对话记录（本意不进公开库）"),
]

# ── 闸 2：内容模式 ──────────────────────────────────────────────────
# 扫暂存区文本内容。宁可多报几次，不可漏一次 —— 误报的成本是你改一行正则，
# 漏报的成本是又一份真实账号在公开仓库躺几周。
CONTENT_BLOCK = [
    ("账号类标识",
     re.compile(r"(客户号|资金账号|交易编码|AccountID|InvestorID|tradingcode)[^\n]{0,12}\d{6,}")),
    ("手机号",
     re.compile(r"(?<![\d.])1[3-9]\d{9}(?![\d.])")),
    ("凭据硬编码",
     re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|auth_?code|CTP_PASSWORD)\b"
                r"\s*[:=]\s*[\"'][^\"'\s]{6,}[\"']")),
]

BINARY_EXT = re.compile(r"\.(pdf|png|jpe?g|gif|zip|gz|tar|xlsx?|docx?|pptx?|so|dylib|exe)$", re.I)


def sh(args):
    return subprocess.run(args, capture_output=True, text=True).stdout


def staged_files():
    """暂存区里新增/修改的文件（删除的不算）"""
    out = sh(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    return [f for f in out.split("\n") if f.strip()]


def staged_new_files():
    """暂存区里【新增】的文件"""
    out = sh(["git", "diff", "--cached", "--name-only", "--diff-filter=A"])
    return [f for f in out.split("\n") if f.strip()]


def tracked_files():
    return [f for f in sh(["git", "ls-files"]).split("\n") if f.strip()]


def matches_path_block(path):
    for pat, why in PATH_BLOCK:
        if re.search(pat, path, re.I):
            return why
    return None


def is_binary(path):
    if BINARY_EXT.search(path):
        return True
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return False


def read_text(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if b"\x00" in raw[:8192]:
            return None
        return raw.decode("utf-8", "ignore")
    except OSError:
        return None


def is_ignored(path):
    r = subprocess.run(["git", "check-ignore", "--no-index", "-q", path],
                       capture_output=True)
    return r.returncode == 0


def check(files, new_files):
    """返回 (阻断项, 提示项)"""
    blocks, notes = [], []

    for f in files:
        # 闸 1 · 路径
        why = matches_path_block(f)
        if why:
            blocks.append((f, f"路径黑名单 —— {why}"))
            continue

        # 闸 2 · 二进制（按类型，避免读文件）
        if is_binary(f):
            blocks.append((f, "二进制文件 —— 内容无法扫描，一律不进 git"))
            continue

        # 闸 3 · 内容
        text = read_text(f)
        if text is None:
            continue
        for name, pat in CONTENT_BLOCK:
            for m in pat.finditer(text):
                # 只报位置和形态，不打印命中的实际值
                line_no = text[:m.start()].count("\n") + 1
                blocks.append((f, f"内容命中【{name}】第 {line_no} 行（值不打印，自行查看）"))

    # 闸 4 · 新增文件却匹配 .gitignore —— 降级为【提示，不阻断】
    #
    # 为什么降级（2026-09-11 首次自测发现）：
    #   .gitignore 里现存多条失效规则（data/scanner_log/、data/*.csv、data/*.json…），
    #   它们覆盖的文件早已被跟踪 —— 规则从写下那天就没生效过。
    #   若闸 4 阻断，则每天新增的 scanner_log 会被拦 → 三天后用户就会 --no-verify，
    #   等于把整道闸关掉。宁可少拦一类，不可逼出绕行习惯。
    #   真正危险的东西（settlement*/*.pdf/.env/凭据）由闸 1 硬拦，不依赖本闸。
    #   未生效规则的完整清单 → python3 tools/sensitive_guard.py --audit
    for f in new_files:
        if is_ignored(f):
            r = subprocess.run(["git", "check-ignore", "-v", "--no-index", f],
                               capture_output=True, text=True).stdout.strip()
            rule = r.split("\t")[0].split(":")[-1] if r else "(规则名未解析出)"
            notes.append((f, f"新增文件命中 .gitignore 规则 `{rule}` —— "
                             f"若这条规则是有意跟踪的，应删掉规则而非绕过闸"))

    return blocks, notes


def rule_of(path, tracked=False):
    """返回命中该文件的 .gitignore 规则名（tracked=True 时必须带 --no-index）"""
    args = ["git", "check-ignore", "-v"] + (["--no-index"] if tracked else []) + [path]
    r = subprocess.run(args, capture_output=True, text=True).stdout.strip()
    return r.split("\t")[0].split(":")[-1] if r else None


def audit():
    """规则体检：每条 .gitignore 规则【实际在挡什么】+【有没有历史遗留】

    为什么这么设计（2026-09-11 教练踩坑后重写）：
      旧版只报「已跟踪但匹配规则」的文件，把规则报成"失效的"。
      但规则对【未跟踪】文件照常生效 —— 那才是它们本来的用途。
      实测：data/*.csv 看着"失效"（12 个已跟踪命中），实际正挡着
      2.4M 的 deep_otm 数据。按旧报告删规则 = 下次 git add -A 全部扫进库。
      教训：判断规则死活，必须看【未跟踪侧的工作量】，不能只看已跟踪侧。
    """
    untracked = [f for f in sh(["git", "ls-files", "--others"]).split("\n") if f.strip()]
    tracked = tracked_files()

    # 规则 → (挡住的未跟踪文件, 已跟踪命中)
    live = {}
    for f in untracked:
        r = rule_of(f, tracked=False)
        if r:
            size = os.path.getsize(f) if os.path.exists(f) else 0
            live.setdefault(r, {"blocking": [], "legacy": [], "bytes": 0})["blocking"].append(f)
            live[r]["bytes"] += size
    for f in tracked:
        r = rule_of(f, tracked=True)
        if r:
            live.setdefault(r, {"blocking": [], "legacy": [], "bytes": 0})["legacy"].append(f)

    total_b = sum(v["bytes"] for v in live.values())
    total_n = sum(len(v["blocking"]) for v in live.values())

    print(f"\n📋 .gitignore 规则体检")
    print(f"   规则共挡住 {total_n} 个未跟踪文件 / {total_b / 1024 / 1024:.1f} MB "
          f"—— 这就是它们的真实工作量")
    print()
    print(f"   {'规则':<26} {'在挡':>10} {'体积':>8}  {'历史遗留':>8}  判定")
    print("   " + "-" * 66)
    for rule, v in sorted(live.items(), key=lambda x: -x[1]["bytes"]):
        nb, nl = len(v["blocking"]), len(v["legacy"])
        mb = v["bytes"] / 1024 / 1024
        size_s = f"{mb:.1f}M" if mb >= 0.1 else f"{v['bytes'] / 1024:.0f}K"
        if nb:
            verdict = "✅ 有效，保留"
        elif nl:
            verdict = "⚪ 空转（无害，可留可删）"
        else:
            verdict = "⚪ 未命中任何文件"
        print(f"   {rule:<26} {nb:>10} {size_s:>8}  {nl:>8}  {verdict}")

    legacy_total = sum(len(v["legacy"]) for v in live.values())
    print()
    print(f"   ⚠️  历史遗留 {legacy_total} 个「规则说忽略、实际已跟踪」——"
          f"这是 git 的正常语义（.gitignore 不追溯已跟踪文件），")
    print(f"      不代表规则失效。删规则前先看它「在挡」那列的体积。")
    print(f"      真要改用追踪状态 → git rm --cached <文件>（那是另一件事，别混）")


def main():
    args = sys.argv[1:]

    if "--audit" in args:
        audit()
        return 0

    if "--files" in args:
        i = args.index("--files")
        files = args[i + 1:]
    else:
        # 不在 git 仓库里就直接放行（避免误伤）
        if subprocess.run(["git", "rev-parse", "--git-dir"],
                          capture_output=True).returncode != 0:
            return 0
        files = staged_files()

    if not files:
        return 0

    # --files 是内容/路径专项体检，不判断"是否新增"（否则每行都会被闸 4 提示一遍）
    new_files = [] if "--files" in args else staged_new_files()
    blocks, notes = check(files, new_files)

    if notes:
        print(f"\n⚠️  提示（不阻断）：{len(notes)} 个新增文件命中未生效的 .gitignore 规则")
        seen_rules = set()
        for f, why in notes:
            rule = why.split("`")[1] if "`" in why else "?"
            if rule not in seen_rules:
                seen_rules.add(rule)
                print(f"    规则 `{rule}`  ← 例：{f}")
        print("    （完整清单：python3 tools/sensitive_guard.py --audit）")

    if not blocks:
        return 0

    print("\n" + "=" * 68)
    print("⛔ 提交被拦下 —— 敏感信息闸")
    print("=" * 68)
    for f, why in blocks:
        print(f"\n  🔴 {f}")
        print(f"     {why}")
    print("\n" + "-" * 68)
    print("  怎么处理：")
    print("    · 文件不该进 git      → git reset HEAD <文件>（并补 .gitignore）")
    print("    · 内容是真敏感信息    → 删掉/脱敏后再提交")
    print("    · 确认无误要放行      → git commit --no-verify（明确知道自己要放行时才用）")
    print("=" * 68 + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
