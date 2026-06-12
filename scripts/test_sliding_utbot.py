"""Test the sliding window UTBot against EA's 500-bar dump."""
import time
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc
from backtest.indicators import compute_utbot

EA_DUMPS = "sampledata/ea_dumps"
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"

for tf in ["M2", "M3", "M5"]:
    print(f"\n{'='*70}")
    print(f"  {tf}: Sliding window UTBot vs EA")
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
    ea_dir = ea["direction"].values.astype(float)
    ea_trail = ea["trail_stop"].values.astype(float)
    ea_times = ea["time_dt"].values

    # Load bars and compute UTBot with sliding window
    df = load_ohlc(f"{BARS_DIR}/{tf}.csv")
    df_times = pd.to_datetime(df["time"])

    t0 = time.time()
    utbot = compute_utbot(df, lookback=500)
    elapsed = time.time() - t0
    print(f"  compute_utbot took {elapsed:.1f}s for {len(df)} bars")

    our_dir = np.where(utbot["closed_bias"].values == "BULLISH", 1.0, -1.0)
    our_trail = utbot["closed_trail_stop"].values.astype(float)
    our_times = pd.DatetimeIndex(df_times)

    # Compare at EA's bar times
    dir_match = 0
    dir_total = 0
    trail_match = 0
    mismatches = []

    for i in range(len(ea)):
        t = ea_times[i]
        idx = our_times.get_indexer([t], method=None)[0]
        if idx < 0:
            continue
        dir_total += 1

        ea_d = ea_dir[i]
        bt_d = our_dir[idx]
        if (ea_d > 0) == (bt_d > 0):
            dir_match += 1
        else:
            d_ea = "BULL" if ea_d > 0 else "BEAR"
            d_bt = "BULL" if bt_d > 0 else "BEAR"
            mismatches.append(f"    {t}: EA={d_ea}(trail={ea_trail[i]:.2f}) BT={d_bt}(trail={our_trail[idx]:.2f}) close={ea['close'].iloc[i]:.2f}")

        if abs(ea_trail[i] - our_trail[idx]) < 0.02:
            trail_match += 1

    print(f"  Direction: {dir_match}/{dir_total} ({100*dir_match/max(dir_total,1):.1f}%)")
    print(f"  Trail (<0.02): {trail_match}/{dir_total} ({100*trail_match/max(dir_total,1):.1f}%)")
    if mismatches:
        print(f"  Direction mismatches ({len(mismatches)}):")
        for m in mismatches[:15]:
            print(m)
        if len(mismatches) > 15:
            print(f"    ... and {len(mismatches)-15} more")
