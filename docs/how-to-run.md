# How to Run

## Docker Setup (Remote Server)

```bash
# 1. Navigate to docker directory
cd docker

# 2. Copy and edit environment file
cp .env.example .env
# Edit .env: set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

# 3. Build and start container
docker compose up -d --build

# 4. Access MT5 via browser
# Open http://<server-ip>:3000 in your browser
# Login with CUSTOM_USER/PASSWORD from .env

# 5. Rebuild after EA changes
docker compose up -d --build
```

The container auto-installs MT5 via Wine, compiles `SignalMaster.mq5`, and starts the EA on the configured symbol.

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
# Run backtest against 60-day data (no MT5 needed)
uv run python -m backtest --config config-gold.yaml --data sampledata/XAUUSD_M1_60d.csv --balance 10000

# With 1-week sample data
uv run python -m backtest --config config-gold.yaml --data sampledata/sample.csv --balance 10000

# With date range filter
uv run python -m backtest --config config-gold.yaml --data sampledata/XAUUSD_M1_60d.csv \
    --start 2026-06-01 --end 2026-06-07 --balance 10000
```

## Strategy Combo Testing

```bash
# Test strategy combos with different SL/RR values
uv run python tests/run_combos.py --data sampledata/XAUUSD_M1_60d.csv

# With trailing stop (distance in dollars)
uv run python tests/run_combos.py --data sampledata/XAUUSD_M1_60d.csv --trailing 3.0

# Allow multiple concurrent positions
uv run python tests/run_combos.py --data sampledata/XAUUSD_M1_60d.csv --multi
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

### UT Bot SELL permutation testing

```bash
# Quick smoke test (10 candidates)
uv run python tests/run_utbot_sell_permutations.py \
  --data sampledata/sample.csv \
  --limit 10

# Full run (all generated combinations)
uv run python tests/run_utbot_sell_permutations.py \
  --data sampledata/sample.csv
```

See `docs/permutation-testing.md` for full details and report format.

## MT5 Utility Tools

```bash
# Query account info (balance, equity, margin)
uv run python tools/account_info.py

# Query symbol/ticker info
uv run python tools/ticker_info.py
```

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
