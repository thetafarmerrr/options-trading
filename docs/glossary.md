# 期权量化术语对照

> 从你的笔记中提取。每天扫描器和训练都会碰到，不需要背。

---

## 基础概念

| 中文 | English | 出现在哪 |
|------|---------|---------|
| 看涨期权 | Call Option / Call | 扫描器、链面 |
| 看跌期权 | Put Option / Put | 扫描器、链面 |
| 行权价 | Strike Price / Strike | 链面第一列 |
| 到期日 | Expiration Date / Expiry | 链面 |
| 权利金 | Premium | 你每笔交易的收入/成本 |

## 实值·平值·虚值

| 中文 | English | 含义 |
|------|---------|------|
| 实值 | In the Money (ITM) | 立即行权能赚钱 |
| 平值 | At the Money (ATM) | 行权价 ≈ 标的价格 |
| 虚值 | Out of the Money (OTM) | 行权价比标的价格差很远 |

## 报价

| 中文 | English |
|------|---------|
| 买价 | Bid |
| 卖价 | Ask / Offer |
| 价差 | Spread / Bid-Ask Spread |
| 价差% | Spread % = (Ask - Bid) / Bid × 100% |

## 希腊字母

| 中文 | English | 一句话 |
|------|---------|--------|
| Delta | Delta | 标的涨1元，期权涨几元 |
| Gamma | Gamma | 标的涨1元，Delta 变多少 |
| Theta | Theta | 过1天，期权掉几元（买方亏，卖方赚）|
| Vega | Vega | 波动率涨1%，期权涨几元 |
| Rho | Rho | 利率涨1%，期权涨几元（商品期权忽略）|

## 波动率

| 中文 | English | 缩写 |
|------|---------|------|
| 隐含波动率 | Implied Volatility | IV |
| 历史波动率 | Historical Volatility | HV |
| 已实现波动率 | Realized Volatility | RV |
| IV > HV → 期权贵（卖方优势）| IV > HV → options expensive → sell |
| IV < HV → 期权便宜（买方优势）| IV < HV → options cheap → buy |

## 波动率结构

| 中文 | English |
|------|---------|
| 正向市场（远月IV > 近月）| Contango |
| 倒挂（近月IV > 远月）| Backwardation |
| 偏度 | Skew |
| 期限结构 | Term Structure |
| 波动率微笑 | Volatility Smile |

## 策略

| 中文 | English |
|------|---------|
| 裸卖 | Naked Sell / Short Naked |
| 信用价差 | Credit Spread |
| 跨式（同时买 Call + Put）| Straddle |
| 宽跨式（买 OTM Call + OTM Put）| Strangle |
| 牛市看涨价差 | Bull Call Spread |
| 熊市看跌价差 | Bear Put Spread |
| 日历价差 | Calendar Spread |
| 盒式价差 | Box Spread |

## 头寸方向

| 中文 | English |
|------|---------|
| 买入（做多）| Long / Buy |
| 卖出（做空）| Short / Sell |
| 买方（付权利金）| Buyer / Holder |
| 卖方（收权利金）| Seller / Writer |

## 市场术语

| 中文 | English |
|------|---------|
| 标的资产 | Underlying / Underlying Asset |
| 期货 | Futures |
| 合约乘数 | Multiplier / Contract Size |
| 保证金 | Margin |
| 止损 | Stop Loss |
| 平仓 | Close Position |

## 绩效

| 中文 | English |
|------|---------|
| 胜率 | Win Rate |
| 盈亏比 | Profit-Loss Ratio / P&L Ratio |
| 夏普比率 | Sharpe Ratio |
| 最大回撤 | Maximum Drawdown / Max DD |
| 权利金收入 | Premium Collected |
| 到期归零 | Expire Worthless（卖方最理想的结果）|

---

> 每天扫描器输出里出现的英文词，这张表都有。碰到了回来看一眼，三天就记住了。
