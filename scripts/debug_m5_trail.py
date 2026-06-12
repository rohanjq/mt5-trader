"""Debug M5 trail divergence between EA FULL dump and our sliding window."""
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc
from backtest.indicators import compute_utbot

# Load EA FULL M5 trail
for enc in ('utf-8-sig', 'utf-16', 'latin-1'):
    try:
        ea = pd.read_csv('sampledata/ea_dumps/XAUUSD_utbot_trail_FULL_M5.csv', encoding=enc)
        break
    except Exception:
        continue
ea['time_dt'] = pd.to_datetime(ea['time'], format='%Y.%m.%d %H:%M')
ea['atr_num'] = pd.to_numeric(ea['atr'], errors='coerce')
ea['trail_num'] = pd.to_numeric(ea['trail_stop'], errors='coerce')
ea['dir_num'] = pd.to_numeric(ea['direction'], errors='coerce')

# Load our M5 bars
df_m5 = load_ohlc('sampledata/XAUUSD_bars_20260413_20260612/M5.csv')

# Get EA ATR for our bars
bar_times = pd.to_datetime(df_m5['time'])
ea_lookup = {t: (a, tr, d) for t, a, tr, d in
             zip(ea['time_dt'], ea['atr_num'], ea['trail_num'], ea['dir_num'])}
ea_atr_arr = np.array([ea_lookup.get(t, (np.nan, 0, 0))[0] for t in bar_times])
matched = np.count_nonzero(~np.isnan(ea_atr_arr))
ea_atr_arr = pd.Series(ea_atr_arr).ffill().bfill().values
print(f'EA ATR matched: {matched}/{len(df_m5)}')

# Compute UTBot with EA ATR using our sliding window
utbot = compute_utbot(df_m5, ea_atr=ea_atr_arr)

# Compare direction at key times around mismatches
# The mismatches are at consecutive_bull_bars for M5
# Let's find where EA FULL direction differs from our computation
print("\nDirection mismatches (EA FULL vs our sliding window):")
print(f"{'Time':20s} {'Close':>10s} {'EA_dir':>7s} {'BT_dir':>7s} {'EA_trail':>12s} {'BT_trail':>12s}")
print("-" * 80)

n_mismatch = 0
for i in range(len(df_m5)):
    t = bar_times.iloc[i]
    if t not in ea_lookup:
        continue
    ea_atr_v, ea_trail, ea_dir = ea_lookup[t]
    bt_dir_str = utbot['closed_bias'].iloc[i]
    bt_dir = 1 if bt_dir_str == 'BULLISH' else -1
    
    if ea_dir != bt_dir:
        close = df_m5['close'].iloc[i]
        # Get our trail from the raw arrays if available
        bt_trail = 0  # we don't output trail_stop in compute_utbot result directly
        print(f"{str(t):20s} {close:10.2f} {int(ea_dir):7d} {bt_dir:7d} {ea_trail:12.4f}")
        n_mismatch += 1

print(f"\nTotal direction mismatches: {n_mismatch} out of {len(df_m5)}")

# Focus on the trade-relevant times
print("\n\nDirection at trade-relevant M5 bars:")
trade_times = [
    '2026-06-09 18:40', '2026-06-09 18:45',
    '2026-06-10 08:35', '2026-06-10 08:40', '2026-06-10 08:45',
    '2026-06-10 11:00', '2026-06-10 11:05',
    '2026-06-10 22:50', '2026-06-10 22:55',
    '2026-06-11 05:00', '2026-06-11 05:05',
    '2026-06-11 07:00',
]
print(f"{'Time':20s} {'Close':>10s} {'EA_dir':>7s} {'BT_dir':>12s} {'EA_trail':>12s}")
print("-" * 70)
for t_str in trade_times:
    t = pd.Timestamp(t_str)
    idx = bar_times.searchsorted(t)
    if idx >= len(bar_times):
        continue
    bt = bar_times.iloc[idx]
    close = df_m5['close'].iloc[idx]
    bt_dir = utbot['closed_bias'].iloc[idx]
    if bt in ea_lookup:
        ea_atr_v, ea_trail, ea_dir = ea_lookup[bt]
        print(f"{str(bt):20s} {close:10.2f} {int(ea_dir):7d} {bt_dir:>12s} {ea_trail:12.4f}")
    else:
        print(f"{str(bt):20s} {close:10.2f} {'?':>7s} {bt_dir:>12s}")
