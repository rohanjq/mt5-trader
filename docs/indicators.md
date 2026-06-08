# Indicator Reference

Complete reference for all indicators available in signal expressions. Each indicator is identified by `{indicator}_{timeframe}` (e.g., `utbot_M1`, `rsi14_M5`).

## UT Bot Alert (`utbot`)

Trend-following indicator based on ATR trailing stop crossovers.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_signal` | enum | `BUY`, `SELL`, `NONE` | One-bar flash signal on crossover |
| `closed_bias` | enum | `BULLISH`, `BEARISH`, `NONE` | Current directional bias (persists) |
| `closed_atr` | float | | Current ATR value |
| `trailing_stop` | float | | Current UT Bot trailing stop level |
| `consecutive_bull_bars` | int | | Consecutive bars with bullish bias |
| `consecutive_bear_bars` | int | | Consecutive bars with bearish bias |
| `atr_key_value` | float | | ATR sensitivity multiplier |
| `above_trailing` | enum | `TRUE`, `FALSE` | Price above trailing stop |
| `ema_value` | float | | EMA value used in calculation |

**Key usage**: `closed_signal` is the entry trigger (fires once per crossover). `closed_bias` is the trend filter (persists until next crossover).

## Donchian Channel (`dc`)

Price channel based on highest high / lowest low over N periods.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_price_zone` | enum | `UPPER`, `UPPER_MID`, `MID`, `LOWER_MID`, `LOWER` | Price position in channel |
| `dc_compressed` | enum | `TRUE`, `FALSE` | Channel width below threshold |
| `channel_width` | float | | Upper band − lower band |
| `upper_band` | float | | Channel upper boundary |
| `lower_band` | float | | Channel lower boundary |
| `mid_band` | float | | Channel midline |
| `closed_upper_wick_rej` | enum | `TRUE`, `FALSE` | Wick rejection at upper band |
| `closed_lower_wick_rej` | enum | `TRUE`, `FALSE` | Wick rejection at lower band |
| `closed_breakout_up` | enum | `TRUE`, `FALSE` | Price broke above upper band |
| `closed_breakout_down` | enum | `TRUE`, `FALSE` | Price broke below lower band |

## EMA (`ema9`, `ema21`, `ema50`, `ema200`)

Exponential Moving Average with slope detection.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_price_vs_ema` | enum | `ABOVE`, `BELOW` | Price relative to EMA |
| `ema_slope` | enum | `RISING`, `FALLING`, `FLAT` | EMA direction |
| `ema_value` | float | | Current EMA value |

## RSI (`rsi14`, `rsi2`)

Relative Strength Index.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_rsi` | float | 0-100 | Current RSI value |
| `closed_zone` | enum | `EXTREME_OB`, `OB`, `NEUTRAL`, `OS`, `EXTREME_OS` | RSI zone |
| `closed_cross` | enum | `CROSS_UP_50`, `CROSS_DOWN_50`, `CROSS_UP_52`, `NONE` | Level crossings |

**RSI2 zones**: EXTREME_OB (>95), OB (>80), NEUTRAL, OS (<20), EXTREME_OS (<5)  
**RSI14 zones**: OB (>70), NEUTRAL, OS (<30)

## ADX (`adx14`)

Average Directional Index — measures trend strength, not direction.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_adx` | float | 0-100 | ADX value |
| `closed_trend_strength` | enum | `RANGING`, `WEAK_TREND`, `TRENDING`, `STRONG_TREND` | ADX-based regime |
| `closed_di_bias` | enum | `BULLISH`, `BEARISH`, `NEUTRAL` | DI+ vs DI- comparison |

**Strength thresholds**: RANGING (<20), WEAK_TREND (20-25), TRENDING (25-40), STRONG_TREND (>40)

## MACD (`macd12_26_9`)

Moving Average Convergence Divergence.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_cross` | enum | `CROSS_UP`, `CROSS_DOWN`, `NONE` | MACD/signal line crossover |
| `histogram_direction` | enum | `RISING`, `FALLING` | Histogram momentum direction |
| `macd_vs_zero` | enum | `ABOVE`, `BELOW` | MACD line position vs zero |

## Stochastic (`stoch5_3_3`)

Stochastic Oscillator.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `stoch_k` | float | 0-100 | %K value |
| `stoch_zone` | enum | `OB`, `NEUTRAL`, `OS` | OB (>80), OS (<20) |

## Bollinger Bands (`bb20d2`)

Bollinger Bands with squeeze detection.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_reenter_from_below` | enum | `TRUE`, `FALSE` | Price re-entered bands from below lower band |
| `closed_reenter_from_above` | enum | `TRUE`, `FALSE` | Price re-entered bands from above upper band |
| `bb_squeeze` | enum | `TRUE`, `FALSE` | Bands contracted (low volatility) |
| `bb_width_pct` | float | | Band width as % of middle band |
| `closed_band_position` | enum | `ABOVE_UPPER`, `UPPER_HALF`, `LOWER_HALF`, `BELOW_LOWER` | Price within bands |

## ATR (`atr14`)

Average True Range — measures volatility.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `running_atr` | float | | Current ATR value |
| `volatility_state` | enum | `EXPANDING`, `ABOVE_AVG`, `BELOW_AVG`, `CONTRACTING` | ATR vs its 20-period SMA |
| `atr_vs_sma_ratio` | float | | ATR / SMA(ATR, 20) ratio |

**State thresholds**: EXPANDING (≥1.3), ABOVE_AVG (≥1.0), BELOW_AVG (≥0.7), CONTRACTING (<0.7)

## VWAP (`vwap`)

Volume Weighted Average Price, reset at session boundary (22:00 UTC / 5 PM ET).

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_price_vs_vwap` | enum | `ABOVE`, `BELOW` | Price relative to VWAP |
| `running_dist_pct` | float | | Distance from VWAP as percentage |

## Expression Examples

```yaml
# UT Bot crossover with trend alignment
- utbot_M1.closed_signal == BUY
- utbot_M5.closed_bias == BULLISH

# RSI oversold bounce
- rsi2_M1.closed_zone == EXTREME_OS
- rsi14_M1.closed_rsi > 50

# ADX trending with directional bias
- adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND
- adx14_M1.closed_di_bias == BULLISH

# Bollinger squeeze breakout
- bb20d2_M1.bb_squeeze is TRUE
- dc_M1.dc_compressed is TRUE
- atr14_M1.volatility_state in EXPANDING,ABOVE_AVG

# VWAP proximity filter
- vwap_M1.closed_price_vs_vwap == ABOVE
- vwap_M1.running_dist_pct < 3.0

# EMA trend stack
- ema200_M5.closed_price_vs_ema == ABOVE
- ema50_M5.ema_slope == RISING
- ema9_M1.closed_price_vs_ema == ABOVE
```
