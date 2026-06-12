"""Definitive test: compute trail on EA's exact 500-bar window using our ATR.

This tells us exactly how many direction errors come from ATR warmup vs
the sliding window approach.
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from backtest.data_loader import load_ohlc

EA_DUMPS = "sampledata/ea_dumps"
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"

for tf in ["M2", "M3", "M5"]:
    print(f"\n{'='*70}")
    print(f"  {tf}: Our ATR + EA's exact 500-bar window")
    print(f"{'='*70}")

    # Load EA 500-bar dump
    path = f"{EA_DUMPS}/XAUUSD_utbot_trail_{tf}.csv"
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            ea = pd.read_csv(path, encoding=enc)
            if "time" in ea.columns:
                break
        except Exception:
            continue
    ea["time_dt"] = pd.to_datetime(ea["time"], format="%Y.%m.%d %H:%M")
    ea_trail = ea["trail_stop"].values.astype(float)
    ea_dir = ea["direction"].values.astype(float)
    ea_close = ea["close"].values.astype(float)
    ea_times = ea["time_dt"].values

    # Load our full bars and compute ATR over ALL data
    df = load_ohlc(f"{BARS_DIR}/{tf}.csv")
    df_times = pd.to_datetime(df["time"])
    full_atr = ta.atr(df["high"], df["low"], df["close"], length=10).fillna(0).values

    # Now also compute manual Wilder ATR to see if it's more accurate
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n_full = len(df)

    # True Range
    tr = np.zeros(n_full)
    tr[0] = high[0] - low[0]
    for i in range(1, n_full):
        tr[i] = max(high[i] - low[i],
                     abs(high[i] - close[i-1]),
                     abs(low[i] - close[i-1]))

    # Wilder's smoothing (RMA)
    wilder_atr = np.zeros(n_full)
    wilder_atr[:10] = 0.0
    wilder_atr[9] = np.mean(tr[:10])  # SMA of first 10 TRs
    for i in range(10, n_full):
        wilder_atr[i] = (wilder_atr[i-1] * 9 + tr[i]) / 10

    # ALSO: compute Wilder ATR seeded with EA's first ATR value
    # Load EA full dump to get ATR at our first bar
    path_full = f"{EA_DUMPS}/XAUUSD_utbot_trail_FULL_{tf}.csv"
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            ea_full = pd.read_csv(path_full, encoding=enc)
            if "time" in ea_full.columns:
                break
        except Exception:
            continue
    ea_full["time_dt"] = pd.to_datetime(ea_full["time"], format="%Y.%m.%d %H:%M")
    ea_full["atr_num"] = pd.to_numeric(ea_full["atr"], errors="coerce")

    # Find EA's ATR at our first bar (or closest)
    our_first = df_times.iloc[0]
    match_idx = ea_full["time_dt"].searchsorted(our_first)
    if match_idx < len(ea_full):
        ea_seed_atr = ea_full["atr_num"].iloc[match_idx]
        print(f"  EA ATR at our first bar ({our_first}): {ea_seed_atr:.4f}")
    else:
        ea_seed_atr = None
        print(f"  Cannot find EA ATR at our first bar")

    seeded_atr = np.zeros(n_full)
    if ea_seed_atr is not None and np.isfinite(ea_seed_atr) and ea_seed_atr > 0:
        seeded_atr[0] = ea_seed_atr
        for i in range(1, n_full):
            seeded_atr[i] = (seeded_atr[i-1] * 9 + tr[i]) / 10
    else:
        seeded_atr = wilder_atr.copy()

    # For each ATR method, compute trail on EA's 500-bar window
    # and count direction matches
    methods = {
        "pandas_ta": full_atr,
        "manual_wilder": wilder_atr,
        "seeded_wilder": seeded_atr,
    }

    for method_name, atr_vals in methods.items():
        # Get our ATR values at the EA's bar times
        our_atr_at_ea = np.zeros(500)
        our_close_at_ea = np.zeros(500)
        found = 0

        for i in range(500):
            t = ea_times[i]
            idx = df_times.searchsorted(t)
            if idx < len(df_times) and df_times.iloc[idx] == t:
                our_atr_at_ea[i] = atr_vals[idx]
                our_close_at_ea[i] = close[idx]
                found += 1
            else:
                our_atr_at_ea[i] = 0
                our_close_at_ea[i] = ea_close[i]

        # Compute trail using our ATR but EA's close values and window
        nloss = 2.0 * our_atr_at_ea
        trail = np.zeros(500)
        direction = np.ones(500)

        for i in range(min(10, 500)):
            trail[i] = ea_close[i]
            direction[i] = 1.0

        for i in range(10, 500):
            if ea_close[i] > trail[i-1]:
                trail[i] = ea_close[i] - nloss[i]
                if direction[i-1] > 0:
                    trail[i] = max(trail[i], trail[i-1])
                direction[i] = 1.0
            else:
                trail[i] = ea_close[i] + nloss[i]
                if direction[i-1] < 0:
                    trail[i] = min(trail[i], trail[i-1])
                direction[i] = -1.0

        dir_match = np.sum((direction > 0) == (ea_dir > 0))
        print(f"  {method_name:20s}: direction match = {dir_match}/500 ({100*dir_match/500:.1f}%)")

        # Show first few ATR diffs in this method
        ea_atr_num = pd.to_numeric(ea["atr"], errors="coerce").values
        atr_diffs_start = [(i, abs(our_atr_at_ea[i] - ea_atr_num[i]))
                           for i in range(10, 20) if np.isfinite(ea_atr_num[i])]
        atr_diffs_end = [(i, abs(our_atr_at_ea[i] - ea_atr_num[i]))
                         for i in range(490, 500) if np.isfinite(ea_atr_num[i])]
        avg_start = np.mean([d for _, d in atr_diffs_start]) if atr_diffs_start else 0
        avg_end = np.mean([d for _, d in atr_diffs_end]) if atr_diffs_end else 0
        print(f"  {'':20s}  ATR diff start={avg_start:.4f} end={avg_end:.4f}")
