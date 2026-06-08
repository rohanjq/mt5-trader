# Permutation Testing Scripts

This repository includes scripts to generate many strategy combinations and run backtests automatically.

## Scripts

### `tests/run_permutations.py`
Original BUY-side permutation runner.

- Focus: UT Bot M1 BUY combinations
- Generates test configs under `tests/configs/`
- Runs each config through `python -m backtest`
- Parses summary metrics and prints ranked console output

### `tests/run_utbot_sell_permutations.py`
SELL-side permutation runner (new).

- Focus: UT Bot M1 SELL expressions
- Tests 2/3/4-condition combinations (base UTBot sell + extra filters)
- Includes both trend and early-entry style filters (RSI2, MACD flip, BB re-entry, Donchian break, etc.)
- Sweeps multiple SL values (`4.0`, `5.0`, `6.0`, `7.5`)
- Generates configs in `tests/sell_configs/`
- Produces markdown report in `tests/reports/utbot_sell_permutation_report.md`

## How to run

Use `UV_CACHE_DIR=/tmp/uv-cache` to avoid cache-write issues in restricted environments.

### Quick smoke test (10 candidates)

```bash
cd /root/mt5-trader
mkdir -p /tmp/uv-cache
UV_CACHE_DIR=/tmp/uv-cache uv run python tests/run_utbot_sell_permutations.py \
  --data sampledata/sample.csv \
  --limit 10
```

### Medium batch (example: 300 candidates)

```bash
cd /root/mt5-trader
mkdir -p /tmp/uv-cache
UV_CACHE_DIR=/tmp/uv-cache uv run python tests/run_utbot_sell_permutations.py \
  --data sampledata/sample.csv \
  --limit 300
```

### Full exhaustive run

```bash
cd /root/mt5-trader
mkdir -p /tmp/uv-cache
UV_CACHE_DIR=/tmp/uv-cache uv run python tests/run_utbot_sell_permutations.py \
  --data sampledata/sample.csv
```

## Output files

- Generated configs: `tests/sell_configs/*.yaml`
- Result report: `tests/reports/utbot_sell_permutation_report.md`

## Report contents

The report includes:

- Total/Success/Failed run counts
- Top performers by net profit
- Best result per condition-count bucket (2/3/4)
- Full sortable-style table of all successful runs

Primary metrics captured from each run:

- `Total Trades`
- `Win Rate`
- `Net Profit`
- `Profit Factor`
- `Max Drawdown`
- `Expectancy`

## Notes

- Backtests are replay-based and depend on indicator alignment behavior in `backtest/`.
- Treat permutation winners as candidates for further validation, not production-ready strategies.
- Re-run top candidates on additional datasets/time windows before enabling live trading.
