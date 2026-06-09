# XAUUSD Gold Scalping Research for MT5 and Python Automation

The research base points to a clear conclusion: XAUUSD is highly tradable for automated scalping, but only when the bot is built around gold’s actual microstructure rather than a generic FX or crypto template. Gold is deep and nearly continuous, yet its best short-horizon edges cluster around London, New York, and scheduled U.S. macro events. For a production MT5 Expert Advisor and a Python execution layer, that means session-aware strategies, hard spread controls, dynamic stop sizing, and explicit news filters. It does **not** mean firing a constant-stream M1 strategy all day the way many BTC bots do. Public evidence also favours treating COMEX futures and London benchmark behaviour as the “reference market”, while the MT5 CFD/spot feed is the execution venue. citeturn10view2turn18view3turn19view1turn10view1

## Gold microstructure, volatility and session behaviour

Gold is one of the deepest tradable markets in the world. The World Gold Council describes gold as a liquid asset with turnover comparable to many global stock markets and currency markets, and LBMA states that London remains the oldest and biggest financial market for gold. CME adds that its benchmark gold futures contract trades the equivalent of nearly **27 million ounces daily** and provides nearly 24-hour electronic access. For an MT5 scalper, that matters because it means the market can support repeated intraday entries, but it also means price discovery is dominated by specific venues and time windows rather than being evenly distributed through the day. citeturn10view3turn18view3turn19view1

The market is also structurally two-layered. London OTC is enormous, and the LBMA Gold Price benchmark is set twice daily at **10:30** and **15:00 London time** via electronic auction. Yet a 17-year price-discovery study found that COMEX futures often play the larger role in incorporating new information, despite London OTC spot volume being much larger. That is a crucial design input for live XAUUSD automation: use session and macro logic that respects London fixing windows, but treat COMEX-style futures behaviour and U.S. macro transmission as the dominant reference for directional scalps. citeturn34search0turn34search2turn10view1turn12view5

Gold’s microstructure is materially different from BTC’s. Bitcoin research highlights a highly fragmented trading landscape, sub-second leader-lagger effects across venues, and fee-regime sensitivity, while the New York Fed finds Bitcoin unusually disconnected from macro and monetary news compared with other U.S. asset classes. Gold is the opposite: macro-sensitive, session-clustered, and benchmarked through large institutional venues. The contrast also shows up in current volatility benchmarks. On 4 June 2026, the Cboe Gold Volatility Index series on FRED printed **23.87**, while CF Benchmarks showed the CME CF Bitcoin Volatility Index around **49.34** on 7 June 2026. Those are not perfectly like-for-like underlyings, but they are both forward-looking 30-day volatility benchmarks and they reinforce the practical point: gold is calmer than BTC, but still far too volatile for careless ultra-tight stops on retail execution. citeturn31view0turn10view7turn28view0turn29view0

Intraday gold behaviour is strongly sessional. Research using 1-minute Tokyo and New York gold futures data found that Tokyo trading is more associated with uninformed trading, while New York trading shows stronger evidence of informed trading. The same study found that volatility is relatively high at the open of the Tokyo, London, and New York day sessions; London hours show a U-shaped volatility pattern; and New York hours tend to decline more linearly after the open. CME’s own liquidity work also found that more than half of total gold options volume now occurs during the London trading day, with European-hour top-of-book spreads nearly as competitive as American hours. In practical trading terms, Asia is usually the better regime for mean reversion, while London open, the overlap, and early New York are the better regimes for momentum, pullback continuation, and breakout strategies. citeturn12view0turn12view1turn13view0turn24view0

| Session | What the research implies | Best use in an MT5 scalping bot |
|---|---|---|
| Asian session | Lower information quality relative to New York; range behaviour more common; spreads matter more relative to realised move | Range fade and mean reversion only |
| London open and London morning | Volatility increases at the open; London liquidity is strong and institutionally relevant | Breakouts, trend starts, first pullbacks |
| New York open and early New York day | Highest information content; U.S. macro and COMEX price discovery dominate | Trend following, continuation, post-data secondary breakouts |
| London–New York overlap | Best combined liquidity and the cleanest directional moves | Highest-quality window for live scalping |

The table above is a strategy-engineering synthesis of the cited academic and exchange evidence. citeturn12view0turn12view1turn24view0turn10view1

Macro events matter a great deal for gold at the scalp horizon. A classic intraday gold futures paper found that among 23 U.S. announcements, employment reports, GDP, CPI, and personal income had the greatest impact. Later high-frequency work found that the majority of gold’s reaction to macro announcements is completed within roughly **90 seconds**, and that unemployment rate and GDP surprises can be especially powerful. A separate gold futures study found a clear link between higher volatility, higher trading costs, and lower transaction volume around major scheduled U.S. announcements. More recent intraday jump evidence points to U.S. scheduled macro news as the dominant predictor of gold jumps and co-jumps, with **FOMC**, **initial jobless claims**, **unemployment**, **NFP**, **GDP**, and **CPI** all showing up as important event drivers in different jump specifications. Gold’s response to FOMC shocks is also asymmetric: one study finds gold returns and volatility are more sensitive to looser-than-expected policy shocks, and that adjustment can continue for more than five minutes after the event. citeturn32view0turn10view5turn21view0turn23view0turn10view9

CPI deserves its own treatment. The Federal Reserve’s work on how markets process macro news shows that market reactions are materially stronger when CPI investor attention is elevated, which has been especially relevant in inflation-shock periods. That fits what an execution engine sees in practice: CPI, NFP and FOMC are the events most likely to invalidate “normal” gold scalping assumptions for several minutes because they simultaneously hit rates, the dollar, and safe-haven demand. The New York Fed’s Treasury term-premia framework also matters here because yield moves are not all the same. Rising yields usually pressure gold because of the opportunity-cost channel, but World Gold Council and S&P Global research both show that this relationship can weaken or even invert when bond uncertainty, central-bank diversification, or geopolitical risk dominate. In other words, yields are a **soft directional filter**, not an iron law. citeturn10view8turn35view0turn17view0turn17view1turn17view2

For a live MT5 gold scalper, the answer on news filters is therefore simple: **yes, use them**. Use a **hard block** for CPI, NFP, FOMC rate decisions and Powell press conferences; a **medium block** for PPI and unemployment claims; and a benchmark-auction block around the LBMA gold auctions. The objective is not to avoid volatility altogether. It is to avoid the very short window in which spread, slippage, and microstructure noise become dominant over the signal. This is especially important because research shows announcement volatility and trading costs jump together, and because some employment reports appear to increase noise even when they do not cleanly increase price discovery. citeturn21view0turn10view9turn12view5turn34search0

## Stops, targets and execution constraints

Current public volatility gauges say gold remains a large-range asset even before you look at intraday moves. On Barchart’s current Gold Aug ’26 futures technical page, the **14-day ATR** is about **112.1**, average daily range about **106.1**, and 14-day historical volatility about **18.89%**. On FRED, the Cboe Gold Volatility Index series printed **23.87** on 4 June 2026. That combination says the current regime is not quiet, and it strongly argues against sub-noise stop placement on a retail CFD/spot feed. Gold can absolutely be scalped, but the stop must sit beyond spread and session noise. citeturn15view0turn28view0

Broker execution details reinforce that point. Broker specifications are not universal, but they are close enough to establish design constraints. Pepperstone advertises gold CFD spreads from **0.1**, while IC Markets lists variable spreads on gold, no minimum stop distance, a typical **100 oz** contract size for 1.00 lot, minimum lot 0.01, and a raw round-turn commission schedule. That means your EA should **never** hard-code a single spread or tick-value assumption. It should read the live symbol properties every time and calculate stop distance, lot size, and cost buffers from current spread, tick size, and tick value. Most published intraday research is on COMEX futures; the execution engine’s job is to translate that market behaviour into broker-specific CFD sizing in real time. citeturn36view0turn10view11

A good practical framework for MT5 gold scalping is to compute volatility on both **M1** and **M5**. Use **ATR(14) on M1** as the short-horizon expansion filter and **ATR(14) on M5** as the stable stop-sizing anchor. That avoids two common mistakes: using a fixed-dollar stop that stops working when gold changes regime, and using an M1 ATR-based stop that expands or contracts too violently from one bar to the next. Based on the current volatility regime, broker cost structure, and the sessional evidence above, the minimum practical stop for M1–M5 XAUUSD scalping is usually around **US$0.70–0.90/oz** in the cleanest conditions, and more realistically **US$0.90–2.20/oz** for production trading. Below that, spread and random intrabar noise become too dominant. A **US$10/oz** stop, by contrast, is usually too wide for true scalping and belongs more to an event-day intraday trade than to a standard M1/M5 scalping module. citeturn15view0turn36view0turn21view0turn12view1

For MT5 point conversion, the bot should always calculate from `_Point` rather than assumptions. On a 2-decimal gold quote, **US$1.00 = 100 points**. On a 3-decimal quote, **US$1.00 = 1000 points**. The correct universal formula is:

```text
price_move_points = abs(entry_price - stop_price) / _Point
```

With many brokers using 100 oz per 1.00 lot, a **US$1.00** move is roughly **US$100 per lot** before costs, but this must still be taken from live symbol metadata, not hard-coded. citeturn10view11

The stop bands below are the best production starting ranges for a non-HFT MT5 gold bot in the current regime. They are not “promises”; they are research-informed engineering bands built from the cited market behaviour, current volatility, and broker cost realities.

| Context | Working stop band |
|---|---|
| Absolute lower bound for any live M1 gold scalp | **US$0.70–0.90** |
| Asian mean-reversion fade | **US$0.80–1.20** |
| London pullback / trend continuation | **US$1.00–1.80** |
| London–New York overlap breakout / trend | **US$1.40–2.20** |
| Post-news secondary breakout | **US$2.50–4.00**, or stand aside |

To avoid premature stop-outs, the rule should be: place the stop beyond **structure plus a volatility buffer**, not merely at structure. In code, that means the stop sits beyond the signal swing high/low **and** beyond a minimum ATR-based floor. It also means no entries during the first minute after a major release, no range fades when ADX is climbing, and no new orders when spread expands beyond the strategy maximum. These design choices follow directly from the evidence that gold volatility clusters around opens and announcements and that trading costs widen when volatility rises. citeturn13view0turn21view0turn23view0

Take-profit logic should also be strategy-specific rather than universal. A fixed 1:1 or 1:1.25 target is the easiest to test and is often valid for pullback and range-fade scalps. Trend and breakout gold scalps usually need a larger payoff profile because their win rates are lower but their best moves occur during volatility expansion. Public intraday gold research establishes volatility clustering, macro jump behaviour, and strong session dependence, but it does **not** provide a single universally-best M1/M5 target model for retail CFDs. The most robust live choice is therefore a **hybrid** approach: fixed-RR baselines for simplicity, ATR caps for regime adaptation, and structure targets where local highs, lows, VWAP, or Donchian boundaries clearly define the next liquidity pool. citeturn32view0turn13view0turn23view0

My recommended default target logic is:

| Strategy family | Best target style | Starting target |
|---|---|---|
| Pullback continuation | Structure + modest fixed RR | **1:1.2 to 1:1.3** |
| Trend following | Fixed RR with optional trail | **1:1.4 to 1:1.6** |
| Range fade | Structure-based to VWAP / mid-band | **1:0.9 to 1:1.1** |
| Volatility breakout | ATR / fixed RR hybrid with trail | **1:1.6 to 1:1.9** |

The strategy-specific tables below implement that framework.

## Session impulse EMA ADX trend strategy

This is the cleanest “go with the move” strategy for gold and the easiest one to automate robustly. It exploits the fact that New York trading tends to show the strongest evidence of informed trading, that volatility expands around London and New York opens, and that gold reacts quickly to macro information once the market is actually in motion. It should be treated as a session strategy, not an all-day strategy. citeturn12view0turn12view1turn13view0

The rule set below is designed for live MT5 deployment on **M1 entries with M5 trend context**. It is aggressive enough to generate repeatable intraday signals in London morning, the overlap, and early New York, but it avoids the most common retail gold mistake: trying to chase every M1 push without a higher-timeframe trend and volatility filter.

| Field | Specification |
|---|---|
| Strategy name | **Session Impulse EMA ADX** |
| Core idea | Trade fresh directional impulses only when short-term momentum, higher-timeframe trend, and volatility expansion all agree |
| Entry timeframe | **M1** |
| Higher timeframe filter | **M5** |
| Indicators | M1 **EMA9**, **EMA21**, **ADX14**, **ATR14**, session **VWAP**; M5 **EMA50**, **EMA200**, **RSI14** |
| Exact parameters | EMA9/21 M1; ADX14 M1; ATR14 M1; EMA50/200 M5; RSI14 M5 |
| Long conditions | M5 close > EMA200; M5 EMA50 > EMA200; M5 EMA50 > EMA50[3]; M5 RSI14 > **55**; M1 EMA9 > EMA21 for current and previous bar; M1 ADX14 > **22** and +DI > -DI; M1 ATR14 > **1.10 × SMA(ATR14,20)**; M1 close > session VWAP; current close > highest high of prior **3** M1 bars by at least **US$0.05** |
| Short conditions | Mirror image: M5 close < EMA200; M5 EMA50 < EMA200; M5 EMA50 < EMA50[3]; M5 RSI14 < **45**; M1 EMA9 < EMA21 for 2 bars; ADX14 > **22** and -DI > +DI; ATR14 > **1.10 × SMA(ATR14,20)**; close < VWAP; close < lowest low of prior **3** bars by at least **US$0.05** |
| Entry trigger | Place stop order **US$0.03** beyond signal-bar high/low; cancel if not filled within **2** bars |
| Exit conditions | Full TP at **1.5R**; early exit if after **8** bars price has not reached **0.6R** and ADX14 falls below **18**; immediate exit on opposite M1 close through EMA21 after at least **4** bars in trade |
| Stop loss logic | **SL = max(0.35 × ATR14_M5, US$1.20, 4 × live spread)** |
| Take profit logic | **TP = 1.5 × SL distance** |
| Spread filter | **spread <= min(US$0.25, 0.18 × ATR14_M1)** |
| Volatility filter | Trade only when **ATR14_M1 > 1.10 × ATR-SMA20** and **ATR14_M1 < 2.20 × ATR-SMA20** |
| Session filter | London morning, London–New York overlap, early New York; skip Asia |
| News filter | Hard block for CPI, NFP, FOMC and Powell; medium block for PPI and claims |
| Risk per trade | **0.25%–0.40%** of equity |
| Expected win rate | **43%–49%** research-informed engineering estimate |
| Expected trades per day | **8–20** on active days |
| Risk-reward ratio | **1:1.5** |

A practical long example looks like this. M5 is above EMA200, EMA50 is rising, and M5 RSI14 prints 58. On M1, EMA9 is already above EMA21, ADX14 rises to 25, ATR14 is 1.18 times its 20-bar ATR average, and a strong body candle closes above the prior 3-bar high while remaining above session VWAP. The bot places a buy-stop 0.03 above the signal high. If filled, the stop goes at `max(0.35×ATR14_M5, 1.20, 4×spread)` and the profit target at 1.5R. If momentum stalls and ADX collapses back under 18, the bot exits early rather than waiting to be mean-reverted. This suits gold because gold’s best directional intraday moves tend to be sessional bursts rather than endless smooth trends. citeturn13view0turn12view1

The short example is the mirror image. M5 is below EMA200, EMA50 is falling, RSI14 is below 45, M1 EMA9 is below EMA21 for two bars, -DI dominates, ATR is expanding, and a decisive M1 close breaks the prior 3-bar low while staying under VWAP. The engine sells the continuation, not the first random red candle. That distinction is important because gold produces a lot of noise during employment reports and rate-sensitive risk events; you want the trade only once structure, trend, and volatility align. citeturn12view5turn21view0

## VWAP pullback continuation strategy

This is the best first-launch gold scalping strategy if the objective is to combine decent frequency with cleaner expectancy after spread. It takes advantage of the fact that gold often trends impulsively during London and New York, then pulls back briefly into micro-support or micro-resistance before continuing. That behaviour fits the session and price-discovery evidence well, and it is often easier to fill and risk-manage than pure breakout chasing. citeturn12view1turn24view0

The philosophy here is strict: do **not** buy weakness in a weak market, and do **not** short strength in a strong market. Instead, wait for a real higher-timeframe directional bias, allow a pullback into the intraday value area, then require short-term momentum to re-ignite.

| Field | Specification |
|---|---|
| Strategy name | **VWAP Pullback Continuation** |
| Core idea | Buy or sell the first controlled retracement inside an established M5 trend |
| Entry timeframe | **M1** |
| Higher timeframe filter | **M5 + M15** |
| Indicators | M1 **EMA9**, **EMA21**, **RSI2**, **RSI14**, **ATR14**, session **VWAP**; M5 **EMA21**, **EMA50**, **ADX14**; M15 **EMA200** |
| Exact parameters | EMA9/21 M1; RSI2 M1; RSI14 M1; ATR14 M1; EMA21/50 M5; ADX14 M5; EMA200 M15 |
| Long conditions | M15 close > EMA200; M5 EMA21 > EMA50; M5 EMA21 > EMA21[2]; M5 ADX14 > **18**; during last **5** M1 bars, low touched EMA21 or dipped below it by no more than **US$0.15**; RSI2 printed **<=10** during pullback; current bar closes back above EMA9; RSI14_M1 > **50**; signal-bar close > session VWAP |
| Short conditions | M15 close < EMA200; M5 EMA21 < EMA50; M5 EMA21 < EMA21[2]; M5 ADX14 > **18**; price pulled back to EMA21; RSI2 printed **>=90**; current bar closes back below EMA9; RSI14_M1 < **50**; signal-bar close < session VWAP |
| Entry trigger | Stop order **US$0.03** beyond signal-bar high/low; valid for **2** bars |
| Exit conditions | Full TP at prior impulse high/low **or** **1.25R**, whichever comes first; skip the trade if structure target is less than **1.0R** away; time exit after **6** bars if not at least **0.5R** in profit |
| Stop loss logic | **SL = max(0.28 × ATR14_M5, US$0.90, 4 × live spread)** |
| Take profit logic | **TP = min(prior impulse extreme, 1.25 × SL distance)** |
| Spread filter | **spread <= min(US$0.20, 0.15 × ATR14_M1)** |
| Volatility filter | M1 ATR14 between **0.90 × ATR-SMA20** and **1.90 × ATR-SMA20** |
| Session filter | London morning, overlap, early New York |
| News filter | Same hard and medium event blocks as the trend strategy |
| Risk per trade | **0.25%–0.50%** of equity |
| Expected win rate | **51%–58%** research-informed engineering estimate |
| Expected trades per day | **10–30** |
| Risk-reward ratio | **1:1.2 to 1:1.3** |

A typical long setup begins with a strong London morning up-move. M15 is above EMA200, M5 EMA21 sits above EMA50 with ADX at 21, and price is still above session VWAP. Gold then pulls back for several M1 bars into EMA21, RSI2 becomes oversold at 7, but the retracement remains shallow and does not break the broader structure. The next M1 candle closes back above EMA9 and RSI14 is back above 50. The bot buys the break of that signal bar, places the stop under the ATR floor, and targets the prior intraday high or 1.25R—whichever comes first. This is usually the highest-quality “bread and butter” gold scalp because it enters after the impulse has proven itself but before the move is exhausted. citeturn12view1turn13view0

The short example is the same sequence in reverse. After a bearish U.S. rates impulse, M15 sits below EMA200, M5 EMA21 is below EMA50, and a brief M1 bounce lifts gold into EMA21 with RSI2 over 90. Once price rolls back below EMA9 and the signal candle closes under VWAP, the bot sells the continuation. Because employment and CPI releases can create sudden whipsaw, this strategy still needs the same news filters as the trend strategy, but once those filters are in place it is generally the best blend of frequency, automation, and execution realism. citeturn32view0turn21view0turn10view8

## Bollinger VWAP range fade strategy

Gold is not only a breakout market. During Asia and during transitional lulls after the first directional burst, it often behaves like a wide but tradeable intraday range instrument. The academic evidence that Tokyo-style trading is more dominated by uninformed flow, together with the documented time-of-day volatility profile, makes a strong case for a separate mean-reversion engine rather than forcing every trade into a trend or breakout framework. citeturn12view0turn12view1

This strategy must be treated with more discipline than the previous two. Mean reversion in gold can be very profitable in the right regime, but it is the easiest strategy to destroy by trading it during genuine trend days or during macro-news spillovers. Its survival depends on strong regime filters.

| Field | Specification |
|---|---|
| Strategy name | **Bollinger VWAP Reversion Fade** |
| Core idea | Fade statistically stretched M1 moves only when the higher-timeframe environment is non-trending |
| Entry timeframe | **M1** |
| Higher timeframe filter | **M5 + M15** |
| Indicators | M1 **Bollinger Bands 20,2**, **RSI2**, **RSI14**, **Stochastic 5,3,3**, **ATR14**, session **VWAP**; M5 **ADX14**; M15 **RSI14** |
| Exact parameters | Bollinger **20,2**; RSI2; RSI14; Stochastic **5,3,3**; ADX14 M5 |
| Long conditions | M5 ADX14 < **18**; M15 RSI14 between **45** and **55**; current price distance from session VWAP <= **0.60 × ATR14_M5**; M1 closes below lower Bollinger Band; RSI2 < **5**; Stoch K < **10**; next M1 bar closes back inside the bands and above the prior candle midpoint |
| Short conditions | M5 ADX14 < **18**; M15 RSI14 between **45** and **55**; price not too far from VWAP; M1 closes above upper Bollinger Band; RSI2 > **95**; Stoch K > **90**; next bar closes back inside the bands and below prior midpoint |
| Entry trigger | Enter at close of the re-entry candle that closes back inside the Bollinger Bands |
| Exit conditions | Target session VWAP or Bollinger midline; skip if the available target is less than **0.9R** away; force exit after **5** bars |
| Stop loss logic | **SL = max(0.22 × ATR14_M5, US$0.80, 4 × live spread)** |
| Take profit logic | **TP = VWAP or Bollinger midline**, capped at roughly **1.0R** |
| Spread filter | **spread <= min(US$0.18, 0.14 × ATR14_M1)** |
| Volatility filter | Only if **ATR14_M1 <= 1.50 × ATR-SMA20** |
| Session filter | Asia; late-London lull; post-impulse flat periods only |
| News filter | No trading during hard news block; no trading in the first **20** minutes after London or New York open |
| Risk per trade | **0.20%–0.35%** of equity |
| Expected win rate | **57%–64%** research-informed engineering estimate |
| Expected trades per day | **15–40** |
| Risk-reward ratio | **1:0.9 to 1:1.1** |

A typical long example occurs in Asia. Price drifts lower inside a bounded session range, M5 ADX sits at 14, M15 RSI14 still hovers around 50, and a brief sell burst closes outside the lower Bollinger Band with RSI2 at 3 and Stochastic below 10. The next candle closes back inside the band and above the prior midpoint. The bot buys that re-entry, places a modest but not tiny stop below the flush low, and targets the return to VWAP. This is the kind of trade that can fire repeatedly when gold is moving, but not trending. citeturn12view0turn13view0

A typical short is the mirror image: a brief overbought push above the upper band in a flat regime, then a close back inside. The danger is trend misclassification. Gold research on intraday jumps shows that U.S. macro news is the dominant jump predictor and that effective spreads and realised volatility elevate before major jumps. That is why this strategy needs the strictest news and regime vetoes. If ADX begins to rise, if price keeps separating from VWAP, or if you are close to U.S. data, turn this strategy off. citeturn23view0turn21view0

## Donchian compression breakout strategy

Gold often alternates between compression and violent expansion. That is one of the most repeatedly observed practical facts about the metal, and it is consistent with the research on macro announcements, jumps, and volatility clustering. The breakout engine below is designed specifically for those compression-to-expansion transitions and is the best way to monetise gold’s “nothing happens until everything happens” behaviour without resorting to fully discretionary news trading. citeturn32view0turn23view0

Unlike the trend strategy, this one cares more about **pre-break compression** than pre-existing EMA alignment. It still uses a direction filter, but its real edge comes from identifying when range contraction is ending and a liquidity event is beginning.

| Field | Specification |
|---|---|
| Strategy name | **Compression to Expansion Donchian Breakout** |
| Core idea | Trade the first clean breakout after statistically compressed M1 range structure |
| Entry timeframe | **M1** |
| Higher timeframe filter | **M5** |
| Indicators | M1 **Donchian 20**, **Bollinger Bands 20,2**, **ATR14**, **ADX14**, session **VWAP**; M5 **EMA50**, **EMA200** |
| Exact parameters | Donchian **20**; Bollinger **20,2**; ATR14 M1; ADX14 M1; EMA50/200 M5 |
| Long conditions | M5 EMA50 > EMA200; Donchian20 width <= **0.75 × SMA(Donchian width,20)**; Bollinger Bandwidth <= **0.85 × SMA(BBWidth,20)**; ATR14_M1 > **1.30 × ATR-SMA20**; current close > Donchian upper band by at least **US$0.08**; signal-bar body >= **60%** of bar range; ADX14_M1 > **20** after breakout close; close > session VWAP |
| Short conditions | M5 EMA50 < EMA200; Donchian width compressed; Bollinger bandwidth compressed; ATR expansion active; close < Donchian lower band by **US$0.08**; body >= **60%** of range; ADX > **20**; close < VWAP |
| Entry trigger | Stop order **US$0.03** beyond breakout-bar high/low; valid for **2** bars only |
| Exit conditions | Take **50%** at **1.0R**; move stop to breakeven on remainder; trail the balance using Donchian10 midpoint or close remaining piece at **1.8R** |
| Stop loss logic | **SL = max(0.45 × ATR14_M5, US$1.40, 4 × live spread)** |
| Take profit logic | Effective target profile **1:1.7 to 1:1.8** |
| Spread filter | **spread <= min(US$0.25, 0.16 × ATR14_M1)** |
| Volatility filter | Compression must precede expansion; if ATR is already extreme for several bars, skip late entries |
| Session filter | London open, overlap, early New York; also valid for post-data secondary breakouts once spread normalises |
| News filter | Do **not** trade the first release print; allow only the second-leg breakout after the block expires |
| Risk per trade | **0.20%–0.35%** of equity |
| Expected win rate | **38%–46%** research-informed engineering estimate |
| Expected trades per day | **5–15** normally, more on heavy macro days |
| Risk-reward ratio | **1:1.7 to 1:1.8** effective |

A long example is a pre-overlap squeeze. The last 20 M1 bars have compressed into a narrow Donchian channel, Bollinger bandwidth is below 0.85 of its 20-bar average, then ATR expands sharply and a strong body candle closes through the upper channel and above VWAP. The bot places a stop order just above that candle, uses the wider breakout stop, takes partial profit at 1R, and trails the rest. This is the correct way to trade gold expansion without having to predict the news. It reacts only once the market shows a genuine transition from low-volatility compression to directional range expansion. citeturn23view0turn10view5

The short example occurs after a compressed base fails to hold during a bearish rates move or a strong-dollar impulse. Compression resolves lower, ADX wakes up, the close prints beyond the lower Donchian boundary, and the engine enters only if the spread remains within tolerance. The key distinction from reckless breakout systems is that this module refuses late-stage spikes. If compression is already gone and ATR has been extreme for multiple bars, it stands aside. That is important because gold’s largest event-driven moves can also be the noisiest and most expensive to execute. citeturn21view0turn10view9

## Automation, optimisation, deployment ranking and revised prompt

The coding architecture should be boring and deterministic. The MT5 EA should evaluate signals only on **new M1 bar close**; the Python layer should compute session state, macro-event blocks, optional yield and dollar bias, and a spread/latency health flag; and each strategy should have its own **magic number**, cooldown, loss counter, and session enablement window. The gold literature strongly supports this structure because session, macro announcements, and volatility regime all matter materially, while trading costs worsen exactly when many naïve bots try to trade more aggressively. citeturn21view0turn13view0turn23view0

A robust execution state machine looks like this:

```text
On each new M1 bar:
    update M1/M5/M15 indicators
    update active session flags
    update major-news and benchmark-auction blocks
    read live spread, point, tick size, tick value
    if daily drawdown >= 2.0%: disable trading for rest of day
    for each strategy:
        if session not allowed: continue
        if news block active: continue
        if spread > strategy max: continue
        if strategy cooldown active: continue
        if no open position for that strategy:
            if long signal:
                calc stop, target, lot size
                place order
            if short signal:
                calc stop, target, lot size
                place order
        else:
            manage stop, TP, time exit, and trail rules
    if strategy has 3 consecutive losses in same session:
        disable strategy until next session
```

The most important lot-sizing formula is the cash-risk-per-lot calculation. Use broker metadata, not assumptions:

```text
risk_cash = equity * risk_pct
cash_risk_per_lot = (abs(entry - stop) / tick_size) * tick_value
fee_buffer_per_lot = (spread / tick_size) * tick_value + round_turn_commission
lots = floor_to_volume_step( risk_cash / (cash_risk_per_lot + fee_buffer_per_lot) )
```

A compact MQL5 lot-size helper looks like this:

```mql5
double CalcLotsByRisk(double entryPrice, double stopPrice, double riskPct, double roundTurnCommissionPerLot)
{
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskCash  = equity * riskPct;
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double volStep   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;

   double cashRiskPerLot = (MathAbs(entryPrice - stopPrice) / tickSize) * tickValue;
   double feeBuffer      = (spread / tickSize) * tickValue + roundTurnCommissionPerLot;

   double lots = riskCash / (cashRiskPerLot + feeBuffer);
   lots = MathFloor(lots / volStep) * volStep;

   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;
   return lots;
}
```

A compact MQL5-style signal skeleton for the pullback strategy looks like this:

```mql5
bool PullbackLongSignal(double ema9_m1, double ema21_m1,
                        double rsi2_m1, double rsi14_m1,
                        double ema21_m5, double ema50_m5, double adx_m5,
                        double close_m15, double ema200_m15,
                        double close_m1, double vwap_session,
                        double low_touch_distance)
{
   bool htfTrend   = (close_m15 > ema200_m15) && (ema21_m5 > ema50_m5) && (adx_m5 > 18.0);
   bool pbTouched  = (low_touch_distance <= 0.15);
   bool momentum   = (rsi2_m1 <= 10.0) && (close_m1 > ema9_m1) && (rsi14_m1 > 50.0);
   bool valueSide  = (close_m1 > vwap_session);

   return htfTrend && pbTouched && momentum && valueSide;
}
```

Python-side signal generation should mirror the same rules exactly. A practical pattern is to compute all indicators in pandas, build a dict of boolean gates, and return an order specification only when every gate is satisfied.

```python
def pullback_long_signal(m1, m5, m15, spread):
    atr1 = m1["atr14"].iloc[-1]
    atr1_sma20 = m1["atr14"].rolling(20).mean().iloc[-1]
    atr5 = m5["atr14"].iloc[-1]

    conds = {
        "m15_above_ema200": m15["close"].iloc[-1] > m15["ema200"].iloc[-1],
        "m5_trend": m5["ema21"].iloc[-1] > m5["ema50"].iloc[-1],
        "m5_adx": m5["adx14"].iloc[-1] > 18,
        "pullback_rsi2": m1["rsi2"].iloc[-2:].min() <= 10,
        "reclaim_ema9": m1["close"].iloc[-1] > m1["ema9"].iloc[-1],
        "rsi14_reclaim": m1["rsi14"].iloc[-1] > 50,
        "above_vwap": m1["close"].iloc[-1] > m1["vwap_session"].iloc[-1],
        "spread_ok": spread <= min(0.20, 0.15 * atr1),
        "vol_ok": 0.90 * atr1_sma20 <= atr1 <= 1.90 * atr1_sma20,
    }

    if not all(conds.values()):
        return None

    entry = m1["high"].iloc[-1] + 0.03
    sl_dist = max(0.28 * atr5, 0.90, 4 * spread)
    stop = entry - sl_dist
    take = entry + 1.25 * sl_dist

    return {
        "side": "buy",
        "entry": round(entry, 3),
        "stop": round(stop, 3),
        "take": round(take, 3),
        "meta": conds
    }
```

For optimisation, the goal is not to find the “perfect” threshold. It is to find a stable plateau that survives spread inflation, session shifts, and walk-forward testing. The ranges below are where I would start.

| Parameter family | Starting range | More robust or more overfit |
|---|---|---|
| Fast EMA | **7–12** | Usually robust |
| Slow EMA | **18–34** | Usually robust |
| Trend EMA | **40–80** | Robust if used as a family, not exact value worship |
| Regime EMA | **150–250** | Robust |
| RSI14 trend threshold | **52–58** long, **42–48** short | Moderately robust |
| RSI2 pullback threshold | **3–12** long, **88–97** short | More overfit-prone |
| ADX threshold | **18–28** | Robust as a regime family |
| ATR expansion multiplier | **1.05–1.40 × ATR-SMA20** | Moderately robust |
| ATR stop multiplier on M5 | **0.20–0.50 × ATR14_M5** | Robust if paired with absolute floor |
| Bollinger length | **18–24** | Robust |
| Bollinger standard deviation | **1.8–2.4** | More overfit-prone if tuned too finely |
| Donchian length | **15–30** | Robust |
| Session windows | Broad named sessions | Robust |
| Minute-specific time slices | e.g. 08:17–08:46 only | Highly overfit-prone |

The strongest overfit risks in gold scalping are not usually the broad EMA lengths. They are minute-specific session windows, tiny threshold differences such as RSI2 = 7 instead of 8, and fixed-dollar stops that are not normalised to volatility. The parameters that usually remain more stable are the broad session family, the presence or absence of a higher-timeframe trend, the need for a spread veto, and the principle of ATR-based stop normalisation. That is also why the first live deployment should use the simpler trend and pullback engines before the faster range-fade module. citeturn13view0turn21view0turn10view11turn36view0

My ranking for first production deployment is as follows:

| Strategy | Expected profitability | Win rate | Trade frequency | Robustness | Ease of automation |
|---|---|---|---|---|---|
| **VWAP Pullback Continuation** | **Highest** | High | High | **Highest** | High |
| **Session Impulse EMA ADX** | Very high | Medium | Medium-high | Very high | **Highest** |
| **Compression to Expansion Donchian Breakout** | High | Lower | Medium | High | High |
| **Bollinger VWAP Reversion Fade** | Medium after costs | **Highest** | **Highest** | Lowest on trend days | Medium |

The first two strategies I would deploy live are therefore **VWAP Pullback Continuation** and **Session Impulse EMA ADX**. They best match gold’s documented session behaviour, they absorb spread better than the mean-reversion module, and they are simpler to code and validate than the breakout engine while still generating enough trade frequency for a meaningful automated system. After that, I would add the breakout engine as the third module and only then introduce the range-fade strategy behind a strict low-ADX regime switch. citeturn12view1turn13view0turn21view0

A realistic combined daily trade count for the four-strategy stack on one raw-spread XAUUSD feed is roughly **35–100 trades/day** under active conditions. Above **100** is possible on unusually busy days, but pushing toward **200/day** on retail MT5 infrastructure usually means entering the zone where noise, spread, and slippage dominate the signal. That is more an HFT problem than a normal EA problem. The cited evidence on announcement reactions and trading costs strongly supports that caution. citeturn21view0turn23view0

The revised prompt below is the version I would actually use if you want another model to generate strategy blueprints that are precise enough to code directly:

```text
You are a quantitative trading systems researcher and execution engineer.

Task:
Produce a deep, research-driven, production-grade report on XAUUSD gold scalping strategies for:
1) MetaTrader 5 Expert Advisors
2) Python-based automated execution

Objective:
Design profitable, realistic gold scalping strategies that can be backtested and deployed live. Prioritise strategies that can realistically generate around 5–30 trades/day per strategy, and potentially 40–100+ trades/day when multiple orthogonal strategies are run together, but avoid unrealistic HFT-style assumptions. Do not optimise for ultra-tight stop losses that will fail after spread and noise.

Critical requirements:
- Do not give generic trading advice.
- Use specific indicators, exact parameters, exact thresholds, and exact signal conditions.
- Where possible, cite academic studies, exchange data, institutional research, broker specifications, or macro research relevant to gold intraday behaviour.
- If a statement is an engineering inference rather than directly documented by research, label it clearly.

Research areas to cover:
1. Current gold market behaviour
   - Gold intraday volatility characteristics
   - Gold microstructure vs BTC
   - Session behaviour: Asian, London, New York, London–New York overlap
   - Which sessions are best for scalping
   - Impact of CPI, NFP, FOMC, PPI, unemployment claims, Treasury yields
   - Whether news filters should be used in automated scalpers

2. Design exactly four distinct XAUUSD scalping strategies:
   A) Trend following
   B) Pullback continuation
   C) Range fade / mean reversion
   D) Volatility breakout

3. For each strategy provide:
   - Strategy name
   - Logic explanation
   - Entry timeframe
   - Higher timeframe filter
   - Exact indicators and exact parameters
   - Long conditions
   - Short conditions
   - Entry trigger
   - Exit conditions
   - Stop-loss logic
   - Take-profit logic
   - Spread filters
   - Volatility filters
   - Session filters
   - Risk % per trade
   - Expected win rate estimate
   - Expected trades/day estimate
   - Risk-reward ratio
   - Long worked example
   - Short worked example

4. Use exact indicator values such as:
   - EMA9, EMA21, EMA50, EMA200
   - RSI14, RSI2
   - ATR14
   - ADX14
   - MACD 12,26,9
   - Bollinger Bands 20,2
   - Donchian 20
   - Stochastic 5,3,3
   - VWAP

5. Use exact thresholds such as:
   - RSI crosses above 55
   - ADX > 22
   - ATR > 1.1 × ATR-SMA20
   - Price closes above EMA21
   - Close breaks previous 3-bar high
   - Donchian width <= 0.75 × its 20-bar average
   - Bollinger bandwidth <= 0.85 × its 20-bar average
   - etc.

6. Stop-loss research
   - Recommend SL in ATR multiples
   - Recommend SL in dollar terms
   - Recommend SL in MT5 points
   - State the minimum practical SL before spread/noise becomes problematic
   - Give session-specific SL recommendations
   - Explain how to avoid premature stop-outs

7. Take-profit research
   - Compare fixed RR targets vs ATR-based targets vs structure-based targets
   - State which target style is best for each strategy type
   - Recommend a practical hybrid if appropriate

8. MT5 and Python implementation guidance
   - Exact rule logic suitable for coding
   - Pseudocode
   - MQL5 examples
   - Python signal logic
   - Position sizing formulas using risk %
   - Trade sizing formulas using live broker tick size, tick value, spread, and volume step
   - Explicitly note that XAUUSD contract size and point precision vary by broker and should not be hard-coded

9. Optimisation research
   - Give optimisation ranges for EMA lengths, RSI thresholds, ADX thresholds, ATR multipliers, Bollinger settings, Donchian settings
   - Explain which parameters are likely robust and which are likely overfit

10. Final ranking
   - Rank all four strategies by profitability, win rate, trade frequency, robustness, and ease of automation
   - Recommend the best two strategies to deploy first in a live MT5 bot

Format requirements:
- Use clear section headings
- Use tables wherever useful
- Be highly detailed
- Give exact signals and exact conditions
- State all assumptions explicitly
- Prefer raw-spread / low-cost execution assumptions
- Assume this will be used to build a live MT5 + Python gold scalping stack

Important implementation notes:
- Treat futures/COMEX behaviour as the reference market and MT5 XAUUSD as the execution venue
- Include hard news filters for CPI, NFP, FOMC, and Powell press conference
- Include medium news filters for PPI and unemployment claims
- Include benchmark-auction filters around LBMA gold fix windows
- Avoid martingale, grid averaging, and unrestricted re-entry
- Keep the system deterministic and backtestable
```

