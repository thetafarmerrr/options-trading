# IV Rank vs IV Percentile — English Transcript

> Source: https://www.youtube.com/watch?v=KvuQGqKBh2U
> Tastytrade: The Skinny on Options Data Science

---

[Music]

Welcome back to the show. My name is

Mike. This is my whiteboard. And today

we're going to be covering the

difference between IV rank and IV

percentile. So, we actually just

released a new IV rank or IV percentile

adjustment in the Dough platform just

last night. So if we go to the next

slide, I can show you exactly where that

is. On the trade page, if you pull up

the trade page, the curve view, you type

in any underlying there. You're going to

get the IV rank circle as you see here.

So I pulled this yesterday. IV rank was

around 47. And now what you can do is

click on that IV rank circle and you can

actually change your IV rank type. So,

you can change it from a 52- week toss

style IV rank, which is the exact same

number you're going to see in the toss

platform, or you can select any of these

IV percentiles. So, some of you might be

saying, well, we use IV rank. What is IV

percentile? And that's exactly what

we're going to break down today. So,

we've got a 30-day, a 60-day, a

six-month, and a one-year IV percentile

selection. Now, and it's just a

different way to look at the

calculations. It's another way to

visualize and really interpret where the

implied volatility is in relation to

itself over these certain time frames.

So let's go on to the next slide and

we'll first talk about IV rank and we'll

look at the calculation for this. So IV

rank is what we've been using on a lot

of the segments. We talk about selling

premium in high IV environments and

usually we look at IV rank over 50 or

anywhere around 50 is usually good

enough for us to be selling premium. And

really what we're doing is taking the

current IV, measuring it against the 52-

week low and the 52- week high. So, the

actual calculation is taking the current

IV, subtracting the 52- week low, and

then dividing that value by the 52- week

high subtracted from the 52- week low

here. So, if we have a current IV of

100% and over a 52-e time frame, we had

a low IV rank of 30% but a high IV rank

of 150%. Then, this is what the

calculation would look like. we'd have

100 - 30 which would give us 70 divided

by 150 over 30 which would be 120 and

that gives us this percentage of 58.3%.

So an interesting thing is that IV is

not capped at 100 although IV rank is

because really we're just ranking the

current IV on a scale from zero which is

the 52- week low to 100 which is the 52-

week high. implied volatility itself can

be anywhere above 100%. I just looked at

the VIX earlier today and I think the

current uh VIX expiration that's

expiring today is over 200% which is

insane. But as you can see here the raw

implied volatility can be over 100%. So

that's why we're looking at IV rank. So

the reason we look at IV rank is because

we're looking at different underlyings

that have different implied

volatilities. We're going to get to

another slide here in just a second

where we're going to look at a few

different graphs of implied volatility

and we're going to see the reasoning

behind IV rank. But the first big

takeaway here is that IV rank only looks

at the IV high over a 52-E period and

the IV low over a 52-E period. Once we

figure out those two points, we can

measure where we are currently and

that's where it's going to give us that

percentage down here. So the first thing

to take away from IV rank is that it's a

very simple calculation. If I can easily

see the IV rank low and see the IV rank

high over a 52-E period, I'm sorry, I

should be saying the IV high and a IV

low over a 52-E period. I can take the

current implied volatility, measure it

within that range, and give myself a

percentage here or just eyeball exactly

where that is. So there's a difference

when we look at IV percentile compared

to IV rank and that's the fact that it's

going to be a little bit more complex.

So let's go to the next slide here and

we'll talk about the calculation for IV

percentile.

So the big difference between IV rank

and IV percentile is that IV percentile

does not just look at the IV high and

the IV low. It's going to look at every

single data point and every single day

that the actual underlying is trading.

So the IV percentile calculation is

going to be the number of days under the

current IV over the number of trading

days total. So in that same exact

scenario, let's say that if I had a

current IV of 100% and I knew that my IV

high was 150% and my IV low was 30%. If

I've got a current IV of 100% and 200

out of the total 252 trading days, the

IV was lower than 100%. It would give me

an IV percentile of 79.4%.

So, as you can see, the two numbers are

a little bit different. And the reason

is because of the fact that IV rank is

going to look at just the high and the

low where IV percentile takes all the

data points into considerations and it

gives you a much smoother calculation.

So let's go to the next slide and we'll

look at some visuals here in terms of IV

rank. So I've got three different

scenarios here. The very top one is

looking at an IV over a 52-E period

between 20 and 30%. So, you could say

that this is an underlying that's really

not too volatile. Sure, 20 or 30% an

underlying moving that much in a certain

time frame, 52 weeks, can still be

pretty volatile, but the fact that it's

staying between 20 and 30% for an entire

year means to me that it's not too

volatile. It's a pretty mediocre in

terms of volatility underlying. So

basically what we did here to find the

IV rank is we looked at the low point

which would be right down here of 20%.

And we're measuring that against the

high point which is 30%. So when we're

looking at IV rank it's going to be

taking that 20% low assigning that a

zero value and going to the 30% high and

assigning that a 100 value. So now we

would look at the current implied

volatility, measure that against the low

of zero and the high of 100 and that's

where we get our rank. So in this

example, a 50 IV rank would be right in

between there. It would be 25% raw

implied volatility. And I know that is

the case because if zero is assigned the

low of 20%. And 100 is assigned to the

high of 30%. If I go right smack dab in

the middle at 25%, that's what's going

to give me that 50 IV rank. It's right

in between zero and 100. So that's what

gives me the 50 there. Now we're looking

at a different situation where we're

much more volatile. So this was the the

example I was referring to in the first

IV rank calculation. So now we're

looking at an IV low of 30%, which you

can see is right here. And we're

measuring that against an IV high of

150%. Which is right up here. So the

difference between IV rank and IV

percentile again is that IV rank is only

going to look at this low point and

measure it against that high point and

anywhere in between here is going to

fall in between and give you an IV rank.

Where IV percentile is going to take

each one of these days. Let's say these

are weekly spikes. So here's one week,

here's another week, here's another

week. Basically, what it's going to do

is take all those data points into

consideration. So this spike in IV and

this low in IV is going to be smoothed

out. It's not going to have such a

drastic change on the IV rank as you saw

with the IV rank calculation. So when

we're looking at IV percentile, it's

much more smooth of a calculation.

Although it is more complex because we

have all these data points we have to

consider, it's going to give us a more

smooth calculation. Some people like it

over IV rank. But I think the important

thing is whatever you're more

comfortable with using, just stick to

that. Be consistent. Because if you're

switching between both of these, it's

going to be confusing and kind of get

you off track of where you were looking

previously. So, if I'm looking at IV

rank for 6 months and all of a sudden I

jump over to IV percentile, it's going

to be giving me a different number and

maybe a spike or a drop in IV percentile

isn't going to have that same effect

that it would have if I was still

looking at IV rank since it was

something I was familiar with. So,

lastly, we've got a very low IV

underlying. And I think this is

potentially one of the issues with IV

rank is that when we're looking at just

IV rank, if we don't look at the actual

implied volatility, we can get ourselves

into a situation where we might be

selling premium when there's really not

too much premium to be sold or buying

premium when we think it's low when it's

really not. So, this is a super low

implied volatility underlying. As you

can see, over 52-E period, the raw

implied volatility was only ranging from

7% to 10%. Now, you can see there's only

a 3 percentage point difference as

opposed to this one where there's 120

percentage point difference here. But

with this one, with IV rank, we still

have to assign it a low and we still

have to assign it a high. So the 7% low

would be somewhere around here and that

10% high would be somewhere around here.

Now what's the importance of this? Well,

if we're talking about actual pricing

models, a slight change in implied

volatility like this, three percentage

points isn't really going to change the

pricing of the options too much.

Although a 7% IV is going to give me a

zero IV rank and a 10% is going to give

me a 100 IV rank. So over the course of

a few days, I might go from zero IV rank

to 100 IV rank and I might think there's

an extreme opportunity there. But if I

actually look at the raw implied

volatility, I might see that it's only

jumped from 7% to 10%. Which really

shouldn't change that options pricing

too much. So it's really important to

number one look at the IV rank or IV

percentile, whichever calculation we're

using first. But then we want to still

dig into the raw implied volatility

because the raw implied volatility is

really what's going to be the reflection

of the option prices. Again, implied

volatility is just a reflection of the

option prices. If option prices are

increasing, the input for the black

shores model, which is the implied

volatility, we can't really know that

number and input it into the black

shores model. we can take all the other

inputs and figure out or get close to

figuring out what implied volatility is.

But since we don't actually know the

implied volatility value, we know that

the option prices are dictating implied

volatility. So whether we're using IV

rank or IV percentile, the important

thing to remember is to always look back

at the raw implied volatility. Because

if I've got a situation like this, it

might be much less lucrative than a

situation here where maybe I'm selling

premium up here and watching it drop all

the way down there, which would probably

give me a much bigger profit than if I

were to be selling premium up here and

have it only drop down to 7% in this

example. So, that was a ton of

information, but let's wrap it up with

some takeaways on the last slide here.

So, the first takeaway is that IV rank

is a simple calculation. I can easily

see the 52- week low, measure it against

the 52- week high of implied volatility,

and see where my current implied

volatility level is. I can easily just

map it out and give myself a visual of

where that IV rank is. IV percentile,

however, is a little bit more complex.

There's a lot more data points going

into it because we're looking at each

and every single day, regardless of the

IV high and the IV low. While yes, it

will have an impact on the IV

percentile, it's not going to have a

drastic impact like you saw it have in

the IV rank calculation. If we get a

spike in implied volatility, it's going

to alter that high for the IV rank.

Whereas in IV percentile, it's just

going to skew it a tiny bit. It's not

going to totally drastically change that

calculation. So, with that said, IV

percentile is going to be smoother.

We're not going to see those big spikes

or big drops in implied volatility

having a great effect on IV percentile

as you might see it have an effect on IV

rank. But really the question is going

to be which one should I use? Which

one's better? In all honesty, it's going

to be up to you. You can use IV rank if

you're more comfortable with it. IV

percentile if you have the ability to

figure figure that out calculation and

be able to calculate that consistently

then by all means you can certainly use

it. We've got it all in do so. So, you

can check out the 52- week IV rank or

you can switch off between the different

time frames for IV percentile. But

really, just be consistent. If you're

consistent with an underlying in the

calculation, you're going to give

yourself the best probability of success

in the long run. So, this is the

difference between IV rank and IV

percentile. Thanks so much for tuning

in. Hopefully, you enjoyed it. If you've

got any questions or feedback, shoot it

over to these emails or shoot me

Trader Mike. We've got Jim Schultz with

Theory to Practice coming up next

though, so stay tuned.

Hey everyone, thanks for watching our

video. If you liked this video, give it

a thumbs up or share it with a friend.

Click below to watch more videos,

subscribe to our channel, or go to our

website.

[Music]

