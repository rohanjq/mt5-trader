# SignalMaster EA — Signal Reference for Trading System

## Overview

A single MQL5 Expert Advisor (`SignalMaster.mq5`) attached to one chart computes all indicators across all timeframes.
It writes one CSV per indicator+timeframe+symbol to the Common/Files directory, symlinked to `/data/signals/` on the host.

Files are updated every 5 seconds. Format: key-value CSV with `key,value` header row.

---

## File Naming Convention

```
<SYMBOL>_<indicator><params>_<timeframe>.csv
```

Indicators with parameters include them in the name (e.g. `bb20d2`, `adx14`, `macd12_26_9`).
Indicators without extra params use bare names (e.g. `utbot`, `dc`, `vwap`).

Examples: `XAUUSD_utbot_M1.csv`, `XAUUSD_bb20d2_M1.csv`, `XAUUSD_adx14_M5.csv`, `XAUUSD_macd12_26_9_M3.csv`

---

## All Available Signal Files

### UT Bot ATR Trailing Stop (`utbot`)
```
BTCUSDT_utbot_M1.csv
BTCUSDT_utbot_M3.csv
BTCUSDT_utbot_M10.csv
BTCUSDT_utbot_M15.csv
BTCUSDT_utbot_M45.csv
```
Config per instance: `TF:ATR_Period:ATR_Mult` (default all `10:2.0`)

### Donchian Channels (`dc`)
```
BTCUSDT_dc_M1.csv
BTCUSDT_dc_M3.csv
BTCUSDT_dc_M5.csv
BTCUSDT_dc_M15.csv
BTCUSDT_dc_M45.csv
```
Config per instance: `TF:Length:Offset` (default all `20:0`)

### Liquidity Grab (`liqgrab`)
```
BTCUSDT_liqgrab_M3.csv
BTCUSDT_liqgrab_M5.csv
BTCUSDT_liqgrab_M15.csv
BTCUSDT_liqgrab_H1.csv
BTCUSDT_liqgrab_H4.csv
```
Config per instance: `TF:LookbackRange:BarsN:WickBodyRatio:CandlesBeforeBreakout:MAPeriod` (defaults `50:5:2.0:5:100`)

### EMA (`ema`)
```
BTCUSDT_ema9_M1.csv
BTCUSDT_ema21_M1.csv
BTCUSDT_ema50_M1.csv
BTCUSDT_ema200_M1.csv
BTCUSDT_ema20_M3.csv
BTCUSDT_ema50_M5.csv
BTCUSDT_ema200_M5.csv
BTCUSDT_ema50_M15.csv
BTCUSDT_ema200_M15.csv
```
Config per instance: `TF:Period` (e.g. `1:9` = M1 with 9-period EMA)

### RSI (`rsi`)
```
BTCUSDT_rsi14_M1.csv
BTCUSDT_rsi2_M1.csv
BTCUSDT_rsi14_M3.csv
BTCUSDT_rsi14_M5.csv
```
Config per instance: `TF:Period` (e.g. `1:14` = M1 with 14-period RSI)

### Bollinger Bands (`bb{period}d{dev}`)
```
BTCUSDT_bb20d2_M1.csv
BTCUSDT_bb20d2_M3.csv
BTCUSDT_bb20d2_M5.csv
```
Config per instance: `TF:Period:Deviation` (e.g. `1:20:2.0` = M1 with 20-period, 2.0 std dev)

### ADX (`adx{period}`)
```
BTCUSDT_adx14_M5.csv
BTCUSDT_adx14_M15.csv
```
Config per instance: `TF:Period` (e.g. `5:14` = M5 with 14-period ADX)

### MACD (`macd{fast}_{slow}_{signal}`)
```
BTCUSDT_macd12_26_9_M1.csv
BTCUSDT_macd12_26_9_M3.csv
```
Config per instance: `TF:Fast:Slow:Signal` (e.g. `1:12:26:9` = M1 standard MACD)

### Stochastic (`stoch{k}_{d}_{slowing}`)
```
BTCUSDT_stoch5_3_3_M3.csv
```
Config per instance: `TF:K:D:Slowing` (e.g. `3:5:3:3` = M3 with %K=5, %D=3, slowing=3)

### ATR standalone (`atr{period}`)
```
BTCUSDT_atr14_M1.csv
BTCUSDT_atr14_M3.csv
BTCUSDT_atr14_M5.csv
```
Config per instance: `TF:Period` (e.g. `1:14` = M1 with 14-period ATR)

### Session VWAP (`vwap`)
```
BTCUSDT_vwap_M1.csv
BTCUSDT_vwap_M5.csv
BTCUSDT_vwap_M15.csv
```
Config per instance: `TF` (e.g. `1` = M1 output timeframe; VWAP always computed from M1 bars, resets daily at 00:00 server)

---

## Standard Header (every file)

```
key                 → description
symbol              → BTCUSDT
indicator           → utbot | dc | liqgrab | ema | rsi | bb | adx | macd | stoch | atr | vwap
timeframe           → M1, M3, M5, M10, M15, M45, H1, H4
timeframe_minutes   → 1, 3, 5, 10, 15, 45, 60, 240
server_time         → 2026.06.07 07:30:30
bid                 → current bid price
ask                 → current ask price
spread              → ask - bid
```

---

## Running vs Closed Bars (every file)

Every file outputs TWO sets of OHLCV data:

- `running_*` = current candle still forming (values WILL change before close)
- `closed_*`  = last completed candle (confirmed, final)

```
running_bar_time    → timestamp of current forming bar
running_open        → open price
running_high        → high so far
running_low         → low so far
running_close       → current close (= latest tick)
running_volume      → tick volume so far

closed_bar_time     → timestamp of last completed bar
closed_open         → open price (final)
closed_high         → high price (final)
closed_low          → low price (final)
closed_close        → close price (final)
closed_volume       → total tick volume (final)
```

**Rule of thumb:**
- Use `closed_*` for confirmed trade signals (candle fully formed)
- Use `running_*` for early detection or monitoring (signal may flip before close)

---

## UT Bot Fields

Computes ATR trailing stop and direction. Detects bias flips (BUY/SELL signals).

```
running_atr              → ATR value on current bar
running_nloss            → ATR * multiplier (the trailing distance)
running_trail_stop       → trailing stop level (current bar)
running_bias             → BULLISH or BEARISH (current direction)
running_signal           → BUY (flipped bull), SELL (flipped bear), or NONE

closed_atr               → ATR value on last closed bar
closed_nloss             → ATR * multiplier
closed_trail_stop        → trailing stop level (confirmed)
closed_bias              → BULLISH or BEARISH (confirmed)
closed_signal            → BUY, SELL, or NONE (confirmed flip on closed candle)

consecutive_bull_bars    → count of consecutive bullish-direction bars
consecutive_bear_bars    → count of consecutive bearish-direction bars

cfg_atr_period           → ATR period used (e.g. 10)
cfg_atr_mult             → ATR multiplier used (e.g. 2.0)
```

**Signal logic:**
- `closed_signal=BUY` → direction flipped from BEARISH to BULLISH on the last closed candle
- `closed_signal=SELL` → direction flipped from BULLISH to BEARISH on the last closed candle
- `closed_signal=NONE` → no direction change, trend continues
- `closed_bias` → current confirmed trend direction

---

## Donchian Channel Fields

Computes upper/lower bands from highest high and lowest low over N bars.
Detects price zone, touches, breakouts, and wick rejections.

```
upper_band               → highest high over lookback period
lower_band               → lowest low over lookback period
mid_band                 → (upper + lower) / 2
channel_width            → upper - lower

running_price_zone       → UPPER | UPPER_MID | MIDDLE | LOWER_MID | LOWER
running_pct_in_channel   → 0-100 (where bid sits within the channel)
running_touched_upper    → TRUE if running bar high >= upper band
running_touched_lower    → TRUE if running bar low <= lower band
running_break_upper      → TRUE if running bar close > upper band
running_break_lower      → TRUE if running bar close < lower band

closed_price_zone        → same zones for closed bar
closed_pct_in_channel    → 0-100
closed_touched_upper     → TRUE/FALSE
closed_touched_lower     → TRUE/FALSE
closed_break_upper       → TRUE/FALSE (confirmed breakout above)
closed_break_lower       → TRUE/FALSE (confirmed breakout below)
closed_upper_wick_rej    → TRUE if wick touched upper but body closed below (bearish rejection)
closed_lower_wick_rej    → TRUE if wick touched lower but body closed above (bullish rejection)

channel_width_sma20      → 20-bar SMA of channel_width (historical average width)
width_vs_sma_ratio       → channel_width / channel_width_sma20 (<1 = narrower than average)
dc_compressed            → TRUE if width_vs_sma_ratio < 0.75 (squeeze/compression detected)

cfg_length               → DC lookback length (e.g. 20)
cfg_offset               → DC offset (e.g. 0)
```

**Price zones** (based on % position in channel):
- UPPER: >= 90%
- UPPER_MID: 70-89%
- MIDDLE: 31-69%
- LOWER_MID: 11-30%
- LOWER: <= 10%

**Compression detection:**
- `dc_compressed=TRUE` → channel width < 75% of its 20-bar average (squeeze forming, expect breakout)
- `width_vs_sma_ratio` < 0.75 → compressed, > 1.2 → expanded

---

## Liquidity Grab Fields

Implements Smart Money Concepts (SMC) liquidity grab detection.
Finds key support/resistance levels, detects wick rejections that sweep past those levels,
then looks for breakout confirmation + moving average trend alignment.

Based on: https://www.mql5.com/en/articles/16518

```
key_high                 → identified resistance level (highest high with rejection confirmation), or "NONE"
key_low                  → identified support level (lowest low with rejection confirmation), or "NONE"
dist_to_key_high         → current high - key_high (negative = below, positive = above)
dist_to_key_low          → current low - key_low (positive = above, negative = below)

rejection_up             → TRUE if a bullish liquidity grab detected (lower wick swept below key_low, body closed above)
rejection_up_bar         → how many bars ago the rejection occurred (-1 if none)
rejection_down           → TRUE if a bearish liquidity grab detected (upper wick swept above key_high, body closed below)
rejection_down_bar       → how many bars ago the rejection occurred (-1 if none)

breakout_up              → TRUE if price broke above a recent key high (bullish breakout after grab)
breakout_down             → TRUE if price broke below a recent key low (bearish breakout after grab)

ma_value                 → SMA value (trend filter)
ma_trend                 → ABOVE (bullish) or BELOW (bearish) — price relative to MA

liq_signal               → composite signal:
                            BUY  = rejection_up + breakout_up + price above MA
                            SELL = rejection_down + breakout_down + price below MA
                            NONE = conditions not met

cfg_lookback             → lookback range for key level search (e.g. 50)
cfg_barsN                → bars for rejection confirmation (e.g. 5)
cfg_wick_ratio           → minimum wick:body ratio for rejection (e.g. 2.0)
cfg_candles_bk           → candles to look back for recent rejections (e.g. 5)
cfg_ma_period            → MA period for trend filter (e.g. 100)
```

**How liquidity grab detection works:**
1. Find key level = highest high (or lowest low) that has price rejection (local peak/trough confirmed by surrounding bars)
2. Look for rejection candle = wick sweeps past the key level but body closes back on the other side, with wick >= `wick_ratio` * body size
3. Look for breakout = after the rejection, price breaks through the opposite key level
4. Filter by trend = price must be on the right side of the MA (above MA for buy, below for sell)
5. All 3 conditions met → composite signal fires

---

## EMA Fields

Computes Exponential Moving Average. Detects price position relative to EMA, distance, and slope direction.

```
running_ema              → EMA value on current forming bar
running_price_vs_ema     → ABOVE or BELOW (bid vs EMA)
running_dist             → bid - EMA (positive = above, negative = below)
running_dist_pct         → distance as % of EMA value

closed_ema               → EMA value on last closed bar
closed_price_vs_ema      → ABOVE or BELOW (close vs EMA)

ema_slope                → RISING, FALLING, or FLAT (EMA direction over last 3 bars)
ema_slope_value          → raw slope value (EMA[0] - EMA[3])

cfg_period               → EMA period (e.g. 9, 21, 50, 200)
```

**Usage patterns:**
- `closed_price_vs_ema=ABOVE` + `ema_slope=RISING` → bullish trend confirmed
- `running_dist_pct` close to 0 → price at EMA (pullback entry zone)
- Compare multiple EMAs (e.g. ema9 vs ema21) for crossover detection in Python

---

## RSI Fields

Computes Relative Strength Index. Classifies into zones and detects key level crosses.

```
running_rsi              → RSI value on current forming bar
running_zone             → zone classification (see below)

closed_rsi               → RSI value on last closed bar
closed_zone              → zone classification
closed_prev_rsi          → RSI value on bar before closed (for cross detection)
closed_cross             → level cross event on closed bar (see below)

cfg_period               → RSI period (e.g. 14, 2)
```

**RSI zones** (based on RSI value):
- `EXTREME_OB`: >= 80
- `OVERBOUGHT`: 70-79
- `BULLISH`: 55-69
- `NEUTRAL`: 45-54
- `BEARISH`: 30-44
- `OVERSOLD`: 20-29
- `EXTREME_OS`: < 20

**Cross events** (detected on closed bar vs previous bar):
- `CROSS_UP_30` → RSI crossed above 30 (leaving oversold)
- `CROSS_DOWN_70` → RSI crossed below 70 (leaving overbought)
- `CROSS_UP_50` → RSI crossed above 50 (bullish momentum shift)
- `CROSS_DOWN_50` → RSI crossed below 50 (bearish momentum shift)
- `CROSS_UP_52` → RSI crossed above 52 (used by some scalping strategies)
- `NONE` → no cross detected

---

## Bollinger Bands Fields

Computes Bollinger Bands (upper, middle, lower). Detects band touches, outside closes, and re-entries.

```
upper_band               → upper band value (running bar)
middle_band              → middle band (SMA)
lower_band               → lower band value
band_width               → upper - lower (absolute width)

running_pct_in_band      → 0-100 (where bid sits within bands, 0=lower, 100=upper)
running_above_upper      → TRUE if bid > upper band
running_below_lower      → TRUE if bid < lower band

closed_pct_in_band       → 0-100 for closed bar
closed_above_upper       → TRUE if close > upper band
closed_below_lower       → TRUE if close < lower band
closed_reenter_from_below → TRUE if bar opened below lower band but closed above it (bullish reversal)
closed_reenter_from_above → TRUE if bar opened above upper band but closed below it (bearish reversal)

bb_bandwidth             → normalized bandwidth: (upper - lower) / middle × 100
bb_bandwidth_sma20       → 20-bar SMA of bb_bandwidth
bb_bandwidth_ratio       → bb_bandwidth / bb_bandwidth_sma20 (<1 = tighter than average)
bb_squeeze               → TRUE if bb_bandwidth_ratio < 0.85 (Bollinger squeeze detected)

cfg_period               → BB period (e.g. 20)
cfg_deviation            → BB standard deviation multiplier (e.g. 2.0)
```

**Usage patterns:**
- `closed_below_lower=TRUE` → price closed outside lower band (mean reversion setup)
- `closed_reenter_from_below=TRUE` → bullish reversal signal (range fade entry)
- `bb_squeeze=TRUE` → Bollinger squeeze detected, expect volatility expansion
- `bb_bandwidth_ratio` < 0.85 → compressed, > 1.2 → expanding
- `running_pct_in_band` near 50 → price at middle band

---

## ADX Fields

Computes Average Directional Index with +DI and -DI. Measures trend strength and direction.

```
running_adx              → ADX value on current bar
running_plus_di          → +DI value (bullish directional)
running_minus_di         → -DI value (bearish directional)

closed_adx               → ADX on last closed bar
closed_plus_di           → +DI confirmed
closed_minus_di          → -DI confirmed
closed_trend_strength    → trend classification (see below)
closed_adx_rising        → TRUE if ADX rising over last 3 bars (trend strengthening)
closed_di_bias           → BULLISH (+DI > -DI) or BEARISH (-DI > +DI)

cfg_period               → ADX period (e.g. 14)
```

**Trend strength levels** (based on closed ADX value):
- `RANGING`: ADX < 18 (no trend, avoid trend-following)
- `WEAK_TREND`: 18-24 (emerging trend)
- `TRENDING`: 25-39 (confirmed trend)
- `STRONG_TREND`: >= 40 (powerful trend)

**Usage patterns:**
- `closed_trend_strength=RANGING` → use mean reversion strategies
- `closed_trend_strength=TRENDING` + `closed_di_bias=BULLISH` → confirmed uptrend
- `closed_adx_rising=TRUE` → trend is strengthening (momentum entry)

---

## MACD Fields

Computes MACD line, signal line, and histogram. Detects histogram flips and zero-line crosses.

```
running_macd             → MACD line value (current bar)
running_signal           → signal line value
running_histogram        → MACD - signal (histogram bar)

closed_macd              → MACD line (confirmed)
closed_signal            → signal line (confirmed)
closed_histogram         → histogram value (confirmed)
closed_hist_cross        → histogram cross event (see below)
closed_zero_cross        → MACD zero-line cross event (see below)

cfg_fast                 → fast EMA period (e.g. 12)
cfg_slow                 → slow EMA period (e.g. 26)
cfg_signal               → signal SMA period (e.g. 9)
```

**Histogram cross events:**
- `BULLISH_FLIP` → histogram crossed from negative to positive (MACD crossed above signal)
- `BEARISH_FLIP` → histogram crossed from positive to negative (MACD crossed below signal)
- `NONE` → no cross

**Zero-line cross events:**
- `CROSS_ABOVE` → MACD line crossed above zero (bullish momentum)
- `CROSS_BELOW` → MACD line crossed below zero (bearish momentum)
- `NONE` → no cross

**Usage patterns:**
- `closed_hist_cross=BULLISH_FLIP` → classic buy signal
- `closed_histogram` increasing → momentum building
- `closed_zero_cross=CROSS_ABOVE` → strong bullish confirmation

---

## Stochastic Fields

Computes Stochastic Oscillator (%K and %D). Detects overbought/oversold zones and K/D crosses.

```
running_k                → %K value (current bar)
running_d                → %D value (signal line)

closed_k                 → %K confirmed
closed_d                 → %D confirmed
closed_zone              → OVERBOUGHT (K>=80), OVERSOLD (K<=20), or NEUTRAL
closed_cross             → K/D cross event (see below)

cfg_k_period             → %K period (e.g. 5)
cfg_d_period             → %D period (e.g. 3)
cfg_slowing              → slowing period (e.g. 3)
```

**Cross events:**
- `BULLISH_OS` → %K crossed above %D while below 25 (strongest buy signal — oversold cross)
- `BULLISH` → %K crossed above %D (general bullish cross)
- `BEARISH_OB` → %K crossed below %D while above 75 (strongest sell signal — overbought cross)
- `BEARISH` → %K crossed below %D (general bearish cross)
- `NONE` → no cross

**Usage patterns:**
- `closed_cross=BULLISH_OS` → high-probability long entry (K crosses D in oversold)
- `closed_zone=OVERSOLD` + waiting for `BULLISH_OS` → re-entry setup
- Combine with ADX trend filter: only take `BULLISH_OS` when `closed_di_bias=BULLISH`

---

## ATR Fields (standalone)

Computes Average True Range with SMA smoothing for volatility regime detection.
Note: ATR is also used internally by UT Bot, but these are standalone ATR instances.

```
running_atr              → ATR value (current bar)
running_atr_pct          → ATR as % of price (normalized volatility)
closed_atr               → ATR confirmed (last closed bar)
atr_sma20                → 20-bar simple moving average of ATR
atr_vs_sma_ratio         → running_atr / atr_sma20 (>1 = above average volatility)
volatility_state         → regime classification (see below)

cfg_period               → ATR period (e.g. 14)
```

**Volatility states** (based on ATR vs its 20-bar SMA ratio):
- `EXPANDING`: ratio > 1.2 (volatility surging — breakout or panic)
- `ABOVE_AVG`: ratio 1.0-1.2 (above normal — active market)
- `BELOW_AVG`: ratio 0.8-1.0 (below normal — quiet market)
- `CONTRACTING`: ratio < 0.8 (volatility drying up — squeeze forming)

**Usage patterns:**
- `volatility_state=CONTRACTING` → squeeze setup, expect breakout
- `volatility_state=EXPANDING` → widen stops, avoid mean reversion
- `running_atr_pct` → use for position sizing (higher ATR% = smaller position)
- `running_atr` → use for stop-loss distance (e.g. 1.5 × ATR)

---

## VWAP Fields (session)

Computes Volume-Weighted Average Price from session start (00:00 server time).
VWAP = Σ(typical_price × volume) / Σ(volume), where typical_price = (H+L+C)/3.
Always computed from M1 bars regardless of output timeframe. Resets daily.

```
vwap                     → current session VWAP value
running_price_vs_vwap    → ABOVE or BELOW (bid vs VWAP)
running_dist_to_vwap     → bid - VWAP (positive = above, negative = below)
running_dist_pct         → distance as % of VWAP value
closed_price_vs_vwap     → ABOVE or BELOW (last closed bar close vs VWAP)
closed_dist_to_vwap      → close - VWAP
session_m1_bars          → number of M1 bars since session start (session maturity)
cum_volume               → cumulative tick volume since session start
```

**Usage patterns:**
- `closed_price_vs_vwap=ABOVE` → price above fair value (bullish intraday bias)
- `running_dist_pct` close to 0 → price at VWAP (mean level, pullback zone)
- `running_dist_pct` > 0.1 → significantly above VWAP (extended, mean reversion risk)
- `session_m1_bars` < 30 → early session, VWAP not yet mature (less reliable)
- Combine with trend filters: only buy when above VWAP, only sell when below

---

## How to Read Any Signal File (Generic Parser)

```python
import csv

def read_signal(filepath):
    """Read a signal CSV and return as dict."""
    signals = {}
    try:
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # skip header row
            for row in reader:
                if len(row) >= 2:
                    signals[row[0].strip()] = row[1].strip()
    except (FileNotFoundError, StopIteration):
        pass
    return signals

# Example:
sig = read_signal("/data/signals/BTCUSDT_utbot_M1.csv")
print(sig.get("closed_bias"))     # "BULLISH"
print(sig.get("closed_signal"))   # "BUY" / "SELL" / "NONE"
print(sig.get("indicator"))       # "utbot"
print(sig.get("timeframe"))       # "M1"
```

The `indicator` field in every file tells you which set of fields to expect.
All files share the same standard header + bar fields, so a generic reader works for all.

---

## Example Trade Trigger Ideas

These combine multiple signals across indicators and timeframes:

1. **DC Low + UT Bot Confluence Buy**: DC M15 `closed_price_zone=LOWER` AND UT Bot M1 `closed_signal=BUY` AND UT Bot M45 `consecutive_bull_bars >= 5`

2. **DC Wick Rejection Buy**: DC M15 `closed_lower_wick_rej=TRUE` AND UT Bot M3 `closed_bias=BULLISH`

3. **UT Bot Multi-TF Alignment**: UT Bot M1 `closed_signal=BUY` AND UT Bot M15 `closed_bias=BULLISH` AND UT Bot M45 `closed_bias=BULLISH`

4. **Liquidity Grab + UT Bot**: LiqGrab M15 `liq_signal=BUY` AND UT Bot M1 `closed_bias=BULLISH`

5. **Liquidity Grab + DC Support**: LiqGrab H1 `rejection_up=TRUE` AND DC M15 `closed_price_zone=LOWER_MID` AND UT Bot M3 `closed_signal=BUY`

6. **DC Breakout + Trend Confirmation**: DC M15 `closed_break_upper=TRUE` AND LiqGrab H1 `ma_trend=ABOVE` AND UT Bot M15 `closed_bias=BULLISH`
