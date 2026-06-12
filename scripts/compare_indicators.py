"""Compare indicator values at each live trade time vs BT computation.

Parses the live log to extract indicator values reported at trade time,
then computes the same indicators from our M1 data and forward-fill to
see what the BT would have at that same M1 bar.
"""
import re
import pandas as pd
import numpy as np
from backtest.data_loader import load_ohlc
from backtest.indicators import (
    resample_ohlc, compute_utbot, compute_ema, compute_vwap,
    compute_dc, compute_candle, forward_fill_to_m1,
)

# ── Parse live log ───────────────────────────────────────────────────────
LOG_PATH = "logs/live_2026-06-09_to_2026-06-11.log"
TRIGGER_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] trade\.initiator: "
    r"Rule (\S+) triggered: (BUY|SELL) — (.+)$"
)

live_trades = []
with open(LOG_PATH) as f:
    for line in f:
        m = TRIGGER_RE.match(line.strip())
        if m:
            time_str, rule, direction, conditions = m.groups()
            # Parse conditions like "utbot_M2.closed_signal=SELL, ema50_M5.closed_price_vs_ema=BELOW"
            conds = {}
            for part in conditions.split(", "):
                k, v = part.split("=", 1)
                conds[k] = v
            live_trades.append({
                "time": pd.Timestamp(time_str),
                "rule": rule,
                "dir": direction,
                "conditions": conds,
            })

print(f"Parsed {len(live_trades)} live trade triggers\n")

# ── Compute indicators ──────────────────────────────────────────────────
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"
df_m1 = load_ohlc(f"{BARS_DIR}/M1.csv")
m1_times = df_m1["time"].values

# TF map for forward-fill
TF_MAP = {"M2": "2min", "M3": "3min", "M5": "5min", "M10": "10min",
           "M15": "15min", "M30": "30min", "M45": "45min", "H1": "60min"}

# Load native bars where available, else resample
def get_tf_bars(tf_str):
    import os
    native_path = f"{BARS_DIR}/{tf_str}.csv"
    if os.path.exists(native_path):
        return load_ohlc(native_path)
    return resample_ohlc(df_m1, tf_str)

# Compute indicators for each TF we need
indicators = {}

for tf_str, freq in TF_MAP.items():
    df_htf = get_tf_bars(tf_str)
    utbot = compute_utbot(df_htf)
    utbot_ff = forward_fill_to_m1(utbot, df_htf["time"].values, m1_times, freq=freq)
    for col in utbot.columns:
        indicators[f"utbot_{tf_str}.{col}"] = utbot_ff[col].values

# EMA
for tf_str in ["M5"]:
    df_htf = get_tf_bars(tf_str)
    for period in [50]:
        ema = compute_ema(df_htf, period)
        freq_s = TF_MAP[tf_str]
        ema_ff = forward_fill_to_m1(ema, df_htf["time"].values, m1_times, freq=freq_s)
        for col in ema.columns:
            indicators[f"ema{period}_{tf_str}.{col}"] = ema_ff[col].values

# VWAP M1
vwap = compute_vwap(df_m1)
for col in vwap.columns:
    indicators[f"vwap_M1.{col}"] = vwap[col].values

# DC
for tf_str in ["M5", "M15"]:
    df_htf = get_tf_bars(tf_str)
    dc = compute_dc(df_htf)
    freq_s = TF_MAP[tf_str]
    dc_ff = forward_fill_to_m1(dc, df_htf["time"].values, m1_times, freq=freq_s)
    for col in dc.columns:
        indicators[f"dc_{tf_str}.{col}"] = dc_ff[col].values

# Candle
for tf_str in ["M3", "M5"]:
    df_htf = get_tf_bars(tf_str)
    candle = compute_candle(df_htf)
    freq_s = TF_MAP[tf_str]
    candle_ff = forward_fill_to_m1(candle, df_htf["time"].values, m1_times, freq=freq_s)
    for col in candle.columns:
        indicators[f"candle_{tf_str}.{col}"] = candle_ff[col].values

# Build M1 time index
m1_time_idx = pd.DatetimeIndex(m1_times)

# ── Compare each live trade ─────────────────────────────────────────────
print("=" * 140)
print(f"{'Time':20s} {'Rule':35s} {'Condition':45s} {'Live':>10s} {'BT':>10s} {'Match':>6s}")
print("-" * 140)

total_checks = 0
total_matches = 0

for trade in live_trades:
    # Find the M1 bar at trade time (floor to minute)
    trade_m1 = trade["time"].floor("min")

    # Find M1 index
    m1_idx = m1_time_idx.get_indexer([trade_m1], method="ffill")[0]
    if m1_idx < 0:
        print(f"{trade['time']}  {trade['rule']:35s}  M1 bar not found!")
        continue

    for cond_key, live_val in trade["conditions"].items():
        total_checks += 1
        bt_val = "?"

        if cond_key in indicators:
            raw = indicators[cond_key][m1_idx]
            if isinstance(raw, (float, np.floating)):
                if np.isnan(raw):
                    bt_val = "NaN"
                else:
                    bt_val = f"{raw:.2f}" if raw != int(raw) else str(int(raw))
            else:
                bt_val = str(raw)

        match = "OK" if bt_val.upper() == live_val.upper() else "MISS"
        if match == "OK":
            total_matches += 1

        # Only print mismatches
        if match != "OK":
            print(f"{str(trade['time']):20s} {trade['rule']:35s} {cond_key:45s} {live_val:>10s} {bt_val:>10s} {match:>6s}")

print("-" * 140)
print(f"Total condition checks: {total_checks}, Matches: {total_matches}, "
      f"Mismatches: {total_checks - total_matches}")
print(f"Match rate: {total_matches/total_checks*100:.1f}%")
