"""Check where M2 UTBot signal diverges from EA."""
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc
from backtest.indicators import compute_utbot, forward_fill_to_m1

BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"

df_m2 = load_ohlc(f"{BARS_DIR}/M2.csv")
df_m1 = load_ohlc(f"{BARS_DIR}/M1.csv")
utbot = compute_utbot(df_m2)
utbot_ff = forward_fill_to_m1(utbot, df_m2["time"].values, df_m1["time"].values, freq="2min")

m1_times = pd.DatetimeIndex(df_m1["time"])

# EA reported utbot_M2.closed_signal=SELL at these times
triggers = [
    "2026-06-09 17:48", "2026-06-09 18:44", "2026-06-10 11:04",
    "2026-06-10 12:58", "2026-06-10 18:36", "2026-06-10 22:54",
    "2026-06-10 23:58", "2026-06-11 03:22", "2026-06-11 04:36",
    "2026-06-11 05:04", "2026-06-11 13:20",
]

print(f"{'Time':20s} {'Our Signal':12s} {'EA Signal':10s} {'Match':6s}")
print("-" * 55)
misses = 0
for t_str in triggers:
    t = pd.Timestamp(t_str)
    m1_t = t.floor("min")
    idx = m1_times.get_indexer([m1_t], method="ffill")[0]
    our_sig = str(utbot_ff["closed_signal"].iloc[idx])
    match = "OK" if our_sig == "SELL" else "MISS"
    if match == "MISS":
        misses += 1
    print(f"{t_str:20s} {our_sig:12s} {'SELL':10s} {match:6s}")

print(f"\nMatched: {len(triggers) - misses}/{len(triggers)}")

# Now find the FIRST M2 bar where our direction differs from what it should be
print("\n\n=== Trail path from 16:46 to 17:48 (where SELL fires) ===")
m2_times = pd.to_datetime(df_m2["time"])
close_arr = df_m2["close"].values
trail = utbot["closed_trail_stop"].values.astype(float)
bias = utbot["closed_bias"].values

# Show every bar from 16:44 to 17:48
start_t = pd.Timestamp("2026-06-09 16:44")
end_t = pd.Timestamp("2026-06-09 17:50")
mask = (m2_times >= start_t) & (m2_times <= end_t)
indices = np.where(mask)[0]

print(f"{'Time':20s} {'Close':>10s} {'Trail':>12s} {'Gap':>10s} {'Bias':8s} {'Signal':6s}")
print("-" * 72)
for i in indices:
    gap = close_arr[i] - trail[i]
    sig = utbot["closed_signal"].iloc[i]
    print(f"{str(m2_times[i]):20s} {close_arr[i]:10.2f} {trail[i]:12.4f} {gap:10.4f} {bias[i]:8s} {sig:6s}")

# The question: at 17:46, gap is only 0.82. If EA's trail was 0.83 higher,
# direction would be BEARISH. That means the trail accumulated an extra 0.83
# somewhere in the bullish run. This can happen if at some earlier bar in the
# run, the EA's trail ratcheted to a higher value because its ATR was slightly
# different (making close-nloss slightly higher).

# Check: what's the maximum ratchet value for the trail in this run?
print("\n\n=== Ratchet analysis for BULLISH run ===")
run_start_t = pd.Timestamp("2026-06-09 16:46")
run_start = int((m2_times - run_start_t).abs().idxmin())

# The trail ratchets up via: trail[i] = max(close[i] - nloss[i], trail[i-1])
# Find where the trail value was SET (not just carried forward)
nloss = 2.0 * utbot["closed_atr"].values.astype(float)
for i in range(run_start, indices[-1] + 1):
    candidate = close_arr[i] - nloss[i]
    if candidate >= trail[i] - 0.001:  # this bar set the trail
        print(f"  {m2_times[i]}: trail SET to {candidate:.4f} "
              f"(close={close_arr[i]:.2f} - nloss={nloss[i]:.4f})")

# If the EA's nloss was 0.83 LESS at any of these SET points, its trail
# would be 0.83 higher → enough to flip direction at 17:46
print(f"\n  Trail at 17:46: {trail[indices[-2]]:.4f}")
print(f"  If trail were {trail[indices[-2]] + 0.83:.4f}, close {close_arr[indices[-2]]:.2f} would be BELOW → BEARISH")

# KEY INSIGHT: The EA reports closed_signal=SELL at 17:48, meaning the
# CLOSED bar (17:46) has direction=BEARISH. In our data, 17:46 is BULLISH
# with gap of only 0.82. The EA's trail must be at least 4258.54.
# Our trail is 4257.71. Difference: 0.83.
# This 0.83 accumulates from a trail ratchet at some bar being higher
# because the EA's nloss (2*ATR) was lower by at least 0.83 at that bar.
# That requires ATR to be lower by 0.415.
# With ATR ~8.4, this is a 5% difference.
# ATR with period=10 and ~28000 bars of warmup should have 0% difference.
# UNLESS: the M2 bars themselves differ between what the EA saw live and
# what we downloaded after the fact.

# Let's check if there's a gap or missing bar in our data around the
# critical time
print("\n\n=== Checking for data gaps around divergence ===")
for i in range(max(0, run_start - 5), min(len(m2_times), indices[-1] + 3)):
    if i > 0:
        gap_min = (m2_times[i] - m2_times[i-1]).total_seconds() / 60
        if gap_min != 2:
            print(f"  GAP at {m2_times[i]}: {gap_min:.0f}min since prev bar")
