# MT5 Auto-Trader — System Architecture

## What Is This

A plugin-based, multithreaded automated trading bot for **BTCUSDT** on MetaTrader 5.
It runs on a remote Linux machine, connecting to MT5 running inside a Podman container
(Wine on Debian) via rpyc bridge on port 8001.

- **Language**: Python 3.12, managed by `uv`
- **MT5 Bridge**: `mt5linux` + `rpyc==5.3.1` → `localhost:8001`
- **TUI Dashboard**: `textual` — live panels, keybindings
- **Config**: `pyyaml` — hot-reloaded every 2s (no restart needed for most changes)
- **Broker**: PXBT Trading MT5 Terminal (demo account)
- **Order Filling**: `ORDER_FILLING_FOK`, magic=100, deviation=20
- **Success retcode**: 10009

## How to Run

```bash
# Remote machine
cd mt5-trader
git pull && uv sync
uv run python main.py
```

## Directory Structure

```
mt5-trader/
├── main.py                    # Entry point — Config → Engine → TUI
├── config.yaml                # All settings (hot-reloaded)
├── pyproject.toml             # uv project, deps, entry point
├── trader.log                 # Runtime log file
│
├── core/
│   ├── config.py              # Thread-safe YAML config, dotpath access, hot-reload
│   ├── engine.py              # Main orchestrator, signal loop + monitor loop
│   ├── events.py              # Centralized event ring buffer (for dashboard)
│   ├── models.py              # All dataclasses and enums
│   └── mt5_client.py          # Thread-safe MT5 wrapper (orders, ticks, positions)
│
├── signals/                   # Signal source plugins (read CSVs from SignalMaster EA)
│   ├── base.py                # BaseSignal ABC, build_signal_plugins() factory
│   ├── ut_bot.py              # UTBotSignal — reads BTCUSDT_utbot_{TF}.csv
│   └── donchian.py            # DonchianSignal — reads BTCUSDT_dc_{TF}.csv
│
├── rules/                     # Trigger rule plugins (decide WHEN to trade)
│   ├── base.py                # BaseRule ABC, TriggerAction/Result, discover_rules()
│   ├── utbot_simple.py        # UT Bot 1m signal alone (testing)
│   ├── dc_confluence.py       # DC zone + UT Bot signal + trend bars
│   ├── dc_wick_rejection.py   # DC wick rejection + UT Bot bias
│   └── utbot_multi_tf.py      # UT Bot multi-timeframe alignment
│
├── filters/                   # Trade filter plugins (gate between trigger and execution)
│   ├── base.py                # BaseFilter ABC, FilterChain, discover_filters()
│   ├── manual_switch.py       # Toggle auto-trading on/off (key: t)
│   ├── cooldown.py            # Block trading X min after a loss
│   └── reversal_cooldown.py   # Block reverse direction for 60s after close
│
├── exits/                     # Exit rule plugins (manage open positions)
│   ├── base.py                # BaseExitRule ABC, ExitAction/Result, discover_exit_rules()
│   ├── breakeven.py           # Move SL to entry when price moves $50
│   ├── trailing_stop.py       # Trail SL at fixed $ distance
│   └── signal_reversal.py     # Close on signal flip (currently disabled)
│
├── trade/
│   ├── initiator.py           # Evaluates rules, runs filters, executes orders
│   └── manager.py             # Tracks open trade, runs exit rules, syncs MT5
│
├── ui/
│   └── dashboard.py           # Textual TUI — all panels, keybindings
│
├── strategies/                # DEPRECATED — replaced by rules/
│   ├── base.py
│   ├── utbot_simple.py
│   └── dc_reversal.py
│
└── mql5/
    └── DC_Channels.mq5        # Donchian Channel EA (kept for version control)
```

## Data Flow

```
SignalMaster EA (MT5) → writes CSV files to ../MetaTrader5-Docker/data/signals/
        │
        ▼
Signal Plugins (poll every 2s) → read CSV, parse ALL fields into Signal.metadata
        │
        ▼
Engine._signal_loop() → passes dict[name→Signal] to:
        │
        ├──→ TradeInitiator.on_signals()
        │         │
        │         ▼
        │    Trigger Rules (priority order, first trigger wins)
        │         │
        │         ▼ TriggerResult(TRIGGER_BUY/SELL)
        │    Filter Chain (sequential, first BLOCK wins)
        │         │
        │         ▼ ALLOW
        │    Execute order via MT5Client
        │         │
        │         ▼
        │    TradeManager.register_trade()
        │
        └──→ TradeManager.update_signals() (for exit rules)

Engine._monitor_loop() (every 1s):
        │
        ├──→ TradeManager.update_open_position()
        │         → update P&L from live tick
        │         → run exit rules (breakeven, trailing, signal reversal)
        │
        └──→ TradeManager.sync_positions_from_mt5()
                  → detect if broker closed position (SL/TP hit)
                  → record real exit price and P&L
```

## Signal CSV Format

SignalMaster EA writes one CSV per indicator+timeframe. Files are key-value pairs
(header row + data row). The signal plugins read ALL fields into `Signal.metadata`.

**File naming**: `{SYMBOL}_{indicator}_{TF}.csv` → e.g. `BTCUSDT_utbot_M1.csv`

**UT Bot fields** (example):
- `closed_bias` — BULLISH / BEARISH / NONE (persistent trend state)
- `closed_signal` — BUY / SELL / NONE (one-bar flash on crossover)
- `closed_atr` — ATR value
- `consecutive_bull_bars`, `consecutive_bear_bars` — trend strength
- `running_*` variants for the current unconfirmed bar

**Donchian Channel fields** (example):
- `closed_price_zone` — UPPER / UPPER_MID / MID / LOWER_MID / LOWER
- `closed_upper_wick_rej` — TRUE/FALSE (candle rejected from upper band)
- `closed_lower_wick_rej` — TRUE/FALSE
- `upper_band`, `lower_band` — channel boundaries

**Encoding**: Wine/MetaEditor writes UTF-16 LE or ANSI. Reader tries utf-8-sig → utf-16 → latin-1.

## Key Data Models (core/models.py)

**Signal** (frozen dataclass):
- `source` (str): e.g. "utbot_M1", "dc_M15"
- `direction` (SignalDirection): BUY/SELL/NEUTRAL — for dashboard display only
- `metadata` (dict): ALL CSV key-value pairs — rules read from this

**TradeRequest**: direction, symbol, volume, signal, sl, tp, risk_dollars, state
**TradeRecord**: full trade lifecycle — entry/exit price/time, ticket, P&L, SL/TP
**TriggerResult**: action (NO_ACTION/TRIGGER_BUY/TRIGGER_SELL), reason, rule_name
**FilterResult**: verdict (ALLOW/BLOCK/MODIFY), reason
**ExitResult**: action (HOLD/MODIFY_SL/MODIFY_TP/CLOSE), reason, new_sl/new_tp

## Plugin System

All plugins are **auto-discovered** at startup via `pkgutil.iter_modules()`.
Drop a new `.py` file in the right folder and it's loaded automatically.

- **Signals**: config-driven via `signals.sources` in YAML
- **Rules**: auto-discovered from `rules/`, sorted by priority (lower = first)
- **Filters**: auto-discovered from `filters/`, evaluated sequentially
- **Exit rules**: auto-discovered from `exits/`

## Config Hot-Reload

`core/config.py` polls the YAML file every 2 seconds. Changes to these take
effect immediately without restart:
- `trading.volume`, `trading.sl_dollars`, `trading.reward_ratio`
- `filters.cooldown_minutes`, `filters.reversal_cooldown_seconds`
- `exit_rules.breakeven_trigger_dollars`, `exit_rules.trailing_stop_dollars`
- `rules.*.enabled` (enable/disable rules on the fly)

## TUI Dashboard Keybindings

| Key | Action |
|-----|--------|
| `b` | Manual BUY (bypasses filters, auto SL/TP) |
| `s` | Manual SELL (bypasses filters, auto SL/TP) |
| `t` | Toggle auto-trading on/off |
| `c` | Close current position |
| `r` | Reconnect to MT5 |
| `q` | Quit |

## Startup Sequence

1. Load config from `config.yaml`
2. Discover all plugins (signals, rules, filters, exits)
3. Connect to MT5 via rpyc
4. **Adopt any existing positions** (survives restart mid-trade)
5. Start config hot-reload watcher
6. Start signal loop (daemon thread, polls every 2s)
7. Start monitor loop (daemon thread, runs every 1s)
8. Launch TUI dashboard

## Important Implementation Details

- **Thread safety**: Config, MT5Client, TradeManager all use locks
- **Dedup**: Once a rule triggers BUY, same rule+direction won't re-trigger until trade closes
- **Order retcode 10009** = success in MT5
- **Magic number 100**: Used to identify our bot's positions vs manual trades
- **Position adoption**: On restart, adopts open positions matching symbol + magic
- **Breakeven ≠ loss**: P&L of $0.00 is not counted as a loss for cooldown purposes
