# How to Run

## Live Trading

```bash
# 1. Pull latest code and install dependencies
cd mt5-trader
git pull && uv sync

# 2. Start trading with gold config
uv run python main.py --config config-gold.yaml

# 3. Or use BTC config
uv run python main.py --config config-btc.yaml

# 4. Or use default config
uv run python main.py
```

Requires MT5 terminal running with SignalMaster EA and rpyc bridge on localhost:8001.

## Backtesting

```bash
# Run backtest against sample data (no MT5 needed)
uv run python -m backtest --config config-gold.yaml --data sampledata/sample.csv --balance 10000

# With date range filter
uv run python -m backtest --config config-gold.yaml --data data/XAUUSD_M1.csv \
    --start 2026-06-01 --end 2026-06-07 --balance 10000
```

## Download OHLC Data

```bash
# Requires MT5 connection via rpyc bridge
uv run python scripts/download_ohlc.py
```

Downloads M1 OHLC data from MT5 and saves to `data/XAUUSD_M1.csv`.

## Strategy Permutation Testing

```bash
# Test 20 UT Bot BUY indicator combos against sample data
uv run python tests/run_permutations.py --data sampledata/sample.csv
```

Generates test configs in `tests/configs/`, runs each backtest, and prints a comparison table sorted by profit factor.

## Adding a Strategy

1. Browse `strategies/` folder for available strategy expressions
2. Copy the YAML block from the strategy's `.md` file
3. Paste into `config-gold.yaml` under `rules.expressions`
4. Set `enabled: true`
5. Config hot-reloads — no restart needed (or restart for backtest)

## Common Options

| Command | Description |
|---------|-------------|
| `--config <file>` | Config YAML to use (default: config.yaml) |
| `--data <file>` | OHLC CSV for backtesting |
| `--balance <amount>` | Starting balance for backtesting (default: 10000) |
| `--start <date>` | Filter data start date (YYYY-MM-DD) |
| `--end <date>` | Filter data end date (YYYY-MM-DD) |
