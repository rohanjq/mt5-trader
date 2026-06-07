# How to Add a New Trigger Rule

There are two ways to add rules:
1. **Expression rules** (recommended) — define in YAML, no Python needed
2. **Python rules** — full code control for complex logic

---

## Method 1: Expression Rules (YAML)

Add rules directly in `config.yaml` under `rules.expressions`. No code changes needed.
Just edit YAML, and the config hot-reloads (or restart the app).

### Expression Format

```
signal_name.field_name OPERATOR value
```

All conditions in a `buy:` or `sell:` block are ANDed (all must be true).

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equals (case-insensitive) | `utbot_M1.closed_signal == BUY` |
| `!=` | Not equals | `utbot_M1.closed_bias != NONE` |
| `>` | Greater than (numeric) | `utbot_M45.consecutive_bull_bars > 3` |
| `>=` | Greater or equal | `utbot_M45.consecutive_bull_bars >= 5` |
| `<` | Less than | `utbot_M1.closed_atr < 50` |
| `<=` | Less or equal | `dc_M15.channel_width <= 500` |
| `in` | Value is one of (comma-separated) | `dc_M15.closed_price_zone in LOWER,LOWER_MID` |
| `not_in` | Value is NOT one of | `dc_M15.closed_price_zone not_in MID` |
| `is` | Alias for `== TRUE` | `dc_M15.closed_lower_wick_rej is TRUE` |
| `is_not` | Alias for `!= TRUE` | `dc_M15.closed_upper_wick_rej is_not TRUE` |

### Example Rules

```yaml
rules:
  expressions:
    # Simple: UT Bot 1m signal + 15m trend
    - name: ut_trend_follow
      enabled: true
      priority: 140
      description: "UT 1m signal + 15m trend"
      buy:
        - utbot_M1.closed_signal == BUY
        - utbot_M15.closed_bias == BULLISH
      sell:
        - utbot_M1.closed_signal == SELL
        - utbot_M15.closed_bias == BEARISH

    # DC zone + UT Bot + trend strength
    - name: dc_zone_entry
      enabled: true
      priority: 105
      description: "DC zone + UT Bot signal + trend bars"
      buy:
        - dc_M15.closed_price_zone in LOWER,LOWER_MID
        - utbot_M1.closed_signal == BUY
        - utbot_M45.consecutive_bull_bars >= 5
      sell:
        - dc_M15.closed_price_zone in UPPER,UPPER_MID
        - utbot_M1.closed_signal == SELL
        - utbot_M45.consecutive_bear_bars >= 5

    # DC wick rejection (high quality)
    - name: dc_wick
      enabled: true
      priority: 115
      description: "DC wick rejection + UT Bot bias"
      buy:
        - dc_M15.closed_lower_wick_rej is TRUE
        - utbot_M3.closed_bias == BULLISH
      sell:
        - dc_M15.closed_upper_wick_rej is TRUE
        - utbot_M3.closed_bias == BEARISH

    # Full alignment (highest conviction)
    - name: full_align
      enabled: true
      priority: 90
      description: "All TFs + DC zone"
      buy:
        - utbot_M1.closed_signal == BUY
        - utbot_M15.closed_bias == BULLISH
        - utbot_M45.closed_bias == BULLISH
        - dc_M15.closed_price_zone in LOWER,LOWER_MID,MIDDLE
      sell:
        - utbot_M1.closed_signal == SELL
        - utbot_M15.closed_bias == BEARISH
        - utbot_M45.closed_bias == BEARISH
        - dc_M15.closed_price_zone in UPPER,UPPER_MID,MIDDLE

    # ATR volatility filter
    - name: ut_low_vol
      enabled: false
      priority: 160
      description: "UT signal only in low volatility"
      buy:
        - utbot_M1.closed_signal == BUY
        - utbot_M1.closed_atr < 40
      sell:
        - utbot_M1.closed_signal == SELL
        - utbot_M1.closed_atr < 40
```

### How to Add a New Expression Rule

1. Open `config.yaml`
2. Add a new entry under `rules.expressions:`
3. Set `name`, `enabled`, `priority`, `description`
4. Add `buy:` conditions (all must be true to trigger BUY)
5. Add `sell:` conditions (all must be true to trigger SELL)
6. **Optional**: Set `sl_dollars` and `reward_ratio` for per-rule risk/reward (overrides global defaults)
7. Save — the config hot-reloads (or restart)

That's it. No Python code needed.

### Per-Rule Risk/Reward

Each expression rule can override the global `trading.sl_dollars` and `trading.reward_ratio`:

```yaml
- name: "breakout_strategy"
  enabled: true
  priority: 50
  sl_dollars: 150.0     # wider stop for breakouts ($150 instead of default $100)
  reward_ratio: 1.8     # target 1.8R ($270 TP)
  description: "Breakout with wide stops"
  buy: [...]
  sell: [...]
```

If `sl_dollars` or `reward_ratio` are omitted, the global config values are used.

**Current per-rule settings:**

| Strategy | SL | RR | TP | Style |
|----------|----|----|-------|-------|
| `macd_stoch_reentry` | $120 | 1:1.5 | $180 | Continuation pullback |
| `ema_pullback` | $100 | 1:1.5 | $150 | Trend pullback |
| `bb_range_fade` | $75 | 1:1.0 | $75 | Mean reversion |
| `dc_vol_breakout` | $150 | 1:1.8 | $270 | Breakout |
| LG rules | $100 | 1:1.25 | $125 | Smart money |
| Original UT/DC rules | (global) | (global) | (global) | Default |

---

## Method 2: Python Rules (for complex logic)

## Signal Data Available to Rules

Rules receive a `dict[str, Signal]` where keys are signal names like `utbot_M1`,
`dc_M15`, etc. Each `Signal.metadata` contains ALL CSV key-value pairs from the
SignalMaster EA.

### UT Bot Signal Fields (`utbot_{TF}`)

Available timeframes: M1, M3, M10, M15, M45 (configured in `config.yaml`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_bias` | str | BULLISH / BEARISH / NONE | Persistent trend direction. Stays until UT Bot crosses. |
| `closed_signal` | str | BUY / SELL / NONE | **One-bar flash** — fires on the crossover bar, then goes back to NONE. This is the actual entry trigger. |
| `closed_atr` | float | e.g. 31.2 | ATR value at bar close. Useful for volatility-based decisions. |
| `closed_trail_stop` | float | e.g. 62300.5 | UT Bot trailing stop level. |
| `consecutive_bull_bars` | int | e.g. 10 | Number of consecutive bullish-bias bars. Resets on bias flip. Good for trend strength. |
| `consecutive_bear_bars` | int | e.g. 5 | Number of consecutive bearish-bias bars. |
| `running_bias` | str | BULLISH / BEARISH / NONE | Current unconfirmed bar's bias. Changes in real-time. |
| `running_signal` | str | BUY / SELL / NONE | Current unconfirmed bar's signal. Not reliable — use `closed_*`. |
| `running_atr` | float | | Current bar ATR (live). |

**Key insight**: `closed_signal` fires ONCE per crossover event. It is the correct field
for entry triggers. `closed_bias` persists and is good for trend confirmation on higher TFs.

### Donchian Channel Fields (`dc_{TF}`)

Available timeframes: M1, M3, M5, M15, M45 (configured in `config.yaml`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_price_zone` | str | UPPER / UPPER_MID / MIDDLE / LOWER_MID / LOWER | Where price closed relative to the DC channel. |
| `closed_upper_wick_rej` | str | TRUE / FALSE | Candle wicked into the upper band and was rejected. Bearish signal. |
| `closed_lower_wick_rej` | str | TRUE / FALSE | Candle wicked into the lower band and was rejected. Bullish signal. |
| `upper_band` | float | e.g. 62382.0 | Upper Donchian channel boundary. |
| `lower_band` | float | e.g. 61264.8 | Lower Donchian channel boundary. |
| `channel_width` | float | | upper_band - lower_band. Can be used for volatility/squeeze detection. |
| `running_price_zone` | str | Same as closed | Current bar's zone (unconfirmed). |
| `running_upper_wick_rej` | str | TRUE / FALSE | Current bar wick rejection (unconfirmed). |
| `running_lower_wick_rej` | str | TRUE / FALSE | Current bar wick rejection (unconfirmed). |

**Key insight**: Wick rejections are one-bar events (like `closed_signal`). The zone
is persistent and good for bias/context.

### Liquidity Grab Fields (`liqgrab_{TF}`)

Available timeframes: M3, M5, M15, H1, H4 (configured in `config.yaml`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `liq_signal` | str | BUY / SELL / NONE | **Composite signal** — fires when rejection + breakout + MA trend all align. High quality. |
| `rejection_up` | str | TRUE / FALSE | Bullish liquidity grab — lower wick swept below key support and closed above. |
| `rejection_down` | str | TRUE / FALSE | Bearish liquidity grab — upper wick swept above key resistance and closed below. |
| `rejection_up_bar` | int | -1 if none | How many bars ago the bullish rejection occurred. |
| `rejection_down_bar` | int | -1 if none | How many bars ago the bearish rejection occurred. |
| `breakout_up` | str | TRUE / FALSE | Price broke above a recent key high (bullish breakout after grab). |
| `breakout_down` | str | TRUE / FALSE | Price broke below a recent key low (bearish breakout after grab). |
| `key_high` | float / NONE | Identified resistance level. |
| `key_low` | float / NONE | Identified support level. |
| `dist_to_key_high` | float | Distance from current high to key_high (negative = below). |
| `dist_to_key_low` | float | Distance from current low to key_low (positive = above). |
| `ma_value` | float | SMA value (trend filter). |
| `ma_trend` | str | ABOVE / BELOW | Price relative to MA — ABOVE = bullish, BELOW = bearish. |

**How it works** (Smart Money Concepts):
1. Find key level (highest high / lowest low with confirmed rejection)
2. Detect liquidity grab: wick sweeps past key level, body closes on the other side (wick ≥ 2x body)
3. Wait for breakout: price then breaks through the opposite key level
4. Filter by trend: price must be on the right side of MA (above for buy, below for sell)
5. All 3 met → `liq_signal` fires

**Key insight**: `liq_signal` is already a multi-condition composite — using it alone is valid.
The sub-components (`rejection_up`, `breakout_up`, `ma_trend`) are available for custom combos.

### EMA Fields (`ema{period}_{TF}`)

Signal names include the period: `ema9_M1`, `ema21_M1`, `ema50_M5`, `ema200_M15`, etc.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_price_vs_ema` | str | ABOVE / BELOW | Price position relative to EMA. |
| `ema_slope` | str | RISING / FALLING / FLAT | EMA direction over last 3 bars. |
| `running_dist_pct` | float | | Distance from price to EMA as % (near 0 = at EMA). |

### RSI Fields (`rsi{period}_{TF}`)

Signal names include the period: `rsi14_M1`, `rsi2_M1`, `rsi14_M3`, etc.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_rsi` | float | 0-100 | RSI value. |
| `closed_zone` | str | EXTREME_OB / OVERBOUGHT / BULLISH / NEUTRAL / BEARISH / OVERSOLD / EXTREME_OS | RSI zone classification. |
| `closed_cross` | str | CROSS_UP_30 / CROSS_DOWN_70 / CROSS_UP_50 / CROSS_DOWN_50 / CROSS_UP_52 / NONE | Level cross event on closed bar. |

### Bollinger Bands Fields (`bb_{TF}`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_pct_in_band` | float | 0-100 | Where price sits within bands (0=lower, 100=upper). |
| `closed_reenter_from_below` | str | TRUE / FALSE | Bar opened below lower band, closed above it (bullish reversal). |
| `closed_reenter_from_above` | str | TRUE / FALSE | Bar opened above upper band, closed below it (bearish reversal). |
| `band_width` | float | | Band width (squeeze detection: shrinking = breakout likely). |

### ADX Fields (`adx_{TF}`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_trend_strength` | str | RANGING / WEAK_TREND / TRENDING / STRONG_TREND | Trend regime classification. |
| `closed_adx_rising` | str | TRUE / FALSE | ADX increasing over last 3 bars (trend strengthening). |
| `closed_di_bias` | str | BULLISH / BEARISH | +DI vs -DI directional bias. |

### MACD Fields (`macd_{TF}`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_hist_cross` | str | BULLISH_FLIP / BEARISH_FLIP / NONE | Histogram sign change (classic signal). |
| `closed_zero_cross` | str | CROSS_ABOVE / CROSS_BELOW / NONE | MACD line zero-line cross. |
| `closed_histogram` | float | | Raw histogram value (> 0 = bullish momentum). |

### Stochastic Fields (`stoch_{TF}`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `closed_cross` | str | BULLISH_OS / BULLISH / BEARISH_OB / BEARISH / NONE | K/D cross event. `BULLISH_OS` = strongest buy (K crosses D in oversold). |
| `closed_zone` | str | OVERBOUGHT / OVERSOLD / NEUTRAL | Stochastic zone. |

### Standalone ATR Fields (`atr_{TF}`)

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `volatility_state` | str | EXPANDING / ABOVE_AVG / BELOW_AVG / CONTRACTING | Volatility regime (ATR vs its 20-bar SMA). |
| `running_atr` | float | | Current ATR value. |
| `atr_vs_sma_ratio` | float | | ATR / SMA20(ATR). >1 = above average volatility. |

---

## Creating a New Rule

### Step 1: Create a File

Create `rules/my_rule.py`. The file is auto-discovered at startup.

### Step 2: Implement the Class

```python
from __future__ import annotations

import logging
from core.models import Signal
from rules.base import BaseRule, TriggerAction, TriggerResult

log = logging.getLogger(__name__)


class MyRule(BaseRule):
    """Description of what this rule does."""

    name = "my_rule"                    # unique name, used in config and events
    description = "Short description"   # shown in dashboard
    priority = 150                      # lower = evaluated first (100-200 range)

    def evaluate(self, signals: dict[str, Signal]) -> TriggerResult:
        # Check if enabled in config (default False = opt-in)
        if not self.config.get("rules.my_rule.enabled", False):
            self._last_result = TriggerResult()
            return self._last_result

        # Read signal metadata using helpers
        # self._val(signals, "utbot_M1", "closed_signal")  → "BUY" / "SELL" / "NONE"
        # self._is_true(signals, "dc_M15", "closed_lower_wick_rej")  → True/False
        # self._int_val(signals, "utbot_M45", "consecutive_bull_bars")  → int
        # self._get(signals, "utbot_M1")  → full metadata dict

        ut_signal = self._val(signals, "utbot_M1", "closed_signal").upper()
        ut15_bias = self._val(signals, "utbot_M15", "closed_bias").upper()

        # BUY logic
        if ut_signal == "BUY" and ut15_bias == "BULLISH":
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_BUY,
                reason=f"UT M1 BUY + M15 BULLISH",
                rule_name=self.name,
            )
            return self._last_result

        # SELL logic (always implement the inverse)
        if ut_signal == "SELL" and ut15_bias == "BEARISH":
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_SELL,
                reason=f"UT M1 SELL + M15 BEARISH",
                rule_name=self.name,
            )
            return self._last_result

        # No action
        self._last_result = TriggerResult(rule_name=self.name)
        return self._last_result
```

### Step 3: Add Config

In `config.yaml` under `rules:`:

```yaml
rules:
  my_rule:
    enabled: true
    # any custom parameters your rule reads via self.config.get("rules.my_rule.xxx")
```

### Step 4: Add Signal Sources (if needed)

If your rule needs a timeframe not already configured, add it:

```yaml
signals:
  sources:
    - indicator: utbot
      timeframes: [M1, M3, M15, M45]  # add M10 here if needed
```

### No Other Changes Needed

The rule will be auto-discovered, instantiated, and evaluated in priority order.
It will show up in the dashboard rules panel automatically.

---

## Helper Methods on BaseRule

| Method | Returns | Description |
|--------|---------|-------------|
| `self._get(signals, "utbot_M1")` | `dict` | Full metadata dict for a signal source. Empty dict if not available. |
| `self._val(signals, "utbot_M1", "closed_signal")` | `str` | Single metadata value. Returns `""` if missing. |
| `self._is_true(signals, "dc_M15", "closed_lower_wick_rej")` | `bool` | True if value is "TRUE" (case-insensitive). |
| `self._int_val(signals, "utbot_M45", "consecutive_bull_bars")` | `int` | Integer value. Returns default (0) on parse failure. |
| `self.config.get("rules.my_rule.param", default)` | `any` | Read config value (hot-reloaded). |

---

## Rule Design Guidelines

1. **Always use `closed_*` fields** for confirmed signals. `running_*` fields change mid-bar.
2. **Always implement both BUY and SELL** — inverse logic.
3. **Always gate with `self.config.get("rules.xxx.enabled", False)`** so it can be toggled.
4. **Set `self._last_result`** — the dashboard reads it to show rule state.
5. **Priority matters** — lower numbers are evaluated first. Range: 100 (highest conviction) to 200 (lowest).
6. **First trigger wins** — if dc_confluence (pri 100) fires, utbot_simple (pri 200) is skipped.

## Ideas for New Rules

- **DC squeeze breakout**: Channel width narrows below threshold → wait for UT Bot signal to catch expansion
- **Multi-indicator alignment**: DC zone + UT Bot signal + UT Bot higher-TF trend + ATR filter
- **ATR-based**: Only trade when ATR is above/below a threshold (volatility filter as a rule)
- **Consecutive bars threshold**: UT Bot bias has been consistent for N bars → enter on signal
- **Counter-trend with wick**: DC wick rejection on M45 (rare, high-quality) + any UT Bot confirmation

## Numeric Values for Rule Design

These are typical ranges observed in live trading on BTCUSDT:

| Metric | M1 | M3 | M15 | M45 |
|--------|----|----|-----|-----|
| ATR typical | 25-60 | 50-100 | 150-300 | 300-500 |
| Consecutive bars (trend) | 0-15 | 0-10 | 0-40 | 0-40 |
| UT Bot signal frequency | ~every few minutes | ~every 5-15 min | ~every 30-60 min | ~every few hours |
| DC wick rejection | frequent | moderate | uncommon | rare (high quality) |

**SL/TP reference**: Currently SL=$100, TP=$125. Breakeven at $50 from entry.
On M1, $50 ≈ 1-2x ATR. On M15, $100 ≈ 0.5x ATR.
