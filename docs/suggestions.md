# Deep Review Suggestions — MT5 Auto-Trader (No Code Changes Applied)

Date: 2026-06-08  
Scope reviewed:
- Python trader repo: `/Users/rohan.arora/repos/mt5-trader`
- EA generator file: `/Users/rohan.arora/repos/MetaTrader5-Docker/MQL5/Experts/SignalMaster.mq5`
- Signal docs: `/Users/rohan.arora/repos/MetaTrader5-Docker/SIGNAL_REFERENCE.md`

This document contains **recommended fixes only**. No source/config files were modified.

---

## 1) High-Priority Code Fixes (Bugs / Correctness)

## 1.1 `rules/expression.py` — signal-name parser bug with underscore-heavy names

### Why this matters
Your config actively uses names like:
- `bb20d2_M1`
- `adx14_M5`
- `macd12_26_9_M1`
- `stoch5_3_3_M3`

The parser currently assumes the expression format `signal.field OP value`, but relies on a regex that should be hardened against edge cases where signal IDs include multiple underscores, digits, and potential mixed-case tokens.

### Recommended change
- Tighten and test the expression regex and parser normalization path to ensure **all configured signal IDs** parse correctly and deterministically.
- Add unit tests for all active naming patterns, including invalid expressions.

### Proposed test cases
- `macd12_26_9_M1.closed_histogram > 0`
- `stoch5_3_3_M3.closed_k >= 20`
- `bb20d2_M1.closed_band_zone == LOWER`
- `adx14_M5.closed_trend_strength in TRENDING,STRONG_TREND`
- malformed examples (`missing operator`, `missing value`, `extra dot`, etc.)

---

## 1.2 `rules/expression.py` — boolean alias semantics (`is` / `is_not`) are too permissive

### Why this matters
`is` and `is_not` currently behave like case-insensitive string equality against raw metadata. This can silently pass on non-boolean strings and create false positives.

### Recommended change
- Treat `is` / `is_not` as strict boolean operators with canonical accepted values:
  - true-set: `TRUE`, `1`, `YES`
  - false-set: `FALSE`, `0`, `NO`
- Reject ambiguous values (`"maybe"`, empty string, arbitrary text) as invalid comparisons.

### Benefit
Removes hidden logic drift between indicator output formatting and rule evaluation.

---

## 1.3 `signals/generic.py` — CSV type coercion and null safety

### Why this matters
Signal CSVs coming from EA commonly mix numbers, enums, booleans, and placeholders (`NONE`, empty strings, `nan`-like values). If generic loader keeps everything as raw strings without strict normalization, downstream comparisons become brittle (especially numeric comparisons in expression rules).

### Recommended change
- Normalize input fields on load:
  - strip whitespace
  - preserve enums as uppercase strings
  - canonicalize booleans to `TRUE/FALSE`
  - leave missing as empty sentinel (or explicit `None`, consistently)
- Add defensive handling for malformed rows and partial writes (file lock race between EA write and Python read).
- Ensure loader can ignore/skip trailing incomplete line while file is being written.

### Benefit
Prevents transient parse failures and rule misfires.

---

## 1.4 `trade/manager.py` + exits — state transitions under partial TP / breakeven / trailing

### Why this matters
Exit logic must be idempotent per position per event. Common failure mode in trade managers:
- partial TP executes
- same tick loop re-enters logic
- duplicate partial close or repeated SL updates happen due to stale state snapshot

### Recommended change
- Enforce explicit per-position flags:
  - `partial_tp_done`
  - `breakeven_done`
  - `last_sl_update_price`
- Guard each exit action with monotonic condition checks and dedupe keys.
- Ensure manager refreshes live position state after each modification before next rule pass.

### Benefit
Avoids duplicate close attempts and jittery SL churn.

---

## 1.5 `core/engine.py` — thread coordination and snapshot consistency

### Why this matters
Engine has multiple loops/threads (`signal-loop`, `monitor-loop`) sharing latest signal snapshots and invoking trade actions. If shared dicts are copied/read without atomicity guarantees, race windows can produce mixed-bar condition evaluations.

### Recommended change
- Ensure all accesses to shared latest-signals map are under lock or immutable snapshot copy (`copy()` under lock) before evaluation.
- Keep signal timestamp/bar-time attached and reject mixed-age snapshots when strategy requires aligned bar close.

### Benefit
Reduces non-deterministic entries caused by cross-thread timing.

---

## 1.6 `trade/initiator.py` — risk sizing edge cases

### Why this matters
Current risk-based volume sizing depends on `trade_tick_size`, `trade_tick_value`, and step rounding. Common edge bugs:
- step-rounding to zero for tiny risk amounts
- division precision issues when tick size is very small
- volume clamp happening after rounding in a way that can underflow to invalid lot step

### Recommended change
- Normalize order of operations:
  1. compute raw volume
  2. floor to step
  3. clamp to `[min_volume, max_volume]`
  4. re-quantize to step exactly
- Validate non-zero volume before send.
- Log full sizing inputs when fallback is used.

### Benefit
Fewer silent fallback lots and cleaner sizing reproducibility.

---

## 2) Filter & Exit Logic Review (Design Correctness)

## 2.1 Breakeven (`exits/breakeven.py`)

### Findings
- Breakeven at fixed `% of initial risk` is conceptually correct.
- Risk: if SL already above/below entry due to earlier trailing or manual adjustment, BE move can regress protective SL if not guarded.

### Recommendation
- Move-to-BE only if it is **strictly more protective** than current SL.
- Add optional `be_offset_dollars` (e.g., +0.10 for BUY / -0.10 for SELL) to cover spread.

---

## 2.2 Partial TP (`exits/partial_tp.py`)

### Findings
- 80/20 split logic is sensible for scalping, but must be one-shot and volume-step-aware.
- Risk: partial close volume may round to zero with small lots.

### Recommendation
- Compute partial close quantity with broker step + minimum volume checks.
- If close size < minimum, skip partial and keep full position with log reason.
- Persist one-shot state in manager memory keyed by position ticket.

---

## 2.3 Trailing stop integration

### Findings
- Config has trailing stop fields, but if trailing logic runs without BE/partial coordination order, stop can oscillate.

### Recommendation
- Enforce exit order per tick:
  1. hard close signals
  2. partial TP (once)
  3. breakeven (once)
  4. trailing update (monotonic)
- Trailing must be monotonic-only in favorable direction.

---

## 3) Strategy Review — `config-gold.yaml` (Primary)

Goal specified: **high-conviction profitable gold scalping**.

## 3.1 General observations

- Your active gold stack is mostly coherent: trend + momentum + pullback + regime filters.
- There is overlap/redundancy in some rules (multiple EMA alignment checks + VWAP side + RSI>50 on same TF) which can over-filter and reduce frequency without materially improving quality.
- Some SL values look too tight for XAUUSD M1/M3 noise during active sessions.

## 3.2 SL sizing recommendations (XAUUSD)

For M1/M3 scalping on XAUUSD, fixed-dollar stops should generally align to recent ATR regime.

### Recommended baseline bands (guideline)
- Very tight scalp: `$2.8–$3.8` (only in compressed/low-noise phases)
- Standard intraday scalp: `$4.0–$6.5`
- Breakout/impulse: `$6.0–$9.0`

### Per-strategy guidance
- `gold_vwap_pullback` (`sl_dollars: 3.5`)  
  - Acceptable but borderline tight. Prefer `$4.0–$4.8` unless additional compression filter is enforced.
- `gold_session_impulse` (`sl_dollars: 5.0`)  
  - Reasonable default.
- Mean-reversion variants should avoid oversized SL with low RR; either tighter SL + faster exits or disable in high-trend ADX states.

## 3.3 Reward ratio realism

- Pullback continuation: `RR 1.2–1.4` realistic.
- Strong trend impulse: `RR 1.4–1.8` possible but needs volatility confirmation.
- Mean reversion scalp: often better with `RR ~1.0–1.25` + high hit rate.

### Recommendation
- Keep mixed RR profile by strategy type; avoid forcing one global RR.
- For rules with lower signal quality, demand higher confluence rather than raising RR blindly.

## 3.4 Condition coherence and redundancies

### `gold_vwap_pullback`
Potential redundancy:
- `ema21_M5 ABOVE`
- `ema50_M5 ABOVE`
- `vwap_M1 ABOVE`
- `rsi14_M1 > 50`

These can all encode similar directional bias. Suggest replacing one with a true pullback-resume trigger (e.g., `closed_reenter_from_below` for bands or a reclaim pattern) to reduce correlated filters.

### `gold_session_impulse`
Strong structure. Suggest adding explicit anti-chop block:
- avoid entries when `bb20d2_M1.bb_squeeze is TRUE` **without** breakout confirmation.

### Mean reversion rules
Ensure they explicitly require:
- ADX ranging/weak trend
- exhaustion marker (RSI2 extreme + band touch/re-entry)
- immediate invalidation condition

---

## 4) BTC Config Consistency — `config-btc.yaml`

## Findings
- BTC strategy set uses significantly larger absolute SL values (expected).
- Structural rule templates should match gold architecture conventions (naming, BE/partial toggles).

## Recommendations
- Standardize strategy schema fields across gold/btc:
  - always include `sl_dollars`, `reward_ratio`, `breakeven_pct`, `partial_tp`
- Ensure disabled rules are explicitly marked and documented with reason.

---

## 5) Rule Engine Robustness Checklist

For `rules/expression.py`:
- Add whitespace-tolerant parsing tests.
- Validate unsupported operators with explicit error logs.
- Detect missing signal source vs missing field separately in logs.
- For `in/not_in`, trim and uppercase all tokens; reject empty token lists.

---

## 6) Signal Loader Robustness Checklist

For `signals/generic.py`:
- Validate header presence and required columns.
- Ignore unknown columns safely (forward compatibility).
- Support BOM (`utf-8-sig`) and normalize line endings.
- Guard against partially-written CSV row reads (EA write race).
- Add row-level error counters and log summaries every N cycles.

---

## 7) EA Review — `SignalMaster.mq5`

## Findings (from interface/docs alignment perspective)
- Field naming appears extensive and generally consistent with docs.
- Critical integration risk is not indicator math, but **contract drift** between EA CSV field names and Python rule expectations.

## Recommendations
- Add a generated “schema line” (header contract version + timestamp) to each CSV.
- Maintain strict backward-compatible naming or provide alias mapping in Python loader.
- For boolean fields, always emit `TRUE/FALSE` (not mixed 0/1/text across indicators).

---

## 8) Priority-Ordered Implementation Plan (if you want me to apply later)

1. `rules/expression.py`: parser + boolean strictness + tests  
2. `signals/generic.py`: robust CSV normalization and partial-write safety  
3. `trade/manager.py` + exits: idempotent BE/partial/trailing sequencing  
4. `core/engine.py`: snapshot atomicity and mixed-age guard  
5. `config-gold.yaml`: SL/RR/condition refinements by strategy class  
6. `config-btc.yaml`: schema consistency pass

---

## 9) Suggested Gold Strategy Tweaks (Concrete)

If optimizing for high-conviction scalping:

- Keep 2 primary families only:
  - Trend pullback continuation
  - Session impulse breakout
- Demote/disable overlapping mid-quality rules that fire in same regime.
- Apply volatility-adaptive stop framework:
  - `effective_sl = max(base_sl, ATR_M1 * k)` with k tuned per strategy.
- Use asymmetric management:
  - early partial at ~0.8R to 1.0R
  - move BE after partial
  - trail runner only when momentum remains aligned

---

## 10) What I would change first (minimal, high impact)

- Harden `rules/expression.py` parser and boolean semantics.
- Make `signals/generic.py` resilient to malformed/partial CSV rows.
- Enforce one-shot partial TP and monotonic BE/trailing in `trade/manager.py`.
- Widen `gold_vwap_pullback` SL from 3.5 to ~4.2 unless strict compression filter is added.

---

## Note
This report intentionally does **not** modify any project files besides creating this `suggestions.md` document, per your instruction.
