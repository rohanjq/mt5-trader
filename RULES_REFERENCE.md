# Active Rules, Filters & Exit Rules Reference

Last updated: 2026-06-07

## Current Config State (config.yaml)

```yaml
trading:
  symbol: BTCUSDT
  volume: 0.1          # lot size (user changed from 0.001)
  sl_dollars: 100.0    # $100 SL
  reward_ratio: 1.25   # TP = $125

signals:
  sources:
    - indicator: utbot, timeframes: [M1, M3, M15, M45]
    - indicator: dc, timeframes: [M15, M45]
```

---

## Trigger Rules (rules/)

Rules are evaluated in priority order. First one that fires wins. Only fire when no position is open.

| Rule | File | Priority | Enabled | Entry Logic |
|------|------|----------|---------|-------------|
| `utbot_simple` | `rules/utbot_simple.py` | 200 | **YES** | UT Bot M1 `closed_signal` = BUY or SELL |
| `dc_confluence` | `rules/dc_confluence.py` | 100 | NO | DC M15 zone LOWER/UPPER + UT M1 signal + UT M45 bull/bear bars ≥ 5 |
| `dc_wick_rejection` | `rules/dc_wick_rejection.py` | 110 | NO | DC M15 wick rejection TRUE + UT M3 bias BULLISH/BEARISH |
| `utbot_multi_tf` | `rules/utbot_multi_tf.py` | 120 | NO | UT M1 signal + UT M15 bias + UT M45 bias all aligned |

### Rule Details

**utbot_simple** (ACTIVE — testing mode):
- BUY: `utbot_M1.closed_signal == "BUY"`
- SELL: `utbot_M1.closed_signal == "SELL"`
- Fires on every UT Bot crossover. No confluence required. High frequency.
- Config: `rules.utbot_simple.enabled`, `rules.utbot_simple.timeframe`

**dc_confluence** (DISABLED):
- BUY: DC M15 zone in (LOWER, LOWER_MID) AND UT M1 signal=BUY AND UT M45 consecutive_bull_bars ≥ 5
- SELL: DC M15 zone in (UPPER, UPPER_MID) AND UT M1 signal=SELL AND UT M45 consecutive_bear_bars ≥ 5
- High-quality mean-reversion setup. Requires price near DC boundary + short-term entry + long-term trend confirmation.
- Config: `rules.dc_confluence.dc_timeframe`, `.ut_entry_timeframe`, `.ut_trend_timeframe`, `.min_trend_bars`

**dc_wick_rejection** (DISABLED):
- BUY: DC M15 `closed_lower_wick_rej == TRUE` AND UT M3 `closed_bias == BULLISH`
- SELL: DC M15 `closed_upper_wick_rej == TRUE` AND UT M3 `closed_bias == BEARISH`
- Wick rejection = candle tested the band and was rejected (reversal signal).
- Config: `rules.dc_wick_rejection.dc_timeframe`, `.ut_timeframe`

**utbot_multi_tf** (DISABLED):
- BUY: UT M1 signal=BUY AND UT M15 bias=BULLISH AND UT M45 bias=BULLISH
- SELL: UT M1 signal=SELL AND UT M15 bias=BEARISH AND UT M45 bias=BEARISH
- Pure trend-following. All timeframes must agree. Fewer trades, higher conviction.
- Config: `rules.utbot_multi_tf.entry_timeframe`, `.mid_timeframe`, `.trend_timeframe`

---

## Filters (filters/)

Filters gate between a rule trigger and order execution. Evaluated sequentially. First BLOCK wins.

| Filter | File | Behavior |
|--------|------|----------|
| `manual_switch` | `filters/manual_switch.py` | Press `t` in TUI to pause/resume auto-trading. Always loaded. |
| `cooldown` | `filters/cooldown.py` | Blocks ALL trading for 5 min after a losing trade. Config: `filters.cooldown_minutes` |
| `reversal_cooldown` | `filters/reversal_cooldown.py` | Blocks opposite-direction trade for 60s after any close. E.g. BUY just closed → can't SELL for 60s. Same direction allowed immediately. Config: `filters.reversal_cooldown_seconds` |

**Note**: Manual trades (`b`/`s` keys) bypass ALL filters.

### Filter Config Not Yet Implemented

These are in config.yaml but **not yet wired** into any filter:
- `filters.max_consecutive_losses: 3`
- `filters.pause_after_consecutive_minutes: 15`
- `filters.max_daily_loss: 500.0`

---

## Exit Rules (exits/)

Exit rules run every second while a position is open. They can CLOSE the position or MODIFY SL/TP.

| Exit Rule | File | Enabled | Action | Logic |
|-----------|------|---------|--------|-------|
| `breakeven` | `exits/breakeven.py` | **YES** | MODIFY_SL | Move SL to entry when price moves $50 from entry. Config: `exit_rules.breakeven_trigger_dollars` |
| `trailing_stop` | `exits/trailing_stop.py` | NO (0) | MODIFY_SL | Trail SL at fixed $ distance. Currently set to $0 = off. Config: `exit_rules.trailing_stop_dollars` |
| `signal_reversal` | `exits/signal_reversal.py` | **NO** | CLOSE | Close when entry signal flips opposite. Currently disabled to let TP/SL hit. Config: `exit_rules.signal_reversal_exit` |

**Priority**: CLOSE action wins over MODIFY. If multiple rules fire, CLOSE is processed first.

### Current SL/TP Behavior

With signal_reversal OFF and breakeven ON:
1. Trade opens with SL=$100, TP=$125 from entry
2. Price moves $50 in your favor → SL moves to entry (breakeven)
3. Trade rides until TP hit ($125 profit) or SL hit ($0 breakeven or $100 loss if breakeven didn't trigger)

---

## Observed Live Behavior

- **Breakeven at $50 may be too tight** for BTC volatility. ATR on M1 is ~30-50. A $50 move is 1-2x ATR — price can easily retrace. Consider $75-100.
- **utbot_simple fires frequently** on M1 UT Bot crossovers. Good for testing, but will take many small trades.
- **Signal reversal was causing whipsaw** (signal flickers on 1-min). Disabled in favor of fixed TP/SL.
