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
| Delta 中性 | Delta Neutral | Delta 正负对冲后总和为零 |
| Omega（杠杆倍数）| Omega / Leverage | 标的价格涨 1%，期权涨百分之几 |
| 买卖权平价 | Put-Call Parity | C + K·e^(-rT) = P + S，同一行权价 Call/Put 的无套利关系 |
| 买方 Greeks | Buyer Greeks | Δ+/Γ+/Θ−/V+（正 Gamma、负 Theta、正 Vega）|
| 卖方 Greeks | Seller Greeks | Δ−/Γ−/Θ+/V−（负 Gamma、正 Theta、负 Vega）|

## 波动率

| 中文 | English | 缩写 |
|------|---------|------|
| 隐含波动率 | Implied Volatility | IV |
| 历史波动率 | Historical Volatility | HV |
| 已实现波动率 | Realized Volatility | RV |
| IV 排名 | IV Rank / IVR | IVR |
| IV 百分位 | IV Percentile / IVP | IVP |
| 均值回归 | Mean Reversion | — |
| 收盘-收盘波动率 | Close-to-Close Volatility | 最基础的 RV 算法 |
| Parkinson 估计器 | Parkinson Estimator | 用日内高低点算波动率，比收盘-收盘更准 |
| IV > HV → 期权贵（卖方优势）| IV > HV → options expensive → sell |
| IV < HV → 期权便宜（买方优势）| IV < HV → options cheap → buy |
| 波动率风险溢价 | Volatility Risk Premium / Variance Premium | IV 通常高于 RV，卖方赚的就是这个 |

## BSM 模型

| 中文 | English | 含义 |
|------|---------|------|
| 对数正态分布 | Log-normal Distribution | BSM 核心假设：价格变动服从对数正态 |
| 肥尾 | Fat Tails | 极端事件频率远超正态分布预测 |
| 随机游走 | Random Walk | BSM 假设价格连续变动无跳跃 |
| Ito 引理 | Ito's Lemma | BSM 推导用的随机微积分工具（Layer 5 前不需要）|

## 波动率结构

| 中文 | English |
|------|---------|
| 正向市场（远月IV > 近月）| Contango |
| 倒挂（近月IV > 远月）| Backwardation |
| 偏度 | Skew |
| 期限结构 | Term Structure |
| 波动率微笑 | Volatility Smile |

## 期权价格构成

| 中文 | English | 含义 |
|------|---------|------|
| 内在价值 | Intrinsic Value | 立即行权能拿到的钱。虚值 = 0 |
| 时间价值 | Time Value / Extrinsic Value | 期权价格 − 内在价值。虚值期权全部是时间价值 |
| 盈亏平衡点 | Break-even Point | 到期时不亏不赚的标的价格 |
| 到期盈亏图 | Expiration P&L Diagram | 横轴标的价格、纵轴盈亏的到期曲线 |

## 估值与数据

| 中文 | English | 含义 |
|------|---------|------|
| 活跃度加权 | Activity Weighting | iv_collector 找 ATM：bid 越高 + Call≈Put → 评分越高 |
| 主力合约 | Front-Month Contract / Active Contract | 交易最活跃的到期月 |
| 安全网（5% 偏离回退）| Safety Net | 今天 ATM 偏离昨天 >5% → 用昨天的，防开盘流动性假象 |

## 持仓管理

| 中文 | English |
|------|---------|
| 三档监控体系 | Three-Tier Monitoring System |
| 六步进场检查 | Six-Step Entry Checklist（第6步：赚什么钱）|
| 指派风险 | Assignment Risk |
| 末日轮 | Expiration Day Gamma Explosion |
| 近值过滤 | Near-the-Money Filter |
| 提前平仓 | Early Close / Exit Before Expiration |

## 策略

| 中文 | English | Layer |
|------|---------|-------|
| 裸卖 | Naked Sell / Short Naked | — |
| 信用价差 | Credit Spread | L1 |
| 铁鹰 | Iron Condor（卖 Put 价差 + 卖 Call 价差）| L2 |
| 跨式（同时买 Call + Put）| Straddle | L2 |
| 宽跨式（买 OTM Call + OTM Put）| Strangle | L2 |
| 卖出跨式 | Short Straddle | L2 |
| 卖出宽跨式 | Short Strangle | L2 |
| 牛市看涨价差 | Bull Call Spread | L2 |
| 熊市看跌价差 | Bear Put Spread | L2 |
| 日历价差 | Calendar Spread | L3 |
| 蝶式 | Butterfly | L3 |
| 比率价差 | Ratio Spread | L3 |
| 盒式价差 | Box Spread | L5 |

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
| 换月/移仓换月 | Rollover（持仓从近月移到远月）|
| 行权价间距 | Strike Interval（如豆粕 50 点、铁矿石 10 点）|
| 挂单量/买量 | Bid Volume（bid 上的手数，不是成交量）|
| 浮盈/浮亏 | Unrealized P&L / Paper P&L |
| 滑点 | Slippage（下单到成交之间价格变了）|
| 做市商 | Market Maker |

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

---

## 波动率估计器（Sinclair 第 2 章）

| 中文 | English | 说明 |
|------|---------|------|
| 收盘价-收盘价估计量 | Close-to-Close Estimator | 只用收盘价算 HV，信息损失大 |
| Parkinson 估计量 | Parkinson Estimator | 用最高/最低价，效率 5 倍。假设无漂移+连续交易 |
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

## 认知功能（MBTI）

| 中文 | English | 说明 |
|------|---------|------|
| 内倾思考 | Introverted Thinking (Ti) | 内部逻辑一致性，建系统框架 |
| 外倾直觉 | Extraverted Intuition (Ne) | 模式识别，发散联想 |
| 内倾情感 | Introverted Feeling (Fi) | 内在价值观一致性 |
| 外倾感觉 | Extraverted Sensing (Se) | 即时感官体验 |
| 外倾思考 | Extraverted Thinking (Te) | 执行、外部结构、效率 |
| 内倾感觉 | Introverted Sensing (Si) | 经验内化、习惯形成（执行弱项）|
| Te 先于 Ti | Te Before Ti | 操作原则：先做再分析 |

## 英语学习方法

| 中文 | English | 说明 |
|------|---------|------|
| 堆量法 | Volume Stacking | Ne 驱动：大量输入替代精拆，零摩擦启动 |
| 影子跟读 | Shadowing | 跟着音频张嘴，不停不休 |
| 90 秒炸弹 | 90-Second Bomb | 定时张嘴说，不给 Ti 编辑时间 |
