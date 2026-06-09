# mt5-trader

Monorepo for automated MetaTrader 5 trading: Docker container, MQL5 Expert Advisor, Python trading engine, and signal-replay backtester.

## Features

- **YAML-defined strategies** — add, modify, or disable strategies without writing Python
- **Multi-timeframe analysis** — combine indicators across M1, M5, M15 and higher timeframes
- **Risk management** — position sizing, stop-loss, take-profit, breakeven, trailing stops
- **Safety filters** — cooldowns, consecutive loss limits, daily loss caps
- **Hot-reload config** — change settings while running, no restart needed
- **Signal-replay backtester** — test strategies against historical OHLC data
- **TUI dashboard** — live terminal UI with signals, positions, and trade log
- **Strategy permutation testing** — automated search for optimal indicator combinations
- **Docker container** — MT5 runs in Wine/KasmVNC container on Linux
- **SignalMaster EA** — single EA computes all indicators across all timeframes → CSV

## Quick Start

### Docker Setup (Remote Server)

```bash
cd docker
cp .env.example .env
# Edit .env with your MT5 credentials
docker compose up -d --build
# Access MT5 via browser at http://<host>:3000
```

### Live Trading

```bash
git clone https://github.com/rohanjq/mt5-trader.git
cd mt5-trader
uv sync
uv run python main.py --config config-gold.yaml
```

Requires MT5 running with the SignalMaster EA and rpyc bridge on localhost:8001.

### Backtesting

```bash
# Run backtest against 60-day data
uv run python -m backtest --config config-gold.yaml --data sampledata/XAUUSD_M1_60d.csv --balance 10000

# Run strategy combo tests with trailing stop
uv run python tests/run_combos.py --data sampledata/XAUUSD_M1_60d.csv --trailing 3.0

# Run strategy permutation tests
uv run python tests/run_permutations.py --data sampledata/sample.csv
```

No MT5 connection needed for backtesting.

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System overview, directory structure, component diagram |
| [Trading System](docs/trading-system.md) | Live trading pipeline, signal flow, execution |
| [Backtester](docs/backtester.md) | Backtester usage, how it works, limitations |
| [Config Reference](docs/config-reference.md) | Complete YAML config key reference |
| [Indicators](docs/indicators.md) | All indicator fields and expression examples |
| [Signal Reference](docs/SIGNAL_REFERENCE.md) | EA signal CSV file format and all fields |
| [Signal Changes](docs/SIGNAL_CHANGES.md) | Latest EA signal additions (VWAP, BB squeeze, DC compression) |
| [Strategy Findings](docs/buy-strategy-findings.md) | BUY strategy research results and winners |
| [Expression Reference](docs/expression-reference.md) | All expression operators and examples |
| [Development Guide](docs/development-guide.md) | How to add indicators to EA + backtester |
| [Known Issues](docs/known-issues.md) | Tracked bugs and limitations |

## Project Structure

```
MQL5/       — SignalMaster EA source (MQL5 Expert Advisor)
docker/     — Dockerfile, compose, startup scripts
core/       — Config, engine, MT5 client, models
signals/    — Signal source plugins (CSV readers)
rules/      — Trade trigger rules (YAML expressions + Python)
filters/    — Pre-trade safety filters
exits/      — Position exit rules (breakeven, trailing, runners)
trade/      — Trade execution and position management
ui/         — Textual TUI dashboard
backtest/   — Signal-replay backtester
scripts/    — Utility scripts (OHLC download)
tests/      — Strategy permutation testing
tools/      — MT5 utility scripts (account info, ticker info)
docs/       — Documentation
```

## Requirements

- Python 3.12+
- uv package manager
- MT5 terminal with rpyc bridge (for live trading only)
- Docker (for running MT5 on Linux)
