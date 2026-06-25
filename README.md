# thetafarmer

用 AI 做中国商品期权波动率套利。每天扫描，有信号下单，无信号训练。所有交易记录公开。

## 在做什么

- 商品期权虚值信用价差（卖方）
- IV 波动率均值回归套利
- 工具全部开源：扫描器、分析器、风控面板

## 仓库结构

```
journal/         每日交易日志，每笔盈亏可查
unified_scanner.py   多品种统一扫描器
drill_system.py      期权直觉训练系统
risk_dashboard.py    风控面板
Natenberg.md         学习笔记
```

## 原则

实盘记录。公开 commit。不表演，只记录。
