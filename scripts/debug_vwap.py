"""Debug VWAP mismatches at 2026-06-10 13:48 and 2026-06-11 05:04."""
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc
from backtest.indicators import compute_vwap

df_m1 = load_ohlc('sampledata/XAUUSD_bars_20260413_20260612/M1.csv')
vwap = compute_vwap(df_m1)

m1_times = pd.DatetimeIndex(df_m1['time'])

for t_str in ['2026-06-10 13:48', '2026-06-11 05:04']:
    t = pd.Timestamp(t_str)
    idx = m1_times.get_indexer([t], method='ffill')[0]
    
    print(f"\n=== {t_str} ===")
    # Show a few bars around the mismatch
    for offset in range(-3, 4):
        i = idx + offset
        if i < 0 or i >= len(df_m1):
            continue
        close = df_m1['close'].iloc[i]
        vwap_val = vwap['closed_price_vs_vwap'].iloc[i]
        time = m1_times[i]
        marker = " <-- trade" if offset == 0 else ""
        print(f"  {time}: close={close:.2f} vwap_pos={vwap_val}{marker}")
    
    # What's the raw VWAP value?
    close = df_m1['close'].iloc[idx]
    # Check if we have the raw vwap value
    if 'vwap_value' in vwap.columns:
        vwap_v = vwap['vwap_value'].iloc[idx]
        print(f"  VWAP value: {vwap_v:.2f}, Close: {close:.2f}, Diff: {close - vwap_v:.2f}")

# Also check the EA's VWAP signal dump
ea_vwap = pd.read_csv('sampledata/ea_dumps/signals/XAUUSD_vwap_M1.csv', encoding='utf-16')
print("\nEA VWAP M1 signal dump:")
print(ea_vwap.to_string())
