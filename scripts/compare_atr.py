"""Compare our ATR vs EA's ATR to find where they converge.

The EA uses iATR(full broker history). We use pandas_ta.atr(our 2 months).
We need to find how much our ATR differs and how to fix it.
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from backtest.data_loader import load_ohlc

EA_DUMPS = "sampledata/ea_dumps"
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"

for tf in ["M2", "M3", "M5"]:
    print(f"\n{'='*70}")
    print(f"  {tf}: ATR comparison")
    print(f"{'='*70}")

    # Load EA FULL trail (has ATR for every bar)
    path = f"{EA_DUMPS}/XAUUSD_utbot_trail_FULL_{tf}.csv"
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            ea = pd.read_csv(path, encoding=enc)
            if "time" in ea.columns:
                break
        except Exception:
            continue

    ea["time_dt"] = pd.to_datetime(ea["time"], format="%Y.%m.%d %H:%M")
    ea["atr_num"] = pd.to_numeric(ea["atr"], errors="coerce")

    # Load our bars and compute ATR
    df = load_ohlc(f"{BARS_DIR}/{tf}.csv")
    df_times = pd.to_datetime(df["time"])
    our_atr = ta.atr(df["high"], df["low"], df["close"], length=10).fillna(0).values

    # Find overlap
    ea_valid = ea[ea["atr_num"].notna() & (ea["atr_num"] < 1000) & (ea["atr_num"] > 0)].reset_index(drop=True)

    # Match by time
    our_idx = pd.DatetimeIndex(df_times)
    ea_times = ea_valid["time_dt"].values
    ea_atr = ea_valid["atr_num"].values

    diffs = []
    for i in range(len(ea_valid)):
        t = ea_times[i]
        idx = our_idx.get_indexer([t], method=None)[0]
        if idx < 0:
            continue
        diff = abs(our_atr[idx] - ea_atr[i])
        diffs.append((idx, t, our_atr[idx], ea_atr[i], diff))

    if not diffs:
        print("  No overlapping bars found")
        continue

    diffs_arr = np.array([d[4] for d in diffs])
    print(f"  Overlapping bars: {len(diffs)}")
    print(f"  Max ATR diff: {diffs_arr.max():.6f}")
    print(f"  Mean ATR diff: {diffs_arr.mean():.6f}")

    # When does ATR converge to < 0.01?
    converge_idx = None
    for i, (idx, t, our, ea_v, diff) in enumerate(diffs):
        if diff < 0.01:
            # Check if stays converged
            remaining = diffs_arr[i:]
            if remaining.max() < 0.05:
                converge_idx = i
                break

    if converge_idx is not None:
        _, t, _, _, _ = diffs[converge_idx]
        print(f"  ATR converges (<0.01, stays <0.05) at bar {converge_idx}: {t}")
        print(f"    That's {converge_idx} bars into our data")
    else:
        # Show how the diff changes over time
        print(f"\n  ATR diff profile (every 1000 bars):")
        for i in range(0, len(diffs), 1000):
            idx, t, our, ea_v, diff = diffs[i]
            print(f"    bar {idx:6d} ({t}): our={our:.4f} ea={ea_v:.4f} diff={diff:.4f}")
        # last bar
        idx, t, our, ea_v, diff = diffs[-1]
        print(f"    bar {idx:6d} ({t}): our={our:.4f} ea={ea_v:.4f} diff={diff:.4f}")

    # Show first 20 and last 20 diffs
    print(f"\n  First 10 bars:")
    for idx, t, our, ea_v, diff in diffs[:10]:
        print(f"    {t}: our={our:.4f} ea={ea_v:.4f} diff={diff:.4f}")
    print(f"\n  Last 10 bars:")
    for idx, t, our, ea_v, diff in diffs[-10:]:
        print(f"    {t}: our={our:.4f} ea={ea_v:.4f} diff={diff:.4f}")
