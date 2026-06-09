# Development Guide

How to add new indicators, modify the EA, and keep the backtester and live system in sync.

## The Dual-Implementation Rule

Every indicator exists in **two places**:

| Component | File | Language | Purpose |
|-----------|------|----------|---------|
| **EA** | `MQL5/Experts/SignalMaster.mq5` | MQL5 | Computes indicators live → writes CSV |
| **Backtester** | `backtest/indicators.py` | Python | Computes same indicators from historical OHLC |

**When you add or change an indicator, update BOTH files.** The backtester must produce identical field names and values as the EA's CSV output.

## Adding a New Indicator

### Step 1: Add to SignalMaster EA (`MQL5/Experts/SignalMaster.mq5`)

1. Add input parameters for the new indicator config (timeframes, periods, etc.)
2. Add the `Write<Name>Signal()` function that computes the indicator and writes CSV
3. Call it from `OnTimer()` alongside existing indicators
4. CSV output must include the standard header (symbol, indicator, timeframe, server_time, bid, ask, spread)
5. Add the `running_*` and `closed_*` field pairs

### Step 2: Add to backtester (`backtest/indicators.py`)

1. Add a `compute_<name>()` function that takes M1 OHLC DataFrame + params
2. Use pandas-ta or manual computation to match the EA's logic
3. Return a DataFrame with the same field names as the EA's CSV
4. Register it in the `INDICATOR_REGISTRY` dict at the bottom of the file

### Step 3: Add signal source to config

```yaml
signals:
  sources:
    - indicator: myindicator
      timeframes: [M1, M5, M15]
```

### Step 4: Add to signal reader (`signals/generic.py` or new file)

The `GenericCSVSignal` reader handles most indicators automatically — it reads any CSV with `key,value` format. Only create a custom signal reader if you need special parsing logic.

### Step 5: Create strategy expressions

```yaml
rules:
  expressions:
    - name: my_new_strategy
      enabled: true
      direction: BUY
      conditions:
        - myindicator_M5.some_field == SOME_VALUE
```

### Step 6: Rebuild Docker container

In the companion [MetaTrader5-Docker](https://github.com/rohanjq/MetaTrader5-Docker) repo:

```bash
cd ../MetaTrader5-Docker
docker compose up -d --build
```

The Dockerfile copies `MQL5/` from `../mt5-trader/MQL5` and the startup script auto-compiles all `.mq5` files.

## Field Naming Conventions

| Prefix | Meaning |
|--------|---------|
| `running_` | Current candle still forming (may change) |
| `closed_` | Last completed candle (confirmed, final) |
| `cfg_` | Configuration parameter (static) |
| no prefix | Computed state field (e.g., `channel_width`, `ema_value`) |

## Multi-Timeframe Resampling (Backtester)

The backtester stores all data at M1 resolution. For higher timeframes:

1. Resample M1 data to target timeframe (e.g., M15 OHLC from M1 bars)
2. Compute indicator on resampled data
3. Forward-fill results back to M1 resolution

This means the first few bars of each session may have stale higher-TF values until enough data accumulates.

## Docker Workflow

Docker infrastructure lives in the companion repo [MetaTrader5-Docker](https://github.com/rohanjq/MetaTrader5-Docker). Both repos should be cloned as siblings:

```
repos/
├── mt5-trader/           ← this repo (EA source + Python trader)
└── MetaTrader5-Docker/   ← Docker container (builds with ../mt5-trader/MQL5)
```

### Rebuilding After EA Changes

```bash
# 1. Edit MQL5/Experts/SignalMaster.mq5 in mt5-trader
# 2. Rebuild container:
cd ../MetaTrader5-Docker
docker compose up -d --build
```

The Dockerfile copies `../mt5-trader/MQL5` into the container, and `start.sh` auto-compiles using MetaEditor64.

## Testing a New Indicator

1. Add to EA and backtester (steps above)
2. Create a test strategy expression in `config-gold.yaml`
3. Run backtest:
   ```bash
   uv run python -m backtest --config config-gold.yaml --data sampledata/XAUUSD_M1_60d.csv --balance 10000
   ```
4. Check that the indicator fields appear in the backtest output
5. Test multiple SL/RR combos:
   ```bash
   uv run python tests/run_combos.py --data sampledata/XAUUSD_M1_60d.csv
   ```

## Common Pitfalls

- **Field name mismatch**: EA writes `closed_signal` but backtester computes `signal` → strategy silently fails
- **M45 timeframe**: Not a real MT5 timeframe. EA uses M15 bars×3 to synthesize it. Backtester does the same.
- **real_volume is always 0**: Use `tick_volume` instead (forex/CFD markets don't report real volume)
- **Forward-fill lag**: Higher-TF indicators may show stale values at session start until enough bars accumulate
- **RSI2 extremes**: RSI with period=2 uses zones EXTREME_OS (<5) and EXTREME_OB (>95), not the standard 30/70
