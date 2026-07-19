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
| 价差 | Spread / Ask-Bid Spread |
| 价差% | Spread % = (Ask - Bid) / Bid × 100% |
| 净价（价差整体报价）| Net Price / Net Debit(付)·Net Credit(收) |
| 买量/卖量（挂单量）| Bid Size / Ask Size |

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
| IV 分位 / IV 排名 | IV Percentile / IV Rank | — |
| IV > HV → 期权贵（卖方优势）| IV > HV → options expensive → sell |
| IV < HV → 期权便宜（买方优势）| IV < HV → options cheap → buy |

## 波动率结构

| 中文 | English | 一句话 |
|------|---------|--------|
| 正向市场（远月IV > 近月）| Contango | 市场平静，远期保险更贵 |
| 倒挂（近月IV > 远月）| Backwardation | 恐慌——大家都在抢近期保险 |
| 偏度 | Skew | OTM Put IV > OTM Call IV，下跌风险被定价更高 |
| 期限结构 | Term Structure | IV 随到期时间变化的曲线 |
| 波动率微笑 | Volatility Smile | 不同行权价的 IV 连成 U 形曲线 |
| 杠杆效应 | Leverage Effect | 价格跌 → IV 涨（价格驱动波动率） |
| 波动率反馈 | Volatility Feedback | IV 涨 → 恐慌抛售 → 价格跌（波动率反驱价格） |
| 尖峰厚尾 | Leptokurtic / Fat Tails | 极端行情发生频率远高于正态分布预测 |
| 波动率聚集 | Volatility Clustering | 大波动后跟大波动，小波动后跟小波动 |
| Parkinson 波动率 | Parkinson HV | 用日内最高/最低价估计波动率，比收盘价法准 5 倍 |

## 量价分析

| 中文 | English | 一句话 |
|------|---------|--------|
| HV₂₀ vs HV₆₀ | 20d vs 60d HV | 20d > 60d = 近期波动加剧，卖方谨慎 |
| ⚡ 标记 | HV gap alert | iv_collector 自动标记：HV₂₀−HV₆₀ > 3% |
| IV 斜率 | IV Slope | 近 3 天 IV 斜率：⬆加速 ⬇回落 ➡企稳 |
| 放量真贵 | Real IV expansion | 放量+IV高 → 分歧真实，不追卖 |
| 缩量虚高 | Fake IV spike | 缩量+IV高 → 虚张声势，可卖 |

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
| 成交量 | Volume |
| 持仓量 | Open Interest (OI) |
| 现手（最近一笔成交量）| Last Traded Size |
| 组合单 / 价差单 | Combo Order / Spread Order |
| 分腿（先平一腿再平另一腿）| Legging (In / Out) |

## 决策与纪律

| 中文 | English | 一句话 |
|------|---------|--------|
| 结果偏差 | Outcome Bias / Resulting | 用结果好坏评判决策，而非当时的赔率——错的 |
| 期望值 | Expected Value (EV) | 胜率×盈利 − 败率×亏损，负 EV 别做 |
| 尾部风险 | Tail Risk | 小概率大损失（USDA 跳空那种）|
| 事件驱动 | Event-Driven | 报告/数据前后的波动 |

## 策略（补充）

| 中文 | English | 一句话 |
|------|---------|--------|
| 铁秃鹰 | Iron Condor | 同时卖出 OTM Put Spread + OTM Call Spread，收双份权利金 |
| 铁蝴蝶 | Iron Butterfly | ATM Short Straddle 加两端保护腿 |
| 备兑看涨 | Covered Call | 持标的同时卖 Call |
| 现金担保 Put | Cash-Secured Put | 预留全额现金卖 Put（卖方入门首选）|
| 对角价差 | Diagonal Spread | 不同行权价 + 不同到期日的组合 |

## 期权估值

| 中文 | English | 一句话 |
|------|---------|--------|
| 内在价值 | Intrinsic Value | 立即行权能拿到的钱（ITM 才有，OTM = 0）|
| 外在价值 / 时间价值 | Extrinsic Value / Time Value | Premium − Intrinsic Value，到期归零的部分 |
| 时间流逝 / 时间衰减 | Time Decay / Theta Decay | DTE 越短 Theta 越快，卖方的主要收入来源 |
| 平值点 / 中间价 | Mid Price / Mark | (Bid + Ask) / 2，理论参考价 |

## 交易执行与持仓管理

| 中文 | English | 一句话 |
|------|---------|--------|
| 行权 | Exercise | 买方行使权利（买入/卖出标的） |
| 指派 / 被指派 | Assignment | 卖方被要求履约——买方行权，你被配对 |
| 提前指派 | Early Assignment | 到期前被指派（美式期权，深度 ITM 或分红前） |
| 距到期天数 | Days to Expiration (DTE) | Tastytrade 偏好 30-45 DTE 开仓 |
| 盈亏平衡点 | Breakeven | Strike ± Premium，期权到期时不赚不赔的价格 |
| 最大盈利 | Max Profit | = 净权利金收入（信用价差卖方） |
| 最大亏损 | Max Loss | = 价差宽度 − 净权利金收入（信用价差卖方） |
| 移仓 | Roll / Rolling | 平仓当前头寸 + 开同方向更远月/不同行权价的仓位 |
| 向上移（Roll 成更高行权价）| Roll Up | 同样方向，调到更高行权价 |
| 向下移（Roll 成更低行权价）| Roll Down | 同样方向，调到更低行权价 |
| 展期（Roll 到更远月）| Roll Out | 同样行权价，拉到更远到期日 |
| 移仓收钱 | Roll for a Credit | Tastytrade 铁律：移仓必须是净收权利金 |
| 提前止盈 | Take Profit / Manage Winner | Tastytrade 标准：到 50% 最大盈利时平仓 |
| 固定风险 vs 无限风险 | Defined Risk vs Undefined Risk | 价差=固定风险；裸卖=无限风险 |

## 风险与概率

| 中文 | English | 一句话 |
|------|---------|--------|
| 盈利概率 | Probability of Profit (POP) | 到期时有盈利的概率 |
| 被触碰概率 | Probability of Touching | 到期前任一时刻碰到某价位的概率（≈ 2×Delta） |
| 预期波动幅度 | Expected Move | 市场对标的在未来一段时间内波动幅度的定价（≈ Strike × IV × √DTE/365） |
| 针形风险 | Pin Risk | 到期日标的恰好收盘在行权价上——卖方不知道会不会被指派 |
| 隔夜跳空风险 | Overnight Gap Risk | 收盘后到第二天开盘之间发生大跳空（卖方最大的风险源） |
| 行权指派风险 | Assignment Risk | 被提前指派后仓位移到裸腿（腿序反了） |
| 滑点 | Slippage | 实际成交价和预期价的差，流动性差的时候更严重 |
| 成交 | Fill / Getting Filled | 订单执行成功的口语说法 |

## 账户与资金

| 中文 | English | 一句话 |
|------|---------|--------|
| 购买力 | Buying Power | 账户能开新仓位的上限 |
| 购买力占用 | Buying Power Reduction (BPR) | 开一个仓位被锁住的资金 |
| 名义价值 | Notional Value | 标的当前价格 × 合约乘数 |
| 组合保证金 | Portfolio Margin | 按组合整体风险算保证金（比 Reg-T 宽松） |
| Delta 中性 | Delta Neutral | 多腿组合 Delta 互相抵消 ≈ 0，不受标的方向影响 |
| Beta 加权 | Beta-Weighting | 把所有持仓的 Delta 换算成对标普 500 的 Beta 暴露 |

## Tastytrade / Mike 高频短语

| 英文 | 中文 | 什么时候听到 |
|------|------|-------------|
| "Sell premium" / "Be a net seller of premium" | 做权利金的净卖方 | 每集都会说 |
| "Collect theta" / "Collect theta decay" | 收时间价值 | 解释为什么卖方的胜率高 |
| "Trade small, trade often" | 每次下小仓位，高频交易 | Tastytrade 核心口诀 |
| "Stay small" | 控制单笔仓位（1-5%） | 风控重复提醒 |
| "Mechanical approach" | 机械化执行，不凭感觉 | 进场/离场规则的哲学 |
| "Manage winners early" | 盈利到了就平，不要贪 | 50% 止盈背后的逻辑 |
| "Manage at 21 DTE" | 持有到距到期 21 天时关仓 | Tastytrade 标准离场规则 |
| "Put the probabilities on your side" | 让概率站在你这边 | 解释为什么卖虚值期权胜率高 |
| "IV tends to overstate RV" | 隐含波动率倾向于高估实际波动 | 卖方存在的理论基础 |
| "The market is mean-reverting" | 市场有均值回归倾向 | 解释波动率回归 |
| "All else being equal..." | 其他条件不变的情况下… | Mike 开始一段分析的口头禅 |
| "Think of it this way..." | 换一种方式理解… | Mike 切换解释角度的信号 |
| "At the end of the day..." | 说到底/归根结底 | 总结要点时的过渡语 |

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
>
> **Mike 系列看视频时**：碰到表里没有的术语或短语，签到时说一声，随时追加。

---

## 句型库

So any contracts that are just out there open, they haven't been assigned, they haven't been exercised, they haven't been closed. So how I like to think of it is basically open contracts that are out there that I can become a part of in some way. So volume is essentially tracking the number of contracts that were closed or traded that day。

1. 无伤大雅的口语松散点（日常聊天完全能用）
just out there open
纯口语，书面应改为 outstanding open（金融标准术语：未平仓）；out there 属于口头填充词，正式文本要删掉。
they haven't been assigned, they haven't been exercised, they haven't been closed
重复主语 they，口语没问题；书面可合并精简。
how I like to think of it is basically open contracts
轻微句式杂糅：主干是 What I think of it is...，原句省略引导词 What，口语允许，正式写作需要补全。
that I can become a part of in some way
语义模糊：读者看不出 “参与开仓做多 / 做空”，属于口语省略细节。
2. 一处轻微语法瑕疵（书面会扣分）
how I like to think of it is basically open contracts
主语从句缺失先行引导词，规范书面必须改为：
What I like to think of them as is basically outstanding open contracts
原句 how 使用错误：how 表 “方式”，此处想表达 “我对它们的理解是…”，要用 what。
3. 专业术语小不规范（交易语境）
描述未平仓合约行业标准词：outstanding contracts / open interest contracts，不用 open contracts that are out there
volume 定义句语法无错，金融表述准确：成交量 = 当日成交平仓 / 换手合约数，这句是整段最标准、无问题的一句。


So again, open interest is the number of contracts open or outstanding.

In any case, as long as this transaction happens and this contract opens between these
two people, open interest will increase by one. So, this is important because when people are opening contracts and closing contracts,open interest can actually go up and go
down. And in some cases, it can even stay flat,which we'll get into a little bit later.

on the next slide here, we'll talk about volume. And volume is essentially the number of contracts traded per day. So essentially, if Brad sells two puts to Sarah or if Sarah buys two puts from Brad, then there's going to be two ticks for volume going into that volume container. So what's interesting with volume is that volume can really only go up. Unlike open interest where it can go up, go down, or stay the same, since volume is really only tracking the number of sheer transactions that are completed, it can only
go up. So even if a contract is open and closed, it's still going to count as volume for each of those transactions.

when we look at hedging, we're basically looking at minimizing risk. So when we're looking at minimizing risk, when we're talking about long stock, I've got this full circle here and it's signifying directional risk. So if I'm just buying long stock and I'm fully exposed with long stock, I'm also fully exposed to that directional risk. However, if I use a covered call instead, which is buying stock and selling a call against it, which havet differing assumptions in terms of direction, what I do is I take a chunk of that directional risk out of the equation and it reduces that directional risk for me. So, this is great for a few reasons and we're going to talk about


### 解释概念
- Open interest is the number of contracts open or outstanding.  （Mike E08）
- Volume is the number of contracts traded per day.  （Mike E08）
- Unlike open interest, volume can only go up — it tracks sheer transactions.  （Mike E08）
- Unlike open interest where it can go up, go down, or stay the same, volume can only go up — it's only tracking the number of sheer transactions.  （Mike E08, Volume vs OI）


### 给判据 / 下标准
- I want to make sure that either open interest or volume has over a thousand contracts open or a thousand contracts traded that day.  （Mike E05 后半段）
- That's just going to give me a good indication that there's a fair market for that specific strike.  （Mike E05 后半段）
- The more options that are traded, the more people agree upon the bid and ask spread, which is going to make that spread narrow and give me a more fair market price.  （Mike E05 后半段）

### 自产·笔译修正
- Today all three short call spread signals got killed: IV is below HV, so I'd be selling insurance at a discount.  （7/17 笔译修正）
- Even though the environment score was 4/5, I still passed.  （7/17 笔译修正）
- The IV–HV check outranks the environment check — there's no variance premium to sell.  （7/17 笔译修正）
