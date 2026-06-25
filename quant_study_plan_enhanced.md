# 量化学习计划增强版：从入门到权威

> 基于原计划的补充与扩展，目标不是"会写策略"而是成为量化金融领域的专业人士。

---

## 📊 原计划核心问题与修复

原计划偏"技术工具人"路线。以下是需要注入的关键模块：

---

## 🔴 并行轨道一：金融理论（贯穿24个月）

这个轨道是原计划最大缺失。量化权威的根基在于金融经济学，而非仅仅编程。

### 书单（按阅读顺序）

| 阶段 | 书籍 | 时间 | 核心内容 |
|------|------|------|----------|
| 基础 | 《Options, Futures, and Other Derivatives》Hull | 第3-6个月 | 衍生品定价圣经，必读必做习题 |
| 基础 | 《Investments》Bodie, Kane, Marcus | 第3-6个月 | 资产定价、组合理论 |
| 中级 | 《Active Portfolio Management》Grinold & Kahn | 第8-12个月 | **量化权威必读**，信息率、alpha/beta分离 |
| 中级 | 《Quantitative Equity Portfolio Management》Chincarini | 第12-15个月 | 股票多因子实操 |
| 进阶 | 《Advances in Financial Machine Learning》Lopez de Prado | 第13-18个月 | 金融ML独有挑战：标签、回测过拟合 |
| 进阶 | 《Machine Learning for Asset Managers》Lopez de Prado | 第15-18个月 | 浓缩版，先读这本 |
| 高阶 | 《Stochastic Calculus for Finance II》Shreve | 第14-18个月 | 连续时间金融，衍生品定价核心 |
| 高阶 | 《Market Microstructure in Practice》Lehalle | 第16-20个月 | 订单簿、流动性、执行算法 |
| 参考 | 《Econometric Analysis of Cross Section and Panel Data》Wooldridge | 第10-14个月 | 计量经济学，因子研究必备 |
| 参考 | 《The Elements of Statistical Learning》Hastie | 第10-14个月 | ML理论圣经 |

### 每月金融理论任务

| 月份 | 阅读任务 | 习题/实践 |
|------|----------|-----------|
| 3 | Hull 第1-5章（期货、远期） | 课后奇数题 |
| 4 | Hull 第6-10章（期权基础） | 用Python实现BS定价 |
| 5 | Hull 第11-15章（二叉树、希腊字母） | 计算期权希腊字母 |
| 6 | Hull 第16-20章（波动率微笑、VaR） | 实现隐含波动率曲面 |
| 7 | Bodie 第5-10章（组合理论、CAPM） | 实现有效前沿 |
| 8 | Bodie 第11-15章（APT、EMH） | 因子模型回测 |
| 9 | Grinold & Kahn 第1-5章 | 信息率计算框架 |
| 10 | Grinold & Kahn 第6-10章 | 实现alpha组合模型 |
| 11 | Grinold & Kahn 第11-14章 | 交易成本建模 |
| 12 | Chincarini 第1-5章 | 多因子框架实践 |
| 13 | Lopez de Prado (AMLA) 第1-5章 | 标签方法实现 |
| 14 | Lopez de Prado (AMLA) 第6-10章 | 回测过拟合检测 |
| 15 | Shreve I 复习 + 新读 Lopez de Prado (AFML) 第1-4部分 | 随机微积分+ML应用 |
| 16 | Shreve II 第1-3章 | 鞅定价理论 |
| 17 | Shreve II 第4-6章 | 利率模型、跳跃过程 |
| 18 | Lehalle 第1-5章 | 订单簿建模 |
| 19 | Lehalle 第6-10章 | 执行算法 |
| 20 | Wooldridge 后半部分 | 面板数据实战 |
| 21 | Hastie 第7-10章 | 模型评估与选择 |
| 22-24 | 论文精读期（见下文） | — |

---

## 🔴 并行轨道二：竞赛与行业认可

权威需要外部验证。按时间线安排：

| 时间 | 竞赛/活动 | 目标 |
|------|-----------|------|
| 第4-5个月 | LeetCode 200题熟练 | 算法面试基础 |
| 第6-8个月 | Kaggle Jane Street Market Prediction | Top 30% |
| 第9-11个月 | WorldQuant Challenge | Gold 级别 |
| 第12-14个月 | Kaggle Optiver Trading Competition | Top 10% |
| 第15-17个月 | 发表第一篇量化相关博客/文章 | 建立个人品牌 |
| 第18-20个月 | 开源量化框架/tool | GitHub 100+ stars |
| 第20-22个月 | 量化金融会议投稿（QuantCon等） | 行业曝光 |
| 第22-24个月 | 撰写量化研究白皮书/论文 | 实质性研究输出 |

---

## 🔴 并行轨道三：实盘经验（第13个月起）

这是区分"回测选手"和"真正量化员"的分水岭：

| 阶段 | 内容 | 资金规模 |
|------|------|----------|
| 第13-15个月 | 模拟交易，严格记录 | $0 |
| 第16-18个月 | 小额实盘（自营账户） | $1,000-5,000 |
| 第19-21个月 | 策略迭代，风控系统 | $5,000-20,000 |
| 第22-24个月 | 系统化实盘运营 | $20,000+ |

**关键要求**：
- 每笔交易记录：入场理由、出场理由、情绪状态
- 每月出损益报告 + 归因分析
- 回测 vs 实盘偏差记录（最重要的学习材料）

---

## 📅 第三阶段：金融理论+策略研发（原第12-16个月）— 详细展开

### 📍 2026年12月（第11个月）：多因子模型系统

**目标**：构建完整的因子研究系统

| 周 | 主题 | 具体内容 | 关键资料 |
|----|------|----------|----------|
| W1 | 因子分类 | 价值、动量、质量、低波、规模 | 《Your Complete Guide to Factor-Based Investing》Swedroe |
| W2 | Alpha因子构建 | 从学术论文到可交易因子 | 复现3篇经典因子论文 |
| W3 | 因子组合 | IC分析、因子加权、正交化 | Grinold & Kahn 第7-8章 |
| W4 | 因子回测系统 | 构建完整因子研究平台 | 输出：可复用的因子研究框架 |

**核心论文精读（本月完成3篇）**：
1. Fama & French (1993) — 三因子模型
2. Carhart (1997) — 动量因子
3. Fama & French (2015) — 五因子模型

---

### 📍 2027年1月（第12个月）：Barra风险模型

**目标**：掌握机构级风险管理

| 周 | 主题 | 具体内容 | 关键资料 |
|----|------|----------|----------|
| W1 | 风险模型基础 | 协方差估计、风险因子 | MSCI Barra 文档 |
| W2 | 行业和风格因子 | 构建中国市场的Barra模型 | 复现 CNE5 模型 |
| W3 | 风险归因 | 组合风险分解 | 《Quantitative Risk Management》 |
| W4 | 组合优化 | 约束条件下的最优组合 | cvxpy 实现 |

---

### 📍 2027年2月（第13个月）：期权定价与波动率

**目标**：掌握衍生品定价的数值方法

| 周 | 主题 | 具体内容 | 关键资料 |
|----|------|----------|----------|
| W1 | Black-Scholes深入 | 推导、假设、局限 | Shreve II 第4章 |
| W2 | 数值方法 | 有限差分、蒙特卡洛 | 《Paul Wilmott on Quantitative Finance》卷2 |
| W3 | 波动率曲面 | 构建与套利 | Gatheral 《The Volatility Surface》 |
| W4 | 期权策略回测 | 波动率交易策略 | 实现straddle/strangle回测 |

---

### 📍 2027年3月（第14个月）：宏观量化与资产配置

**目标**：理解跨资产类别的量化策略

| 周 | 主题 | 具体内容 | 关键资料 |
|----|------|----------|----------|
| W1 | 资产配置理论 | Black-Litterman、风险平价 | 《Asset Management》Ang |
| W2 | 宏观因子 | 增长、通胀、流动性因子 | Bridgewater 全天候研究 |
| W3 | CTA策略 | 趋势跟踪、动量、carry | 《Following the Trend》Clenow |
| W4 | 跨资产策略开发 | 股票+债券+商品+外汇 | 构建多资产策略 |

---

### 📍 2027年4月（第15个月）：金融NLP与另类数据

**目标**：掌握非结构化金融数据分析

| 周 | 主题 | 具体内容 | 关键资料 |
|----|------|----------|----------|
| W1 | 文本数据获取 | SEC filing、新闻、社交媒体 | EDGAR API, FinnHub |
| W2 | NLP基础 | BERT、FinBERT 微调 | 《Natural Language Processing with Transformers》 |
| W3 | 情绪分析 | 构建金融情绪指标 | 论文：Tetlock (2007) |
| W4 | 另类数据项目 | 卫星图像、信用卡数据、供应链 | 实现一个另类数据策略 |

---

## 📅 第四阶段：高性能计算+系统架构（原第17-20个月）— 详细展开

### 📍 2027年5月（第16个月）：C++与低延迟

| 周 | 主题 | 具体内容 |
|----|------|----------|
| W1-2 | C++基础 | C++11/14/17核心特性、STL |
| W3-4 | C++量化应用 | 实现订单簿、简单回测引擎 |

**资料**：《A Tour of C++》Stroustrup + 《C++ Crash Course》

---

### 📍 2027年6月（第17个月）：Python性能优化

| 周 | 主题 | 具体内容 |
|----|------|----------|
| W1 | Cython/Numba | 加速计算密集型代码 |
| W2 | 并行计算 | multiprocessing、joblib、dask |
| W3 | 数据库 | TimescaleDB、ClickHouse 金融时序存储 |
| W4 | 数据管道 | Apache Kafka/Redpanda 实时数据流 |

---

### 📍 2027年7月（第18个月）：系统架构

| 周 | 主题 | 具体内容 |
|----|------|----------|
| W1-2 | 实时交易系统设计 | 事件驱动架构、状态机 |
| W3-4 | 构建执行系统 | 订单管理、风控检查、连接模拟交易所 |

---

### 📍 2027年8月（第19个月）：深度学习在量化中的应用

| 周 | 主题 | 具体内容 |
|----|------|----------|
| W1 | DNN/CNN | 用神经网络做价格预测 |
| W2 | LSTM/Transformer | 时序深度学习模型 |
| W3 | GNN | 图神经网络与股票关系图 |
| W4 | RL基础 | 强化学习与交易智能体 |

**资料**：Lopez de Prado (AFML) Part 3 + Deep Q-Networks 论文

---

## 📅 第五阶段：前沿研究+综合能力（原第21-24个月）— 详细展开

### 📍 2027年9月（第20个月）：市场微观结构

| 周 | 主题 | 具体内容 |
|----|------|----------|
| W1-2 | 订单簿建模 | Hawkes过程、LOB动力学 |
| W3-4 | 执行算法 | TWAP/VWAP、最优执行、Almgren-Chriss |

### 📍 2027年10月（第21个月）：高频交易基础

| 周 | 主题 | 具体内容 |
|----|------|----------|
| W1-2 | 高频策略 | 做市、套利、统计套利 |
| W3-4 | 回测陷阱 | 前视偏差、生存偏差、数据清洗 |

### 📍 2027年11月（第22个月）：加密货币量化

| 周 | 主题 | 具体内容 |
|----|------|----------|
| W1-2 | CEX/DEX | 中心化/去中心化交易所数据 |
| W3-4 | MEV与链上分析 | 三明治攻击、套利机器人 |

### 📍 2027年12月-2028年1月（第23-24个月）：综合能力

| 周 | 主题 |
|----|------|
| 第23个月 | 独立研究项目：自选课题深入3个月 |
| 第24个月 | 求职/面试准备 + 个人品牌建设 |

---

## 📚 每月必读论文清单（精选，累计50+篇）

### 经典必读（第3-8个月）
1. Markowitz (1952) — Portfolio Selection
2. Sharpe (1964) — CAPM
3. Fama (1970) — Efficient Market Hypothesis
4. Black & Scholes (1973) — Option Pricing
5. Fama & French (1993) — Three-Factor Model
6. Carhart (1997) — Momentum
7. Jegadeesh & Titman (1993) — Returns to Buying Winners
8. Fama & French (2015) — Five-Factor Model

### 量化策略与因子（第9-15个月）
9. Asness et al. (2013) — Value and Momentum Everywhere
10. Ang et al. (2006) — Downside Risk
11. Novy-Marx (2013) — Profitability
12. Frazzini & Pedersen (2014) — Betting Against Beta
13. Ibbotson et al. (2013) — Liquidity as an Investment Style
14. Daniel & Moskowitz (2016) — Momentum Crashes

### 金融ML（第13-18个月）
15. Lopez de Prado (2015) — The 7 Reasons Most ML Funds Fail
16. Bailey et al. (2014) — Pseudo-Mathematics and Financial Charlatanism
17. Bailey & Lopez de Prado (2014) — Deflated Sharpe Ratio
18. Gu, Kelly, Xiu (2020) — Empirical Asset Pricing via Machine Learning
19. Biais, Bisière, Bouvard, Casamatta (2019) — The Blockchain Folk Theorem

### 市场微观结构（第16-20个月）
20. Kyle (1985) — Continuous Auctions and Insider Trading
21. Glosten & Milgrom (1985) — Bid-Ask and Transaction Prices
22. Hendershott, Jones, Menkveld (2011) — Does Algorithmic Trading Improve Liquidity?
23. Biais, Foucault, Moinas (2015) — Equilibrium Fast Trading
24. Almgren & Chriss (2001) — Optimal Execution of Portfolio Transactions

### 前沿方向（第20-24个月）
25. Sirignano & Cont (2019) — Universal Features of Price Formation
26. Easley et al. (2020) — Microstructure in the Machine Age
27. Cong et al. (2021) — Tokenomics
28. Harvey & Liu (2021) — Lucky Factors

---

## 🎯 权威量化员能力模型检查清单

| 能力域 | 24个月后应达到的水平 | 检查 |
|--------|---------------------|------|
| Python | 熟练，numpy/pandas/sklearn精通 | ☐ |
| C++ | 能写生产级别回测引擎核心模块 | ☐ |
| SQL/数据库 | 能处理TB级金融数据 | ☐ |
| 线性代数/概率 | 能手推PCA、随机过程 | ☐ |
| 微积分/优化 | 能推导梯度下降、凸优化问题 | ☐ |
| 衍生品定价 | 能推导BS公式、理解随机微积分 | ☐ |
| 多因子模型 | 能独立设计因子回测系统 | ☐ |
| 机器学习 | 能处理金融数据特有的ML问题 | ☐ |
| 深度学习/RL | 了解并实现过基本模型 | ☐ |
| 市场微观结构 | 理解订单簿、执行算法 | ☐ |
| 实盘经验 | 至少12个月实盘记录 | ☐ |
| 竞赛成绩 | 至少1次Top 10% | ☐ |
| 研究输出 | 至少发表过1篇研究报告 | ☐ |
| 开源贡献 | 至少1个量化开源项目 | ☐ |
| 行业网络 | 参加过至少1次量化会议 | ☐ |

---

## ⚠️ 现实提示

1. **这份计划的强度是每天 8-12 小时**，等同于一份全职工作的强度，持续 24 个月。
2. **实际完成度可能在 60-70%**，但即使如此，也比 95% 的自学者走得远。
3. **到第 18 个月左右，你应该开始找量化实习/全职**，因为实盘经验和机构环境无法自学。
4. **权威不是终点**——即使在顶级对冲基金工作 10 年的人，也很少自称"权威"。这个过程本身就是你的护城河。

---

## 📅 建议的每日节奏

| 时段 | 内容 |
|------|------|
| 08:00-10:00 | 新知识学习（阅读、课程） |
| 10:00-12:00 | 编程实现 |
| 13:00-16:00 | 项目开发/研究 |
| 16:00-18:00 | 竞赛/LeetCode |
| 19:00-20:00 | 金融理论阅读 |
| 20:00-21:00 | 笔记整理+复盘 |

周末：项目冲刺 + 论文精读 + 博客写作
