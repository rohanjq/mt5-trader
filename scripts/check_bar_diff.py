"""Check if EA and our data have different M2 bars (missing/extra)."""
import pandas as pd
from backtest.data_loader import load_ohlc

ea = pd.read_csv("sampledata/ea_dumps/XAUUSD_utbot_trail_FULL_M2.csv", encoding="utf-16")
ea["time_dt"] = pd.to_datetime(ea["time"], format="%Y.%m.%d %H:%M")

df = load_ohlc("sampledata/XAUUSD_bars_20260413_20260612/M2.csv")
df_times = pd.to_datetime(df["time"])

our_start = df_times.iloc[0]
our_end = df_times.iloc[-1]
ea_overlap = ea[(ea["time_dt"] >= our_start) & (ea["time_dt"] <= our_end)]

print(f"Our bars: {len(df)}")
print(f"EA bars in overlap: {len(ea_overlap)}")
print(f"Difference: {len(ea_overlap) - len(df)}")

ea_set = set(ea_overlap["time_dt"])
our_set = set(df_times)
ea_only = sorted(ea_set - our_set)
our_only = sorted(our_set - ea_set)
print(f"Bars in EA only: {len(ea_only)}")
print(f"Bars in our data only: {len(our_only)}")
if ea_only:
    print("First 20 EA-only bars:")
    for t in ea_only[:20]:
        print(f"  {t}")
if our_only:
    print("First 20 our-only bars:")
    for t in our_only[:20]:
        print(f"  {t}")
