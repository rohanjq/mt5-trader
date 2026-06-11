"""Compare M1 candles built from ticks vs MT5 server M1 bars.

If these differ, indicator values will differ, causing trade divergence.
"""
import pandas as pd
import numpy as np
from backtest.tick_builder import CandleBuilder
from backtest.data_loader import load_ohlc

# Load server M1 bars
server = load_ohlc("sampledata/XAUUSD_M1_combined.csv")
print(f"Server M1: {len(server)} bars")
print(f"  {server['time'].iloc[0]} → {server['time'].iloc[-1]}")

# Load ticks and build M1
ticks = pd.read_csv("sampledata/XAUUSD_ticks_20260604_20260611.csv")
ticks["time"] = pd.to_datetime(ticks["time"])
print(f"\nTicks: {len(ticks):,}")

builder = CandleBuilder(1)
for i in range(len(ticks)):
    t = ticks["time"].iloc[i].to_pydatetime()
    builder.on_tick(t, float(ticks["bid"].iloc[i]))
builder.finalize()

tick_m1 = builder.to_dataframe()
tick_m1["time"] = pd.to_datetime(tick_m1["time"])
print(f"Tick M1: {len(tick_m1)} bars")
print(f"  {tick_m1['time'].iloc[0]} → {tick_m1['time'].iloc[-1]}")

# Find overlapping time range
overlap_start = max(server["time"].iloc[0], tick_m1["time"].iloc[0])
overlap_end = min(server["time"].iloc[-1], tick_m1["time"].iloc[-1])
print(f"\nOverlap: {overlap_start} → {overlap_end}")

srv = server[(server["time"] >= overlap_start) & (server["time"] <= overlap_end)].set_index("time")
tkm = tick_m1[(tick_m1["time"] >= overlap_start) & (tick_m1["time"] <= overlap_end)].set_index("time")

# Find common times
common = srv.index.intersection(tkm.index)
print(f"Common bars: {len(common)}")
print(f"Server-only bars: {len(srv.index.difference(tkm.index))}")
print(f"Tick-only bars: {len(tkm.index.difference(srv.index))}")

# Compare OHLC on common bars
if len(common) > 0:
    s = srv.loc[common]
    t = tkm.loc[common]
    
    for col in ["open", "high", "low", "close"]:
        diff = (s[col] - t[col]).abs()
        n_mismatch = (diff > 0.01).sum()
        max_diff = diff.max()
        mean_diff = diff.mean()
        print(f"\n{col.upper():5s}: {n_mismatch:5d} mismatches (>{0.01}), max={max_diff:.2f}, mean={mean_diff:.4f}")
        
        # Show worst mismatches
        if n_mismatch > 0:
            worst = diff.nlargest(5)
            for ts, d in worst.items():
                print(f"  {ts}: server={s.loc[ts, col]:.2f} tick={t.loc[ts, col]:.2f} diff={d:.2f}")

    # Focus on the critical trading window
    print("\n" + "=" * 80)
    print("CRITICAL WINDOW: Jun 9 17:00 → Jun 11 00:00")
    window = common[(common >= "2026-06-09 17:00") & (common <= "2026-06-11 00:00")]
    sw = srv.loc[window]
    tw = tkm.loc[window]
    
    for col in ["open", "high", "low", "close"]:
        diff = (sw[col] - tw[col]).abs()
        n_mismatch = (diff > 0.01).sum()
        max_diff = diff.max()
        print(f"  {col.upper():5s}: {n_mismatch} mismatches, max_diff={max_diff:.2f}")
