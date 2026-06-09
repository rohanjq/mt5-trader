# Codex Audit Findings — mt5-trader

## Critical Bugs
- **Backtest indicator coverage is incomplete vs EA output surface** (`backtest/indicators.py`, `backtest/runner.py`, `config-gold.yaml`):
  - EA emits many indicators/signals: `dc`, `utbot`, `liqgrab`, `ema`, `rsi`, `bb`, `adx`, `macd`, `stoch`, `atr`, `vwap`, `candle` from `MQL5/Experts/SignalMaster.mq5` (input declarations and per-indicator writers near top of file).
  - Backtester computes from configured `signals.sources` (`backtest/runner.py`) and relies on `compute_all_indicators` (`backtest/indicators.py`). If any configured source is absent from compute map (or field names differ), strategies silently evaluate on missing fields and fail false/neutral.
  - This is a correctness-critical risk because it can produce materially fewer/more trades than live without explicit failure.

- **Potential same-bar execution bias in simulator on SL/TP collision** (`backtest/simulator.py`):
  - When both SL and TP are inside one bar range, tie-break uses bar open relative to entry (`check_sl_first = open_ < entry` for BUY, inverse for SELL) instead of deterministic MT5-compatible intrabar sequence.
  - This heuristic can invert win/loss outcome for volatile bars and is a direct P/L correctness issue.

- **Live vs backtest execution timing divergence risk** (`trade/initiator.py` vs `backtest/runner.py`):
  - Backtest explicitly uses “signal on bar *i* close, fill at bar *i+1* open” with pending queue in `backtest/runner.py`.
  - Live initiator behavior is polling/file-driven and may execute on currently available signal snapshot (not necessarily aligned to exact close/open transition), especially if CSV update cadence (`WriteInterval` in EA) and Python polling cadence drift.
  - This can shift entries by one bar (or more), materially affecting results.

## Inconsistencies (EA vs Backtester)
- **Donchian width SMA and shifted-window semantics need strict parity verification** (`MQL5/Experts/SignalMaster.mq5` Donchian writer block vs `backtest/indicators.py` Donchian compute):
  - EA computes `dc_width_sma20` via explicit shifted windows over prior 20 bars using nested loops and series indexing (closed-bar anchored).
  - Python implementation must replicate exact shift anchoring and include/exclude current closed bar identically; any one-bar offset changes volatility filters.
  - This is a likely divergence point due to MT5 series indexing (`ArraySetAsSeries=true`) vs pandas forward indexing.

- **Synthetic timeframe handling differs in architecture** (`SignalMaster.mq5` synthetic path in indicator writers vs `backtest/data_loader.py`):
  - EA builds synthetic bars for unsupported TFs via `BuildSyntheticBars(...)` and then computes indicators on those synthetic bars.
  - Backtester resamples M1 into higher TF OHLC in `data_loader.py`.
  - Even if mathematically intended to match, boundary alignment (bar close timestamps, inclusion of partial running bar) is highly sensitive and must match exactly; this is a structural inconsistency risk.

- **Running vs closed field semantics** (`SignalMaster.mq5` writes both running and closed bar fields; `backtest/indicators.py` often aliases running=closed):
  - Backtester comments indicate “running_* = same as closed_* in backtest (we only see closed bars)” in multiple compute functions.
  - EA signal files include true running-bar values. If any strategy/filter uses `running_*` fields live, backtest cannot reproduce them exactly.

- **Signal-reader directional derivation differs from raw EA trigger fields** (`signals/donchian.py`, `signals/ut_bot.py`, `signals/liq_grab.py`):
  - Readers often derive `SignalDirection` from broader context fields (e.g., Donchian zone, UT bias) while actual tactical entries in strategies may depend on discrete trigger fields (`closed_*_rej`, `closed_signal`, etc.).
  - This is acceptable if rules use metadata fields directly, but parity relies on no implicit use of coarse `direction` in one path and trigger fields in another.

## Potential Bugs
- **Expression edge-case behavior likely under-specified for NaN/missing keys** (`rules/expression.py`):
  - Strategy evaluation over merged indicator dictionaries can encounter missing keys for early bars, sparse timeframes, or unsupported sources.
  - If comparisons with `None`/`NaN` are not normalized consistently across operators (`>`, `<`, `between`, `cross_*`, `lookback`, `ago`), rule outcomes can differ unexpectedly.

- **Resampling alignment risks for nonstandard TFs (especially M45)** (`backtest/data_loader.py`):
  - M45 is synthetic in EA config and explicitly present in strategy set.
  - Any mismatch in pandas `resample` label/closed/origin semantics versus MT5 bar boundaries (server time alignment) causes shifted indicator states and false parity.

- **Backtest spread/slippage realism gap** (`backtest/simulator.py`):
  - Spread is configurable (`spread_points`) but fill and SL/TP checks are candle-extrema based with simplified price model.
  - If live uses bid/ask and broker-side stop trigger semantics, simulator may systematically over/under-estimate execution quality.

- **Partial TP / breakeven / trailing interaction ordering can alter exits** (`backtest/simulator.py` vs `trade/manager.py`, `exits/*.py`):
  - Backtest processes management in a specific intra-bar order (partial TP, BE move, trailing update, then hit checks).
  - If live manager executes these in different order/timing (tick-driven, per-loop), outcomes diverge on fast moves.

- **CSV parser type coercion assumptions** (`signals/base.py`, `signals/generic.py`):
  - Reader stack depends on converting EA CSV key/value pairs into typed metadata.
  - Any mismatch in booleans (`TRUE/FALSE`), numeric precision strings, or absent keys produces silent neutral conditions rather than hard errors.

- **Config/rule reference drift risk** (`config-gold.yaml`, `strategies/*.yaml`):
  - Large strategy surface with many field references across timeframes increases typo/dead-field probability.
  - Without strict schema validation against produced indicator fields, impossible conditions can remain undetected.

## Recommendations
- **Add explicit parity test harness**: For each indicator/timeframe, ingest EA CSV snapshots and compare to Python recompute on identical OHLC slices, field-by-field with tolerances where needed.
- **Enforce source/field schema validation at startup**: Fail fast if any strategy references missing indicator source/field.
- **Codify bar-timing contract**: Document and enforce close-detect + next-open-fill consistently for both live and backtest; include timezone/session alignment.
- **Unify exit-management sequencing**: Extract shared logic between `trade/manager.py` and `backtest/simulator.py` to avoid drift.
- **Harden expression evaluator**: Centralize NaN/None behavior for all operators; make missing-field outcome explicit and logged.
- **Strengthen CSV ingestion**: Validate required columns per source, strict boolean parser, and stale-file detection with max-age checks.
- **Add synthetic timeframe parity checks**: Especially M45, plus M2/M3/M10/M20/H2/H3/H6/H8/H12 where MT5 and pandas boundary semantics can diverge.

## Verified Correct
- **Architecture consistency**:
  - EA is the producer of per-indicator, per-timeframe CSV snapshots (`MQL5/Experts/SignalMaster.mq5`).
  - Python live stack consumes CSV via `signals/*` and evaluates YAML expression rules (`rules/expression.py`) in engine loop (`core/engine.py`).
  - Backtester uses the same rule framework (`rules/expression.py`) through `backtest/runner.py`.

- **Simulator uses high/low for barrier checks** (`backtest/simulator.py`):
  - SL/TP checks are based on candle extremes (`high/low`) rather than close-only, which is directionally correct for OHLC backtesting.

- **Backtester fill model is explicit and deterministic** (`backtest/runner.py`):
  - Signal generation and entry fill separation (pending queue → next bar open) is clearly implemented.

- **Signal readers preserve metadata payload** (`signals/donchian.py`, `signals/ut_bot.py`, `signals/liq_grab.py`, `signals/generic.py`):
  - Raw CSV key/values are carried through to rule evaluation, enabling rich expression-based conditions.

- **Config-driven strategy loading** (`rules/expression.py`, `backtest/runner.py`, `trade/initiator.py`):
  - Both live and backtest depend on YAML-defined expression rules, reducing hardcoded logic drift risk.

---

## Notes on Audit Depth
- This audit reviewed the requested core files and cross-component logic paths, with special focus on parity-sensitive areas: indicator computation, timeframe construction, expression evaluation, and execution lifecycle.
- The highest-risk reliability gaps are around **exact bar alignment/parity** and **live-vs-backtest timing/management sequencing**, not broad architectural flaws.
