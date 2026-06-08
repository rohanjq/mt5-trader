# Backtester

## Overview

The backtester is a signal-replay engine that simulates live trading using historical M1 OHLC data. It computes all indicators locally (no MT5 needed), evaluates the same YAML expression rules used in live trading, and simulates order fills with SL/TP management.

## Usage

```bash
# Run backtest with gold config against sample data
uv run python -m backtest --config config-gold.yaml --data sampledata/sample.csv --balance 10000

# With date range filter
uv run python -m backtest --config config-gold.yaml --data data/XAUUSD_M1.csv \
    --balance 10000 --start 2026-06-01 --end 2026-06-07
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--config` | (required) | Path to YAML config file |
| `--data` | (required) | Path to OHLC CSV file |
| `--balance` | 10000.0 | Starting account balance |
| `--start` | (none) | Start date filter (YYYY-MM-DD) |
| `--end` | (none) | End date filter (YYYY-MM-DD) |

## How It Works

### Step 1: Load Data

`backtest/data_loader.py` reads OHLC CSV with auto-detected delimiter and column normalisation. Supports various column name formats (tick_volume, tickvol, vol, etc.).

Required columns: `time`, `open`, `high`, `low`, `close`  
Optional: `volume` (defaults to 0 if missing)

### Step 2: Compute Indicators

`backtest/indicators.py` computes all indicators defined in the config's `signals.sources` using vectorised pandas-ta operations. For multi-timeframe indicators:

1. Resample M1 data to target timeframe (M3, M5, M15, etc.)
2. Compute indicator on the resampled data
3. Forward-fill results back to M1 resolution

#### Supported Indicators

| Indicator | Config Key | Fields Generated |
|-----------|-----------|-----------------|
| UT Bot Alert | `utbot` | closed_signal, closed_bias, closed_atr, consecutive_bull_bars, consecutive_bear_bars, ... |
| Donchian Channel | `dc` | closed_price_zone, dc_compressed, channel_width, upper_band, lower_band, ... |
| EMA (any period) | `ema9`, `ema21`, `ema50`, `ema200` | closed_price_vs_ema, ema_slope, ema_value |
| RSI | `rsi14`, `rsi2` | closed_rsi, closed_zone, closed_cross |
| ADX | `adx14` | closed_adx, closed_trend_strength, closed_di_bias |
| MACD | `macd12_26_9` | closed_cross, histogram_direction, macd_vs_zero |
| Stochastic | `stoch5_3_3` | stoch_k, stoch_zone |
| Bollinger Bands | `bb20d2` | closed_reenter_from_below, closed_reenter_from_above, bb_squeeze, bb_width_pct |
| ATR | `atr14` | running_atr, volatility_state, atr_vs_sma_ratio |
| VWAP | `vwap` | closed_price_vs_vwap, running_dist_pct |

### Step 3: Bar-by-Bar Replay

`backtest/runner.py` iterates through each M1 bar:

```
For each bar i:
  1. Check SL/TP on open positions (using bar open, high, low, close)
  2. Fill pending entries from previous bar's signals at this bar's OPEN price
  3. Build signal snapshot from precomputed indicators at bar i
  4. Evaluate expression rules against signals
  5. Queue triggered entries for next bar's open (no look-ahead bias)
```

**Important**: Signals are evaluated on bar i's close data, but entries fill at bar i+1's open. This prevents look-ahead bias — the system cannot trade on information that wasn't available yet.

### Step 4: Order Simulation

`backtest/simulator.py` manages simulated positions:

- **Entry**: At next bar's open price after signal fires
- **SL/TP Check**: Against each bar's high and low
- **Same-bar ambiguity**: When both SL and TP are hit in the same bar, uses bar open direction to decide which fires first
- **Volume sizing**: `volume = (balance × risk_pct / 100) / ((sl_dollars / tick_size) × tick_value)`
- **Spread**: Optional spread deduction from entry price
- **Commission**: Optional per-lot commission

#### Backtest-Specific Config

These settings go under the `backtest` key in the YAML config:

| Key | Default | Description |
|-----|---------|-------------|
| `initial_balance` | 10000.0 | Starting account balance |
| `tick_size` | 0.01 | Price increment per tick |
| `tick_value` | 1.0 | Dollar value per tick per lot (XAUUSD: $1.00) |
| `volume_step` | 0.01 | Minimum volume increment |
| `commission_per_lot` | 0.0 | Commission charged per lot |
| `spread_points` | 0.0 | Spread in points (applied to entry) |

### Step 5: Results

`backtest/stats.py` computes and displays:

- Total trades, win rate, net profit, ROI
- Profit factor, expectancy
- Average win/loss, average duration
- Max consecutive wins/losses
- Max drawdown (from peak balance)
- Breakdown by direction (LONG/SHORT)
- Breakdown by strategy
- Breakdown by exit reason (SL/TP/BREAKEVEN/END_OF_DATA)
- Trade log (first 50 trades)

## Backtest Filters

`backtest/filters.py` implements a simplified filter chain for backtesting. It reads the same config keys as the live system:

- **Cooldown**: `filters.cooldown_seconds` — blocks re-entry for N seconds after any trade
- **Reversal cooldown**: `filters.reversal_cooldown_seconds` — blocks direction reversal for N seconds
- **Consecutive loss**: `filters.max_consecutive_losses` — pauses after N losses in a row

## Shared Code with Live System

The backtester imports directly from the live trading codebase:

| Import | Module | Usage |
|--------|--------|-------|
| `Config` | `core/config.py` | Same YAML config parser |
| `Signal`, `SignalDirection` | `core/models.py` | Same signal data model |
| `ExpressionRule`, `load_expression_rules` | `rules/expression.py` | Same strategy evaluation engine |

This ensures the backtester evaluates strategies identically to live trading.

## Strategy Permutation Testing

The `tests/run_permutations.py` script generates multiple test configs with different indicator combinations and runs them all:

```bash
uv run python tests/run_permutations.py --data sampledata/sample.csv
```

It creates YAML configs in `tests/configs/`, runs each backtest, parses the results, and produces a comparison table sorted by profit factor. This is useful for finding optimal indicator combinations for a given strategy.

## Downloading Historical Data

```bash
# Requires MT5 connection via rpyc bridge
uv run python scripts/download_ohlc.py
```

This fetches M1 OHLC data from MT5 and saves it to `data/XAUUSD_M1.csv`. The data file is gitignored (large CSVs). A sample file is provided in `sampledata/sample.csv`.

## Known Limitations

1. **Bar-based simulation**: Cannot simulate intra-bar price movement. SL/TP are checked against bar high/low only.
2. **No slippage model**: Fills are assumed at exact SL/TP/open prices.
3. **VWAP session reset**: Resets at 22:00 UTC (5 PM ET) to match typical forex broker sessions. May differ from your broker.
4. **Forward-fill on resample**: Higher-TF indicators are forward-filled to M1 resolution. The first few bars of each session may have stale values until enough data accumulates.
