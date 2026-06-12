"""Vectorised indicator computation from OHLC data using pandas_ta.

Computes all indicators needed by mt5-trader expression rules:
  utbot, dc, ema{9,21,50,200}, rsi{14,2}, adx14, macd12_26_9,
  stoch5_3_3, bb20d2, atr14, vwap, candle

Each compute_* function returns a DataFrame with the same index as input,
containing all fields that the EA would write to CSV.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pandas_ta as ta

log = logging.getLogger(__name__)


# ── UT Bot ─────────────────────────────────────────────────────────────────────

def compute_utbot(df: pd.DataFrame, atr_period: int = 10, key_value: float = 2.0) -> pd.DataFrame:
    """Compute UT Bot Alert indicator (matches SignalMaster EA exactly).

    The UT Bot uses ATR trailing stop. When close crosses above the trail stop,
    bias flips to BULLISH and a BUY signal fires (one bar). Vice versa for SELL.

    The trail stop only ratchets (holds previous level) when the previous
    direction matches the current one.  On a direction *flip* the trail resets
    to ``close ± nLoss`` without clamping — this matches the EA behaviour and
    prevents excessive whipsaws near the trail boundary.

    Parameters:
        atr_period: ATR period (default 10 to match SignalMaster EA)
        key_value: ATR multiplier for trail stop distance (default 2.0)
    """
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(close)

    # Compute ATR
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=atr_period)
    atr_vals = atr_series.fillna(0).values
    nloss = key_value * atr_vals

    # Trailing stop + direction (matches EA: direction[i] = +1 bull, -1 bear)
    trail_stop = np.zeros(n)
    direction = np.ones(n)  # default BULLISH

    # Initialise first atr_period bars to close / direction +1 (EA convention)
    for i in range(min(atr_period, n)):
        trail_stop[i] = close[i]
        direction[i] = 1.0

    for i in range(atr_period, n):
        prev_stop = trail_stop[i - 1]
        prev_dir = direction[i - 1]

        if close[i] > prev_stop:
            trail_stop[i] = close[i] - nloss[i]
            # Ratchet up ONLY if previous direction was already bullish
            if prev_dir > 0:
                trail_stop[i] = max(trail_stop[i], prev_stop)
            direction[i] = 1.0
        else:
            trail_stop[i] = close[i] + nloss[i]
            # Ratchet down ONLY if previous direction was already bearish
            if prev_dir < 0:
                trail_stop[i] = min(trail_stop[i], prev_stop)
            direction[i] = -1.0

    # Bias: above trail = BULLISH, below = BEARISH
    bias = np.where(direction > 0, "BULLISH", "BEARISH")

    # Signal: fires on bias change
    signal = np.full(n, "NONE", dtype=object)
    for i in range(1, n):
        if direction[i] > 0 and direction[i - 1] < 0:
            signal[i] = "BUY"
        elif direction[i] < 0 and direction[i - 1] > 0:
            signal[i] = "SELL"

    # Consecutive bars — per-bar closed count
    closed_consec_bull = np.zeros(n, dtype=int)
    closed_consec_bear = np.zeros(n, dtype=int)
    for i in range(1, n):
        if direction[i] > 0:
            closed_consec_bull[i] = closed_consec_bull[i - 1] + 1
            closed_consec_bear[i] = 0
        else:
            closed_consec_bear[i] = closed_consec_bear[i - 1] + 1
            closed_consec_bull[i] = 0

    # The EA counts from the running bar backward, so its count = closed_count + 1
    # when the running bar continues the same direction.  At bar close the running
    # bar has just opened at approximately the same price, so it will share the
    # same direction as the closed bar in nearly all cases.  Add +1 to match.
    consec_bull = np.where(closed_consec_bull > 0, closed_consec_bull + 1, 0)
    consec_bear = np.where(closed_consec_bear > 0, closed_consec_bear + 1, 0)

    result = pd.DataFrame(index=df.index)
    result["closed_bias"] = bias
    result["closed_signal"] = signal
    result["closed_atr"] = atr_vals
    result["closed_trail_stop"] = trail_stop
    result["consecutive_bull_bars"] = consec_bull
    result["consecutive_bear_bars"] = consec_bear
    # running_* = same as closed_* in backtest (we only see closed bars)
    result["running_bias"] = bias
    result["running_signal"] = signal
    result["running_atr"] = atr_vals
    return result


# ── Candle Pattern (comprehensive candle analysis) ─────────────────────────────

def compute_candle(df: pd.DataFrame) -> pd.DataFrame:
    """Compute comprehensive candle analysis fields.

    Matches SignalMaster EA WriteCandleBarFields exactly.

    Size fields (price units):
        body_size, upper_wick_size, lower_wick_size, total_range

    Percentage fields (% of total range):
        body_pct, upper_wick_pct, lower_wick_pct

    Ratio fields (wick / body):
        upper_wick_ratio, lower_wick_ratio

    Direction & type:
        candle_dir: UP / DOWN / DOJI
        candle_type: MARUBOZU / HAMMER / SHOOTING_STAR / DOJI / SPINNING_TOP / NORMAL

    Boolean flags:
        has_long_upper: upper_wick >= 2x body
        has_long_lower: lower_wick >= 2x body
        is_bullish: close > open
        is_bearish: close < open
    """
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values

    body_top = np.maximum(o, c)
    body_bottom = np.minimum(o, c)
    body_size = body_top - body_bottom
    upper_wick = h - body_top
    lower_wick = body_bottom - l
    total_range = h - l

    # Safe divisors — use _Point=0.01 for XAUUSD to match EA
    # The EA uses _Point (smallest price increment) as its epsilon,
    # which is 0.01 for XAUUSD.  Using 1e-10 caused classification
    # differences for candles with very small bodies.
    point = 0.01
    range_safe = np.where(total_range > point, total_range, point)
    body_safe = np.where(body_size > point, body_size, point)

    # Percentages
    body_pct = np.round(body_size / range_safe * 100, 1)
    upper_wick_pct = np.round(upper_wick / range_safe * 100, 1)
    lower_wick_pct = np.round(lower_wick / range_safe * 100, 1)

    # Ratios (wick / body) — 0 if doji
    has_body = body_size > point
    upper_wick_ratio = np.where(has_body, np.round(upper_wick / body_safe, 2), 0.0)
    lower_wick_ratio = np.where(has_body, np.round(lower_wick / body_safe, 2), 0.0)

    # Direction
    candle_dir = np.where(c > o, "UP", np.where(c < o, "DOWN", "DOJI"))

    # Boolean flags
    has_range = total_range > point
    has_long_upper = np.where((upper_wick >= 2.0 * body_safe) & has_range, "TRUE", "FALSE")
    has_long_lower = np.where((lower_wick >= 2.0 * body_safe) & has_range, "TRUE", "FALSE")
    is_bullish = np.where(c > o, "TRUE", "FALSE")
    is_bearish = np.where(c < o, "TRUE", "FALSE")

    # Candle type classification (matches EA logic exactly)
    candle_type = np.full(len(c), "NORMAL", dtype=object)
    # DOJI: no range or body < 10% of range
    candle_type = np.where(~has_range, "DOJI", candle_type)
    candle_type = np.where(has_range & (body_pct < 10.0), "DOJI", candle_type)
    # MARUBOZU: body > 80% of range
    candle_type = np.where(has_range & (body_pct >= 80.0), "MARUBOZU", candle_type)
    # HAMMER: lower_wick >= 2x body AND upper_wick < body
    is_hammer = has_range & (body_pct >= 10.0) & (body_pct < 80.0) & \
                (lower_wick >= 2.0 * body_safe) & (upper_wick < body_safe)
    candle_type = np.where(is_hammer, "HAMMER", candle_type)
    # SHOOTING_STAR: upper_wick >= 2x body AND lower_wick < body
    is_shooting = has_range & (body_pct >= 10.0) & (body_pct < 80.0) & \
                  (upper_wick >= 2.0 * body_safe) & (lower_wick < body_safe)
    candle_type = np.where(is_shooting, "SHOOTING_STAR", candle_type)
    # SPINNING_TOP: body 10-40%, both wicks > 0.5x body
    is_spinning = has_range & (body_pct >= 10.0) & (body_pct < 40.0) & \
                  (upper_wick > 0.5 * body_safe) & (lower_wick > 0.5 * body_safe) & \
                  ~is_hammer & ~is_shooting
    candle_type = np.where(is_spinning, "SPINNING_TOP", candle_type)

    result = pd.DataFrame(index=df.index)

    # Closed fields
    result["closed_body_size"] = np.round(body_size, 5)
    result["closed_upper_wick_size"] = np.round(upper_wick, 5)
    result["closed_lower_wick_size"] = np.round(lower_wick, 5)
    result["closed_total_range"] = np.round(total_range, 5)
    result["closed_body_pct"] = body_pct
    result["closed_upper_wick_pct"] = upper_wick_pct
    result["closed_lower_wick_pct"] = lower_wick_pct
    result["closed_upper_wick_ratio"] = upper_wick_ratio
    result["closed_lower_wick_ratio"] = lower_wick_ratio
    result["closed_candle_dir"] = candle_dir
    result["closed_candle_type"] = candle_type
    result["closed_has_long_upper"] = has_long_upper
    result["closed_has_long_lower"] = has_long_lower
    result["closed_is_bullish"] = is_bullish
    result["closed_is_bearish"] = is_bearish

    # Running fields (same as closed in backtester — we only see closed bars)
    result["running_body_size"] = result["closed_body_size"]
    result["running_upper_wick_size"] = result["closed_upper_wick_size"]
    result["running_lower_wick_size"] = result["closed_lower_wick_size"]
    result["running_total_range"] = result["closed_total_range"]
    result["running_body_pct"] = result["closed_body_pct"]
    result["running_upper_wick_pct"] = result["closed_upper_wick_pct"]
    result["running_lower_wick_pct"] = result["closed_lower_wick_pct"]
    result["running_upper_wick_ratio"] = result["closed_upper_wick_ratio"]
    result["running_lower_wick_ratio"] = result["closed_lower_wick_ratio"]
    result["running_candle_dir"] = result["closed_candle_dir"]
    result["running_candle_type"] = result["closed_candle_type"]
    result["running_has_long_upper"] = result["closed_has_long_upper"]
    result["running_has_long_lower"] = result["closed_has_long_lower"]
    result["running_is_bullish"] = result["closed_is_bullish"]
    result["running_is_bearish"] = result["closed_is_bearish"]

    return result


# ── Donchian Channel ───────────────────────────────────────────────────────────

def compute_dc(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Compute Donchian Channel indicator.

    Zones: UPPER, UPPER_MID, MIDDLE, LOWER_MID, LOWER based on position
    within the channel (5 equal zones).
    """
    dc = ta.donchian(df["high"], df["low"], lower_length=period, upper_length=period)
    if dc is None or dc.empty:
        return _empty_dc(df)

    upper_col = [c for c in dc.columns if "upper" in c.lower() or "DCU" in c]
    lower_col = [c for c in dc.columns if "lower" in c.lower() or "DCL" in c]
    mid_col = [c for c in dc.columns if "mid" in c.lower() or "DCM" in c]

    if not upper_col or not lower_col:
        return _empty_dc(df)

    upper = dc[upper_col[0]].values
    lower = dc[lower_col[0]].values
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    width = upper - lower

    # Price zone (5 zones) — EA uses 90/70/30/10 pct thresholds
    zones = []
    for i in range(len(close)):
        if width[i] == 0:
            zones.append("MIDDLE")
            continue
        pct = (close[i] - lower[i]) / width[i] * 100.0
        if pct >= 90:
            zones.append("UPPER")
        elif pct >= 70:
            zones.append("UPPER_MID")
        elif pct <= 10:
            zones.append("LOWER")
        elif pct <= 30:
            zones.append("LOWER_MID")
        else:
            zones.append("MIDDLE")

    # Wick rejections — EA requires wick > body AND touch AND close inside
    upper_rej = []
    lower_rej = []
    for i in range(len(close)):
        body_top_i = max(df["open"].iloc[i], close[i])
        body_bottom_i = min(df["open"].iloc[i], close[i])
        upper_wick_i = high[i] - body_top_i
        lower_wick_i = body_bottom_i - low[i]
        body_size_i = body_top_i - body_bottom_i
        upper_rej.append("TRUE" if high[i] >= upper[i] and upper_wick_i > body_size_i and close[i] < upper[i] else "FALSE")
        lower_rej.append("TRUE" if low[i] <= lower[i] and lower_wick_i > body_size_i and close[i] > lower[i] else "FALSE")

    # DC compressed: channel width is below its 20-bar average
    width_sma = pd.Series(width).rolling(20).mean().values
    dc_compressed = np.where(width < width_sma, "TRUE", "FALSE")

    result = pd.DataFrame(index=df.index)
    result["closed_price_zone"] = zones
    result["closed_upper_wick_rej"] = upper_rej
    result["closed_lower_wick_rej"] = lower_rej
    result["upper_band"] = upper
    result["lower_band"] = lower
    result["channel_width"] = width
    result["dc_compressed"] = dc_compressed
    result["running_price_zone"] = zones
    result["running_upper_wick_rej"] = upper_rej
    result["running_lower_wick_rej"] = lower_rej
    return result


def _empty_dc(df: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)
    for col in ["closed_price_zone", "closed_upper_wick_rej", "closed_lower_wick_rej",
                "upper_band", "lower_band", "channel_width", "dc_compressed",
                "running_price_zone", "running_upper_wick_rej", "running_lower_wick_rej"]:
        result[col] = ""
    return result


# ── EMA ────────────────────────────────────────────────────────────────────────

def compute_ema(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Compute EMA indicator fields: price_vs_ema, slope, dist_pct."""
    ema = ta.ema(df["close"], length=period)
    if ema is None:
        ema = pd.Series(np.nan, index=df.index)

    close = df["close"].values
    ema_vals = ema.values

    # Price vs EMA
    vs_ema = np.where(close > ema_vals, "ABOVE", "BELOW")

    # Slope: compare EMA[i] to EMA[i-3]
    slope = np.full(len(close), "FLAT", dtype=object)
    for i in range(3, len(close)):
        diff = ema_vals[i] - ema_vals[i - 3]
        if diff > 0:
            slope[i] = "RISING"
        elif diff < 0:
            slope[i] = "FALLING"

    # Distance percentage
    dist_pct = np.where(ema_vals != 0, ((close - ema_vals) / ema_vals) * 100, 0.0)

    result = pd.DataFrame(index=df.index)
    result["closed_price_vs_ema"] = vs_ema
    result["ema_slope"] = slope
    result["running_dist_pct"] = dist_pct
    return result


# ── RSI ────────────────────────────────────────────────────────────────────────

def compute_rsi(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Compute RSI indicator fields: rsi value, zone, cross events."""
    rsi = ta.rsi(df["close"], length=period)
    if rsi is None:
        rsi = pd.Series(50.0, index=df.index)
    rsi_vals = rsi.fillna(50.0).values

    # Zone classification
    zones = []
    for v in rsi_vals:
        if v >= 90:
            zones.append("EXTREME_OB")
        elif v >= 70:
            zones.append("OVERBOUGHT")
        elif v >= 60:
            zones.append("BULLISH")
        elif v >= 40:
            zones.append("NEUTRAL")
        elif v >= 30:
            zones.append("BEARISH")
        elif v >= 10:
            zones.append("OVERSOLD")
        else:
            zones.append("EXTREME_OS")

    # For RSI2 specifically: extreme zones at 5/95
    if period <= 2:
        zones = []
        for v in rsi_vals:
            if v >= 95:
                zones.append("EXTREME_OB")
            elif v >= 70:
                zones.append("OVERBOUGHT")
            elif v >= 60:
                zones.append("BULLISH")
            elif v >= 40:
                zones.append("NEUTRAL")
            elif v >= 30:
                zones.append("BEARISH")
            elif v >= 5:
                zones.append("OVERSOLD")
            else:
                zones.append("EXTREME_OS")

    # Cross events
    crosses = np.full(len(rsi_vals), "NONE", dtype=object)
    for i in range(1, len(rsi_vals)):
        prev, curr = rsi_vals[i - 1], rsi_vals[i]
        if prev < 30 and curr >= 30:
            crosses[i] = "CROSS_UP_30"
        elif prev > 70 and curr <= 70:
            crosses[i] = "CROSS_DOWN_70"
        elif prev < 50 and curr >= 50:
            crosses[i] = "CROSS_UP_50"
        elif prev > 50 and curr <= 50:
            crosses[i] = "CROSS_DOWN_50"
        elif prev < 52 and curr >= 52:
            crosses[i] = "CROSS_UP_52"

    result = pd.DataFrame(index=df.index)
    result["closed_rsi"] = rsi_vals
    result["closed_zone"] = zones
    result["closed_cross"] = crosses
    return result


# ── ADX ────────────────────────────────────────────────────────────────────────

def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Compute ADX indicator fields: trend strength, rising, DI bias."""
    adx_df = ta.adx(df["high"], df["low"], df["close"], length=period)
    if adx_df is None or adx_df.empty:
        result = pd.DataFrame(index=df.index)
        result["closed_trend_strength"] = "RANGING"
        result["closed_adx_rising"] = "FALSE"
        result["closed_di_bias"] = "BULLISH"
        return result

    adx_col = [c for c in adx_df.columns if "ADX" in c and "DM" not in c]
    dmp_col = [c for c in adx_df.columns if "DMP" in c]
    dmn_col = [c for c in adx_df.columns if "DMN" in c]

    adx_vals = adx_df[adx_col[0]].fillna(0).values if adx_col else np.zeros(len(df))
    dmp_vals = adx_df[dmp_col[0]].fillna(0).values if dmp_col else np.zeros(len(df))
    dmn_vals = adx_df[dmn_col[0]].fillna(0).values if dmn_col else np.zeros(len(df))

    # Trend strength
    strength = []
    for v in adx_vals:
        if v >= 50:
            strength.append("STRONG_TREND")
        elif v >= 25:
            strength.append("TRENDING")
        elif v >= 20:
            strength.append("WEAK_TREND")
        else:
            strength.append("RANGING")

    # ADX rising (last 3 bars)
    rising = np.full(len(adx_vals), "FALSE", dtype=object)
    for i in range(3, len(adx_vals)):
        if adx_vals[i] > adx_vals[i - 3]:
            rising[i] = "TRUE"

    # DI bias
    di_bias = np.where(dmp_vals > dmn_vals, "BULLISH", "BEARISH")

    result = pd.DataFrame(index=df.index)
    result["closed_trend_strength"] = strength
    result["closed_adx_rising"] = rising
    result["closed_di_bias"] = di_bias
    return result


# ── MACD ───────────────────────────────────────────────────────────────────────

def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Compute MACD indicator fields: histogram cross, zero cross, histogram value."""
    macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    if macd_df is None or macd_df.empty:
        result = pd.DataFrame(index=df.index)
        result["closed_hist_cross"] = "NONE"
        result["closed_zero_cross"] = "NONE"
        result["closed_histogram"] = 0.0
        return result

    hist_col = [c for c in macd_df.columns if "h" in c.lower() or "MACDh" in c]
    macd_col = [c for c in macd_df.columns if c.startswith("MACD_") or c == "MACD"]

    histogram = macd_df[hist_col[0]].fillna(0).values if hist_col else np.zeros(len(df))
    macd_line = macd_df[macd_col[0]].fillna(0).values if macd_col else np.zeros(len(df))

    # Histogram cross (sign change)
    hist_cross = np.full(len(histogram), "NONE", dtype=object)
    for i in range(1, len(histogram)):
        if histogram[i - 1] <= 0 and histogram[i] > 0:
            hist_cross[i] = "BULLISH_FLIP"
        elif histogram[i - 1] >= 0 and histogram[i] < 0:
            hist_cross[i] = "BEARISH_FLIP"

    # Zero cross (MACD line crosses 0)
    zero_cross = np.full(len(macd_line), "NONE", dtype=object)
    for i in range(1, len(macd_line)):
        if macd_line[i - 1] <= 0 and macd_line[i] > 0:
            zero_cross[i] = "CROSS_ABOVE"
        elif macd_line[i - 1] >= 0 and macd_line[i] < 0:
            zero_cross[i] = "CROSS_BELOW"

    result = pd.DataFrame(index=df.index)
    result["closed_hist_cross"] = hist_cross
    result["closed_zero_cross"] = zero_cross
    result["closed_histogram"] = histogram
    return result


# ── Stochastic ─────────────────────────────────────────────────────────────────

def compute_stoch(df: pd.DataFrame, k: int = 5, d: int = 3, smooth_k: int = 3) -> pd.DataFrame:
    """Compute Stochastic indicator fields: cross events, zone."""
    stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=k, d=d, smooth_k=smooth_k)
    if stoch_df is None or stoch_df.empty:
        result = pd.DataFrame(index=df.index)
        result["closed_cross"] = "NONE"
        result["closed_zone"] = "NEUTRAL"
        return result

    k_col = [c for c in stoch_df.columns if "STOCHk" in c or "K" in c.upper()]
    d_col = [c for c in stoch_df.columns if "STOCHd" in c or "D" in c.upper()]

    k_vals = stoch_df[k_col[0]].fillna(50).values if k_col else np.full(len(df), 50.0)
    d_vals = stoch_df[d_col[0]].fillna(50).values if d_col else np.full(len(df), 50.0)

    # Zone
    zones = []
    for v in k_vals:
        if v >= 80:
            zones.append("OVERBOUGHT")
        elif v <= 20:
            zones.append("OVERSOLD")
        else:
            zones.append("NEUTRAL")

    # Cross events: K crosses D
    crosses = np.full(len(k_vals), "NONE", dtype=object)
    for i in range(1, len(k_vals)):
        k_prev, k_curr = k_vals[i - 1], k_vals[i]
        d_prev, d_curr = d_vals[i - 1], d_vals[i]
        # K crossed above D
        if k_prev <= d_prev and k_curr > d_curr:
            if k_curr <= 20:
                crosses[i] = "BULLISH_OS"
            else:
                crosses[i] = "BULLISH"
        # K crossed below D
        elif k_prev >= d_prev and k_curr < d_curr:
            if k_curr >= 80:
                crosses[i] = "BEARISH_OB"
            else:
                crosses[i] = "BEARISH"

    result = pd.DataFrame(index=df.index)
    result["closed_cross"] = crosses
    result["closed_zone"] = zones
    return result


# ── Bollinger Bands ────────────────────────────────────────────────────────────

def compute_bb(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Compute Bollinger Bands fields: pct_in_band, reenter, band_width, squeeze."""
    bb_df = ta.bbands(df["close"], length=period, std=std_dev)
    if bb_df is None or bb_df.empty:
        result = pd.DataFrame(index=df.index)
        result["closed_pct_in_band"] = 50.0
        result["closed_reenter_from_below"] = "FALSE"
        result["closed_reenter_from_above"] = "FALSE"
        result["band_width"] = 0.0
        result["bb_squeeze"] = "FALSE"
        return result

    upper_col = [c for c in bb_df.columns if "BBU" in c]
    lower_col = [c for c in bb_df.columns if "BBL" in c]
    mid_col = [c for c in bb_df.columns if "BBM" in c]

    upper = bb_df[upper_col[0]].values if upper_col else np.full(len(df), np.nan)
    lower = bb_df[lower_col[0]].values if lower_col else np.full(len(df), np.nan)
    close = df["close"].values
    open_ = df["open"].values

    width = upper - lower

    # Pct in band: 0 = at lower, 100 = at upper
    pct = np.where(width != 0, ((close - lower) / width) * 100, 50.0)

    # Reenter from below: opened below lower, closed above lower
    reenter_below = np.where((open_ < lower) & (close >= lower), "TRUE", "FALSE")

    # Reenter from above: opened above upper, closed below upper
    reenter_above = np.where((open_ > upper) & (close <= upper), "TRUE", "FALSE")

    # BB Squeeze: band width is below its 20-bar SMA (narrow bands → squeeze)
    width_sma = pd.Series(width).rolling(20).mean().values
    bb_squeeze = np.where(width < width_sma, "TRUE", "FALSE")

    result = pd.DataFrame(index=df.index)
    result["closed_pct_in_band"] = pct
    result["closed_reenter_from_below"] = reenter_below
    result["closed_reenter_from_above"] = reenter_above
    result["band_width"] = width
    result["bb_squeeze"] = bb_squeeze
    return result


# ── ATR (standalone) ───────────────────────────────────────────────────────────

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Compute standalone ATR fields: volatility state, ATR value, ratio."""
    atr = ta.atr(df["high"], df["low"], df["close"], length=period)
    if atr is None:
        atr = pd.Series(0.0, index=df.index)
    atr_vals = atr.fillna(0).values

    # SMA of ATR for comparison
    atr_sma = pd.Series(atr_vals).rolling(20).mean().fillna(pd.Series(atr_vals)).values
    # Safe division: avoid 0/0 NaN warnings
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(atr_sma != 0, atr_vals / atr_sma, 1.0)
    ratio = np.nan_to_num(ratio, nan=1.0)

    # Volatility state
    states = []
    for i in range(len(atr_vals)):
        r = ratio[i]
        if r >= 1.3:
            states.append("EXPANDING")
        elif r >= 1.0:
            states.append("ABOVE_AVG")
        elif r >= 0.7:
            states.append("BELOW_AVG")
        else:
            states.append("CONTRACTING")

    result = pd.DataFrame(index=df.index)
    result["volatility_state"] = states
    result["running_atr"] = atr_vals
    result["atr_vs_sma_ratio"] = ratio
    return result


# ── Liquidity Grab ─────────────────────────────────────────────────────────────

def compute_liqgrab(
    df: pd.DataFrame,
    lookback: int = 50,
    bars_n: int = 5,
    wick_ratio: float = 2.0,
    candles_bk: int = 5,
    ma_period: int = 100,
) -> pd.DataFrame:
    """Compute Liquidity Grab indicator (matches SignalMaster.mq5).

    Finds key structural highs/lows (pivot points), then detects when price
    sweeps past them with a wick but closes back inside (liquidity grab).

    Parameters:
        lookback: Range for finding key levels (default 50)
        bars_n: Pivot window half-size (default 5 = bar must be highest/lowest
                in a 2*5+1 = 11 bar window)
        wick_ratio: Min wick:body ratio for rejection candle (default 2.0)
        candles_bk: How many recent bars to check for rejections (default 5)
        ma_period: SMA period for trend filter (default 100)

    Fields:
        key_high, key_low: current structural pivot levels
        rejection_up: TRUE if bullish wick rejection at key_low in last candles_bk bars
        rejection_down: TRUE if bearish wick rejection at key_high in last candles_bk bars
        rejection_up_count: number of rejection-up bars in last candles_bk bars
        rejection_down_count: number of rejection-down bars in last candles_bk bars
        breakout_up, breakout_down: price broke past key level
        ma_trend: ABOVE/BELOW SMA
        liq_signal: composite BUY/SELL/NONE
    """
    n = len(df)
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    # SMA for trend filter
    sma = pd.Series(closes).rolling(ma_period, min_periods=1).mean().values

    # Output arrays
    key_high_arr = np.full(n, np.nan)
    key_low_arr = np.full(n, np.nan)
    rej_up_arr = np.full(n, "FALSE", dtype=object)
    rej_down_arr = np.full(n, "FALSE", dtype=object)
    rej_up_count_arr = np.zeros(n, dtype=int)
    rej_down_count_arr = np.zeros(n, dtype=int)
    breakout_up_arr = np.full(n, "FALSE", dtype=object)
    breakout_down_arr = np.full(n, "FALSE", dtype=object)
    ma_trend_arr = np.full(n, "BELOW", dtype=object)
    signal_arr = np.full(n, "NONE", dtype=object)

    min_bars = max(lookback, ma_period) + bars_n + 10

    for i in range(min_bars, n):
        # --- Find key high (highest pivot in lookback range) ---
        key_high = _find_key_high(highs, i, bars_n, lookback)
        key_low = _find_key_low(lows, i, bars_n, lookback)
        key_high_arr[i] = key_high
        key_low_arr[i] = key_low

        # --- Check for rejection in last candles_bk closed bars ---
        was_rej_up = False
        was_rej_down = False
        rej_up_cnt = 0
        rej_down_cnt = 0

        for j in range(1, min(candles_bk + 1, i + 1)):
            shift = i - j
            if shift < 0:
                break
            if _is_rejection_up(opens, highs, lows, closes, shift, wick_ratio, key_low):
                was_rej_up = True
                rej_up_cnt += 1
            if _is_rejection_down(opens, highs, lows, closes, shift, wick_ratio, key_high):
                was_rej_down = True
                rej_down_cnt += 1

        rej_up_arr[i] = "TRUE" if was_rej_up else "FALSE"
        rej_down_arr[i] = "TRUE" if was_rej_down else "FALSE"
        rej_up_count_arr[i] = rej_up_cnt
        rej_down_count_arr[i] = rej_down_cnt

        # --- Breakout detection ---
        bk_range = candles_bk + bars_n
        bk_key_high = _find_key_high(highs, i, bars_n, bk_range)
        bk_key_low = _find_key_low(lows, i, bars_n, bk_range)

        brk_up = False
        brk_down = False
        for j in range(1, min(candles_bk + 1, i + 1)):
            shift = i - j
            if shift < 0:
                break
            if closes[shift] > bk_key_high:
                brk_up = True
            if closes[shift] < bk_key_low:
                brk_down = True

        breakout_up_arr[i] = "TRUE" if brk_up else "FALSE"
        breakout_down_arr[i] = "TRUE" if brk_down else "FALSE"

        # --- MA trend ---
        ma_trend_arr[i] = "ABOVE" if closes[i] > sma[i] else "BELOW"

        # --- Composite signal ---
        if was_rej_up and brk_up and closes[i] > sma[i]:
            signal_arr[i] = "BUY"
        elif was_rej_down and brk_down and closes[i] < sma[i]:
            signal_arr[i] = "SELL"

    result = pd.DataFrame(index=df.index)
    result["closed_key_high"] = key_high_arr
    result["closed_key_low"] = key_low_arr
    result["closed_rejection_up"] = rej_up_arr
    result["closed_rejection_down"] = rej_down_arr
    result["closed_rejection_up_count"] = rej_up_count_arr
    result["closed_rejection_down_count"] = rej_down_count_arr
    result["closed_breakout_up"] = breakout_up_arr
    result["closed_breakout_down"] = breakout_down_arr
    result["closed_ma_trend"] = ma_trend_arr
    result["closed_liq_signal"] = signal_arr
    return result


def _find_key_high(highs: np.ndarray, current: int, bars_n: int, lookback: int) -> float:
    """Find the highest pivot high in the lookback range before current bar."""
    best = -np.inf
    found = False
    limit = min(lookback, current - bars_n)
    for offset in range(bars_n, limit):
        idx = current - offset
        if idx < bars_n:
            break
        hi = highs[idx]
        is_peak = True
        for j in range(idx - bars_n, idx + bars_n + 1):
            if j < 0 or j >= len(highs):
                continue
            if j != idx and highs[j] > hi:
                is_peak = False
                break
        if is_peak and hi > best:
            best = hi
            found = True
    return best if found else np.inf


def _find_key_low(lows: np.ndarray, current: int, bars_n: int, lookback: int) -> float:
    """Find the lowest pivot low in the lookback range before current bar."""
    best = np.inf
    found = False
    limit = min(lookback, current - bars_n)
    for offset in range(bars_n, limit):
        idx = current - offset
        if idx < bars_n:
            break
        lo = lows[idx]
        is_trough = True
        for j in range(idx - bars_n, idx + bars_n + 1):
            if j < 0 or j >= len(lows):
                continue
            if j != idx and lows[j] < lo:
                is_trough = False
                break
        if is_trough and lo < best:
            best = lo
            found = True
    return best if found else -1.0


def _is_rejection_up(
    opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    shift: int, wick_ratio: float, key_low: float,
) -> bool:
    """Bullish rejection: lower wick grabs below key_low, closes above it."""
    body = abs(closes[shift] - opens[shift])
    if body < 1e-8:
        return False
    lower_wick = min(opens[shift], closes[shift]) - lows[shift]
    return (lower_wick >= wick_ratio * body
            and lows[shift] < key_low
            and highs[shift] > key_low)


def _is_rejection_down(
    opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    shift: int, wick_ratio: float, key_high: float,
) -> bool:
    """Bearish rejection: upper wick grabs above key_high, closes below it."""
    body = abs(closes[shift] - opens[shift])
    if body < 1e-8:
        return False
    upper_wick = highs[shift] - max(opens[shift], closes[shift])
    return (upper_wick >= wick_ratio * body
            and highs[shift] > key_high
            and lows[shift] < key_high)


# ── VWAP ───────────────────────────────────────────────────────────────────────

def compute_vwap(df: pd.DataFrame, session_reset_hour: int = 0) -> pd.DataFrame:
    """Compute session VWAP: Σ(TP × Vol) / Σ(Vol), reset at session boundary.

    session_reset_hour: UTC hour when session resets (default 0 = midnight).
    Matches SignalMaster EA which resets at 00:00 server time.

    Fields: closed_price_vs_vwap (ABOVE/BELOW), running_dist_pct (%).
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].values.astype(float)

    # Detect session boundaries: reset at 00:00 server time each day
    times = pd.to_datetime(df["time"])
    dates = times.dt.date

    vwap_vals = np.zeros(len(df))
    cum_tp_vol = 0.0
    cum_vol = 0.0
    prev_date = None

    for i in range(len(df)):
        d = dates.iloc[i]
        # Reset when the date changes (midnight boundary)
        if prev_date is not None and d != prev_date:
            cum_tp_vol = 0.0
            cum_vol = 0.0
        prev_date = d

        v = max(vol[i], 1.0)  # avoid zero volume
        cum_tp_vol += tp.iloc[i] * v
        cum_vol += v
        vwap_vals[i] = cum_tp_vol / cum_vol

    close = df["close"].values
    vs_vwap = np.where(close > vwap_vals, "ABOVE", "BELOW")
    dist_pct = np.where(vwap_vals != 0, ((close - vwap_vals) / vwap_vals) * 100, 0.0)

    result = pd.DataFrame(index=df.index)
    result["closed_price_vs_vwap"] = vs_vwap
    result["running_dist_pct"] = dist_pct
    return result


# ── Resample to higher timeframes ─────────────────────────────────────────────

_TF_MAP = {
    "M1": "1min",
    "M2": "2min",
    "M3": "3min",
    "M5": "5min",
    "M10": "10min",
    "M15": "15min",
    "M20": "20min",
    "M30": "30min",
    "M45": "45min",
    "H1": "1h",
    "H2": "2h",
    "H3": "3h",
    "H4": "4h",
    "H6": "6h",
    "H8": "8h",
    "H12": "12h",
    "D1": "1D",
}


def resample_ohlc(df_m1: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample M1 OHLC to a higher timeframe.

    Uses ``label='left', closed='left'`` so that candle boundaries match MT5:
      - M5 bar at 00:00 contains M1 bars [00:00, 00:01, 00:02, 00:03, 00:04]
      - M15 bar at 00:00 contains M1 bars [00:00 … 00:14]
      - H4 bar at 00:00 contains M1 bars [00:00 … 03:59]

    Returns a DataFrame with the same columns but fewer rows.
    Each row represents one completed bar of the target timeframe.
    """
    if timeframe == "M1":
        return df_m1.copy()

    freq = _TF_MAP.get(timeframe)
    if not freq:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    df = df_m1.copy()
    df = df.set_index("time")

    resampled = df.resample(freq, label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["open"])

    resampled = resampled.reset_index()
    return resampled


def forward_fill_to_m1(
    indicator_df: pd.DataFrame,
    htf_times: pd.Series,
    m1_times: pd.Series,
    freq: str = "5min",
) -> pd.DataFrame:
    """Forward-fill higher-TF indicator values to M1 bars.

    Simulates ``closed_*`` fields: an HTF bar's values only become visible
    when the bar's last M1 bar finishes.  For an M5 bar starting at 00:00
    the last M1 bar is 00:04, so M1[00:04] is the first bar to see that
    M5 bar's closed values.

    ``freq`` is the pandas frequency string from ``_TF_MAP`` (e.g. '5min').
    """
    htf_idx = pd.DatetimeIndex(htf_times)
    m1_idx = pd.DatetimeIndex(m1_times)

    # close_m1 = the M1 bar at which each HTF bar finishes.
    # HTF bar at T covers M1 bars [T, T+period).  Its last M1 bar has
    # timestamp T + period - 1min.
    period = pd.Timedelta(freq)
    close_m1 = htf_idx + period - pd.Timedelta("1min")

    # For each M1 time find the latest HTF bar whose close_m1 <= m1_time.
    positions = close_m1.searchsorted(m1_idx, side="right") - 1

    # Build result DataFrame — fully vectorized (no Python loop over bars)
    n_htf = len(indicator_df)
    n_m1 = len(m1_times)
    valid_mask = (positions >= 0) & (positions < n_htf)
    safe_positions = np.clip(positions, 0, max(n_htf - 1, 0))

    result = pd.DataFrame(index=range(n_m1))
    for col in indicator_df.columns:
        vals = indicator_df[col].values
        is_str = len(vals) > 0 and isinstance(vals[0], str)
        if is_str:
            filled = np.where(valid_mask, vals[safe_positions], "")
        else:
            filled = np.where(valid_mask, vals[safe_positions], np.nan)
        result[col] = filled

    return result


# ── Master compute function ───────────────────────────────────────────────────

def compute_all_indicators(
    df_m1: pd.DataFrame,
    sources: list[dict],
    native_bars: dict[str, pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute all indicators for all timeframes as specified in config.

    Args:
        df_m1: M1 OHLC DataFrame with columns [time, open, high, low, close, volume]
        sources: List of dicts like {"indicator": "utbot", "timeframes": ["M1", "M5", "M15"]}
        native_bars: Optional dict mapping TF name (e.g. "M5") to native OHLC DataFrame
                     downloaded directly from MT5.  When provided, these are used instead
                     of resampling from M1, ensuring exact parity with live trading.

    Returns:
        Dict mapping signal name (e.g. "utbot_M1") to DataFrame of indicator fields,
        aligned to the M1 bar index.
    """
    signals: dict[str, pd.DataFrame] = {}
    if native_bars is None:
        native_bars = {}

    # Precompute resampled DataFrames for each unique timeframe
    timeframes_needed: set[str] = set()
    for src in sources:
        for tf in src.get("timeframes", []):
            timeframes_needed.add(tf)

    resampled: dict[str, pd.DataFrame] = {}
    for tf in timeframes_needed:
        if tf in native_bars:
            resampled[tf] = native_bars[tf]
            log.info("Using native MT5 bars for %s: %d bars", tf, len(resampled[tf]))
        else:
            resampled[tf] = resample_ohlc(df_m1, tf)
            log.info("Resampled to %s: %d bars", tf, len(resampled[tf]))

    m1_times = df_m1["time"]

    for src in sources:
        indicator = src["indicator"]
        for tf in src.get("timeframes", []):
            name = f"{indicator}_{tf}"
            df_tf = resampled[tf]
            freq = _TF_MAP.get(tf, "1min")

            log.info("Computing %s (%d bars)", name, len(df_tf))

            if indicator == "utbot":
                ind_df = compute_utbot(df_tf)
            elif indicator == "dc":
                ind_df = compute_dc(df_tf)
            elif indicator.startswith("ema"):
                period = int(indicator.replace("ema", ""))
                ind_df = compute_ema(df_tf, period)
            elif indicator.startswith("rsi"):
                period = int(indicator.replace("rsi", ""))
                ind_df = compute_rsi(df_tf, period)
            elif indicator.startswith("adx"):
                period = int(indicator.replace("adx", ""))
                ind_df = compute_adx(df_tf, period)
            elif indicator.startswith("macd"):
                # e.g. macd12_26_9
                parts = indicator.replace("macd", "").split("_")
                fast, slow, sig = int(parts[0]), int(parts[1]), int(parts[2])
                ind_df = compute_macd(df_tf, fast, slow, sig)
            elif indicator.startswith("stoch"):
                # e.g. stoch5_3_3
                parts = indicator.replace("stoch", "").split("_")
                k, d, smooth = int(parts[0]), int(parts[1]), int(parts[2])
                ind_df = compute_stoch(df_tf, k, d, smooth)
            elif indicator.startswith("bb"):
                # e.g. bb20d2 → period=20, std=2.0
                raw = indicator.replace("bb", "")
                if "d" in raw:
                    p, d = raw.split("d")
                    period, std_dev = int(p), float(d)
                else:
                    period, std_dev = 20, 2.0
                ind_df = compute_bb(df_tf, period, std_dev)
            elif indicator.startswith("atr"):
                period = int(indicator.replace("atr", ""))
                ind_df = compute_atr(df_tf, period)
            elif indicator == "vwap":
                ind_df = compute_vwap(df_tf)
            elif indicator == "candle":
                ind_df = compute_candle(df_tf)
            elif indicator == "liqgrab":
                ind_df = compute_liqgrab(df_tf)
            else:
                log.warning("Unknown indicator: %s — skipping", indicator)
                continue

            # Forward-fill to M1 if higher TF
            if tf != "M1":
                htf_times = df_tf["time"]
                ind_df = forward_fill_to_m1(ind_df, htf_times, m1_times, freq=freq)
            else:
                ind_df = ind_df.reset_index(drop=True)

            signals[name] = ind_df
            log.info("  → %s: %d rows, %d fields", name, len(ind_df), len(ind_df.columns))

    return signals
