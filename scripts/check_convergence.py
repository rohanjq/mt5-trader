"""Find how much historical data we need for M2 UTBot trail to converge.

The trail is path-dependent. We need enough history so that ALL possible
initialization values converge to the same trail path by Jun 9.

Strategy: start the trail from different initial points and see how far
back we need to go before all initializations converge.
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from backtest.data_loader import load_ohlc

BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"
df_m2 = load_ohlc(f"{BARS_DIR}/M2.csv")
close = df_m2["close"].values
n = len(close)
times = pd.to_datetime(df_m2["time"])

# Compute ATR
atr_series = ta.atr(df_m2["high"], df_m2["low"], df_m2["close"], length=10)
atr_vals = atr_series.fillna(0).values
nloss = 2.0 * atr_vals

# Target: Jun 9 17:46
target = pd.Timestamp("2026-06-09 17:46")
target_idx = int((times - target).abs().idxmin())

# Compute trail from the very start (bar 0 = Apr 13)
def compute_trail_from(start_idx, init_dir=1.0):
    """Compute trail from start_idx with given initial direction."""
    trail = np.zeros(n)
    direction = np.ones(n)
    trail[start_idx] = close[start_idx]
    direction[start_idx] = init_dir
    for i in range(start_idx + 1, n):
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
    return trail, direction

# Compute with default (start=0, dir=BULL)
trail_bull, dir_bull = compute_trail_from(0, 1.0)
# Compute with opposite initial direction
trail_bear, dir_bear = compute_trail_from(0, -1.0)

# Find where they converge (same direction)
converge_idx = None
for i in range(1, n):
    if dir_bull[i] == dir_bear[i]:
        # Check if they STAY converged
        if all(dir_bull[i:i+100] == dir_bear[i:i+100]) if i+100 < n else True:
            converge_idx = i
            break

if converge_idx is not None:
    print(f"Trails converge permanently at bar {converge_idx}: {times[converge_idx]}")
    print(f"  That's {converge_idx} bars from start ({times[0]})")
    print(f"  ~{converge_idx * 2 / 60:.1f} hours of market time")
else:
    # Find all divergence points
    diverge_mask = dir_bull != dir_bear
    diverge_indices = np.where(diverge_mask)[0]
    if len(diverge_indices) > 0:
        last_diverge = diverge_indices[-1]
        print(f"Last direction divergence at bar {last_diverge}: {times[last_diverge]}")
        print(f"  Target is bar {target_idx}: {times[target_idx]}")
        print(f"  Bars between last diverge and target: {target_idx - last_diverge}")
        print(f"  That's {(target_idx - last_diverge) * 2 / 60:.1f} hours")
        
        # Show where divergences occur
        print(f"\nTotal divergent bars: {diverge_mask.sum()} out of {n}")
        # Show last 10 divergences before target
        pre_target = diverge_indices[diverge_indices < target_idx]
        if len(pre_target) > 0:
            print(f"\nLast 5 divergences before Jun 9 17:46:")
            for idx in pre_target[-5:]:
                print(f"  {times[idx]}: close={close[idx]:.2f} "
                      f"bull_trail={trail_bull[idx]:.2f}({'+' if dir_bull[idx]>0 else '-'}) "
                      f"bear_trail={trail_bear[idx]:.2f}({'+' if dir_bear[idx]>0 else '-'})")
    else:
        print("Trails are always identical regardless of initial direction!")

# Now check: does starting at different points WITHIN our data change the result?
# Start at bar 500, 1000, 5000, 10000, 20000 and check direction at target
print("\n\n=== Trail at Jun 9 17:46 with different start points ===")
print(f"{'Start Bar':>10s} {'Start Date':>20s} {'Dir at target':>15s} {'Trail at target':>16s}")
print("-" * 65)
for start in [0, 500, 1000, 2000, 5000, 10000, 15000, 20000, 25000]:
    if start >= target_idx:
        continue
    t, d = compute_trail_from(start, 1.0)
    dir_str = "BULL" if d[target_idx] > 0 else "BEAR"
    print(f"{start:10d} {str(times[start]):>20s} {dir_str:>15s} {t[target_idx]:>16.4f}")
    # Also try starting BEARISH
    t2, d2 = compute_trail_from(start, -1.0)
    dir_str2 = "BULL" if d2[target_idx] > 0 else "BEAR"
    if dir_str != dir_str2:
        print(f"{'':10s} {'(init BEAR)':>20s} {dir_str2:>15s} {t2[target_idx]:>16.4f}  ← DIFFERS!")
