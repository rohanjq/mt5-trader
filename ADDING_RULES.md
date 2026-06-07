# How to Add a New Trigger Rule

This guide explains the data model, available signal fields, and how to create
a new trigger rule for the mt5-trader system.

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
| `closed_price_zone` | str | UPPER / UPPER_MID / MID / LOWER_MID / LOWER | Where price closed relative to the DC channel. |
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
