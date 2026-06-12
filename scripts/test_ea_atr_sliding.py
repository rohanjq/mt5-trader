"""Use EA's FULL dump ATR values for our sliding 500-bar trail computation.

Since the ATR from iATR has full broker history warmup, using it directly
should give us near-exact match with the EA's 500-bar trail.
"""
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc

EA_DUMPS = "sampledata/ea_dumps"
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"

for tf in ["M2", "M3", "M5"]:
    print(f"\n{'='*70}")
    print(f"  {tf}: EA ATR + sliding 500-bar window")
    print(f"{'='*70}")

    # Load EA FULL dump for ATR values
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

    # Load EA 500-bar dump (ground truth for comparison)
    path_500 = f"{EA_DUMPS}/XAUUSD_utbot_trail_{tf}.csv"
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            ea_500 = pd.read_csv(path_500, encoding=enc)
            if "time" in ea_500.columns:
                break
        except Exception:
            continue
    ea_500["time_dt"] = pd.to_datetime(ea_500["time"], format="%Y.%m.%d %H:%M")
    ea_500_dir = ea_500["direction"].values.astype(float)
    ea_500_trail = ea_500["trail_stop"].values.astype(float)
    ea_500_times = ea_500["time_dt"].values

    # Load our bars
    df = load_ohlc(f"{BARS_DIR}/{tf}.csv")
    df_times = pd.to_datetime(df["time"])
    close = df["close"].values
    n = len(df)

    # Build ATR array using EA's FULL dump values
    ea_atr_map = dict(zip(ea_full["time_dt"], ea_full["atr_num"]))
    ea_atr_for_our = np.zeros(n)
    for i in range(n):
        t = df_times.iloc[i]
        if t in ea_atr_map:
            v = ea_atr_map[t]
            if np.isfinite(v) and v > 0 and v < 1000:
                ea_atr_for_our[i] = v

    # Check how many we got
    valid = (ea_atr_for_our > 0).sum()
    print(f"  Got EA ATR for {valid}/{n} bars")

    # Fill zeros with interpolation from neighbors (for bars where EA ATR was inf/garbage)
    for i in range(n):
        if ea_atr_for_our[i] == 0 and i > 0:
            ea_atr_for_our[i] = ea_atr_for_our[i-1]

    nloss = 2.0 * ea_atr_for_our

    # Compute trail with sliding 500-bar window using EA ATR
    trail_stop = np.zeros(n)
    direction = np.ones(n)

    for end in range(n):
        start = max(0, end - 499)
        wlen = end - start + 1
        init_len = min(10, wlen)

        w_trail = np.empty(wlen)
        w_dir = np.empty(wlen)

        for j in range(init_len):
            w_trail[j] = close[start + j]
            w_dir[j] = 1.0

        for j in range(init_len, wlen):
            gi = start + j
            prev = w_trail[j-1]
            prev_d = w_dir[j-1]

            if close[gi] > prev:
                w_trail[j] = close[gi] - nloss[gi]
                if prev_d > 0:
                    w_trail[j] = max(w_trail[j], prev)
                w_dir[j] = 1.0
            else:
                w_trail[j] = close[gi] + nloss[gi]
                if prev_d < 0:
                    w_trail[j] = min(w_trail[j], prev)
                w_dir[j] = -1.0

        trail_stop[end] = w_trail[-1]
        direction[end] = w_dir[-1]

    # Compare against EA's 500-bar dump
    our_idx = pd.DatetimeIndex(df_times)
    dir_match = 0
    dir_total = 0
    trail_close = 0
    mismatches = []

    for i in range(len(ea_500)):
        t = ea_500_times[i]
        idx = our_idx.get_indexer([t], method=None)[0]
        if idx < 0:
            continue
        dir_total += 1

        ea_d = ea_500_dir[i]
        bt_d = direction[idx]
        if (ea_d > 0) == (bt_d > 0):
            dir_match += 1
        else:
            mismatches.append(f"    {t}: close={close[idx]:.2f} EA trail={ea_500_trail[i]:.2f} BT trail={trail_stop[idx]:.2f}")

        if abs(ea_500_trail[i] - trail_stop[idx]) < 0.1:
            trail_close += 1

    print(f"  Direction: {dir_match}/{dir_total} ({100*dir_match/max(dir_total,1):.1f}%)")
    print(f"  Trail (<0.1): {trail_close}/{dir_total} ({100*trail_close/max(dir_total,1):.1f}%)")
    if mismatches:
        print(f"  Mismatches ({len(mismatches)}):")
        for m in mismatches[:10]:
            print(m)
        if len(mismatches) > 10:
            print(f"    ... and {len(mismatches)-10} more")
