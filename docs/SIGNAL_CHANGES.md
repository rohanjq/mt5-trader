# SignalMaster — New Signal Changes

These are the latest additions to SignalMaster. All existing signals remain unchanged.

---

## 1. NEW INDICATOR: Session VWAP (`vwap`)

Volume-Weighted Average Price, resetting daily at 00:00 server time.
Computed from M1 bars regardless of output timeframe.

**Formula:** `VWAP = Σ(typical_price × tick_volume) / Σ(tick_volume)` where `typical_price = (High + Low + Close) / 3`

**Config:** `INP_VWAP = "1, 5, 15"` (TF list — just the timeframe minutes, no extra params)

**Files produced:**
```
<SYMBOL>_vwap_M1.csv
<SYMBOL>_vwap_M5.csv
<SYMBOL>_vwap_M15.csv
```

**Fields:**
```
vwap                     → current session VWAP value (absolute price level)
running_price_vs_vwap    → ABOVE or BELOW (current bid vs VWAP)
running_dist_to_vwap     → bid - VWAP (positive = above, negative = below)
running_dist_pct         → distance as % of VWAP (e.g. 0.05 = 0.05% above VWAP)
closed_price_vs_vwap     → ABOVE or BELOW (last closed bar close vs VWAP)
closed_dist_to_vwap      → close - VWAP
session_m1_bars          → number of M1 bars since session start (session maturity indicator)
cum_volume               → cumulative tick volume since session start
```

**Signal name in trading system:** `vwap_M1`, `vwap_M5`, `vwap_M15`

**Expression examples:**
```yaml
# Price above VWAP (bullish intraday bias)
- vwap_M1.closed_price_vs_vwap == ABOVE

# Price at or near VWAP (pullback zone)
- vwap_M1.running_dist_pct < 0.02
- vwap_M1.running_dist_pct > -0.02

# Combine with trend: only buy above VWAP in uptrend
- ema50_M5.closed_price_vs_ema == ABOVE
- vwap_M1.closed_price_vs_vwap == ABOVE
```

**Notes:**
- VWAP is most reliable after ~30 M1 bars into the session (`session_m1_bars >= 30`)
- Early session VWAP is dominated by the first few bars and less meaningful
- VWAP is a **state** field (always has a value), not an event — ideal for use as a filter condition

---

## 2. ENRICHED: Bollinger Bands — Bandwidth & Squeeze Detection

Four new fields added to every existing BB CSV file. No existing fields changed.

**New fields:**
```
bb_bandwidth             → normalized bandwidth: (upper - lower) / middle × 100 (%)
bb_bandwidth_sma20       → 20-bar SMA of bb_bandwidth (average historical bandwidth)
bb_bandwidth_ratio       → bb_bandwidth / bb_bandwidth_sma20 (< 1 = tighter than average)
bb_squeeze               → TRUE if bb_bandwidth_ratio < 0.85 (Bollinger squeeze detected)
```

**Expression examples:**
```yaml
# Bollinger squeeze detected (expect breakout)
- bb_M1.bb_squeeze is TRUE

# Bandwidth expanding (volatility increasing)
- bb_M1.bb_bandwidth_ratio > 1.2

# Range fade only when NOT in a squeeze (avoid false mean reversion before breakout)
- bb_M1.bb_squeeze is_not TRUE
- bb_M1.closed_reenter_from_below is TRUE

# Compression-to-expansion breakout: squeeze was active, now expanding
- bb_M1.bb_bandwidth_ratio > 1.30
```

**What bb_bandwidth_ratio means:**
- `< 0.85` → squeeze (bands abnormally tight, breakout likely)
- `0.85 – 1.0` → below average width
- `1.0 – 1.2` → normal to slightly wide
- `> 1.2` → expanded (volatility surge)

---

## 3. ENRICHED: Donchian Channels — Width SMA & Compression Detection

Three new fields added to every existing DC CSV file. No existing fields changed.

**New fields:**
```
channel_width_sma20      → 20-bar SMA of channel_width (average historical channel width)
width_vs_sma_ratio       → channel_width / channel_width_sma20 (< 1 = narrower than average)
dc_compressed            → TRUE if width_vs_sma_ratio < 0.75 (channel compression/squeeze)
```

**Expression examples:**
```yaml
# DC compression detected (squeeze before breakout)
- dc_M1.dc_compressed is TRUE

# Compression-to-expansion breakout: was compressed, now breaking upper band
- dc_M1.width_vs_sma_ratio < 0.75
- dc_M1.closed_break_upper is TRUE
- adx_M5.closed_trend_strength in TRENDING,STRONG_TREND

# Only trade DC breakouts when channel was compressed (filter out noise breaks)
- dc_M1.dc_compressed is TRUE
- dc_M1.closed_break_upper is TRUE
- atr_M1.volatility_state in EXPANDING,ABOVE_AVG
- macd_M1.closed_histogram > 0
```

**What width_vs_sma_ratio means:**
- `< 0.75` → compressed (channel abnormally narrow, breakout imminent)
- `0.75 – 1.0` → below average width
- `1.0 – 1.2` → normal
- `> 1.2` → expanded range (trending or volatile)

---

## How These Work Together (Gold Strategy Examples)

These fields were added specifically to support XAUUSD gold scalping strategies from `deepresearch-gold.md`. Here's how they map:

### Session Impulse EMA ADX (trend strategy)
```yaml
# Needs: close > session VWAP
- vwap_M1.closed_price_vs_vwap == ABOVE
```

### VWAP Pullback Continuation
```yaml
# Needs: pullback into VWAP zone, then reclaim
- vwap_M1.running_dist_pct < 0.02   # near VWAP
- ema9_M1.closed_price_vs_ema == ABOVE  # reclaimed fast EMA
```

### Bollinger VWAP Range Fade
```yaml
# Needs: non-trending + BB re-entry + near VWAP
- adx_M5.closed_trend_strength == RANGING
- bb_M1.closed_reenter_from_below is TRUE
- vwap_M1.running_dist_pct < 0.03
```

### Compression to Expansion Donchian Breakout
```yaml
# Needs: DC compressed + BB squeezed + ATR expanding + breakout
- dc_M1.dc_compressed is TRUE
- bb_M1.bb_squeeze is TRUE
- atr_M1.volatility_state in EXPANDING,ABOVE_AVG
- dc_M1.closed_break_upper is TRUE
```

---

## Trading System Integration

### Signal sources to add in `config.yaml`:
```yaml
signals:
  sources:
    # ... existing sources ...
    - indicator: vwap
      timeframes: [M1, M5, M15]
```

The trading system's `GenericCSVSignal` reader will automatically pick up VWAP files — no code changes needed, just add the config entry above.

### File naming:
```
<SYMBOL>_vwap_<TF>.csv     →  e.g. BTCUSDT_vwap_M1.csv, XAUUSD_vwap_M1.csv
```

BB and DC files keep existing names — new fields are appended to the same CSV files.
