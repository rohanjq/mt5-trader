# Configuration Reference

Complete reference for all YAML config keys. The config file is hot-reloaded every 2 seconds — most changes take effect without restarting.

## MT5 Connection

```yaml
mt5:
  host: localhost       # rpyc bridge host
  port: 8001            # rpyc bridge port
```

## Trading Settings

```yaml
trading:
  symbol: XAUUSD          # MT5 symbol name
  volume: 0.25            # Fallback lot size if risk sizing fails
  risk_pct: 5.0           # Risk % of account balance per trade
  max_volume: 10.0        # Safety cap on lot size
  min_volume: 0.01        # Broker minimum lot size
  magic: 200              # MT5 magic number (identifies our trades)
  deviation: 20           # Max price deviation in points
  filling: FOK            # Order filling mode: FOK or IOC
  multi_position: true    # Allow multiple concurrent positions
  sl_dollars: 5.0         # Default stop-loss in dollars (price distance)
  reward_ratio: 1.25      # Default TP = SL × reward_ratio
```

### Risk Sizing Formula

```
volume = (balance × risk_pct / 100) / ((sl_dollars / tick_size) × tick_value)
```

Example (XAUUSD, $10,000 balance, 5% risk, $5 SL):
```
volume = (10000 × 0.05) / ((5.0 / 0.01) × 1.0) = 500 / 500 = 1.0 lot
```

## Signal Sources

Defines which indicators and timeframes to monitor. Each entry creates a signal plugin that reads CSVs from the EA.

```yaml
signals:
  poll_interval: 2.0              # Seconds between signal reads
  csv_dir: data/signals   # Where EA writes CSVs
  sources:
    - indicator: utbot            # UT Bot Alert
      timeframes: [M1, M3, M5, M15]
    - indicator: dc               # Donchian Channel
      timeframes: [M1, M5, M15]
    - indicator: ema9             # EMA period 9
      timeframes: [M1]
    - indicator: ema21
      timeframes: [M1, M5]
    - indicator: ema50
      timeframes: [M5, M15]
    - indicator: ema200
      timeframes: [M5, M15]
    - indicator: rsi14            # RSI period 14
      timeframes: [M1, M5, M15]
    - indicator: rsi2             # RSI period 2 (extreme oversold/overbought)
      timeframes: [M1]
    - indicator: adx14            # ADX period 14
      timeframes: [M1, M5]
    - indicator: macd12_26_9      # MACD 12/26/9
      timeframes: [M1]
    - indicator: stoch5_3_3       # Stochastic 5/3/3
      timeframes: [M1]
    - indicator: bb20d2           # Bollinger Bands 20/2
      timeframes: [M1]
    - indicator: atr14            # ATR period 14
      timeframes: [M1, M5]
    - indicator: vwap             # Session VWAP
      timeframes: [M1, M5]
```

### Available Timeframes

M1, M3, M5, M10, M15, M30, M45, H1, H4

## Filters

Pre-trade safety filters. All are applied before a trade can execute.

```yaml
filters:
  cooldown_seconds: 30              # Block re-entry for N seconds after any trade
  max_consecutive_losses: 0         # Pause after N consecutive losses (0 = disabled)
  pause_after_consecutive_minutes: 15  # How long to pause (minutes)
  max_daily_loss: -1                # Daily loss limit in dollars (-1 = disabled)
  reversal_cooldown_seconds: 30     # Block opposite direction for N seconds
```

## Exit Rules

Controls how open positions are managed after entry.

```yaml
exit_rules:
  signal_reversal_exit: false       # Close on opposing signal
  breakeven_pct: 0.0               # Move SL to entry at X% of TP (0 = disabled)
  partial_tp: false                 # Split position: close portion at TP, run rest
  tp_close_pct: 100.0              # % of position to close at TP (100 = close all)
  trailing_stop_dollars: 0.0       # Trail SL by N dollars (0 = disabled)
```

### Breakeven

When `breakeven_pct: 60.0`, the SL moves to entry price when unrealised profit reaches 60% of the distance to TP. Disabled when set to 0.

### Partial TP (Runners)

When `partial_tp: true`, the position is split:
- **Main position**: `tp_close_pct`% of volume, has TP set
- **Runner position**: remaining volume, no TP (rides the trend), same SL

## Expression Rules (Strategies)

Strategies are defined as expression rules under `rules.expressions`. Each rule is a named strategy with BUY and SELL conditions.

```yaml
rules:
  expressions:
    - name: "gold_utbot_trend"
      enabled: true                 # true/false to enable/disable
      priority: 50                  # Lower = evaluated first
      sl_dollars: 5.0              # Override default SL for this strategy
      reward_ratio: 1.25           # Override default RR for this strategy
      breakeven_pct: 0.0           # Override default BE for this strategy
      partial_tp: false            # Override default runner for this strategy
      description: "UT Bot M1 signal + M5/M15 trend alignment"
      buy:
        - utbot_M1.closed_signal == BUY
        - utbot_M5.closed_bias == BULLISH
        - utbot_M15.closed_bias == BULLISH
        - vwap_M1.closed_price_vs_vwap == ABOVE
      sell:
        - utbot_M1.closed_signal == SELL
        - utbot_M5.closed_bias == BEARISH
        - utbot_M15.closed_bias == BEARISH
        - vwap_M1.closed_price_vs_vwap == BELOW
```

### Condition Format

```
{signal_source}.{field_name} {operator} {value}
```

Where:
- `signal_source` = `{indicator}_{timeframe}` (e.g., `utbot_M1`, `rsi14_M5`)
- `field_name` = any field from the signal's metadata
- `operator` = one of: `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not_in`, `is`, `is_not`
- `value` = comparison value (string or numeric)

### Priority

Rules are evaluated in priority order (ascending). Lower priority number = evaluated first. If `multi_position` is false, the first rule that fires wins.

### Per-Strategy Overrides

Each strategy can override the global `sl_dollars`, `reward_ratio`, `breakeven_pct`, and `partial_tp`. If not specified, the global defaults from `trading` and `exit_rules` are used.

## Notifications

```yaml
notifications:
  enabled: false
  pushover_user_key: ""     # or set via PUSHOVER_USER env var
  pushover_app_token: ""    # or set via PUSHOVER_TOKEN env var
```

When enabled, sends push notifications on trade opens and closes via Pushover.

## Current Active Strategies (config-gold.yaml)

| Strategy | Priority | SL | RR | Description |
|----------|----------|-----|------|-------------|
| gold_vwap_pullback | 30 | $4.20 | 1.25 | VWAP pullback continuation |
| gold_session_impulse | 35 | $5.00 | 1.50 | Session impulse EMA ADX |
| gold_dc_breakout | 40 | $6.00 | 1.80 | Compression → expansion breakout |
| gold_bb_range_fade | 45 | $3.00 | 1.00 | BB VWAP mean reversion |
| gold_utbot_trend | 50 | $5.00 | 1.25 | UT Bot multi-TF trend |

Disabled: gold_ema_pullback, gold_utbot_m1_m15
