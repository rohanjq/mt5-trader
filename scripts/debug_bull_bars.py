"""Quick debug of consecutive_bull_bars at mismatch points."""
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc
from backtest.indicators import compute_utbot, forward_fill_to_m1

df_m5 = load_ohlc('sampledata/XAUUSD_bars_20260413_20260612/M5.csv')
for enc in ('utf-8-sig', 'utf-16', 'latin-1'):
    try:
        ea = pd.read_csv('sampledata/ea_dumps/XAUUSD_utbot_trail_FULL_M5.csv', encoding=enc)
        break
    except Exception:
        continue
ea['time_dt'] = pd.to_datetime(ea['time'], format='%Y.%m.%d %H:%M')
ea['atr_num'] = pd.to_numeric(ea['atr'], errors='coerce')
bar_times = pd.to_datetime(df_m5['time'])
ea_atr_map = dict(zip(ea['time_dt'], ea['atr_num']))
ea_atr_arr = np.array([ea_atr_map.get(t, np.nan) for t in bar_times])
ea_atr_arr = pd.Series(ea_atr_arr).ffill().bfill().values
utbot = compute_utbot(df_m5, ea_atr=ea_atr_arr)

df_m1 = load_ohlc('sampledata/XAUUSD_bars_20260413_20260612/M1.csv')
m1_times = df_m1['time'].values
utbot_ff = forward_fill_to_m1(utbot, df_m5['time'].values, m1_times, freq='5min')
m1_time_idx = pd.DatetimeIndex(m1_times)

# Check the EA signal dump for consecutive_bull_bars
ea_sig = pd.read_csv('sampledata/ea_dumps/signals/XAUUSD_utbot_M5.csv', encoding='utf-16')
print("EA signal M5 columns:", ea_sig.columns.tolist())
print(ea_sig.to_string())
print()

for t_str, live_val in [('2026-06-09 18:44', 18), ('2026-06-10 11:04', 4),
                          ('2026-06-10 22:54', 4), ('2026-06-11 05:04', 25)]:
    t = pd.Timestamp(t_str)
    m1_idx = m1_time_idx.get_indexer([t], method='ffill')[0]
    bt_val = int(utbot_ff['consecutive_bull_bars'].iloc[m1_idx])
    m5_bar_idx = bar_times.searchsorted(t, side='right') - 1
    m5_t = bar_times.iloc[m5_bar_idx]
    m5_bull = int(utbot['consecutive_bull_bars'].iloc[m5_bar_idx])
    print(f'{t_str}: Live={live_val} BT_ff={bt_val} M5_bar={m5_t} M5_bull={m5_bull}')
