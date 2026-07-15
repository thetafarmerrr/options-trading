# 签到任务单模板

> 签到时读取此文件。**每条操作必须写完整命令 + 路径 + 判据 + 下一步动作。**
> 用户拿到任务单→照做→回来报结果。不允许出现"见某文件"的跳转——所有信息内联。

## 输出格式

```
## 📋 YYYY-MM-DD 签到 · 周X

### 🔴 纪律计数器：0 / 20（7/10 归零：分腿顺序反+裸空）
### 💧 干旱计数器：X 天（≥5→回顾参数，≥10→系统排查）

### 四道门速览
| 门 | 进度 |
|----|------|
| T | 6/20 |
| D | 0/20 🔴 |
| Data | 5/60 |
| K | 🟢 已过 |

---

| # | 做什么 | 具体操作 |
|---|--------|---------|
| 1 | **Scanner** | `cd ~/Documents/AIcode/gold_option_tools && python3 tools/unified_scanner.py`。看输出 [EXEC] 部分：有信号→复制出来，进六步进场（monitoring-rules.md 第三节）；无信号→输出末尾会提示操作规程，记下干旱天数 |
| 2 | **IV 采集** | `python3 tools/iv_collector.py`。看每个品种五条打分：≥3 条有利=可做卖方；≥3 条不利=今天不交易。看买方视角：哪些品种 IV 分位 <30%→买方黄金窗口 |
| 3 | **Drill B** | `python3 tools/drill_system.py B`。每天必做。报正确率和速度 |
| 3b | **Drill 轮转** | `python3 tools/drill_system.py <今日模块>`。周三=H(买方方向)，周四=A(链面)，周五=F(持仓管理)，周六=D(Greek)，周日=D，周一=A，周二=C(天气→策略)。报分数 |
| 3c | **D-Drill** | `python3 tools/d_drill.py`。17题，答「做/不做」+一句原因。原因写规则内容不是编号（写"下跌趋势不卖Put"不写"禁止8"） |
| 4 | **Sinclair Ch5** | 打开《波动率交易》第5章。今天从上次停的地方继续。不要从头读——带着今天 Scanner 实际碰到的问题进去找答案。读完在 journal 写 3-5 行：今天读到的怎么用在明天的扫描判断上？ |
| 4b | **Douglas** | 打开《Trading in the Zone》每天 5 页。不用写笔记 |
| 5a | **英语·视频** | 打开 Mike 播放列表https://youtube.com/playlist?list=PLPVve34yolHY43YaBegHMzN9WjrTnQfFr 从上次停的地方继续 1 集。①看画面+字幕抓大意→②张嘴跟读不停。不重播不查词 |
| 5b | **英语·挖矿** | 从刚看的视频抓 3 个整句，追加到 `glossary.md` 底部 `## 句型库` 区块。格式：`- 整句  （来源）`。按场景分组，已有场景用现成的，没有就新建 |
| 5c | **英语·炸弹** | 张嘴 90 秒说刚看的内容——不停、不改、不查词。录音→语音转文字→看一眼和原文的差异，不修改 |
| 5d | **英语·笔译** | 把今天 Scanner 的结论翻译成英文，2-3 句。例：No EXEC signals today. IV remains below P30 across all five products. Wait. |
| 6 | **影响力** | 今天 Scanner/IV/训练/D-Drill 里有什么值得截个图配一句话的？有→记在 journal 草稿区标日期，周末发。没有→过。例：PTA IV 分位 86% 但 IV<HV，假信号——来源：iv_collector + 五条卡分析 |
| 7 | **收尾** | ① `python3 tools/daily_quiz.py` 3 题验收→② 把今天训练分数、Scanner结论、学到的东西写进 `journal/YYYY-MM-DD.md`→③ `git add -A && git commit -m "YYYY-MM-DD" && git push` |

> 特殊行——干旱 ≥3 天时插入：
| * | **无信号日操作** | 打开 `trade_log.md`，随机抽一笔历史交易，重读进场离场逻辑。问自己：现在回头看当时该做吗？写一行答案进 journal。或打开 `docs/tail-events.md` 随机选一个事件，用今天的 IV 数据推演如果今天发生会怎样 |

> 周六额外行：
| * | **语言学碎片** | 教练推送一个「为什么英语是这样」的点，10 min 读完，决定存不存 glossary |
| * | **本周碎片整理** | 把本周标了日期的草稿整理成 2-3 条 Twitter，发出 |
```

## 签到时必须做到

1. 从 memory 读取最新数字（纪律计数、干旱天数、门进度、训练分）填入模板
2. 根据当天周几确定 Drill 轮转模块
3. 干旱 ≥3 天 → 插入无信号日操作行
4. 周六 → 插入语言学碎片 + 碎片整理行
5. 不出现「见某文件」——所有操作细节内联
