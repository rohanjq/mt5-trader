"""Compare pandas_ta ATR vs manual Wilder ATR vs EA FULL dump ATR
at specific points to understand the true magnitude of the difference.

Focus on the Jun 9-11 window where we need exact match.
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from backtest.data_loader import load_ohlc

EA_DUMPS = "sampledata/ea_dumps"
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"

# Load M2 bars
df = load_ohlc(f"{BARS_DIR}/M2.csv")
close = df["close"].values
high = df["high"].values
low = df["low"].values
n = len(df)
times = pd.to_datetime(df["time"])

# Compute TR manually
tr = np.zeros(n)
tr[0] = high[0] - low[0]
for i in range(1, n):
    tr[i] = max(high[i] - low[i],
                 abs(high[i] - close[i-1]),
                 abs(low[i] - close[i-1]))

# Wilder ATR from scratch
wilder = np.zeros(n)
wilder[9] = np.mean(tr[:10])
for i in range(10, n):
    wilder[i] = (wilder[i-1] * 9 + tr[i]) / 10

# pandas_ta ATR
pta = ta.atr(df["high"], df["low"], df["close"], length=10).fillna(0).values

# Load EA full dump ATR
ea = pd.read_csv(f"{EA_DUMPS}/XAUUSD_utbot_trail_FULL_M2.csv", encoding="utf-16")
ea["time_dt"] = pd.to_datetime(ea["time"], format="%Y.%m.%d %H:%M")
ea["atr_num"] = pd.to_numeric(ea["atr"], errors="coerce")

# Build EA ATR lookup
ea_atr_map = {}
for _, row in ea.iterrows():
    if pd.notna(row["atr_num"]) and 0 < row["atr_num"] < 1000:
        ea_atr_map[row["time_dt"]] = row["atr_num"]

# Compare at key times (Jun 9 around the signal)
print("M2 ATR comparison at key times:")
print(f"{'Time':20s} {'Wilder':>10s} {'pandas_ta':>10s} {'EA':>10s} {'W-EA':>8s} {'W==pta':>8s}")
print("-" * 72)

key_times = [
    "2026-06-09 16:44", "2026-06-09 16:46", "2026-06-09 17:00",
    "2026-06-09 17:30", "2026-06-09 17:42", "2026-06-09 17:46",
    "2026-06-09 17:48", "2026-06-09 18:44",
    "2026-06-10 11:04", "2026-06-10 18:36",
    "2026-06-11 04:36", "2026-06-11 05:04",
]

for t_str in key_times:
    t = pd.Timestamp(t_str)
    idx = times.searchsorted(t)
    if idx >= n:
        continue
    if times.iloc[idx] != t:
        continue

    w = wilder[idx]
    p = pta[idx]
    e = ea_atr_map.get(t, float("nan"))
    w_eq_p = "YES" if abs(w - p) < 0.0001 else "NO"
    print(f"{t_str:20s} {w:10.4f} {p:10.4f} {e:10.2f} {w-e:8.4f} {w_eq_p:>8s}")

# Check: is pandas_ta using RMA (same as Wilder)?
# Look at the first 15 values
print("\nFirst 15 ATR values:")
print(f"{'Bar':>4s} {'TR':>10s} {'Wilder':>10s} {'pandas_ta':>10s} {'Diff':>10s}")
for i in range(15):
    print(f"{i:4d} {tr[i]:10.4f} {wilder[i]:10.4f} {pta[i]:10.4f} {wilder[i]-pta[i]:10.6f}")

# Overall: how far off is our ATR vs EA at the end of data?
print(f"\nATR at bar 29000 (late Jun 9):")
i = 29000
t = times.iloc[i]
e = ea_atr_map.get(t, float("nan"))
print(f"  Time: {t}")
print(f"  Wilder: {wilder[i]:.10f}")
print(f"  pandas_ta: {pta[i]:.10f}")
print(f"  EA (rounded): {e}")
print(f"  Wilder - pandas_ta: {wilder[i] - pta[i]:.10f}")
