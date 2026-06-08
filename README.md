# mt5-trader

Automated trading system for MetaTrader 5 with YAML-defined strategies and a signal-replay backtester.

## Features

- **YAML-defined strategies** — add, modify, or disable strategies without writing Python
- **Multi-timeframe analysis** — combine indicators across M1, M5, M15 and higher timeframes
- **Risk management** — position sizing, stop-loss, take-profit, breakeven, trailing stops
- **Safety filters** — cooldowns, consecutive loss limits, daily loss caps
- **Hot-reload config** — change settings while running, no restart needed
- **Signal-replay backtester** — test strategies against historical OHLC data
- **TUI dashboard** — live terminal UI with signals, positions, and trade log
- **Strategy permutation testing** — automated search for optimal indicator combinations

## Quick Start

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
# Run backtest against sample data
uv run python -m backtest --config config-gold.yaml --data sampledata/sample.csv --balance 10000

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
| [Known Issues](docs/known-issues.md) | Tracked bugs and limitations |

## Project Structure

```
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
mql5/       — MQL5 Expert Advisor source
docs/       — Documentation
```

## Requirements

- Python 3.12+
- uv package manager
- MT5 terminal with rpyc bridge (for live trading only)
