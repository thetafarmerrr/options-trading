# 一、原文精修版（仅修正转录错字、重复口误、残缺语法；句式、专业定义、段落全部保留，保留原生口语，删除时间戳）
What's up everyone and welcome back to Mike and his whiteboard. My name is Mike. This is my whiteboard and today we're talking about Delta. So we're going to start getting into the option Greeks. We're going to start off with delta, which is probably the most basic to understand, and how that relates to an option's price. And then tomorrow, we're going to wrap that into gamma. So gamma has a direct relationship with delta, so it's going to be a nice pairing. And then we'll finish off our conversation with theta on Tuesday. We've got some other Greeks like rho and vega, but we'll get into those later. I think the big three that we want to learn about are going to be delta, gamma, and theta.

So let's start off with delta and what that means for an option's price. So when we're talking about delta, we're basically talking about the rate of change of an option's price given a $1 increase in the underlying price. So what that basically means is that different options have different deltas, and you can see those on any option chain. So if you're in Dough, you can change the column to delta. You can view them in whatever table you're on, whether it's the curve view or the table view, you can change that to see the delta and see how that changes for out‑of‑the‑money and in‑the‑money options.

But the four big things we're going to talk about today with delta, and this big triangle is what you might see in math equations. So if you look into Skinny on Options Math segments where Jacob is talking about basically big equations, we're going to see this triangle here, and that's basically what we're going to see when you're looking at delta, and you're going to see that on the trade pages as well. So, we're going to talk today about traction and how that basically affects option prices. We're going to talk about directional risk, how we can use delta to hedge, and also its relation to probability of being in the money.

So, let's get right into it and let's talk about traction. So, when I'm talking about delta and traction, the way I like to think about it is think of a drag‑racing car and think about the types of tires that are being used on that car. So, if I have a low‑delta option, I might be throwing on Honda Civic economy tires on that drag‑racing car. We've got so much power, but the wheels are probably going to spin because there's not enough traction in that option. But if I have basically drag‑racing tires that are massive and they're going to grip with the car, I might have a high‑delta option.

So, what this basically means is with traction, the higher delta you have, the more the option price is going to change in relation to an underlying price. So when we get down to it, positive deltas range from 0 to 1.0 when we're talking about option deltas. So when we're talking about stock deltas, you can have 100 deltas, which would be 100 shares of stock, which we'll get into later. But when we're looking at options, you're going to see that range for positive deltas between 0 and 1.0. On the flip side, negative deltas are going to be ranging from ‑1 to zero.

And basically all you really need to know with traction is that deltas that are closer to negative one and positive one will have more option price traction. So if we look at an example here, we can clearly see that. So we've got a $1 increase in the stock price. So if I have a positive 0.25 delta and the stock price goes up $1, then the option price should go up 25 cents. So basically, you can think of it as like stair steps in relation to the option's price and the underlying price. So if I've got a $1 increase in the underlying price and I have a 25 delta, I should see a 25‑cent increase on that option.

Also, if I have a higher‑traction delta like 85, which is going to be a pretty high delta. So, if I'm looking at calls, this is going to be a deep‑in‑the‑money call if I'm buying that call. And for puts, it's going to be the same thing, deep‑in‑the‑money if I'm buying that put. But in any case, if I have an 85 delta and it's a positive delta, if I have a $1 increase in the stock price, now I should have an 85‑cent increase in the option price. So, you can see that's basically traction. And the higher the delta there is, the more that option price is going to move one‑for‑one or closest to one‑for‑one with a stock price. Now, if I had an option delta here that was 1.0, then if I have a dollar increase in the underlying price, I'm going to see a dollar increase in the option price. So, that's when you get super deep‑in‑the‑money. And basically, the options are trading more like stock than options.

So, the next thing we're going to look at is directional risk. So, when I'm talking about directional risk: positive deltas mean I would have a long market assumption. And that's because with the example we just showed, if the underlying is increasing in price and I have positive deltas, the option price is also going to increase. So basically, if I'm buying a call and I want that underlying to go up, I'm going to have positive deltas with the call. Negative deltas mean you are short the market. So it's the opposite. So if I have negative deltas and the underlying goes up, then I would be losing money on that position. But if I for instance buy a put or sell a call, those are going to be negative‑delta directional assumptions with the market.

And neutral deltas or zero deltas is basically going to have a neutral market assumption. So if I have various positions on and I'm trying to keep that delta neutralized, basically if the underlying goes up or the market goes up or down and I have zero deltas, that basically means that my directional risk is going to be much less than if I had positive or negative deltas. So that's what we like to do here at Tasty Trade, is try and keep our deltas as neutralized as possible so that we're all about the duration instead of direction. So we're all about durational trades. So if we keep our deltas neutral, that's going to help us minimize risk to the upside or downside.

So again, when I'm looking at options, if I am buying a call, that's going to have a positive delta because at the end of the day, when I buy a call, I want the underlying to go up because a call option gives me the right to buy 100 shares of stock. So I want that underlying to go up to be successful. And that's why the option is going to have a positive delta because if that underlying actually does go up, I'm going to see profits if I'm buying that call.

On the other side, if I'm buying a put, then I would have negative delta. And that's because buying a put gives me the right to sell 100 shares of stock. So if I buy a put at a certain level and then the stock goes down, I can now sell the shares higher than what they're worth in the marketplace. So that's going to have a negative delta.

Now, if I'm looking at selling options, it's just the opposite. So, if buying a call gives positive delta, selling a call gives negative delta. And if you just think of the transaction: if one person's buying the call and one person's selling the call, one person's going to want the stock to go up while the other's going to want the stock to go down. So, when I'm selling a call, I've got a negative delta. And you'll see that reflected in the option's price.

So, with a short put, it's just the opposite of a long put. So if I'm long a put, I want the underlying to go down. If I'm short a put, I want the underlying to go up. So that's a pretty quick way how you can visualize the options and how the options are going to have these deltas when you're trading them.

So the next thing we're going to look at is going to be hedging. So let's talk about how we can hedge and how we can use deltas to hedge our positions. So we can use options to hedge stock. A lot of this is basically what we do in maybe an IRA account where I might be holding more stock shares than I would be in a margin account because I don't have that additional leverage in an IRA account. So, maybe I'll be trading covered calls more, or having naked stock positions and then looking to hedge those positions when I think that something might be going on in the market or when implied volatility is high and I just want to collect that premium. I'll be looking to hedge that stock.

So, if we look at a couple of examples here with hedging, let's say I've got 200 shares of stock, which is going to give me 200 deltas. And that's because if I have 200 shares of stock and the underlying goes up $1, I should see a profit of $200. And that's just because I have one‑for‑one movement since I actually own the stock.

So, if I'm looking at a covered call, what I could do is hedge the position, but not fully hedge it. So this would be an under‑hedge. So let's say I've got 200 shares of stock and I'm looking at selling two out‑of‑the‑money calls for ‑30 delta each. And again, when I'm selling calls, it's going to have negative delta. So this is going to be me selling out‑of‑the‑money calls, just collecting premium to reduce my cost basis. So if I've got two positions of ‑30 deltas, I've got total ‑60 delta. So instead of me having all the directional risk of 200 shares or 200 delta, now I only have 140 delta. So basically I'm collecting premium, reducing my cost basis, and I'm reducing my directional risk if the underlying does end up going down.

On the other end, I can also do a full hedge. So what's important to note is that delta changes. So that's gamma. Gamma is the change of delta. But what I can do is temporarily give myself a full hedge. Now, if the underlying goes down or up, then this delta is going to change because the delta of the calls is going to change as well. So, if I'm looking at a full hedge of these shares, let's say I'm happy with what's going on or maybe I've seen a pretty big spike up in the underlying and I just want to fully hedge that position. Let's say maybe I don't want to close it, but I want to collect some premium and basically offset any bounce it might have to the downside. So I might look at a full hedge.

So if I'm looking at at‑the‑money calls, basically an at‑the‑money option is going to have a 50 delta. It's basically a 50/50 shot either way. So if I'm selling four at‑the‑money calls that are 50 deltas each, then I'm basically having a negative 200 delta. So if I have positive 200 delta with my 200 shares and negative 200 delta with my short options, then I'm going to have a neutralized delta or a delta of zero at that point in time. So basically I'm collecting the premium. I'm reducing my cost basis and regardless of what happens with the directional movement of that stock, I'm basically giving myself a full hedge temporarily.

So let's take a look at another thing we can use delta for, and that's going to be probability of being in the money. So this is a really quick way to determine what your percentage of being in the money is. So if you look at an option chain, on thinkorswim or Dough, you can change the columns to show you delta or probability in the money. So what you'll see is delta basically goes one‑for‑one and looks almost exactly like probability of being in the money. There's going to be a few percentage points difference, but when you're looking at options, they're basically going to match.

So if I'm looking at a 25 delta, it's probably going to show me a probability of being in the money of close to 25%. So again, an option's delta is roughly equivalent to probability of being in the money. So let's look at a few examples. So if I'm looking at an out‑of‑the‑money option, a short call. So that's going to have a negative delta of 30. And if I looked at that probability of being in the money, since I'm selling an out‑of‑the‑money option, I'm going to have a 30% probability of being in the money. And again, when we're selling options, we want them to remain out of the money. So, if I've got 30% probability of being in the money, I know that I've got a 70% probability of being out of the money. And a quick way we can calculate that is just by taking 100% total probability. You can subtract the probability of being in the money from 100 to get the probability of being out of the money and vice versa.

Now, if I'm looking at at‑the‑money, I've got a 50 delta short put. So, again, it's a 50/50 shot if we're at the money. So, it's going to have a 50% probability of being in the money, which is going to give me a 50% probability of being out of the money. So this really is where we're talking about maybe buying options where you're getting that 50/50 shot if we're buying at‑the‑money options. If we're selling at‑the‑money options, we're going to still be collecting that premium. So it's going to be a little bit higher than a 50% probability of profit because we have that better break‑even point. But in terms of delta, it's going to be 50/50 probability in the money or out of the money.

Now let's look at an in‑the‑money option. And this is going to show you why we don't sell in‑the‑money options. So, if I'm looking at a short call that's in‑the‑money, it's going to have a higher delta than 50. And that's because the further out‑of‑the‑money with calls or puts, doesn't matter, when you're looking out‑of‑the‑money, it's going to have a lower delta because it's going to have a lower probability of being in the money. But the further you go in‑the‑money, it's going to have a higher delta and a higher probability of being in the money.

So again, if I'm selling an option, I want that to be out‑of‑the‑money at expiration. So it expires worthless and I can keep that entire credit. If I'm looking at a ‑60 short call, then this is going to be a 60% probability of being in the money, which is a 40% probability of being out of the money. And again, I want this to be out‑of‑the‑money at expiration. So, if I'm trading with only a 40% probability of being out‑of‑the‑money, it's going to be a low‑probability trade. So, I wouldn't look to enter this trade outright. So, that's why we're selling out‑of‑the‑money options here at Tasty Trade.

So let's look at a few takeaways here. So delta again is the rate of change of an option's price given a $1 increase or decrease in the underlying price. So what's important to note is that if I want the underlying to go up, I'm going to want to have positive deltas. So I'm going to be looking at things like buying call spreads or selling puts or selling put spreads. If I want the underlying to go down, I want to have negative deltas. And I'll be looking at things like selling calls, selling call spreads, buying put spreads, things like that. So if I want the underlying to go up, it's going to be positive deltas. If I want the underlying to go down, it's going to be negative deltas. And deltas signify your directional risk. So the larger your delta magnitude, the more directional risk you have. So again, that could be a good thing or a bad thing. So if the underlying goes in your favor, then that's going to be a good thing in terms of profitability. But if it goes against you, then I'm now going to be losing more money than I would have if I was directionally neutral or had zero deltas.

And another takeaway is deltas roughly equate to probability of being in the money. So it's not going to be totally accurate or completely equal, but when you're looking at deltas and probability of being in the money, they're pretty much going to be similar values. And last but not least, we can hedge our positions using delta. So if you think of one share of stock being one delta, regardless of how many shares you have — you could have 500, 1 000, 10 000 — we just have to make sure that if I'm hedging that position, I need to account for those delta‑equivalent shares. If I'm using stock as an example, then figure out how many calls I would need to sell, or however many puts or whatever option strategy I'm using, to give me negative or positive deltas to offset the directional risk, if that's what I'm trying to do.

We aim to stay pretty much directionally neutral since we're more about duration than direction. So this has been delta. We're going to talk about gamma tomorrow. So gamma is basically a derivative of delta. So delta is the rate of change of an option's price, where gamma is the rate of change of delta. So we're going to get into that tomorrow. If you've got any questions or feedback, shoot it over to support@tastytrade.com. Thank you so much for watching and until next time, this has been Mike and his whiteboard.

Hey guys, I hope you enjoyed this video. Click below to watch more videos. Subscribe to our channel and if you want to trade along with us, visit tastytrade.com.

## 修正明细（仅修复转录瑕疵，专业、句式、段落全部保留）
1. 错字口误：beta → rho（希腊字母转录错误）；DO → Dough（券商软件名称）；under‑h → under‑hedge；out‑of‑the‑oney → out‑of‑the‑money；subsidy of delta → derivative of delta；thinker swim → thinkorswim；dorrading tasty trade → tastytrade邮箱域名；ladder（口误比喻错）修正为stair steps；重复`all all`、重复`the the`删除一处；`a,000`→`1 000`
2. 数字残缺：25 → 25‑cent，85 →85‑cent，补齐美分单位；规范delta正负数值格式
3. 残缺句子：修复`This is a lot of this is`重复从句；修复多处断句残缺；`what we can use delta 4`→`what we can use delta for`
4. 专有名词：`Skinny on Options Math`节目名保留；Tasty Trade / tastytrade统一；IRA、margin account、covered call、naked stock保留原术语
5. 联系方式残缺：补全邮箱格式，保留原口语意图
6. 仅做标点断句优化，**没有调换段落、没有改写任何交易逻辑、没有替换专业术语**，完整保留博主比喻（drag‑racing car / tires）、口语举例。

---
# 二、全套汇总：生词 + 短语 + 口头语 + 典型句式 + 俚语
## 一、专业生词（期权金融，附释义）
1. delta /ˈdeltə/ n. 德尔塔；价格变化敏感度（希腊值）
2. gamma /ˈɡæmə/ n. 伽马；delta的变化率
3. theta /ˈθiːtə/ n. 西塔；时间衰减
4. vega /ˈveɪɡə/ n. 维加；波动率敏感度
5. rho /rəʊ/ n. 柔；利率敏感度
6. option Greeks 期权希腊字母
7. option chain 期权链（行情列表）
8. underlying /ˈʌndəlaɪɪŋ/ n. 标的资产
9. directional risk 方向性风险
10. delta‑neutral /ˈdeltə ˈnjuːtrəl/ adj. 德尔塔中性
11. duration /djʊˈreɪʃn/ n. 持仓存续周期
12. durational trade 时间维度交易（不靠方向盈利）
13. hedge /hedʒ/ v.&n. 对冲
14. under‑hedge n. 不完全对冲
15. full hedge 完全对冲
16. covered call 备兑看涨期权
17. naked stock 裸多头股票（无对冲持仓）
18. IRA account 个人退休账户
19. margin account 保证金账户
20. leverage /ˈliːvərɪdʒ/ n. 杠杆
21. cost basis 持仓成本价
22. probability of being in the money 期权到期实值概率
23. derivative /dɪˈrɪvətɪv/ n. 衍生量（此处：gamma是delta的衍生变化率）
24. magnitude /ˈmæɡnɪtjuːd/ n. 数值大小（delta绝对值）
25. one‑for‑one 一比一（同步涨跌）

## 二、短语（金融专业搭配 + 通用口语短语）
### 金融专业搭配
1. rate of change 变化速率
2. positive delta 正德尔塔（看多）
3. negative delta 负德尔塔（看空）
4. neutralized delta 被对冲后的中性delta
5. minimize upside / downside risk 最小化上行/下行风险
6. collect premium 收取权利金
7. reduce cost basis 摊薄持仓成本
8. offset directional risk 抵消方向性风险
9. offset downside bounce 抵消标的向下反弹
10. deep‑in‑the‑money 深度实值
11. enter a trade outright 直接开仓入场
12. delta‑equivalent shares delta等效股票份数
13. 50/50 shot 五五开概率
### 通用口语短语
1. wrap that into 接续、结合来讲
2. on the flip side 与之相反
3. get right into it 直接进入正题
4. at the end of the day 归根结底
5. one‑for‑one movement 一比一同步变动
6. last but not least 最后一点
7. think of … as 把……理解为
8. in terms of 在……层面上

## 三、全文口头语（视频博主口头禅、过渡口语）
1. What's up everyone 大家好（开场）
2. welcome back 欢迎回到白板课堂
3. So 那么（高频过渡）
4. basically 简单来说
5. I like to think of it as 我习惯把它理解为
6. you can see that 你可以看到
7. for instance 举个例子
8. pretty quick way 很简便的方法
9. let's take a look at 我们来看
10. remember 记住
11. that could be a good thing or a bad thing 有利也有弊
12. if you've got any questions 如果你有问题
13. until next time 下次再见

## 四、典型教学句式（原文原句，适合仿写英文期权教学）
1. Delta is the rate of change of an option's price given a $1 increase in the underlying price.
>释义：Delta代表标的每上涨1美元，期权价格的变化幅度。
2. Positive deltas range from 0 to 1.0; negative deltas range from ‑1 to 0.
>释义：正delta取值0‑1，负delta取值‑1‑0。
3. The higher delta you have, the more the option price moves one‑for‑one with the underlying.
>释义：delta越高，期权价格与标的走势越接近一比一同步。
4. Positive delta means long‑market assumption; negative delta means short‑market assumption.
>释义：正delta代表看多市场，负delta代表看空市场。
5. Buying a call gives positive delta; selling a call gives negative delta. Buying a put gives negative delta; selling a put gives positive delta.
>释义：买看涨=正delta；卖看涨=负delta；买看跌=负delta；卖看跌=正delta。
6. Delta is roughly equivalent to probability of being in the money, but not perfectly accurate.
>释义：delta大致等价于期权到期实值概率，但并非完全精确相等。
7. Gamma is the rate of change of delta.
>释义：Gamma就是delta本身的变化速率。
8. We aim for delta‑neutral so we trade duration instead of market direction.
>释义：我们追求delta中性，依靠时间维度获利而不靠行情方向。

## 五、美式口语俚语 / 自媒体非正式表达
1. What's up everyone 嗨，各位（Youtube博主非正式开场）
2. shoot it over to support 发送邮件给客服（=send）
3. one‑for‑one 一比一（交易口语）
4. 50/50 shot 五五开的机会（口语，不用fifty‑fifty书面）
5. at the end of the day 说到底、归根结底
6. wrap that into 顺带着来讲
7. takeaways 核心要点（教学视频固定）

---
# 三、额外补充解构板块
## 1. 全文行文逻辑框架
1. 开篇：引入期权希腊字母，本期讲Delta，预告明天Gamma、周二Theta
2. Delta底层定义：标的每变动1美元，期权价格的变化率；软件期权链查看delta
3. 比喻讲解「traction牵引力」：delta越大，期权跟随标的股价联动越强；正负delta数值区间
4. 方向性风险：正delta（看多） / 负delta（看空） / 零delta中性；多空四种基础操作对应的delta符号
5. Delta用于对冲实操案例
   - 案例1：部分对冲（under‑hedge）200股股票，卖出虚值看涨，降低总delta、摊薄成本
   - 案例2：完全对冲，卖出ATM看涨，实现瞬时delta=0；提示Gamma会让delta持续变动，对冲只是临时状态
6. Delta≈到期实值概率；举例不同delta对应的ITM概率；解释卖方偏好低delta虚值期权的原因
7. 三条核心Takeaways
   - delta定义、正负delta对应多空方向，delta绝对值代表方向性风险大小
   - delta约等于到期实值概率，仅作近似参考
   - delta用来做持仓对冲；1股股票=1个delta单位
8. 预告Gamma：Gamma即delta的变化率；答疑+频道收尾

## 2. 成对对比易混核心概念
|概念A|概念B|
|---|---|
|Positive delta（买call / 卖put，看多）|Negative delta（买put / 卖call，看空）|
|High‑delta：深度实值，接近股票走势|Low‑delta：深度虚值，股价联动弱|
|Delta（期权价格对股价的敏感度）|Gamma（delta自身的变化速度）|
|Full hedge 完全对冲|Under‑hedge 部分对冲|
|Delta‑neutral（消除方向风险，赚时间/波动率）|Directional exposure（承担行情方向风险）|
|Delta as price sensitivity|Delta as approximate ITM probability（近似实值概率，非100%精确）|

## 3. 文中全部核心规则&计算公式
1. Delta = 标的变动$1 → 期权单价变动幅度（‑1.0 ~ +1.0）
2. 股票：1 share = 1 delta；200 shares = +200 delta
3. 总组合delta = 每笔持仓delta求和
4. 到期虚值概率 ≈ `100% − abs(delta) ×100%`（近似估算）
5. 交易符号规则
   - Buy call → +delta
   - Sell call → −delta
   - Buy put → −delta
   - Sell put → +delta
6. Gamma = rate of change of delta（delta的一阶变化率）

## 4. 句型功能分类（仿写英文期权教学）
1. 系列课程预告：Today we cover X; tomorrow we will talk about Y.
2. 核心定义句式：X is the rate of change of A given a $1 change in B.
3. 类比比喻句式：Think of X as … to help you understand.
4. 正反对照：Doing A gives positive delta, while doing B gives negative delta.
5. 实操案例引导：Let’s take N shares as an example…
6. 重要提醒：Note that X is not static; X changes because of gamma.
7. 近似关系说明：X is roughly equivalent to Y, but not perfectly accurate.
8. 总结课程+下集预告：This has been X. Tomorrow we dive into Y.

## 5. 高频重复词汇汇总
- 专业高频词：delta, gamma, theta, underlying, hedge, directional risk, probability of being in the money, delta‑neutral
- 口语过渡高频：so, basically, let’s, think of, on the other side, again, last but not least

如果你需要，我可以把**这5份Mike白板文稿（put、strike price、ITM‑OTM、intrinsic、extrinsic、delta）全部合并为一份完整学习文档**。