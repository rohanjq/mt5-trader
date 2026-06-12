"""Verify the root cause: EA uses sliding 500-bar window, not continuous trail.

The EA recomputes trail fresh from the LAST 500 bars every timer tick:
  - trail[0:10] = close, direction = BULL (initialization)
  - trail[10:499] = computed from bar data

Our BT computes trail over ALL 30K bars continuously from Apr 13.
Different initialization → different trails.

This script verifies by computing trail using just the last 500 bars
of our data and comparing against the EA's 500-bar dump.
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from backtest.data_loader import load_ohlc

EA_DUMPS = "sampledata/ea_dumps"
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"

for tf in ["M2", "M3", "M5"]:
    print(f"\n{'='*80}")
    print(f"  {tf}: Testing sliding 500-bar window hypothesis")
    print(f"{'='*80}")

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

    # Load our bars
    df = load_ohlc(f"{BARS_DIR}/{tf}.csv")
    df_times = pd.to_datetime(df["time"])

    # Find the EA's 500-bar window end time
    ea_end = ea["time_dt"].iloc[-1]
    ea_start = ea["time_dt"].iloc[0]
    print(f"  EA 500-bar window: {ea_start} → {ea_end}")

    # Our data may not have bars this far (Jun 12) since our data ends Jun 12
    # Find the latest common time
    latest_ea = ea["time_dt"].iloc[-1]
    latest_our = df_times.iloc[-1]
    print(f"  Our data ends: {latest_our}")

    # Get the same time range from our data
    end_idx = df_times.searchsorted(ea_end, side="right") - 1
    if end_idx < 500:
        print(f"  Not enough bars (need 500, have {end_idx})")
        continue

    # Take exactly 500 bars ending at end_idx
    start_idx = end_idx - 499
    window = df.iloc[start_idx:end_idx+1].reset_index(drop=True)
    window_times = pd.to_datetime(window["time"])
    close = window["close"].values
    n = len(close)

    print(f"  Our 500-bar window: {window_times.iloc[0]} → {window_times.iloc[-1]}")
    print(f"  Window size: {n} bars")

    # Compute ATR on this window using pandas_ta
    atr_series = ta.atr(window["high"], window["low"], window["close"], length=10)
    atr_vals = atr_series.fillna(0).values
    nloss = 2.0 * atr_vals

    # Compute trail exactly like EA: first 10 bars = close, dir=BULL
    trail = np.zeros(n)
    direction = np.ones(n)
    for i in range(min(10, n)):
        trail[i] = close[i]
        direction[i] = 1.0

    for i in range(10, n):
        if close[i] > trail[i-1]:
            trail[i] = close[i] - nloss[i]
            if direction[i-1] > 0:
                trail[i] = max(trail[i], trail[i-1])
            direction[i] = 1.0
        else:
            trail[i] = close[i] + nloss[i]
            if direction[i-1] < 0:
                trail[i] = min(trail[i], trail[i-1])
            direction[i] = -1.0

    # Compare against EA dump bar by bar
    ea_times = ea["time_dt"].values
    ea_trail = ea["trail_stop"].values.astype(float)
    ea_dir = ea["direction"].values.astype(float)
    ea_close = ea["close"].values.astype(float)

    dir_matches = 0
    trail_matches = 0
    total = 0

    for i in range(n):
        t = window_times.iloc[i]
        # Find in EA
        ea_idx = np.where(ea_times == np.datetime64(t))[0]
        if len(ea_idx) == 0:
            continue
        ei = ea_idx[0]
        total += 1

        d_match = (direction[i] > 0) == (ea_dir[ei] > 0)
        t_match = abs(trail[i] - ea_trail[ei]) < 0.02

        if d_match:
            dir_matches += 1
        if t_match:
            trail_matches += 1

        if not d_match and total <= 500:
            d_ea = "BULL" if ea_dir[ei] > 0 else "BEAR"
            d_bt = "BULL" if direction[i] > 0 else "BEAR"
            print(f"  DIR MISMATCH at {t}: EA={d_ea}(trail={ea_trail[ei]:.2f}) "
                  f"BT500={d_bt}(trail={trail[i]:.2f}) close={close[i]:.2f}")

    print(f"\n  RESULTS (sliding 500-bar window):")
    print(f"    Matched bars: {total}")
    print(f"    Direction matches: {dir_matches}/{total} ({100*dir_matches/max(total,1):.1f}%)")
    print(f"    Trail value matches (<0.02): {trail_matches}/{total} ({100*trail_matches/max(total,1):.1f}%)")

    # Also check: does the ATR differ?
    atr_diffs = 0
    for i in range(n):
        t = window_times.iloc[i]
        ea_idx = np.where(ea_times == np.datetime64(t))[0]
        if len(ea_idx) == 0:
            continue
        ei = ea_idx[0]
        ea_atr = pd.to_numeric(ea["atr"].iloc[ei], errors="coerce")
        if abs(atr_vals[i] - ea_atr) > 0.01:
            atr_diffs += 1
            if atr_diffs <= 5:
                print(f"  ATR diff at {t}: EA={ea_atr:.4f} BT={atr_vals[i]:.4f}")

    print(f"    ATR differences (>0.01): {atr_diffs}/{total}")
