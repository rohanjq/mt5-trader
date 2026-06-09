# Expression Reference

Complete reference for YAML strategy expression syntax used in `config-gold.yaml` under `rules.expressions`.

## Syntax

```
signal_name.field_name OPERATOR value
```

- `signal_name` = `{indicator}_{timeframe}` (e.g., `utbot_M1`, `rsi14_M5`, `ema200_M15`)
- `field_name` = indicator output field (e.g., `closed_signal`, `closed_rsi`, `ema_slope`)
- `OPERATOR` = comparison operator (see below)
- `value` = expected value (string, number, or comma-separated list)

## Operators

| Operator | Type | Description | Example |
|----------|------|-------------|---------|
| `==` | string/numeric | Equals (case-insensitive) | `utbot_M1.closed_signal == BUY` |
| `!=` | string/numeric | Not equals | `utbot_M1.closed_bias != BEARISH` |
| `>` | numeric | Greater than | `rsi14_M5.closed_rsi > 50` |
| `<` | numeric | Less than | `rsi2_M5.closed_rsi < 5` |
| `>=` | numeric | Greater or equal | `utbot_M45.consecutive_bull_bars >= 5` |
| `<=` | numeric | Less or equal | `adx14_M5.closed_adx <= 20` |
| `in` | set | Value is one of comma-separated list | `adx14_M5.closed_trend_strength in TRENDING,STRONG_TREND` |
| `not_in` | set | Value is NOT in list | `dc_M15.closed_price_zone not_in LOWER,LOWER_MID` |
| `is` | boolean | Alias for `== TRUE` | `dc_M15.closed_lower_wick_rej is TRUE` |
| `is_not` | boolean | Alias for `!= TRUE` | `bb20d2_M1.bb_squeeze is_not TRUE` |

## Strategy Block Format

```yaml
rules:
  expressions:
    - name: my_strategy_name        # Unique identifier
      enabled: true                  # Toggle on/off (hot-reloadable)
      direction: BUY                 # BUY or SELL
      sl_dollars: 3.0               # Override default SL (optional)
      reward_ratio: 1.5             # Override default RR (optional)
      conditions:
        - utbot_M1.closed_signal == BUY
        - ema200_M5.closed_price_vs_ema == ABOVE
        - adx14_M5.closed_trend_strength in TRENDING,STRONG_TREND
```

**All conditions must be true simultaneously** for the strategy to trigger (AND logic).

## Available Timeframes

M1, M2, M3, M5, M10, M15, M20, M30, H1, H2, H3, H4, H6, H8, H12, D1

**Synthetic**: M45 (constructed from M15 bars in backtester)

## Expression Examples by Category

### Trend Following
```yaml
# UT Bot crossover with trend confirmation
- utbot_M1.closed_signal == BUY
- utbot_M15.closed_bias == BULLISH
- utbot_M45.consecutive_bull_bars >= 3

# EMA alignment (price above all EMAs)
- ema50_M15.closed_price_vs_ema == ABOVE
- ema200_M15.closed_price_vs_ema == ABOVE
- ema50_M15.ema_slope == RISING
```

### Mean Reversion (RSI2)
```yaml
# RSI2 extreme oversold bounce
- rsi2_M5.closed_zone == EXTREME_OS
- ema200_M5.closed_price_vs_ema == ABOVE
- adx14_M5.closed_trend_strength in TRENDING,STRONG_TREND
```

### Structure / Support
```yaml
# Donchian channel wick rejection at lower band
- dc_M15.closed_lower_wick_rej is TRUE
- ema50_M15.ema_slope == RISING
- utbot_H1.closed_bias == BULLISH
```

### Volatility Filters
```yaml
# Only trade during expanding volatility
- atr14_M5.volatility_state in EXPANDING,ABOVE_AVG

# Bollinger squeeze (expect breakout)
- bb20d2_M1.bb_squeeze is TRUE

# Donchian compression
- dc_M15.dc_compressed is TRUE
```

### VWAP Confluence
```yaml
# Price above session VWAP (bullish intraday bias)
- vwap_M1.closed_price_vs_vwap == ABOVE

# Near VWAP pullback zone
- vwap_M1.running_dist_pct < 0.02
- vwap_M1.running_dist_pct > -0.02
```

### Multi-Timeframe Confirmation
```yaml
# H1 bullish structure
- utbot_H1.closed_bias == BULLISH

# M15 structure
- ema50_M15.ema_slope == RISING
- dc_M15.closed_lower_wick_rej is TRUE

# M5 entry trigger
- rsi2_M5.closed_zone == EXTREME_OS
```

## Proven Winning Strategies (60-day bearish XAUUSD data)

| Strategy | PF | Trades | Key Conditions |
|----------|---:|-------:|----------------|
| `rsi2_mean_rev_ema200_adx` | 1.41 | 67 | RSI2 M5 extreme OS + EMA200 above + ADX trending |
| `rsi2_mean_rev_full` | 1.40 | 61 | Above + H1 bullish |
| `ema50_dc_wick_h1` | 1.88 | 32 | EMA50 M15 rising + DC M15 wick rej + H1 bullish |
| `rsi2_dc_wick` | 4.27 | 15 | RSI2 M5 extreme OS + EMA200 above + DC M15 wick rej |

## Tips

- Use `closed_*` fields for confirmed signals (candle fully closed)
- Use `running_*` fields for early detection (candle still forming — may flip)
- M15+ timeframes work best for structural signals (DC zones, wick rejections)
- M1-M5 timeframes work best for entry triggers (RSI2, UT Bot crossover)
- Always validate on the longest dataset available (60-day > 1-week)
- Tight SL (3-5) beats wide SL (7.5-10) for bounce-entry strategies
