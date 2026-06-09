# System Architecture

## Overview

mt5-trader is a plugin-based automated trading system for MetaTrader 5. It runs on a remote Linux machine, connecting to MT5 via an rpyc bridge. The system reads indicator signals from CSV files (written by the SignalMaster EA in `MQL5/Experts/SignalMaster.mq5`), evaluates YAML-defined trading strategies, applies risk filters, and executes orders through the MT5 API.

The EA source lives in this repo (`MQL5/`). Docker infrastructure lives in the companion repo [MetaTrader5-Docker](https://github.com/rohanjq/MetaTrader5-Docker), which copies `MQL5/` from here at build time.

A companion backtester module replays historical M1 OHLC data through the same strategy engine, simulating order fills without requiring an MT5 connection.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Package Manager | uv |
| MT5 Bridge | mt5linux + rpyc 5.3.1 → localhost:8001 |
| Indicators (backtest) | pandas-ta 0.4.71b0 |
| TUI Dashboard | textual |
| Configuration | PyYAML, hot-reloaded every 2 seconds |
| Broker | PXBT Trading MT5 Terminal (demo) |

## Directory Structure

```
mt5-trader/
├── main.py                     # Entry point: Config → Engine → TUI
├── config-gold.yaml            # XAUUSD trading config (primary)
├── config-btc.yaml             # BTCUSDT trading config
├── config.yaml                 # Default/fallback config
├── pyproject.toml              # Dependencies, project metadata
│
├── MQL5/                       # MQL5 Expert Advisor source (single source of truth)
│   └── Experts/
│       └── SignalMaster.mq5    # EA that computes all indicators → CSV
│
├── core/                       # Core infrastructure
│   ├── config.py               # Thread-safe YAML config with hot-reload
│   ├── engine.py               # Main orchestrator (signal loop + monitor loop)
│   ├── events.py               # Ring buffer event log for dashboard
│   ├── models.py               # Dataclasses: Signal, TradeRecord, enums
│   ├── mt5_client.py           # Thread-safe MT5 API wrapper
│   └── notifications.py        # Pushover push notifications
│
├── signals/                    # Signal source plugins (read CSV from EA)
│   ├── base.py                 # BaseSignal ABC + build_signal_plugins()
│   ├── ut_bot.py               # UT Bot Alert indicator reader
│   ├── donchian.py             # Donchian Channel indicator reader
│   ├── generic.py              # Generic CSV signal reader
│   └── liq_grab.py             # Liquidity grab detector reader
│
├── rules/                      # Trade trigger rules
│   ├── base.py                 # BaseRule ABC + discover_rules()
│   ├── expression.py           # ExpressionRule: YAML-defined strategies
│   ├── dc_confluence.py        # DC zone + UT Bot confluence (Python rule)
│   ├── dc_wick_rejection.py    # DC wick rejection (Python rule)
│   ├── utbot_multi_tf.py       # UT Bot multi-TF alignment (Python rule)
│   └── utbot_simple.py         # UT Bot M1 only (testing rule)
│
├── filters/                    # Pre-trade safety filters
│   ├── base.py                 # BaseFilter ABC + FilterChain
│   ├── cooldown.py             # Time-based cooldown after losses
│   ├── consecutive_loss.py     # Pause after N consecutive losses
│   ├── daily_loss.py           # Daily loss limit
│   ├── manual_switch.py        # TUI toggle (press 't' to pause)
│   └── reversal_cooldown.py    # Block quick direction reversals
│
├── exits/                      # Position exit rules
│   ├── base.py                 # BaseExitRule ABC + discover_exit_rules()
│   ├── breakeven.py            # Move SL to entry after X% of TP
│   ├── partial_tp.py           # Close portion at TP, let runner ride
│   ├── signal_reversal.py      # Exit on opposing signal
│   └── trailing_stop.py        # Trail SL behind price
│
├── trade/                      # Trade execution
│   ├── initiator.py            # Evaluates rules → opens positions
│   └── manager.py              # Tracks open/closed trades, runs exit rules
│
├── ui/
│   └── dashboard.py            # Textual TUI with live panels
│
├── backtest/                   # Signal-replay backtester
│   ├── __main__.py             # CLI entry point
│   ├── data_loader.py          # OHLC CSV loading + normalisation
│   ├── indicators.py           # Vectorised indicator computation
│   ├── runner.py               # Bar-by-bar strategy replay
│   ├── simulator.py            # Order fill simulation (SL/TP/BE/trailing)
│   ├── filters.py              # Backtest-specific filter chain
│   └── stats.py                # Performance statistics + reporting
│
├── scripts/
│   └── download_ohlc.py        # Fetch historical data from MT5
│
├── tests/
│   ├── backtest_runner.py      # Shared reusable backtest runner
│   ├── run_combos.py           # Strategy combo tester (--trailing, --multi)
│   └── run_*.py                # Strategy variant test scripts
│
├── strategies/
│   └── buy/*.yaml              # All BUY strategy rules
│
├── sampledata/
│   ├── XAUUSD_M1_60d.csv      # 60-day XAUUSD M1 data for backtesting
│   └── sample.csv              # 1-week sample data
│
├── data/
│   └── README.md               # Data format documentation
│
└── docs/                       # Documentation (this folder)
```

## Component Interactions

```
┌──────────────────────────────────────────────────────────────────┐
│                        MT5 Terminal (Wine/Podman)                │
│  SignalMaster EA → writes CSV files → signals/ reads them       │
│  rpyc bridge on localhost:8001 → core/mt5_client.py connects    │
└──────────────────────────────────────────────────────────────────┘
                              ↕
┌──────────────────────────────────────────────────────────────────┐
│                      core/engine.py                             │
│                                                                  │
│   Signal Loop (2s):                                              │
│     signals/ plugins → read CSVs → Signal objects                │
│         ↓                                                        │
│     trade/initiator.py                                           │
│       → rules/expression.py evaluates YAML strategies            │
│       → filters/ chain gates the trade                           │
│       → mt5_client.py sends order to MT5                         │
│         ↓                                                        │
│     trade/manager.py                                             │
│       → tracks open positions                                    │
│       → exits/ rules check SL/TP/BE/trailing                    │
│       → closes positions via mt5_client.py                       │
│                                                                  │
│   Monitor Loop (5s):                                             │
│     → syncs positions with MT5                                   │
│     → detects external closes (manual, SL/TP hit by broker)     │
│     → updates P&L, equity                                        │
│                                                                  │
│   Config Watcher (2s):                                           │
│     → watchdog monitors YAML file for changes                    │
│     → hot-reloads settings without restart                       │
└──────────────────────────────────────────────────────────────────┘
                              ↕
┌──────────────────────────────────────────────────────────────────┐
│                      ui/dashboard.py                             │
│   Textual TUI: signals panel, positions, trade log, events       │
│   Keybinds: b=buy, s=sell, t=toggle auto, x=close all           │
└──────────────────────────────────────────────────────────────────┘
```

## Threading Model

The system uses 3 threads:

| Thread | Purpose | Interval |
|--------|---------|----------|
| signal-loop | Poll signal CSVs, evaluate rules, open trades | 2 seconds |
| monitor-loop | Sync positions with MT5, run exit rules | 5 seconds |
| main (TUI) | Textual event loop, keyboard input, rendering | event-driven |

All shared state is protected by `threading.Lock` or `threading.RLock`. The config uses `watchdog` file observer for hot-reload callbacks.

## Plugin Discovery

All plugins (signals, rules, filters, exits) are auto-discovered at startup:

- **signals/base.py** → `build_signal_plugins(config)` — creates signal readers based on `signals.sources` config
- **rules/base.py** → `discover_rules(config)` — loads all Python rule files in `rules/`
- **rules/expression.py** → `load_expression_rules(config)` — loads YAML-defined expression rules
- **filters/base.py** → `discover_filters(config)` — loads all filter plugins
- **exits/base.py** → `discover_exit_rules(config)` — loads all exit rule plugins

## Configuration Flow

```
config-gold.yaml (on disk)
    ↓ (watchdog detects change)
core/config.py loads + merges with defaults
    ↓
Config.get("trading.sl_dollars") → returns current value
    ↓
All components read config on every evaluation cycle
    ↓
Changes take effect within 2-5 seconds (no restart)
```

Hot-reloadable settings include: risk_pct, sl_dollars, reward_ratio, breakeven_pct, cooldown timers, strategy enabled/disabled, and all expression rule conditions.
