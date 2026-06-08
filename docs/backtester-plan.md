# Backtester Plan

## Approach: Signal Replay (Approach 1)
Pre-compute indicators from OHLC → write signal CSVs → reuse existing expression engine

## Architecture
1. `backtest/indicator_engine.py` — vectorized indicator computation from OHLC using pandas_ta
2. `backtest/mock_mt5.py` — simulates order fills, tracks positions, checks SL/TP vs bar high/low
3. `backtest/runner.py` — per-bar loop: write CSVs → read signals → evaluate rules → execute
4. `backtest/stats.py` — win rate, drawdown, profit factor, trade log

## Key Design
- Pre-compute ALL indicators upfront (vectorized, fast)
- For each bar, write row i to signal CSVs (same format as EA)
- Reuse: rules/expression.py, signals/generic.py, filters/, core/config.py
- Replace: mt5_client with mock, engine loop with bar stepper
- CLI: `uv run python -m backtest --config config-gold.yaml --from 2026-04-01 --to 2026-06-01`

## Signal CSV Fields Needed
Check each indicator CSV for exact field names — match EA output exactly.
Reference: ADDING_RULES.md has field documentation.
Also check actual CSVs on server for ground truth.

## Data Source
MT5 copy_rates_range() via rpyc for 1m OHLC (or export from TradingView)
~43k bars/month for XAUUSD

## Still TODO before backtester
- Fix runner consecutive loss counting (runners inflate the counter 2x)
- Consider max concurrent positions limit
