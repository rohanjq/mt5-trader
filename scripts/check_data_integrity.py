"""Cross-check M2 native bars vs M1 resampled, and compare full ATR traces."""
import pandas as pd
import numpy as np
import pandas_ta as ta
from backtest.data_loader import load_ohlc
from backtest.indicators import resample_ohlc

BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"
df_m1 = load_ohlc(f"{BARS_DIR}/M1.csv")
df_m2_native = load_ohlc(f"{BARS_DIR}/M2.csv")
df_m2_resampled = resample_ohlc(df_m1, "M2")

# Compare around the critical time
t1 = pd.Timestamp("2026-06-09 17:36")
t2 = pd.Timestamp("2026-06-09 17:50")
native = df_m2_native[(df_m2_native["time"] >= t1) & (df_m2_native["time"] <= t2)].reset_index(drop=True)
resampled = df_m2_resampled[(df_m2_resampled["time"] >= t1) & (df_m2_resampled["time"] <= t2)].reset_index(drop=True)

print("NATIVE M2 bars:")
print(native[["time","open","high","low","close"]].to_string(index=False))
print()
print("RESAMPLED from M1:")
print(resampled[["time","open","high","low","close"]].to_string(index=False))
print()

# Full data comparison
merged = df_m2_native.merge(df_m2_resampled, on="time", suffixes=("_native", "_resampled"))
print(f"Total M2 bars: native={len(df_m2_native)}, resampled={len(df_m2_resampled)}, merged={len(merged)}")
if len(df_m2_native) != len(merged):
    # Find bars in native but not in resampled (or vice versa)
    native_only = df_m2_native[~df_m2_native["time"].isin(df_m2_resampled["time"])]
    resampled_only = df_m2_resampled[~df_m2_resampled["time"].isin(df_m2_native["time"])]
    if len(native_only) > 0:
        print(f"\n{len(native_only)} bars in NATIVE only:")
        print(native_only[["time","open","high","low","close"]].head(20).to_string(index=False))
    if len(resampled_only) > 0:
        print(f"\n{len(resampled_only)} bars in RESAMPLED only:")
        print(resampled_only[["time","open","high","low","close"]].head(20).to_string(index=False))

# Check OHLC differences
for col in ["open", "high", "low", "close"]:
    diff = (merged[f"{col}_native"] - merged[f"{col}_resampled"]).abs()
    n_diff = (diff > 0.001).sum()
    if n_diff > 0:
        print(f"\n{col}: {n_diff} bars differ (max diff={diff.max():.4f})")
        bad = merged[diff > 0.001][["time", f"{col}_native", f"{col}_resampled"]].head(10)
        print(bad.to_string(index=False))
    else:
        print(f"{col}: OK (max diff = {diff.max():.6f})")

# Now check: compute UTBot on resampled M2 vs native M2 — are trails different?
print("\n\n=== UTBot on native vs resampled M2 ===")
from backtest.indicators import compute_utbot

utbot_native = compute_utbot(df_m2_native)
utbot_resampled = compute_utbot(df_m2_resampled)

# Align by time
native_times = pd.to_datetime(df_m2_native["time"])
resampled_times = pd.to_datetime(df_m2_resampled["time"])

# Find where trails differ
target = pd.Timestamp("2026-06-09 17:46")
idx_native = int((native_times - target).abs().idxmin())
idx_resampled = int((resampled_times - target).abs().idxmin())

print(f"At {target}:")
print(f"  Native:    trail={utbot_native['closed_trail_stop'].iloc[idx_native]:.4f}, "
      f"bias={utbot_native['closed_bias'].iloc[idx_native]}")
print(f"  Resampled: trail={utbot_resampled['closed_trail_stop'].iloc[idx_resampled]:.4f}, "
      f"bias={utbot_resampled['closed_bias'].iloc[idx_resampled]}")

# Check if there's any trail difference anywhere in the run
n_common = min(len(utbot_native), len(utbot_resampled))
trail_n = utbot_native["closed_trail_stop"].values[:n_common].astype(float)
trail_r = utbot_resampled["closed_trail_stop"].values[:n_common].astype(float)
trail_diff = np.abs(trail_n - trail_r)
n_trail_diff = (trail_diff > 0.001).sum()
print(f"\nTrail differences > 0.001: {n_trail_diff} out of {n_common} bars")
if n_trail_diff > 0:
    first_diff = np.where(trail_diff > 0.001)[0][0]
    print(f"  First difference at bar {first_diff}: "
          f"native={trail_n[first_diff]:.4f}, resampled={trail_r[first_diff]:.4f}")
