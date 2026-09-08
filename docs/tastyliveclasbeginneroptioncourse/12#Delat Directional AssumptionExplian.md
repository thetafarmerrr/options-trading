# 一、原文精修版（仅修正转录错字、口误重复、残缺语法；句式、专业定义、段落完整保留，原生口语风格，删除时间戳）
Hey everyone, welcome back to the show. Happy Friday. Thanks for tuning in. My name is Mike. This is my whiteboard. And today we're going to be talking about a different angle of delta. So when we're talking about delta, we know that it's the rate of change of an option's price given a $1 increase or decrease in the underlying price. But if you wanted to check out the beginner segment on delta, I did cover that previously. You can check out my show at the Find Shows tab on the top of Tasty Trade and then scroll down until you see Mike in his whiteboard, and you'll find it there.

But today we're going to be talking about delta's effect on directional assumption, and how delta can change when the market actually moves, or when that underlying does move against us or when it moves for us. How will that change our delta, and how can we mitigate that delta risk that we are now exposed to. So let's get right into it, and we'll talk about the very first strategy here, and what we need to know first.

So when we talk about delta, we need to know that it changes. And when we're talking about the change or the rate of change of delta, we're actually talking about gamma. So Jim Schultz actually had a great segment on this, and he explained that delta is the speed of price change. Gamma is the acceleration. So if you think about a car that accelerates very fast, that would be said to have a high gamma. And if you think about a car that accelerates slowly, that would have a low gamma. It's just the rate of change of the speed of the option’s‑price movement, or the rate of change of delta itself.

So, as we know, as options move in‑the‑money, their delta actually gets stronger. And if we know that it gets stronger when it moves in‑the‑money, that must mean that the delta gets weaker as an option moves out‑of‑the‑money. So, we're going to break that down in the next few slides, and we're going to talk about how that's affected. And one really special subject is ratio spreads, where we're either buying one option and selling two against it, or buying two options and selling one against it. The structure where we're buying two and selling one would be called a back‑ratio spread, and the ratio spread where we're selling two and buying one would be a front‑ratio spread. But what's interesting about those spreads is that it can actually result in an assumption change. So we'll talk about that, and we'll talk about how that can be possible when we're looking at just delta itself.

So our very first example on the next slide is when we're selling a put, which is a bullish assumption, and we're going to look at what happens when the stock price goes against us and how that affects our delta. So even though we're selling an option, when we sell a put it's actually a positive delta. And that's because we want the stock price to go up. We want the stock price to go up because when we sell an option, we want that option to expire out‑of‑the‑money. If it expires out‑of‑the‑money, the position will expire worthless. Because if we review the put contract itself: a put is just the right for someone to sell their shares at a certain strike. So if I sell someone the right to sell their shares to me, of course I want that underlying to go up, because that would mean that they can sell their shares in the market for a better price than exercising that put contract.

So if we can understand that even though we're selling a put, it's going to have a positive delta because we want the underlying to go up. We're going to look at an example here where we're selling an out‑of‑the‑money put with a 30 delta. And I've got the orange box highlighted here as the delta. So whenever you see this orange box on the next slides, that's going to mark the delta value. So we're looking at a 30‑delta put that we're selling, which corresponds to roughly a 30% probability of expiring in‑the‑money. And if we know that a 30% probability of expiring in‑the‑money yields a 70% chance of this option expiring out‑of‑the‑money, then 70% of the time this option will expire out‑of‑the‑money. And that's what makes it a high‑probability trade.

But what happens when the stock price goes against us? This little blue dot here marks our stock price. So if the stock actually goes down, which is going to be bad for our position, what you'll see is that the delta will actually increase. So as the stock price moves more and more in‑the‑money and gets further in‑the‑money, our deltas are going to increase. So why is that? Well, we know for a fact that deltas have a relationship with probabilities of being in‑the‑money. If I'm selling a 30‑delta put and it's pretty far away from the stock price, it has a probability of around 30% of expiring in‑the‑money. That means that if the stock price moves closer to that strike, the delta would have to be higher. Because if the stock price is closer to the strike price, it would have to have a higher probability of expiring in‑the‑money, and therefore it's going to have a higher delta. But when we look at directional assumption, that's also what's going to increase the delta of this option. So the closer we get to that strike price, the higher the delta is going to be.

When you look at an option on any option chain, if you look at an at‑the‑money option — so let's say this stock was trading right at that strike — you're going to see it have a delta of about 50. And that means that instead of buying the shares outright where you would have a delta of 100 because you actually control those shares, if I were to sell a put right at‑the‑money, I would have a delta of 50. So what does that mean? Well, basically it means that with an increase of $1 in the underlying, I should see an increase on my position of about $50. So, a 50 delta, or 0.5 delta as you would see it in a trading platform, is going to indicate that I basically have half the exposure compared to buying shares outright in this particular scenario. Because selling a put and buying the shares outright both have the same directional assumption. I still want that underlying to go up because that's where I would make money. But the best thing about selling the put here is that I can make money if the stock price doesn't change. And that's what gives us that edge when we're talking about options when comparing it to buying shares outright.

But as we know, as the stock price continues to move down past that put strike, if the stock price goes below the put strike, it's going to push it in‑the‑money. And that's because that put now has intrinsic value. So what you'll see is when the underlying continues to move down and further below that put strike, the delta is going to increase. And that's because as it moves deeper and deeper in‑the‑money, option contracts act much more like long or short stock. At expiration, when there's no time and not much volatility left in that time frame for the option, delta is going to be closer and closer to 100. So, if this had zero days to go — like let's say it's 1:00 right now and this option was expiring in a couple hours here — I would probably see this delta, even though it's just a little bit in‑the‑money, be probably closer to 90 or 95. At expiration, this is going to turn into 100 long shares of stock. And that's going to give me 100 long deltas, or plus 100 deltas.

So, it's really important to understand that the more an option moves against us, it's going to make my delta stronger. And in this case, it's going to make me more and more bullish. Which is why we need to make sure that we keep track of these deltas and adjust them if we're not comfortable with that directional risk. Because there's a big difference: at the start, a $1 increase in the underlying here where I would only make 30 dollars; but if it moves against me, I should see a decrease of about 30 cents. Later on with this same position, if the underlying goes $1 up, I should see about 60 cents in gain. And if it went against me $1 even more, I should see about a 60‑cent loss. So, you can see that my delta is going to change my P&L based on the $1 increase or decrease in that underlying stock. So, we need to understand that when we're looking at positions going against us, we actually become stronger and stronger with that same assumption, because the option would be moving more and more in‑the‑money when we're selling options, and that's going to give us a stronger directional assumption in this case.

So, let's go on to the next slide and we'll talk about what happens when a position goes for us or goes in our favor. So, now we're looking at just buying a call outright. Of course, you wouldn't see us do this on the Tasty Trade Network. There's a lot working against us, like theta working against us, and our break‑even is going to be pretty terrible if we're buying options regardless, because we're paying for that extrinsic value. It moves our break‑even further away. But for simplicity's sake, in this example, I wanted to show you how this would affect an in‑the‑money option that we bought.

So, just like a position moving against us or moving more and more in‑the‑money when we're looking at selling a put, it's very similar if we're buying an option and it moves more and more in‑the‑money. As we know, an option's delta grows stronger when it moves deeper and deeper in‑the‑money. And if we know that for an option, our deltas can only range from 1.0 to negative 1.0, it's going to get closer and closer to 1.0, or 100 delta, when I'm buying a call and it's extremely in‑the‑money. So in this bottom example here, you can see that I've got a delta of 90. So, with every $1 increase or every $1 decrease, I should see a 90‑cent increase or a 90‑cent decrease on my option's price given a $1 increase or decrease in that underlying, which is very different from this visual here where I'm just purchasing a call that's just barely in‑the‑money. As you can see, it's over 50 because we know that at‑the‑money options are going to give me about a 50 delta. So, if I move just in‑the‑money, it's going to be just a little bit higher than that.

But, it's really important to realize that if I'm buying a naked option, I'm going to have gamma working for me. If my position continues to go up and up and up, I'm going to make more money on that same $1 move as my option goes deeper and deeper in‑the‑money. Of course, that sounds all great, but this is going to be a low‑probability trade when we look at it, because we have break‑evens that are worse than where the stock price is trading right now. And when we're looking at buying options, we have to be directionally right, for one, and we have to be directionally right within the given time frame for our option expiration. So, these are a few reasons why we don't trade naked options, but I wanted to show you how a naked option would be affected if the position moved in our favor.

So, our next slide here is actually a really cool scenario where we have a ratio spread, and we're going to be looking at a back‑ratio spread in this case, where we're selling one option and we're buying two options behind it. So, what's cool about this trade is that it can actually change our directional assumption. So, this is where we get into more complex assumptions. When we look at our selling of a naked put in the first slide, it's where we're saying, "Okay, I'm okay with price anywhere above this range." And if the stock actually goes against me, I'm totally fine with it because my strike is much lower than where the stock was trading at the point when I placed the trade, and my cost basis is going to be much lower than if I were to have just bought the shares outright.

In this scenario though, it gives us an opportunity to have multiple assumptions, and we're going to be talking about this on a slide‑by‑slide basis. So, I want you to envision what our assumption would be at each point. So, with this spread, if I'm looking at a put back‑spread or back‑ratio spread, I'm going to be able to enter this for a credit more often than not. It's going to be a very small credit, maybe 10 cents or 20 cents. But if I'm selling a put that's closer to the stock price, this put is going to be worth much more than these puts that are further away. And if this put is worth more than double the value of those further puts, then I'm going to be able to enter this for a credit. And since I want options to expire out‑of‑the‑money when I sell them or when I have a net short position for credit, I'm going to be okay with this stock price expiring anywhere up here. So that's why I have a delta that's slightly positive.

But if the stock price starts going down, what you'll see is that yes, my short put will be in‑the‑money. These long puts are still out‑of‑the‑money, but these long puts here are gaining delta because as we know, the stock price is moving closer and closer to those puts, and it's going to increase their delta as that happens. So, since I am short one option here and long two options here, you might start to see that your deltas go from positive to negative. And as the stock price moves even further away, you're going to see your deltas grow pretty rapidly negative. And if we know that when I'm selling a put, that's going to turn into long stock at expiration. And if I'm buying a put, it's going to turn into short stock at expiration. If I were to convert these into shares, I would have plus 100 shares here, but negative 200 shares here, which leaves me with negative 100 shares. So, as this option moves deeper and deeper in‑the‑money, I would basically have an embedded short put spread that would be at a full loss, but I would have a long naked put that would be gaining more and more value as that stock dropped. And because of that, if I'm profiting when that stock is dropping, I'm going to have that negative delta. So this is a good way to understand how delta works and how it changes as the stock price moves.

Let's wrap it up with some takeaways for you. So the very first takeaway is that deltas grow as options move closer to being in‑the‑money. I don't want to simply say deltas increase or decrease because different option types carry different delta signs. As you know, selling a put has a positive delta. Selling a call has a negative delta. And when we're looking at buying calls, it has a positive delta, and we're looking at buying puts, it has a negative delta. So, I just want you to have the understanding that deltas grow in magnitude as they move closer to being in‑the‑money or as they go in‑the‑money. That's when their magnitude will be the highest.

Secondly, ratio spreads can result in changing directional assumptions based on delta. As you saw, if we're selling one option and buying two, if those options move in‑the‑money, the delta from the extra long options is going to outweigh the delta on the option that I sold because I have two long contracts and just one short contract. So eventually, the net position would become a bearish position.

And lastly, deltas constantly change, which is why we constantly manage them. You'll hear us talking about maintaining a delta‑neutral portfolio. And that's because we feel safer being delta‑neutral, given we cannot predict market movement. If we hold a delta‑neutral portfolio built with uncorrelated underlyings, a broad increase or decrease in the market should not affect our portfolio as drastically as if we were super long or super short.

So thanks so much for tuning in. Hopefully you enjoyed this show. If you've got any questions or feedback, shoot me an email here at support@tastytrade.com or you can tweet me. Jim Schultz is coming up next.

Hey everyone, thanks for watching our video. If you liked this video, give it a thumbs up or share it with a friend. Click below to watch more videos, subscribe to our channel, or go to our website.

## 修正明细（仅修复转录瑕疵，不改动专业逻辑、句式、段落）
1. 错字口误：`exttrinsic`→`extrinsic`；`Taste Trade`→`Tasty Trade`；`sideby‑slide`→`slide‑by‑slide`；`more more often`删除重复；`9095`→`90 or 95`；`tastrade.com`补全邮箱域名；`Find Shows tab`（原转录`fine shows tab`）；重复`box box`删除一处；重复`the the`清理；残缺`under‑ of the money`规范`out‑of‑the‑money`
2. 残缺句子：`what how this would affect`删除多余疑问词；`the difference would to make`等口语断句残缺修复；`net sale of a credit`修正为`net short position for credit`贴合交易含义；`delta grow`补充`in magnitude`还原教学本意；`place this for a credit`统一表述`enter this for a credit`；`maintain them`结合上下文`manage them`
3. 数字与符号：规范delta正负、美分单位`60cent`→`60‑cent`；修正算数举例的口误数字
4. 比喻保留：汽车速度/加速度类比（delta速度、gamma加速度）完整原样保留
5. 专有名词：`back‑ratio spread / front‑ratio spread`、`naked put/call`全部保留术语；节目人名Jim Schultz原样保留
6. 标点断句：只增加必要逗号、破折号，**不调换句子顺序、不重写段落、不新增交易观点**；残缺联系信息补全邮箱格式。

---
# 二、全套汇总：生词 + 短语 + 口头语 + 典型句式 + 俚语
## 一、专业生词（期权金融，附释义）
1. directional assumption 方向性交易预期
2. mitigate /ˈmɪtɪɡeɪt/ v. 减轻、对冲（风险）
3. gamma /ˈɡæmə/ n. 伽马；delta的变化率（加速度）
4. speed n.（类比）delta代表价格变动速度
5. acceleration /əkˌseləˈreɪʃn/ n. 加速度（gamma的比喻）
6. ratio spread 比率价差策略
7. back‑ratio spread 反向比率价差（买多、卖少）
8. front‑ratio spread 正向比率价差（卖多、买少）
9. magnitude /ˈmæɡnɪtjuːd/ n. 绝对值、数值大小
10. naked option 裸期权（无对冲单边开仓）
11. embedded /ɪmˈbedɪd/ adj. 内嵌的（持仓内部隐含结构）
12. net position 净持仓
13. delta‑neutral portfolio delta中性投资组合
14. uncorrelated /ˌʌnkəˈrələteɪd/ adj. 无相关性的（标的）
15. exposure /ɪkˈspəʊʒə(r)/ n. 风险敞口
16. probability trade 概率交易
17. expiration /ˌekspəˈreɪʃn/ n. 到期
18. intrinsic value 内在价值
19. extrinsic value 外在价值
20. P&L 盈亏（profit and loss）

## 二、短语（金融专业搭配 + 通用口语短语）
### 金融专业搭配
1. mitigate delta risk 降低delta风险
2. grow in magnitude （delta）绝对值增大
3. go against us 行情对持仓不利
4. go in our favor 行情对我们有利
5. high‑probability trade 高概率交易
6. low‑probability trade 低概率交易
7. expire out‑of‑the‑money 到期虚值归零
8. enter for a credit 开仓收到权利金（贷方开仓）
9. outweigh the delta （某持仓delta）数值盖过另一方delta
10. change directional assumption 反转/改变整体方向性预期
11. maintain / manage delta‑neutral portfolio 管理delta中性组合
12. convert options into shares 将期权等价换算成股票份数
13. edge in trading 交易上的优势
14. naked put 裸卖看跌期权
### 通用口语短语
1. get right into it 直接进入正题
2. for simplicity’s sake 为简化讲解
3. wrap it up 收尾总结
4. more often than not 多半情况下
5. as you know 正如大家所知
6. on top of that 除此之外
7. in this particular scenario 在该特定场景
8. keep track of 跟踪、留意（指标）

## 三、全文口头语（视频博主口头禅、过渡口语）
1. Hey everyone 大家好
2. Happy Friday 周五愉快（节目开场问候）
3. welcome back to the show 欢迎回到本期节目
4. thanks for tuning in 感谢收看
5. So 那么（高频过渡）
6. basically 简单来说
7. as we know 正如我们所知
8. what’s cool about … …很有意思的一点是
9. let’s look at 我们来看
10. of course 当然
11. you’ll see 你会看到
12. that’s because 那是因为
13. for one 第一点（列举）
14. hopefully you enjoyed this show 希望本期对你有帮助
15. if you’ve got any questions 如果你有任何问题

## 四、典型教学句式（原文原句，仿写英文期权教学）
1. Delta is the rate of change of an option’s price; gamma is the acceleration / rate of change of delta.
>释义：Delta是期权价格变化速率，Gamma是Delta的变化速率（加速度）。
2. As options move in‑the‑money, their delta grows in magnitude; as they move out‑of‑the‑money, delta magnitude weakens.
>释义：期权走向实值，delta绝对值增大；走向虚值，delta绝对值减小。
3. Selling a put carries positive delta even though you are short an option contract.
>释义：尽管你是卖出期权合约，卖看跌期权依然带有正delta。
4. Ratio spreads can cause your overall directional assumption to flip as price moves.
>释义：比率价差策略，会随着价格变动改变整体方向性预期。
5. The deeper in‑the‑money an option goes, the more it behaves like outright stock at expiration.
>释义：期权实值程度越深，到期时行为越接近直接持有股票。
6. We need to keep track of deltas and adjust them if we are uncomfortable with directional risk.
>释义：我们需要跟踪delta；若无法承受方向风险，就要进行调整。
7. Naked long calls have gamma working for them when price moves strongly in your favor, yet they remain low‑probability trades.
>释义：裸买看涨在行情大幅有利时Gamma对我们有利，但仍是低概率交易。
8. We manage delta‑neutral portfolios because uncorrelated underlyings reduce broad‑market directional risk.
>释义：我们管理delta中性组合，无相关性标的可以降低大盘方向风险。

## 五、美式口语俚语 / 自媒体非正式表达
1. shoot me an email 发邮件给我（=send）
2. thumbs up 点赞（Youtube自媒体）
3. for simplicity’s sake 出于简化目的（教学口语）
4. more often than not 多半、大多数情况
5. wrap it up 收尾总结
6. what’s cool about … …的妙处在于（博主常用口语）

---
# 三、额外补充解构板块
## 1. 全文行文逻辑框架
1. 开篇：本期主题——Delta如何改变方向性预期；回顾上期基础delta内容，引出Gamma（类比速度与加速度）
2. 核心底层规则：期权走向实值→delta绝对值变大；走向虚值→delta绝对值变小；介绍比率价差（back‑ratio / front‑ratio）可以反转整体多空预期
3. 案例一：卖出虚值看跌期权（正delta，看多预期）
   - 初始30delta，70%到期虚值，高概率交易
   - 标的下跌，期权逐步进入实值，delta不断升高，看多敞口被动放大；到期深度实值等价于持有100股正股
   - 风险提示：行情不利时，持仓的方向性风险会自动放大，需要监控、调整delta
4. 案例二：裸买看涨期权
   - 行情有利、不断实值，gamma对多头有利，delta持续走高；但裸买期权本身属于低概率交易，受theta损耗，盈亏平衡点差
5. 案例三：反向比率价差 back‑ratio spread
   - 开仓小幅正delta；当标的大幅下行，多份long put的delta总和盖过short put，**整体净delta翻转为负，持仓预期从看多转为看空**；解释到期等价股票份数
6. 三条核心Takeaways
   ① 期权靠近实值，delta的绝对值会增大；不同类型期权delta正负符号不同
   ② 比率价差策略会因为delta变动，彻底反转整体方向性预期
   ③ delta持续动态变化；管理delta‑中性组合降低大盘方向风险
7. 预告下一期Jim Schultz节目，频道常规收尾

## 2. 成对对比易混核心概念
|概念A|概念B|
|---|---|
|Delta：期权价格的**速度**|Gamma：Delta的**加速度**|
|In‑the‑money：delta绝对值变大|Out‑of‑the‑money：delta绝对值变小|
|Sell put：正delta（看多）|Sell call：负delta（看空）|
|Naked option 裸期权（单边）|Ratio spread 比率价差（多合约组合，可反转预期）|
|Initial delta（开仓那一刻delta）|Dynamic delta（行情移动后动态变化delta）|
|Delta‑neutral 中性（消除大盘方向风险）|Directional exposure 暴露方向性风险|

## 3. 文中全部核心规则&计算公式
1. Delta：$1标的变动 → 期权单价变动幅度；Gamma = rate of change of delta
2. Sell put → +delta；Buy put → −delta；Sell call → −delta；Buy call → +delta
3. ITM加深：delta**绝对值 magnitude ↑**；OTM加深：delta**绝对值 magnitude ↓**
4. 组合净delta = 全部单腿合约delta求和（比率价差核心逻辑）
5. Back‑ratio spread示例：Short 1 put + Long 2 puts；价格大跌后，2份long‑put的负delta盖过short‑put正delta，整体净delta转负
6. 到期等价换算：1 ITM put合约到期 = 100股；1 ITM call合约到期 =100股

## 4. 句型功能分类（仿写英文期权教学视频）
1. 往期内容引导：If you want to review beginner material on X, you can find it in the show archives.
2. 类比科普：Think of delta as speed; gamma is the acceleration of that speed.
3. 现象描述：As X moves in‑the‑money, its delta magnitude grows.
4. 反直觉案例讲解：Even though we are selling this option contract, it still carries positive delta.
5. 风险提示：It is critical to monitor delta and adjust when directional risk becomes uncomfortable.
6. 组合策略逻辑：This multi‑leg spread can flip overall directional bias as price moves.
7. 课程总结+下期预告：These are our key takeaways. Next up we have guest speaker ...

## 5. 高频重复词汇汇总
- 专业高频：delta, gamma, directional assumption, magnitude, ratio spread, back‑ratio spread, naked option, in‑the‑money, out‑of‑the‑money, delta‑neutral portfolio
- 口语过渡高频：so, as we know, of course, what’s cool about, let’s look at, for simplicity’s sake, wrap it up

> 提示：至此已经完成6份Mike白板系列文稿解析。如果你需要，我可以把全部6份合并成一份完整学习文档，包含**精修文稿、全套词汇短语、解构板块**。