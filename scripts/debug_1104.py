"""Debug the 11:04 case where BT says 0 consecutive bull bars but live says 4."""
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc
from backtest.indicators import compute_utbot

df_m5 = load_ohlc('sampledata/XAUUSD_bars_20260413_20260612/M5.csv')
for enc in ('utf-8-sig', 'utf-16', 'latin-1'):
    try:
        ea = pd.read_csv('sampledata/ea_dumps/XAUUSD_utbot_trail_FULL_M5.csv', encoding=enc)
        break
    except Exception:
        continue
ea['time_dt'] = pd.to_datetime(ea['time'], format='%Y.%m.%d %H:%M')
ea['atr_num'] = pd.to_numeric(ea['atr'], errors='coerce')
ea['dir_num'] = pd.to_numeric(ea['direction'], errors='coerce')
ea['trail_num'] = pd.to_numeric(ea['trail_stop'], errors='coerce')
bar_times = pd.to_datetime(df_m5['time'])
ea_atr_map = dict(zip(ea['time_dt'], ea['atr_num']))
ea_dir_map = dict(zip(ea['time_dt'], ea['dir_num']))
ea_trail_map = dict(zip(ea['time_dt'], ea['trail_num']))
ea_atr_arr = np.array([ea_atr_map.get(t, np.nan) for t in bar_times])
ea_atr_arr = pd.Series(ea_atr_arr).ffill().bfill().values
utbot = compute_utbot(df_m5, ea_atr=ea_atr_arr)

# Look at bars around 2026-06-10 10:45 to 11:15
center = bar_times.searchsorted(pd.Timestamp('2026-06-10 11:00'))
print(f"{'Time':22s} {'Close':>8s} {'BT_bias':>10s} {'EA_dir':>7s} {'BT_trail':>10s} {'EA_trail':>10s} {'BT_bull':>8s}")
print("-" * 85)
for idx in range(center - 5, center + 5):
    if idx < 0 or idx >= len(bar_times):
        continue
    t = bar_times.iloc[idx]
    close = df_m5['close'].iloc[idx]
    bt_bias = utbot['closed_bias'].iloc[idx]
    bt_trail = utbot['closed_trail_stop'].iloc[idx]
    bt_bull = int(utbot['consecutive_bull_bars'].iloc[idx])
    ea_d = ea_dir_map.get(t, 0)
    ea_t = ea_trail_map.get(t, 0)
    print(f"{str(t):22s} {close:8.2f} {bt_bias:>10s} {int(ea_d):7d} {bt_trail:10.4f} {ea_t:10.4f} {bt_bull:8d}")

# Also check: the trade was at 11:04 which means the M5 bar 11:00 was still running
# and the CLOSED bar was 10:55. What was the live EA's state at that trade time?
print("\n\nThe live trade at 11:04 uses:")
print("  Running bar: 11:00 (still forming)")
print("  Closed bar: 10:55")
idx_1055 = bar_times.searchsorted(pd.Timestamp('2026-06-10 10:55'))
idx_1100 = bar_times.searchsorted(pd.Timestamp('2026-06-10 11:00'))
for idx in [idx_1055, idx_1100]:
    t = bar_times.iloc[idx]
    close = df_m5['close'].iloc[idx]
    bt_bias = utbot['closed_bias'].iloc[idx]
    bt_trail = utbot['closed_trail_stop'].iloc[idx]
    bt_bull = int(utbot['consecutive_bull_bars'].iloc[idx])
    ea_d = ea_dir_map.get(t, 0)
    ea_t = ea_trail_map.get(t, 0)
    print(f"  {str(t):22s} close={close:.2f} bt_bias={bt_bias} ea_dir={int(ea_d)} bt_trail={bt_trail:.4f} ea_trail={ea_t:.4f} bt_bull={bt_bull}")
