# Codex Audit Prompt — mt5-trader

Copy everything below the line into Codex.

---

## Autonomy Policy

If you're working towards goals, do NOT end your turn. This allows for continuous autonomous work.

The user will interrupt you when required, but they will mostly provide steering messages.

Do not pester the user by ending your turn after a unit of work, as that requires them to keep nudging you to keep working.

You MUST continue working autonomously towards any known objectives until the user interrupts you. Do NOT end your turn until there is absolutely nothing left to do.

---

## Your Task

You are auditing a **MetaTrader 5 automated trading system** written in Python + MQL5. Your job is to deeply read, understand, and verify the correctness of all computation logic — both in the **Python backtester** and in the **MQL5 Expert Advisor (EA)**. You must also verify they are consistent with each other.

**DO NOT MAKE ANY CODE CHANGES.** You are read-only. Write ALL your findings, bugs, inconsistencies, and recommendations into a single file: **`codex-findings.md`** at the repo root. That is the ONLY file you may create or write to.

---

## How the System Works

This is a **signal-driven trading system** for XAUUSD (gold) on MetaTrader 5:

1. **MQL5 EA** (`MQL5/Experts/SignalMaster.mq5`) runs inside MT5 terminal. It computes indicators (Donchian channels, EMA, RSI, VWAP, UT Bot, ADX, candlestick patterns) on multiple timeframes and writes signal CSV files to disk.

2. **Python system** reads those CSV signal files, evaluates strategy rules (defined in YAML configs via expression trees), and sends trade orders back to MT5 via an rpyc bridge.

3. **Backtester** (`backtest/`) replays historical M1 OHLC data, recomputes the same indicators in Python, evaluates the same strategy rules, and simulates trades to produce performance stats (PF, win rate, drawdown, etc.).

**The critical correctness requirement:** The backtester's indicator calculations and signal logic must exactly match what the EA produces. Any divergence means backtest results are unreliable.

---

## Important Files to Read (in priority order)

### Core Logic — READ THESE THOROUGHLY
- `MQL5/Experts/SignalMaster.mq5` — The EA. All indicator computations, signal generation, CSV writing. This is the source of truth for what signals look like.
- `backtest/indicators.py` — Python indicator calculations (Donchian, EMA, RSI, VWAP, UT Bot, ADX, candle patterns). Must match the EA exactly.
- `backtest/simulator.py` — Trade simulation engine: entry, exit, SL/TP, partial TP, trailing stop, breakeven logic.
- `backtest/runner.py` — Orchestrates backtest: loads data, computes indicators, evaluates rules, feeds simulator.
- `backtest/data_loader.py` — Loads and resamples M1 CSV data to higher timeframes.
- `backtest/filters.py` — Filter evaluation for backtester.
- `backtest/stats.py` — Performance statistics computation (PF, Sharpe, drawdown, etc.).
- `rules/expression.py` — The expression engine that evaluates YAML strategy rules (comparisons, boolean logic, lookback, cross detection).
- `core/engine.py` — Main live trading loop.
- `trade/initiator.py` — Live trade entry logic: evaluates strategy rules against live signals.
- `trade/manager.py` — Live trade management: trailing stops, breakeven, partial TP, exit logic.
- `signals/` — Signal readers that parse the EA's CSV files (`donchian.py`, `ut_bot.py`, `liq_grab.py`, `generic.py`, `base.py`).
- `config-gold.yaml` — The active strategy configuration with 15 strategies, their entry rules, filters, exit rules, risk params.
- `exits/` — Exit strategy implementations (trailing stop, breakeven, partial TP, signal reversal).
- `filters/` — Trade filters (cooldown, consecutive loss, daily loss, manual switch, reversal cooldown).

### Config & Models
- `core/config.py` — Config loader and accessor.
- `core/models.py` — Data models (Trade, Signal, etc.).
- `core/mt5_client.py` — MT5 rpyc bridge client.

### Strategy Definitions
- `strategies/*.yaml` — Individual strategy YAML files (these are referenced by config-gold.yaml).

### Reference Docs (skim for context)
- `docs/SIGNAL_REFERENCE.md` — Documents all signal file formats and fields.
- `docs/expression-reference.md` — Documents the expression/rule language.
- `docs/architecture.md` — System architecture overview.
- `docs/backtester.md` — Backtester documentation.
- `docs/indicators.md` — Indicator documentation.

### Files to IGNORE (do not waste time on these)
- `.venv/` — virtual environment
- `.git/` — git internals
- `uv.lock` — lockfile
- `sampledata/` — CSV data files (large, not code)
- `data/` — runtime data directory
- `ui/dashboard.py` — TUI dashboard (cosmetic, not logic)
- `core/notifications.py` — Telegram notifications (cosmetic)
- `core/events.py` — Event system (cosmetic)
- `scripts/download_ohlc.py` — Data download utility
- `tests/` — Test runner scripts (not unit tests, just batch runners)
- `docs/deepresearch*.md`, `docs/suggestions.md`, `docs/buy-strategy-findings.md` — Research notes, not code docs
- `strategies/buy/` — Experimental buy strategies subfolder

---

## What to Verify and Report

For each area below, read the code carefully and report findings in `codex-findings.md`:

### 1. Indicator Parity (EA vs Backtester)
- Compare every indicator in `SignalMaster.mq5` with its Python equivalent in `backtest/indicators.py`.
- Check: Donchian Channel (period, high/low source, upper/mid/lower), EMA (period, calculation method), RSI (period, smoothing), VWAP (reset logic, anchoring), UT Bot (ATR period, sensitivity, trailing logic), ADX (period, smoothing), candlestick patterns (hammer, doji, shooting star — body/wick ratio thresholds, minimum size).
- Flag ANY differences in calculation, rounding, or edge cases.

### 2. Timeframe Resampling
- The EA computes indicators on native MT5 timeframes (M1, M2, M3, M5, M10, M15, M20, M30, H1, H2, H3, H4, H6, H8, H12, D1).
- The backtester resamples M1 data to create higher timeframes in `data_loader.py`.
- Verify the resampling logic is correct (OHLC aggregation, volume summing, timestamp alignment).
- M45 is a synthetic timeframe (45-minute bars) — verify it's handled correctly.

### 3. Expression Engine Correctness
- `rules/expression.py` evaluates strategy entry/exit conditions from YAML.
- Verify all operators: `>`, `<`, `>=`, `<=`, `==`, `cross_above`, `cross_below`, `and`, `or`, `not`, `lookback`, `ago`, `between`.
- Check edge cases: missing data, NaN handling, first-bar lookback, type coercion.

### 4. Trade Simulation Accuracy
- `backtest/simulator.py` — verify SL/TP hit detection uses correct high/low (not just close).
- Verify spread/slippage handling.
- Verify partial TP logic (does it correctly reduce position size and move SL?).
- Verify trailing stop logic matches `exits/trailing_stop.py`.
- Verify breakeven logic matches `exits/breakeven.py`.

### 5. Live vs Backtest Consistency
- Compare `trade/initiator.py` (live entry) with `backtest/runner.py` (backtest entry) — do they evaluate the same rules the same way?
- Compare `trade/manager.py` (live management) with `backtest/simulator.py` (backtest management) — same exit logic?
- Flag any cases where live and backtest would produce different results.

### 6. Signal File Parsing
- Compare the CSV format the EA writes (`SignalMaster.mq5`) with what the Python signal readers expect (`signals/*.py`).
- Check for column name mismatches, data type assumptions, missing fields.

### 7. Config Evaluation
- Read `config-gold.yaml` and verify each strategy's rules reference valid signal fields and indicators.
- Check for typos, impossible conditions, or rules that can never trigger.

### 8. Risk & Edge Cases
- Position sizing: is lot size calculation correct?
- Max positions / max per strategy limits — are they enforced consistently?
- What happens on connection loss, missing signal files, stale data?
- Any division by zero, off-by-one, or race condition risks?

---

## Output Format for codex-findings.md

Structure your findings file like this:

```markdown
# Codex Audit Findings — mt5-trader

## Critical Bugs
(Issues that WILL cause incorrect trades or wrong backtest results)

## Inconsistencies (EA vs Backtester)
(Differences between MQL5 and Python indicator calculations)

## Potential Bugs
(Issues that COULD cause problems under certain conditions)

## Recommendations
(Improvements, not bugs — things that would make the system more robust)

## Verified Correct
(Areas you checked and confirmed are working correctly — so we know what was covered)
```

---

## Reminders

- **DO NOT modify any code.** Only create/write `codex-findings.md`.
- Be specific: include file names, line numbers, and code snippets in your findings.
- If two calculations differ, show both side by side.
- Do NOT end your turn until you have thoroughly audited all the areas listed above.
- Work through the files systematically — start with the EA, then indicators, then expression engine, then simulator, then live trade logic, then signal parsing, then config.
