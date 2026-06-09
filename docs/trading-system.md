# Live Trading System

## How It Works

The live trading system polls CSV signal files produced by a MetaTrader 5 Expert Advisor (SignalMaster EA). Each signal file contains the latest indicator values for a specific indicator and timeframe. The system evaluates YAML-defined expression rules against these signals, applies safety filters, and executes trades through the MT5 API.

## Startup Flow

```
main.py --config config-gold.yaml
    │
    ├── Config loads YAML
    ├── Engine.setup()
    │     ├── build_signal_plugins() — creates CSV readers for each indicator+TF
    │     ├── discover_filters() — loads cooldown, consecutive loss, etc.
    │     ├── discover_exit_rules() — loads breakeven, partial TP, trailing
    │     ├── discover_rules() — loads Python rules (dc_confluence, etc.)
    │     ├── load_expression_rules() — loads YAML expression strategies
    │     ├── MT5Client.connect() — connects to rpyc bridge
    │     └── TradeManager.adopt_existing_positions() — picks up prior session
    │
    ├── Engine.start() — launches signal-loop + monitor-loop threads
    └── TradingDashboard — starts Textual TUI
```

## Signal Pipeline

### 1. Signal Sources

The SignalMaster EA (running inside MT5) writes CSV files to a shared directory:

```
data/signals/
├── XAUUSD_utbot_M1.csv
├── XAUUSD_utbot_M5.csv
├── XAUUSD_utbot_M15.csv
├── XAUUSD_dc_M1.csv
├── XAUUSD_dc_M15.csv
├── XAUUSD_ema9_M1.csv
├── XAUUSD_rsi14_M5.csv
└── ... (one file per indicator × timeframe)
```

Each CSV contains one row of the latest indicator values. Signal plugins in `signals/` read these files every 2 seconds and produce `Signal` objects.

### 2. Signal Object

```python
@dataclass
class Signal:
    source: str            # e.g. "utbot_M1"
    direction: SignalDirection  # BUY, SELL, or NONE
    timestamp: datetime
    metadata: dict[str, str]   # all indicator fields as strings
```

The `metadata` dict contains every field from the CSV, e.g.:
```python
{
    "closed_signal": "BUY",
    "closed_bias": "BULLISH",
    "closed_atr": "4.25",
    "consecutive_bull_bars": "3",
    "server_time": "2026.06.08 14:30:00",
}
```

### 3. Expression Rules

Expression rules are defined in YAML and evaluated by `rules/expression.py`. Each rule has a list of conditions for BUY and SELL. All conditions in a direction must be true (AND logic).

```yaml
- name: "gold_utbot_trend"
  enabled: true
  priority: 50
  sl_dollars: 5.0
  reward_ratio: 1.25
  buy:
    - utbot_M1.closed_signal == BUY      # signal field comparison
    - utbot_M5.closed_bias == BULLISH     # higher TF alignment
    - utbot_M15.closed_bias == BULLISH    # even higher TF
    - vwap_M1.closed_price_vs_vwap == ABOVE  # VWAP filter
  sell:
    - utbot_M1.closed_signal == SELL
    - utbot_M5.closed_bias == BEARISH
    - utbot_M15.closed_bias == BEARISH
    - vwap_M1.closed_price_vs_vwap == BELOW
```

#### Expression Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `==` | `utbot_M1.closed_signal == BUY` | Equals (case-insensitive) |
| `!=` | `utbot_M1.closed_bias != NONE` | Not equals |
| `>` | `rsi14_M1.closed_rsi > 50` | Greater than (numeric) |
| `>=` | `adx14_M1.closed_adx >= 25` | Greater or equal |
| `<` | `rsi14_M1.closed_rsi < 30` | Less than |
| `<=` | `dc_M15.channel_width <= 500` | Less or equal |
| `in` | `adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND` | Value in set |
| `not_in` | `dc_M15.closed_price_zone not_in MID` | Value not in set |
| `is` | `dc_M1.dc_compressed is TRUE` | Boolean true check |
| `is_not` | `bb20d2_M1.bb_squeeze is_not TRUE` | Boolean false check |

#### Rising-Edge Detection

Expression rules only fire on transitions from "conditions not met" to "conditions met" (False → True). This prevents the same signal from repeatedly triggering trades while conditions remain true.

### 4. Python Rules

Legacy rules defined as Python classes in `rules/`. Auto-discovered by `discover_rules()`. These are separate from expression rules and run in parallel:

| Rule | Priority | Description |
|------|----------|-------------|
| dc_confluence | 100 | DC zone + UT Bot + trend bars |
| dc_wick_rejection | 110 | DC wick rejection + UT Bot bias |
| utbot_multi_tf | 120 | All UT Bot TFs aligned |
| utbot_simple | 200 | UT Bot M1 signal only (testing) |

Rules are evaluated in priority order (lower = higher priority). First rule that triggers wins.

## Filter Chain

After a rule triggers, the signal passes through the filter chain. Any filter can block the trade.

| Filter | Purpose | Config Key |
|--------|---------|------------|
| ManualSwitch | TUI toggle — press `t` to pause auto-trading | Always active |
| Cooldown | Block all trading for N seconds after a loss | `filters.cooldown_seconds` |
| ConsecutiveLoss | Pause after N consecutive losses | `filters.max_consecutive_losses` |
| ReversalCooldown | Block opposite direction for N seconds after close | `filters.reversal_cooldown_seconds` |
| DailyLoss | Stop trading after daily loss limit hit | `filters.max_daily_loss` |

Manual trades (keyboard `b`/`s` in TUI) bypass all filters.

## Order Execution

When a rule triggers and filters pass:

1. **TradeInitiator** builds a `TradeRequest` with direction, volume, SL, TP
2. **Volume sizing**: `volume = (balance × risk_pct / 100) / (sl_dollars / tick_size × tick_value)`
3. **MT5Client** sends `ORDER_TYPE_BUY` or `ORDER_TYPE_SELL` with `ORDER_FILLING_FOK`
4. **TradeManager** records the trade, starts monitoring

## Exit Rules

Exit rules run every monitor cycle (5s) on open positions:

| Exit Rule | Behaviour | Config |
|-----------|-----------|--------|
| Breakeven | Move SL to entry price when profit reaches X% of TP distance | `exit_rules.breakeven_pct` (0 = disabled) |
| PartialTP | Close X% of position at TP, leave runner with no TP | `exit_rules.partial_tp`, `tp_close_pct` |
| TrailingStop | Trail SL behind price by N dollars | `exit_rules.trailing_stop_dollars` (0 = disabled) |
| SignalReversal | Close position when opposing signal fires | `exit_rules.signal_reversal_exit` |

## Position Monitoring

The monitor loop (5s interval):

1. Queries MT5 for all open positions with the configured magic number
2. Compares with internal trade records
3. Detects externally closed trades (SL/TP hit by broker, manual close)
4. Updates P&L, fires on_trade_closed callbacks
5. Runs exit rules on surviving positions

## TUI Dashboard

The Textual dashboard shows:

- **Signals Panel**: Current values of all signal sources
- **Positions Panel**: Open trades with live P&L
- **Trade Log**: Recent trade history with entry/exit details
- **Event Log**: System events (connections, errors, filter blocks)

Keybindings:

| Key | Action |
|-----|--------|
| `b` | Manual BUY (bypasses filters) |
| `s` | Manual SELL (bypasses filters) |
| `t` | Toggle auto-trading on/off |
| `x` | Close all open positions |
| `q` | Quit |

## Deployment

```bash
# On the remote Linux machine:
cd mt5-trader
git pull && uv sync
uv run python main.py --config config-gold.yaml
```

The MT5 terminal runs inside a Podman container (Wine on Debian). The rpyc bridge exposes MT5 API on localhost:8001.
