# thetafarmer — 中国商品期权量化交易系统

用 AI 辅助做中国商品期权波动率套利。每天扫描，有信号下单，无信号训练。工具全部开源，交易记录公开。

> **当前阶段**：S1 · Layer 1 卖方信用价差。详见 `MASTER_PLAN.md`。

---

## 策略覆盖

| 层 | 策略 | 状态 |
|----|------|------|
| Layer 1 | 卖 Put/Call 信用价差 | ✅ 实盘 |
| Layer 2 | 买 Call/Put 价差 + 跨式/宽跨式 | 🟡 工具就绪，等 IV 数据 ≥ 60 天激活 |

---

## 工具链

### 每日核心

| 工具 | 用途 | 命令 |
|------|------|------|
| `unified_scanner.py` | 多品种信用价差扫描（卖方）+ 买方机会扫描 | `python3 tools/unified_scanner.py` / `--buyer` |
| `iv_collector.py` | IV 数据采集 + 五条环境打分 + 买方视角 | `python3 tools/iv_collector.py` |
| `drill_system.py` | 8 模块交易训练（A-H），每天 B + 轮转 | `python3 tools/drill_system.py B` |
| `daily_quiz.py` | 每日验收题，commit 前 3 道 | `python3 tools/daily_quiz.py` |
| `monitor_stop.py` | 实时持仓监控 + 飞书告警 | `python3 tools/monitor_stop.py` |

### 数据分析

| 工具 | 用途 | 命令 |
|------|------|------|
| `sharpe_calc.py` | Sharpe 比率、回撤、胜率、月盈亏 | `python3 tools/sharpe_calc.py` |
| `monthly_report.py` | 月度 P&L 报告生成（Markdown） | `python3 tools/monthly_report.py --month 2026-07` |
| `surface_viewer.py` | IV 曲面摘要 + 3D 可视化 | `python3 tools/surface_viewer.py --plot` |
| `event_calendar.py` | 中国商品期货高影响事件日历 | `python3 tools/event_calendar.py` |

### 训练模块（drill_system.py）

| 模块 | 内容 | 轮转 |
|------|------|------|
| A | 链面扫异常 | 周一/四 |
| B | 价差判断（可/警/不） | **每天** |
| C | 天气→策略（卖方+买方场景） | 周二/六 |
| D | Greek 场景直觉（双方头寸） | 周日 |
| E | 信用价差扫描 | — |
| F | 持仓管理 | 周五 |
| G | 腿位判断（虚/近/实） | — |
| H | 买方方向判断 | 周四 |

---

## 文档

| 文档 | 内容 |
|------|------|
| `MASTER_PLAN.md` | 总计划：S1→S3 三阶段 × Layer 1→5 五策略层 |
| `.claude/CLAUDE.md` | 每日规则 + 教练角色 + 签到模板 |
| `docs/monitoring-rules.md` | 卖 Put/Call + 买 Call/Put 四象限规则 |
| `glossary.md` | 期权术语对照（中英） + Tastytrade 高频短语 |
| `trade_log.md` | 所有交易完整记录 |
| `mistakes.md` | 错误教训库 |
| `content-backlog.md` | 内容创意池 |
| `docs/tail-events.md` | 50+ 尾部事件 |
| `docs/learning_plan_v3.md` | 历史学习计划（已归档） |

---

## 每日流程

```
签到 → 任务单
1. python3 tools/unified_scanner.py          # 扫描
2. python3 tools/iv_collector.py             # IV + 环境定性
3. python3 tools/drill_system.py B           # 训练
4. Sinclair 阅读                              # 期权教材
5. 英文：Mike 系列 + 跟读 + 90s 炸弹 + 笔译
6. 影响力：本周有可发的吗？（Twitter + Substack）
7. python3 tools/daily_quiz.py               # 验收题
8. journal/ + commit + push
```

周六：复盘 + Reddit 回帖 + 本周碎片整理发出。不推进新内容。

---

## 数据文件

| 文件 | 内容 | 积累目标 |
|------|------|---------|
| `data/iv_history.csv` | 每日 IV/HV 数据 | 60 天（当前 4/60） |
| `drill_state/history.json` | 训练历史 | 持续 |
| `data/quiz_history.json` | 验收题记录 | 持续 |
| `reports/` | 月度报告输出 | 每月 |

---

## 原则

- 实盘记录。公开 commit。不表演，只记录。
- D 门 0/20 > 一切。归零 = 重头来。
- 工具是名片，P&L 是证据。AI 能写代码，不能替你交易。
