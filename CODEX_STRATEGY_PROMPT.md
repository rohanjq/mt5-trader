# Codex Strategy Discovery Prompt — mt5-trader

Copy everything below the line into Codex.

---

## Autonomy Policy

If you're working towards goals, do NOT end your turn. This allows for continuous autonomous work.

The user will interrupt you when required, but they will mostly provide steering messages.

Do not pester the user by ending your turn after a unit of work, as that requires them to keep nudging you to keep working.

You MUST continue working autonomously towards any known objectives until the user interrupts you. Do NOT end your turn until there is absolutely nothing left to do.

**IMPORTANT for long-running commands:** When running backtests (they take 30-120 seconds each), run them in background and keep reading output until they complete. Do NOT wait idly. While one runs, prepare the next strategy config. Always capture the full output including the stats report.

---

## Your Task

You are a **quantitative strategy researcher** for an automated XAUUSD (gold) scalping system on MetaTrader 5. Your job is to **invent, backtest, and report on new short-timeframe strategies** using candle patterns, wick analysis, Donchian Channel structure, and UT Bot trend filters.

**You MUST backtest every strategy idea** against 60 days of M1 data. No theoretical ideas — only backtested results matter.

Write ALL results into a single file: **`codex-strategy-results.md`** at the repo root. That is the ONLY file you may create or write to (besides temporary YAML configs you need for backtesting).

---

## System Overview

This is a signal-driven trading system. Strategies are defined as YAML expression rules. Each rule has `buy` and/or `sell` condition lists — ALL conditions must be true simultaneously (AND logic) for a signal to fire.

### How to Backtest

```bash
uv run python -m backtest --config <your-config.yaml> --data sampledata/XAUUSD_M1_60d.csv --balance 10000
```

This runs a full 60-day replay (~57,700 M1 bars). Output includes: Profit Factor (PF), Win Rate, Max Drawdown, trade count, and per-trade log.

**A good strategy has: PF > 1.3, Win Rate > 55%, 20+ trades, Max DD < 35%.**

### Config Template

Create temporary config files like `config-test-N.yaml` for each strategy. Use this template:

```yaml
mt5:
  host: localhost
  port: 8001

trading:
  symbol: XAUUSD
  volume: 0.25
  risk_pct: 5.0
  max_volume: 10.0
  min_volume: 0.01
  magic: 200
  deviation: 20
  filling: FOK
  multi_position: false
  sl_dollars: 5.0
  reward_ratio: 1.0

signals:
  poll_interval: 2.0
  csv_dir: ../MetaTrader5-Docker/data/signals
  sources:
    # Include ALL indicators your strategy references
    - indicator: utbot
      timeframes: [M1, M2, M3, M5, M10, M15, M30, M45, H1]
    - indicator: dc
      timeframes: [M1, M2, M3, M5, M10, M15, M30, M45, H1]
    - indicator: ema9
      timeframes: [M1, M2, M3, M5, M15]
    - indicator: ema21
      timeframes: [M1, M2, M3, M5, M15]
    - indicator: ema50
      timeframes: [M1, M2, M3, M5, M15, H1]
    - indicator: ema200
      timeframes: [M1, M2, M3, M5, M15, H1]
    - indicator: rsi14
      timeframes: [M1, M2, M3, M5, M15]
    - indicator: rsi2
      timeframes: [M1, M2, M3, M5, M15]
    - indicator: adx14
      timeframes: [M1, M2, M3, M5, M15]
    - indicator: macd12_26_9
      timeframes: [M1, M3, M5, M15]
    - indicator: stoch5_3_3
      timeframes: [M1, M3, M5, M15]
    - indicator: bb20d2
      timeframes: [M1, M3, M5, M15]
    - indicator: atr14
      timeframes: [M1, M3, M5, M15]
    - indicator: vwap
      timeframes: [M1, M3, M5]
    - indicator: candle
      timeframes: [M1, M2, M3, M5, M15]
    - indicator: liqgrab
      timeframes: [M3, M5, M15]

filters:
  cooldown_seconds: 30
  max_consecutive_losses: 0
  pause_after_consecutive_minutes: 0
  max_daily_loss: -1
  reversal_cooldown_seconds: 30

exit_rules:
  signal_reversal_exit: false
  breakeven_pct: 0.0
  partial_tp: false
  tp_close_pct: 100.0
  trailing_stop_dollars: 0.0

backtest:
  initial_balance: 10000
  tick_size: 0.01
  tick_value: 1.0
  volume_step: 0.01
  commission_per_lot: 0.0
  spread_points: 30

rules:
  expressions:
    - name: "your_strategy_name"
      enabled: true
      priority: 100
      sl_dollars: 5.0
      reward_ratio: 1.0
      breakeven_pct: 0.0
      partial_tp: false
      description: "Your description"
      buy:
        - condition1
        - condition2
      sell:
        - condition1
        - condition2
```

---

## Available Indicators & Fields

### Candle Analysis (`candle_{TF}`) — YOUR PRIMARY TOOL
Fields:
- `closed_candle_type` — `HAMMER`, `SHOOTING_STAR`, `DOJI`, `MARUBOZU`, `SPINNING_TOP`, `NORMAL`
- `closed_candle_dir` — `UP`, `DOWN`, `DOJI`
- `closed_body_pct` — body as % of total range (0-100)
- `closed_upper_wick_pct` — upper wick as % of total range
- `closed_lower_wick_pct` — lower wick as % of total range
- `closed_upper_wick_ratio` — upper_wick / body (0 = no wick, 2+ = long wick)
- `closed_lower_wick_ratio` — lower_wick / body
- `closed_has_long_upper` — `TRUE`/`FALSE` (upper wick ≥ 2x body)
- `closed_has_long_lower` — `TRUE`/`FALSE` (lower wick ≥ 2x body)
- `closed_is_bullish` — `TRUE`/`FALSE`
- `closed_is_bearish` — `TRUE`/`FALSE`
- `closed_body_size` — absolute body size in price units
- `closed_total_range` — total candle range in price units

### Donchian Channel (`dc_{TF}`)
- `closed_price_zone` — `UPPER`, `UPPER_MID`, `MIDDLE`, `LOWER_MID`, `LOWER`
- `closed_upper_wick_rej` — `TRUE`/`FALSE` (wick touched upper band, closed below)
- `closed_lower_wick_rej` — `TRUE`/`FALSE` (wick touched lower band, closed above)
- `dc_compressed` — `TRUE`/`FALSE` (channel narrow)
- `channel_width` — float

### UT Bot Alert (`utbot_{TF}`) — YOUR TREND FILTER
- `closed_signal` — `BUY`, `SELL`, `NONE` (one-bar flash on crossover)
- `closed_bias` — `BULLISH`, `BEARISH` (persists between crossovers)
- `consecutive_bull_bars` — int (how many bars in a row bullish)
- `consecutive_bear_bars` — int (how many bars in a row bearish)

### EMA (`ema{9,21,50,200}_{TF}`)
- `closed_price_vs_ema` — `ABOVE`, `BELOW`
- `ema_slope` — `RISING`, `FALLING`, `FLAT`

### RSI (`rsi{14,2}_{TF}`)
- `closed_rsi` — 0-100 float
- `closed_zone` — RSI14: `OVERBOUGHT`, `NEUTRAL`, `OVERSOLD` | RSI2: `EXTREME_OB` (>95), `EXTREME_OS` (<5)
- `closed_cross` — `CROSS_UP_30`, `CROSS_DOWN_70`, `CROSS_UP_50`, `CROSS_DOWN_50`, `NONE`

### ADX (`adx14_{TF}`)
- `closed_trend_strength` — `RANGING`, `WEAK_TREND`, `TRENDING`, `STRONG_TREND`
- `closed_di_bias` — `BULLISH`, `BEARISH`

### VWAP (`vwap_{TF}`)
- `closed_price_vs_vwap` — `ABOVE`, `BELOW`

### Bollinger Bands (`bb20d2_{TF}`)
- `closed_reenter_from_below` — `TRUE`/`FALSE`
- `closed_reenter_from_above` — `TRUE`/`FALSE`
- `bb_squeeze` — `TRUE`/`FALSE`

### Stochastic (`stoch5_3_3_{TF}`)
- `closed_cross` — `BULLISH_OS`, `BEARISH_OB`, `BULLISH`, `BEARISH`, `NONE`
- `closed_zone` — `OVERBOUGHT`, `NEUTRAL`, `OVERSOLD`

### MACD (`macd12_26_9_{TF}`)
- `closed_hist_cross` — `BULLISH_FLIP`, `BEARISH_FLIP`, `NONE`
- `closed_zero_cross` — `CROSS_ABOVE`, `CROSS_BELOW`, `NONE`

---

## Strategy Ideas to Explore

Be **creative**. Mix and match indicators in unexpected ways. Here are starting points but invent your own too:

### Category 1: Candle Pattern + DC Band Rejection
- **Hammer at DC lower band** — M1/M3 hammer candle + DC M5/M15 lower zone + UT Bot M15 bullish
- **Shooting star at DC upper band** — M1/M3 shooting star + DC M5/M15 upper zone + UT Bot M15 bearish
- **Doji at DC extremes** — M3 doji + DC M5 in UPPER/LOWER + mean reversion entry
- **Marubozu breakout** — M1 marubozu (strong momentum) + DC M5 breakout + UT Bot aligned

### Category 2: Wick Analysis
- **Long lower wick rejection** — M1/M3 `has_long_lower == TRUE` + DC lower zone + trend filter
- **Long upper wick rejection** — M1/M3 `has_long_upper == TRUE` + DC upper zone + trend filter
- **Wick ratio extremes** — `lower_wick_ratio >= 3` (very long wick relative to body) at key levels
- **Wick + VWAP proximity** — long wick candle near VWAP level (mean reversion)

### Category 3: Multi-TF Candle Confluence
- **M1 hammer + M3 hammer** — both timeframes showing rejection simultaneously
- **M3 candle + M15 DC zone** — small TF pattern at large TF structure
- **M1 pattern + M5 UT Bot signal** — candle confirmation of trend change

### Category 4: Candle + Oscillator
- **Hammer + RSI2 extreme OS** — double mean reversion signal
- **Shooting star + RSI2 extreme OB** — overbought exhaustion
- **Doji + Stoch cross** — indecision confirmed by momentum flip
- **Marubozu + MACD flip** — momentum candle + MACD histogram confirmation

### Category 5: Wick + Volatility
- **Long wick in BB squeeze** — rejection during low volatility (pre-breakout)
- **Wick rejection + ATR expanding** — rejection in volatile conditions (stronger signal)
- **DC wick rej + compressed channel** — rejection when channel is tight (breakout setup)

### Category 6: Creative Combos (INVENT YOUR OWN)
- Try things nobody would think of
- Combine 3+ indicators in novel ways
- Test both BUY and SELL sides
- Try different SL values: 3.0, 4.0, 5.0, 7.5
- Try different reward ratios: 0.8, 1.0, 1.2, 1.5, 2.0
- Try with and without VWAP filter
- Try with and without EMA200 filter

---

## Execution Plan

1. **Read the existing strategies** in `config-gold.yaml` to understand what already works (don't duplicate them)
2. **Create strategy configs one at a time** — write a `config-test-N.yaml` file
3. **Run the backtest**: `uv run python -m backtest --config config-test-N.yaml --data sampledata/XAUUSD_M1_60d.csv --balance 10000`
4. **Capture the stats** (PF, WR, trades, DD) from output
5. **If PF < 1.0**, the idea is bad — note it and move on
6. **If PF > 1.3 and trades > 15**, it's promising — try variations (tighter SL, different RR, add/remove filters)
7. **Log everything** in `codex-strategy-results.md`
8. **Repeat** — aim for at least **20-30 different strategy ideas** tested
9. **Clean up** — delete all `config-test-*.yaml` files when done

## Output Format for codex-strategy-results.md

```markdown
# Strategy Discovery Results — XAUUSD Scalping

## Summary Table

| # | Name | PF | WR% | Trades | DD% | SL | RR | Direction | Key Conditions |
|---|------|---:|----:|-------:|----:|---:|---:|-----------|----------------|
| 1 | ... | ... | ... | ... | ... | ... | ... | ... | ... |

## Top Performers (PF > 1.3)
(Detailed breakdown of each winning strategy with full YAML config)

## Interesting But Needs Work (PF 1.0-1.3)
(Ideas worth refining)

## Failed Ideas (PF < 1.0)
(Brief notes on what didn't work and why — useful to avoid repeating)

## Patterns Observed
(What worked across strategies? What combinations are consistently good/bad?)
```

---

## Rules

- **Backtest EVERY idea.** No theory-only strategies.
- **Be creative.** Don't just copy existing strategies with minor tweaks.
- **Focus on M1, M2, M3, M5 candle patterns** with M5/M15 DC structure and UT Bot trend filters.
- **Test both BUY and SELL sides** — this was a bearish 60-day period so SELL may dominate.
- **Vary SL/RR** — test at least 2 different SL values per promising idea.
- **Delete temporary config files** (`config-test-*.yaml`) when you're done.
- **Do NOT modify any existing code or config files.** Only create `codex-strategy-results.md` and temporary test configs.
- **Keep working until you've tested at least 20 ideas.** Do NOT stop early.
