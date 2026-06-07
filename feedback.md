## MT5-Trader Bug Report

### BUG 1 — Rising-edge state never reset after trade close (HIGH IMPACT)

**File:** `rules/expression.py` lines 163-167

Each `ExpressionRule` tracks `_prev_buy_met` / `_prev_sell_met` for rising-edge detection (only fire on False→True transition). When a trade closes, `reset_signal_tracking()` is called — but it only resets `_last_trigger_key`, which is **dead code** (never read anywhere). The expression rule edge states are **never reset**.

**Impact:** After a trade closes, if all conditions are still met (e.g., strong trend), the rule **cannot re-fire** until at least one condition naturally drops and comes back. This means missed re-entries in sustained trends.

**Fix needed:** `reset_signal_tracking()` should iterate all expression rules and reset their `_prev_buy_met = False` / `_prev_sell_met = False`.

---

### BUG 2 — `_last_trigger_key` is dead code

**File:** `trade/initiator.py` lines 264-266

`_last_trigger_key` is set in `_execute()` and cleared in `reset_signal_tracking()`, but it is **never read or checked** anywhere in `on_signals()` or any other method. The actual dedup happens via rising-edge detection in expression rules. This makes `reset_signal_tracking()` a no-op.

---

### BUG 3 — RSI `CROSS_UP_52` masked by `CROSS_UP_50` (SIGNALMASTER ISSUE)

**File:** `MQL5/Experts/SignalMaster.mq5` lines 1178-1182

The RSI cross detection uses `else if` chaining. If RSI jumps from 49 → 53 in one bar, it matches `CROSS_UP_50` first and `CROSS_UP_52` is never reached. The `ema_pullback` strategy relies on `CROSS_UP_52` — so if both levels are crossed in one bar, the entry is missed.

```mql5
// Current code — CROSS_UP_52 unreachable if CROSS_UP_50 also matches:
if(rsi_buf[2] < 50 && rsi_buf[1] >= 50)       closed_cross = "CROSS_UP_50";
else if(rsi_buf[2] < 52 && rsi_buf[1] >= 52)   closed_cross = "CROSS_UP_52";
```

**Fix options:**
- Check CROSS_UP_52 **before** CROSS_UP_50 (prefer the more specific level)
- Or have `ema_pullback` accept both: `rsi14_M1.closed_cross in CROSS_UP_50,CROSS_UP_52`

---

### BUG 4 — Unimplemented safety filters (FALSE SENSE OF PROTECTION)

**Config values that are never enforced:**

| Config Key | Value | Status |
|---|---|---|
| `filters.max_consecutive_losses` | 3 | `TradeManager._consecutive_losses` is tracked but **no filter checks it** |
| `filters.pause_after_consecutive_minutes` | 15 | **Never read** by any code |
| `filters.max_daily_loss` | -1 | Even if set > 0, **no filter implements it** |

`CooldownFilter` only checks time since last loss. There is no `MaxConsecutiveLossFilter` or `DailyLossFilter`.

---

### BUG 5 — `signal_reversal_exit` can't work for expression rules (LATENT)

**File:** `exits/signal_reversal.py` line 34

Currently disabled (`signal_reversal_exit: false`), but if enabled: `SignalReversalExit` does `signals.get(trade.signal_source)` where `signal_source` is the rule name (e.g., `"ema_pullback"`, `"bb_range_fade"`). The signals dict only has entries like `"utbot_M1"`, `"ema50_M5"` — there's no signal named `"ema_pullback"`. So it always returns `HOLD` for expression-triggered trades.

---

### BUG 6 — Default config drift

**File:** `core/config.py` line 39

`_DEFAULT_CONFIG` has `breakeven_trigger_dollars: 50.0` but all code reads `exit_rules.breakeven_pct`. If user config doesn't specify `breakeven_pct`, fallback is `0.0` (breakeven disabled), not the intended default. Current config has `breakeven_pct: 65.0` so no impact today, but defaults are wrong.

---

### BUG 7 — Dead `strategies/` directory with wrong signal names

**Files:** `strategies/utbot_simple.py`, `strategies/dc_reversal.py`

- `UTBotStrategy` uses `signals.get("ut_bot_1m")` — should be `"utbot_M1"`
- `DCReversalStrategy` uses `signals.get("dc_channels")` and `signals.get("ut_bot_1m")` — should be `"dc_M15"` and `"utbot_M1"`
- `discover_strategies()` is **never called** by the engine (engine uses `discover_rules`), so these are dead code. But confusing for anyone reading the codebase.

---

### NOT A BUG — Verified correct

- All expression signal names (`ema50_M5`, `rsi14_M1`, `adx_M5`, etc.) match GenericCSVSignal plugin names ✓
- All CSV filenames match SignalMaster output (`BTCUSDT_ema50_M5.csv`, etc.) ✓
- All CSV field names (`closed_price_vs_ema`, `closed_hist_cross`, `volatility_state`, etc.) match SignalMaster output ✓
- `is TRUE` operator correctly compares against `"TRUE"` string ✓
- Numeric comparisons (`closed_histogram > 0`) parse correctly ✓
- `in` operator with comma-separated values works correctly ✓
- DC zone values (`UPPER`, `UPPER_MID`, `MIDDLE`, `LOWER_MID`, `LOWER`) match ✓
- CSV encoding handling (utf-8-sig → utf-16 → latin-1 fallback) is correct ✓
