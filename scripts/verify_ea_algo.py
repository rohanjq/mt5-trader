"""Use EA's own ATR values to recompute trail — should match EA perfectly.

This confirms the algorithm is correct. Then we know the only issue is
that our ATR computation differs from iATR (full history warmup).
"""
import pandas as pd
import numpy as np

EA_DUMPS = "sampledata/ea_dumps"

for tf in ["M2", "M3", "M5"]:
    print(f"\n{'='*70}")
    print(f"  {tf}: Recompute trail using EA's ATR values")
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

    close = ea["close"].values.astype(float)
    ea_atr = pd.to_numeric(ea["atr"], errors="coerce").values
    ea_nloss = pd.to_numeric(ea["nloss"], errors="coerce").values
    ea_trail = ea["trail_stop"].values.astype(float)
    ea_dir = ea["direction"].values.astype(float)
    n = len(ea)

    # Recompute using EA's ATR
    nloss = 2.0 * ea_atr  # should match ea_nloss
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

    # Compare
    dir_match = np.sum((direction > 0) == (ea_dir > 0))
    trail_diff = np.abs(trail - ea_trail)
    trail_match = np.sum(trail_diff < 0.02)

    print(f"  Direction matches: {dir_match}/{n} ({100*dir_match/n:.1f}%)")
    print(f"  Trail matches (<0.02): {trail_match}/{n} ({100*trail_match/n:.1f}%)")

    if dir_match < n:
        mismatches = np.where((direction > 0) != (ea_dir > 0))[0]
        print(f"  First 5 direction mismatches:")
        for idx in mismatches[:5]:
            d_ea = "BULL" if ea_dir[idx] > 0 else "BEAR"
            d_bt = "BULL" if direction[idx] > 0 else "BEAR"
            print(f"    bar {idx} ({ea['time'].iloc[idx]}): close={close[idx]:.2f} "
                  f"EA={d_ea}(trail={ea_trail[idx]:.4f}) "
                  f"recomp={d_bt}(trail={trail[idx]:.4f}) "
                  f"nloss_ea={ea_nloss[idx]:.4f} nloss_calc={nloss[idx]:.4f}")

    # Also check nloss
    nloss_diff = np.abs(nloss - ea_nloss)
    nloss_bad = np.sum(nloss_diff > 0.01)
    print(f"  nloss mismatches (>0.01): {nloss_bad}/{n}")
    if nloss_bad > 0:
        first = np.argmax(nloss_diff > 0.01)
        print(f"    First at bar {first}: calc={nloss[first]:.4f} ea={ea_nloss[first]:.4f}")
