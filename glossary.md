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

## BSM 模型

| 中文 | English | 含义 |
|------|---------|------|
| 对数正态分布 | Log-normal Distribution | BSM 核心假设：价格变动服从对数正态 |
| 肥尾 | Fat Tails | 极端事件频率远超正态分布预测 |
| 随机游走 | Random Walk | BSM 假设价格连续变动无跳跃 |
| Ito 引理 | Ito's Lemma | BSM 推导用的随机微积分工具（Layer 5 前不需要）|

## 波动率估计器（Sinclair 第 2 章）

| 中文 | English | 说明 |
|------|---------|------|
| 收盘价-收盘价估计量 | Close-to-Close Estimator | 只用收盘价算 HV，信息损失大 |
| Garman-Klass 估计量 | Garman-Klass Estimator | 加入开盘价，效率更高。不处理隔夜跳空 |
| Rogers-Satchell-Yoon 估计量 | RSY Estimator | 允许漂移项（趋势），仍未处理跳空 |
| Yang-Zhang 估计量 | Yang-Zhang Estimator | 允许趋势+隔夜跳空，效率 8-14 倍，理论最优 |
| 已实现波动率 | Realized Volatility (RV) | 加总高频收益率平方，精度最高 |
| 漂移项 | Drift | 价格的平均趋势方向（μ），GBM: dS=μSdt+σSdW |
| 跳空 | Jump/Gap | 价格的不连续变动，隔夜或盘中突发事件 |
| 离散取样偏差 | Discrete Sampling Bias | 观察到的极差≤真实极差，取样越粗低估越严重 |
| 年化因子 | Annualization Factor | 中国商品期货 √242，美股 √252 |
| 波动率锥 | Volatility Cone | 多窗口 HV 的分位数分布图 |

## IV Rank vs IV Percentile

| 中文 | English | 说明 |
|------|---------|------|
| IV 排名 | IV Rank | (当前IV-最低IV)/(最高IV-最低IV)，极值敏感 |
| IV 百分位 | IV Percentile | 低于当前IV的天数/总交易日，更平滑 |
| 绝对值陷阱 | Absolute Value Trap | 窄幅品种只看 Rank 不看绝对值会误判 |

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

## Mike 121 集 · 策略名词速查

> 从 121 集标题提炼。看视频前扫一眼，耳朵不陌生。

### 出现 ≥5 次的策略（每集都会碰到）

| English | 中文 | 出现集数 |
|---------|------|---------|
| Credit Spread / Vertical Credit Spread | 信用价差 / 垂直信用价差 | E27, 散布各集 |
| Debit Spread / Vertical Debit Spread | 借方价差 / 垂直借方价差 | E14, E51, E60 |
| Covered Call | 备兑看涨 | E02, E12, E111 |
| Iron Condor | 铁秃鹰 | E04, E50, E62, E103, E115 |
| Short Strangle | 卖出宽跨式 | E13, E16, E75 |
| Poor Man's Covered Call (PMCC) | 穷人备兑 | E17, E29, E101 |
| Calendar Spread | 日历价差 | E08, E106 |
| Jade Lizard | 翡翠蜥蜴 | E47, E69, E94, E112 |

### 出现 2-4 次的策略

| English | 中文 | 说明 |
|---------|------|------|
| Short Straddle | 卖出跨式 | E23, E89 — ATM 卖 Call+Put |
| Broken Wing Butterfly | 断翅蝴蝶 | E30, E54, E83 — 不对称 Iron Fly |
| Big Lizard | 大蜥蜴 | E82, E94, E118 — Jade Lizard 变体 |
| Poor Man's Covered Put (PMCP) | 穷人备兑 Put | E61, E104, E108 |
| Covered Put | 备兑看跌 | E38, E119, E120 |
| Put Ratio Spread | Put 比率价差 | E41 |
| Iron Fly | 铁蝴蝶 | E34 |
| Chicken Iron Condor | 小鸡铁秃鹰 | E20 — 窄幅 Iron Condor |

### Mike 高频动词（听视频时抓这些词）

| English | 中文 | 典型语境 |
|---------|------|---------|
| Sell premium / Be a net seller | 做权利金卖方 | "We want to sell premium when IV is high" |
| Collect theta | 收时间价值 | "You're collecting theta decay every day" |
| Manage winners | 止盈管理 | "Manage winners early, at 50% of max profit" |
| Roll (out/up/down) | 移仓/滚动 | "Roll the untested side" |
| Hedge | 对冲 | "How to hedge your positions" E06 |
| Adjust / Adjustment | 调整 | E04, E13, E39, E64 |
| Close (a trade) | 平仓 | E53 |
| Get filled / Fill | 成交 | E78 — "Getting options filled" |
| Finance (a spread) | 融资/降低成本 | E113 — 用 leg 补贴另一腿 |
| Lock in (losses) | 锁定亏损 | E40 — "Avoid locking in losses" |
| Drag | 拖累 | E121 — "Stock drag" 期权拖累现货收益 |
| Overstate | 高估 | "IV tends to overstate RV" |
| Mean-revert | 均值回复 | E84 — IV mean reversion |

### Mike 高频名词（除 Greek 外）

| English | 中文 | 第一次出现 |
|---------|------|-----------|
| Probability of Profit (POP) | 盈利概率 | E52 |
| Expected Move | 预期波幅 | 散布各集 |
| Return on Capital (ROC) | 资本回报率 | E100 |
| Notional Value | 名义价值 | E67 |
| Buying Power / BPR | 购买力/购买力占用 | E07 小账户 |
| Defined Risk | 固定风险 | E107 |
| Undefined Risk | 无限风险 | E36 裸卖 |
| Assignment / Assignment Risk | 指派/指派风险 | E71, E95, E98 |
| Dividend Risk | 红利风险 | E70 |
| Contrarian Mindset | 反向思维 | E93 |
| Market Awareness | 市场意识 | E99 |
| Checklist | 核对清单 | E97, E111, E114 |

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

### 表达"降低/消除某个因素"
- I take a chunk of that directional risk out of the equation.  （Mike E06, covered call 讲解）
- It reduces that directional risk for me.  （Mike E06）

### 表达"完全暴露于某风险"
- I'm fully exposed to that directional risk.  （Mike E06, 讲裸持股票）


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
- The sell call on MA609 was killed because IV < HV, so the only EXEC of the day went unexecuted.  （7/19 笔译修正：got killed↗gotten killed, executed↗executed）
- The buy call spread on SR609 shows a 9.53:1 risk/reward ratio, with IV at the 5th percentile — a textbook buyer's window.  （7/19 笔译修正：P5≠P95, classicific→textbook）


## 语言学碎片（周六推送）

### a/an 不是语法规定——是口腔经济学
两个元音撞在一起舌头打结（"a apple"），塞一个辅音 n 就顺了（"an apple"）。古英语的 ān（=one）末尾有 n，后来丢掉了——但只丢在辅音前面，元音前面留着。所以不是"规则规定元音前用 an"，而是人的嘴淘汰了拗口的版本。中文也有——"天哪"不是"天啊"（前字 n 尾+"啊"→"哪"）。

### ATM IV ≠ OTM IV：波动率偏度（Skew）
- **ATM IV** = 市场对标的**整体波动幅度**的定价。全部参与者竞价。反映"会晃多狠"。
- **OTM 偏度（Skew）** = 市场参与者在**哪一侧买保险/卖保护**。反映"谁在害怕、在哪边付溢价"。
- **权益市场**：Put skew（怕跌→OTM Put 溢价）。崩盘保护是刚需。
- **商品市场**：常出现 Call skew（生产商有现货→卖 OTM Call 锁定出货价→压低价）。这不是"偏好"，是套保刚需。
- **结论**：ATM IV-HV 溢价=卖方窗口开了。但**卖哪条腿看偏度**——call wing 被生产者占了位置就别卖 Call。
- 来源：7/20 甲醇 C2850 折价 vs ATM 溢价 + Sinclair Ch5 微笑/偏度

- I've been trading on the do follow page for probably between six and seven months. （Mike E07）
- If a bad trade goes against me, I want to make sure that it doesn't totally wipe out or paralyze my account because I traded too large. （Mike E07）
- Master those core structures thoroughly through consistent practice until you fully understand every component of the trade lifecycle. （Mike E07）

## 句型库（每日 Mike 挖矿，按场景分组）

### 定义期权概念
- A call option is essentially the right to buy 100 shares of stock at a certain strike price.  （Mike E03, 0:45）

### 定义Put期权
- A put option is essentially the right to sell 100 shares of stock at a certain strike price.  （Mike E02, 0:30）
- Buying a put is a bearish strategy — we want the stock price to go down. Inversely, selling a put is a bullish strategy — we want the stock price to go up.  （Mike E02）

### 买方 vs 卖方特征
- When we're buying options, we have negative theta — the theta decay is bad for us. When we're selling options, we have positive theta — the theta decay is good for us.  （Mike E02）
- Buying options: unlimited profit, limited loss, low probability of profit. Selling options: limited profit, capped loss, high probability of profit.  （Mike E02）
- When selling a put, we can be profitable in two out of three ways: stock goes up, or stock stays flat. Only one out of three ways makes us lose: stock drops below our strike.  （Mike E02）

### 说明因果关系
- That's because if we sell an option here and the option decays over time, if we can buy it back for a lower amount, the difference in those prices is going to be our profitability.  （Mike E02）

### 解释Theta
- When we're selling calls, we have positive theta — we actually benefit from the decay of the option's price.  （Mike E03, 4:20）

### 保险类比
- The longer I hold insurance coverage, the higher the total premium will be because there's more days until that policy expires.  （Mike E03, 7:10）
