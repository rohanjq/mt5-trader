# Strategy Testing Guide

## Strategy Files

Single-condition BUY strategies live in `strategies/buy/`. Each file has just an expression:

```yaml
name: candle_m5_hammer
description: M5 hammer candle
buy:
- candle_M5.closed_candle_type == HAMMER
```

Production strategies (with SL, RR, etc.) live in `strategies/`.

---

## run_combos.py — Combo Backtest Runner

The main tool for exploring strategy ideas. Runs every strategy file through all SL/RR combinations with extra filters ANDed on.

### Basic Usage

```bash
# Run all 74 buy strategies with defaults (SL=7.5, RR=1.0)
uv run python tests/run_combos.py

# Run from a different folder
uv run python tests/run_combos.py --dir strategies/sell
```

### Filter Specific Strategies (--only)

Supports exact names and wildcards (`*`, `?`):

```bash
# Exact names (comma-separated)
uv run python tests/run_combos.py --only utbot_m2_buy,candle_m5_hammer

# Wildcards
uv run python tests/run_combos.py --only "candle_*"
uv run python tests/run_combos.py --only "utbot_m5_*"
uv run python tests/run_combos.py --only "ema*,dc_*"
uv run python tests/run_combos.py --only "*_hammer"
uv run python tests/run_combos.py --only "*_m15_*"
```

### SL / RR Grid (--sl, --rr)

Comma-separated values. Every combination is tested per strategy:

```bash
# 3 SL × 2 RR = 6 combos per strategy
uv run python tests/run_combos.py --sl 5,7.5,10 --rr 1.0,1.5

# Fine-grained SL scan
uv run python tests/run_combos.py --only "candle_*" --sl 3,4,5,6,7.5,10 --rr 1.0
```

### Extra Filters (--filter)

Conditions ANDed to every strategy. Use `--filter` multiple times:

```bash
# Add second-wave pullback filter
uv run python tests/run_combos.py \
    --filter "utbot_M5.consecutive_bear_bars >= 2"

# Add DC zone + VWAP filter
uv run python tests/run_combos.py \
    --filter "dc_M15.closed_price_zone in LOWER,LOWER_MID" \
    --filter "vwap_M1.closed_price_vs_vwap == ABOVE"

# M15 bullish bias + M5 bounce
uv run python tests/run_combos.py \
    --filter "utbot_M15.closed_bias == BULLISH" \
    --filter "utbot_M5.consecutive_bear_bars >= 2"
```

### Breakeven (--breakeven_pct)

```bash
uv run python tests/run_combos.py --breakeven_pct 0.5 --sl 5,7.5
```

### Full Example

```bash
# Test all candle strategies with second-wave + DC filter, scanning SL and RR
uv run python tests/run_combos.py \
    --only "candle_*" \
    --sl 5,7.5,10 \
    --rr 1.0,1.5,2.0 \
    --filter "utbot_M5.consecutive_bear_bars >= 2" \
    --filter "dc_M15.closed_price_zone in LOWER,LOWER_MID" \
    --breakeven_pct 0.5
```

### All Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dir` | `strategies/buy` | Folder with strategy YAML files |
| `--only` | all | Comma-separated names/wildcards to include |
| `--sl` | `7.5` | Comma-separated SL values |
| `--rr` | `1.0` | Comma-separated reward ratios |
| `--filter` | none | Extra condition (repeatable, ANDed) |
| `--breakeven_pct` | `0.0` | Breakeven percentage |
| `--data` | `sampledata/XAUUSD_M1_60d.csv` | Price data file |
| `--balance` | `10000` | Starting balance |

---

## run_all_strategies.py — Production Strategy Report

Tests all strategies from `strategies/` (the production ones with SL/RR baked in). Supports overrides.

```bash
# Run all enabled production strategies
uv run python tests/run_all_strategies.py

# Override SL and RR for all
uv run python tests/run_all_strategies.py --sl_dollars 3.0 --reward_ratio 2.0

# Wildcard filter
uv run python tests/run_all_strategies.py --only "dc_*"

# Include disabled strategies
uv run python tests/run_all_strategies.py --include-disabled
```

---

## Available Indicator Expressions

### UT Bot (`utbot`)
| Expression | Values |
|-----------|--------|
| `closed_signal` | `BUY`, `SELL`, `NONE` |
| `closed_bias` | `BULLISH`, `BEARISH` |
| `consecutive_bull_bars` | numeric |
| `consecutive_bear_bars` | numeric |

### Donchian Channel (`dc`)
| Expression | Values |
|-----------|--------|
| `closed_price_zone` | `UPPER`, `UPPER_MID`, `MIDDLE`, `LOWER_MID`, `LOWER` |
| `closed_upper_wick_rej` | `TRUE`, `FALSE` |
| `closed_lower_wick_rej` | `TRUE`, `FALSE` |

### EMA (`ema9`, `ema21`, `ema50`, `ema200`)
| Expression | Values |
|-----------|--------|
| `closed_price_vs_ema` | `ABOVE`, `BELOW` |
| `ema_slope` | `RISING`, `FALLING`, `FLAT` |

### RSI (`rsi14`, `rsi2`)
| Expression | Values |
|-----------|--------|
| `closed_zone` | `EXTREME_OB`, `OVERBOUGHT`, `BULLISH`, `NEUTRAL`, `BEARISH`, `OVERSOLD`, `EXTREME_OS` |
| `closed_cross` | `CROSS_UP_30`, `CROSS_DOWN_70`, `CROSS_UP_50`, `CROSS_DOWN_50`, `NONE` |
| `closed_rsi` | numeric (0–100) |

### VWAP (`vwap`)
| Expression | Values |
|-----------|--------|
| `closed_price_vs_vwap` | `ABOVE`, `BELOW` |

### ADX (`adx14`)
| Expression | Values |
|-----------|--------|
| `closed_trend_strength` | `STRONG_TREND`, `TRENDING`, `WEAK_TREND`, `RANGING` |
| `closed_di_bias` | `BULLISH`, `BEARISH` |
| `closed_adx_rising` | `TRUE`, `FALSE` |

### MACD (`macd12_26_9`)
| Expression | Values |
|-----------|--------|
| `closed_hist_cross` | `BULLISH_FLIP`, `BEARISH_FLIP`, `NONE` |
| `closed_zero_cross` | `CROSS_ABOVE`, `CROSS_BELOW`, `NONE` |
| `closed_histogram` | numeric |

### Stochastic (`stoch5_3_3`)
| Expression | Values |
|-----------|--------|
| `closed_cross` | `BULLISH_OS`, `BULLISH`, `BEARISH_OB`, `BEARISH`, `NONE` |
| `closed_zone` | `OVERBOUGHT`, `OVERSOLD`, `NEUTRAL` |

### Bollinger Bands (`bb20d2`)
| Expression | Values |
|-----------|--------|
| `closed_reenter_from_below` | `TRUE`, `FALSE` |
| `closed_reenter_from_above` | `TRUE`, `FALSE` |
| `closed_pct_in_band` | numeric (0–100) |
| `bb_squeeze` | `TRUE`, `FALSE` |

### ATR (`atr14`)
| Expression | Values |
|-----------|--------|
| `volatility_state` | `EXPANDING`, `ABOVE_AVG`, `BELOW_AVG`, `CONTRACTING` |

### Liquidity Grab (`liqgrab`)
| Expression | Values |
|-----------|--------|
| `closed_key_high` | numeric (structural pivot high) |
| `closed_key_low` | numeric (structural pivot low) |
| `closed_rejection_up` | `TRUE`, `FALSE` (bullish wick grab at key low) |
| `closed_rejection_down` | `TRUE`, `FALSE` (bearish wick grab at key high) |
| `closed_rejection_up_count` | numeric (count of rej-up bars in window) |
| `closed_rejection_down_count` | numeric (count of rej-down bars in window) |
| `closed_breakout_up` | `TRUE`, `FALSE` (closed above key high) |
| `closed_breakout_down` | `TRUE`, `FALSE` (closed below key low) |
| `closed_ma_trend` | `ABOVE`, `BELOW` (vs SMA100) |
| `closed_liq_signal` | `BUY`, `SELL`, `NONE` (composite: rejection + breakout + MA) |

Default params: lookback=50, barsN=5, wickRatio=2.0, candlesBk=5, maPeriod=100.

### Candle (`candle`)
| Expression | Values |
|-----------|--------|
| `closed_candle_type` | `MARUBOZU`, `HAMMER`, `SHOOTING_STAR`, `DOJI`, `SPINNING_TOP`, `NORMAL` |
| `closed_candle_dir` | `UP`, `DOWN`, `DOJI` |
| `closed_is_bullish` | `TRUE`, `FALSE` |
| `closed_is_bearish` | `TRUE`, `FALSE` |
| `closed_has_long_upper` | `TRUE`, `FALSE` |
| `closed_has_long_lower` | `TRUE`, `FALSE` |

### Operators
`==`, `!=`, `>=`, `<=`, `>`, `<`, `in` (comma-separated), `not_in`, `is`, `is_not`

### Timeframes
`M1`, `M2`, `M3`, `M5`, `M10`, `M15`, `M30`, `M45`, `H1`, `H4`

### Expression Format
```
{indicator}_{timeframe}.{field} {operator} {value}
```
Example: `utbot_M15.closed_bias == BULLISH`
