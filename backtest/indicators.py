"""Vectorised indicator computation from OHLC data using pandas_ta.

Computes all indicators needed by mt5-trader expression rules:
  utbot, dc, ema{9,21,50,200}, rsi{14,2}, adx14, macd12_26_9,
  stoch5_3_3, bb20d2, atr14, vwap

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

def compute_utbot(df: pd.DataFrame, atr_period: int = 1, key_value: float = 1.0) -> pd.DataFrame:
    """Compute UT Bot Alert indicator.

    The UT Bot uses ATR trailing stop. When close crosses above the trail stop,
    bias flips to BULLISH and a BUY signal fires (one bar). Vice versa for SELL.

    Parameters:
        atr_period: ATR period (default 1 for the standard UT Bot)
        key_value: ATR multiplier for trail stop distance (default 1.0)
    """
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(close)

    # Compute ATR
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=atr_period)
    atr_vals = atr_series.fillna(0).values
    nloss = key_value * atr_vals

    # Trailing stop
    trail_stop = np.zeros(n)
    for i in range(1, n):
        if close[i] > trail_stop[i - 1]:
            trail_stop[i] = max(trail_stop[i - 1], close[i] - nloss[i])
        else:
            trail_stop[i] = min(trail_stop[i - 1], close[i] + nloss[i])

    # Bias: above trail = BULLISH, below = BEARISH
    bias = np.where(close > trail_stop, "BULLISH", "BEARISH")

    # Signal: fires on bias change
    signal = np.full(n, "NONE", dtype=object)
    for i in range(1, n):
        if bias[i] == "BULLISH" and bias[i - 1] != "BULLISH":
            signal[i] = "BUY"
        elif bias[i] == "BEARISH" and bias[i - 1] != "BEARISH":
            signal[i] = "SELL"

    # Consecutive bars
    consec_bull = np.zeros(n, dtype=int)
    consec_bear = np.zeros(n, dtype=int)
    for i in range(1, n):
        if bias[i] == "BULLISH":
            consec_bull[i] = consec_bull[i - 1] + 1
            consec_bear[i] = 0
        elif bias[i] == "BEARISH":
            consec_bear[i] = consec_bear[i - 1] + 1
            consec_bull[i] = 0

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

    # Price zone (5 zones)
    zones = []
    for i in range(len(close)):
        if width[i] == 0:
            zones.append("MIDDLE")
            continue
        pct = (close[i] - lower[i]) / width[i]
        if pct >= 0.8:
            zones.append("UPPER")
        elif pct >= 0.6:
            zones.append("UPPER_MID")
        elif pct >= 0.4:
            zones.append("MIDDLE")
        elif pct >= 0.2:
            zones.append("LOWER_MID")
        else:
            zones.append("LOWER")

    # Wick rejections
    upper_rej = []
    lower_rej = []
    for i in range(len(close)):
        # Upper wick rejection: high touched upper band but close below it
        upper_rej.append("TRUE" if high[i] >= upper[i] and close[i] < upper[i] else "FALSE")
        # Lower wick rejection: low touched lower band but close above it
        lower_rej.append("TRUE" if low[i] <= lower[i] and close[i] > lower[i] else "FALSE")

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


# ── VWAP ───────────────────────────────────────────────────────────────────────

def compute_vwap(df: pd.DataFrame, session_reset_hour: int = 22) -> pd.DataFrame:
    """Compute session VWAP: Σ(TP × Vol) / Σ(Vol), reset at session boundary.

    session_reset_hour: UTC hour when session resets (default 22:00 = 5 PM ET).
    This matches typical forex broker server time session boundaries.

    Fields: closed_price_vs_vwap (ABOVE/BELOW), running_dist_pct (%).
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].values.astype(float)

    # Detect session boundaries: reset when hour crosses session_reset_hour
    times = pd.to_datetime(df["time"])
    hours = times.dt.hour

    vwap_vals = np.zeros(len(df))
    cum_tp_vol = 0.0
    cum_vol = 0.0
    prev_hour = -1

    for i in range(len(df)):
        h = hours.iloc[i]
        # Reset when we cross the session boundary hour
        if prev_hour >= 0 and prev_hour != h and h == session_reset_hour:
            cum_tp_vol = 0.0
            cum_vol = 0.0
        prev_hour = h

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
    "M30": "30min",
    "M45": "45min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}


def resample_ohlc(df_m1: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample M1 OHLC to a higher timeframe.

    Returns a DataFrame with the same columns but fewer rows.
    Each row represents one bar of the target timeframe.
    """
    if timeframe == "M1":
        return df_m1.copy()

    freq = _TF_MAP.get(timeframe)
    if not freq:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    df = df_m1.copy()
    df = df.set_index("time")

    resampled = df.resample(freq, label="right", closed="right").agg({
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
) -> pd.DataFrame:
    """Forward-fill higher-TF indicator values to M1 bars.

    For each M1 bar, use the most recent completed HTF bar's indicator values.
    This simulates "closed_" fields: only update when a higher TF bar closes.
    """
    # Create a mapping: for each M1 time, find the most recent HTF time <= M1 time
    htf_idx = pd.DatetimeIndex(htf_times)
    m1_idx = pd.DatetimeIndex(m1_times)

    # Use searchsorted to find the insertion point
    positions = htf_idx.searchsorted(m1_idx, side="right") - 1

    # Build result DataFrame
    result = pd.DataFrame(index=range(len(m1_times)))
    for col in indicator_df.columns:
        vals = indicator_df[col].values
        filled = []
        for pos in positions:
            if pos >= 0 and pos < len(vals):
                filled.append(vals[pos])
            else:
                filled.append("" if isinstance(vals[0], str) else 0.0)
        result[col] = filled

    return result


# ── Master compute function ───────────────────────────────────────────────────

def compute_all_indicators(
    df_m1: pd.DataFrame,
    sources: list[dict],
) -> dict[str, pd.DataFrame]:
    """Compute all indicators for all timeframes as specified in config.

    Args:
        df_m1: M1 OHLC DataFrame with columns [time, open, high, low, close, volume]
        sources: List of dicts like {"indicator": "utbot", "timeframes": ["M1", "M5", "M15"]}

    Returns:
        Dict mapping signal name (e.g. "utbot_M1") to DataFrame of indicator fields,
        aligned to the M1 bar index.
    """
    signals: dict[str, pd.DataFrame] = {}

    # Precompute resampled DataFrames for each unique timeframe
    timeframes_needed: set[str] = set()
    for src in sources:
        for tf in src.get("timeframes", []):
            timeframes_needed.add(tf)

    resampled: dict[str, pd.DataFrame] = {}
    for tf in timeframes_needed:
        resampled[tf] = resample_ohlc(df_m1, tf)
        log.info("Resampled to %s: %d bars", tf, len(resampled[tf]))

    m1_times = df_m1["time"]

    for src in sources:
        indicator = src["indicator"]
        for tf in src.get("timeframes", []):
            name = f"{indicator}_{tf}"
            df_tf = resampled[tf]

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
            else:
                log.warning("Unknown indicator: %s — skipping", indicator)
                continue

            # Forward-fill to M1 if higher TF
            if tf != "M1":
                htf_times = df_tf["time"]
                ind_df = forward_fill_to_m1(ind_df, htf_times, m1_times)
            else:
                ind_df = ind_df.reset_index(drop=True)

            signals[name] = ind_df
            log.info("  → %s: %d rows, %d fields", name, len(ind_df), len(ind_df.columns))

    return signals
