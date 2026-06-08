# Known Issues and Bugs

Tracked issues in the codebase, with status and severity.

## Live Trading

### BUG 1 — Rising-edge state never reset after trade close

**Severity**: Medium  
**File**: `rules/expression.py`  
**Status**: Open

Each `ExpressionRule` tracks `_prev_buy_met` / `_prev_sell_met` for rising-edge detection (only fire on False→True transition). When a trade closes, `reset_signal_tracking()` is called — but it only resets `_last_trigger_key`, which is dead code. The edge states are never reset.

**Impact**: After a trade closes, if all conditions are still met, the rule cannot re-fire until at least one condition naturally drops and comes back.

### BUG 2 — `_last_trigger_key` is dead code

**Severity**: Low  
**File**: `trade/initiator.py`

`_last_trigger_key` is set in `_execute()` and cleared in `reset_signal_tracking()`, but never read anywhere. The actual dedup happens via rising-edge detection in expression rules.

### BUG 3 — `signal_reversal_exit` cannot work with expression rules

**Severity**: Low (currently disabled)  
**File**: `exits/signal_reversal.py`

`SignalReversalExit` looks up `signals.get(trade.signal_source)` where `signal_source` is the rule name (e.g., `"gold_utbot_trend"`). The signals dict has entries like `"utbot_M1"` — there's no signal named after the rule. Always returns HOLD. No impact while disabled.

### BUG 4 — Default config drift

**Severity**: Low  
**File**: `core/config.py`

`_DEFAULT_CONFIG` has `breakeven_trigger_dollars: 50.0` but all code reads `exit_rules.breakeven_pct`. Defaults are misaligned but current configs explicitly set values, so no runtime impact.

### BUG 5 — Unimplemented filter config keys

**Severity**: Low  
**Status**: Partially fixed

Some config keys are tracked but not fully wired:

| Config Key | Status |
|-----------|--------|
| `filters.max_consecutive_losses` | Implemented in live + backtest |
| `filters.pause_after_consecutive_minutes` | Config read but not enforced |
| `filters.max_daily_loss` | Partially implemented |

## Backtester

### LIMITATION 1 — Bar-based simulation

**Severity**: By design

Cannot simulate intra-bar price movement. When both SL and TP are hit in the same bar, the system uses bar open direction to decide which fires first. This is an approximation.

### LIMITATION 2 — No slippage model

**Severity**: Low

All fills are at exact prices (SL, TP, bar open). Real-world slippage is not modelled. Results will be slightly optimistic.

### LIMITATION 3 — VWAP session boundary

**Severity**: Low

VWAP resets at 22:00 UTC (5 PM ET). If your broker uses a different session boundary, VWAP values will diverge between backtest and live trading.

### LIMITATION 4 — Forward-fill warmup

**Severity**: Low

Higher-TF indicators are forward-filled to M1 resolution. The first bars of the dataset may have stale indicator values until enough data accumulates for the indicator period (e.g., EMA200 needs 200 bars).
