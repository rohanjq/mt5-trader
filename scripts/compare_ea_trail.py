"""Compare EA's UTBot trail dump vs our backtester's trail computation.

Loads the EA's FULL trail dump and our computed trail, finds where they diverge.
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from backtest.data_loader import load_ohlc
from backtest.indicators import compute_utbot

EA_DUMPS = "sampledata/ea_dumps"
BARS_DIR = "sampledata/XAUUSD_bars_20260413_20260612"


def load_ea_trail(tf: str) -> pd.DataFrame:
    """Load EA trail dump CSV (handles UTF-16 BOM)."""
    path = f"{EA_DUMPS}/XAUUSD_utbot_trail_FULL_{tf}.csv"
    # Try different encodings
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc)
            if "time" in df.columns:
                return df
        except Exception:
            continue
    raise ValueError(f"Cannot read {path}")


def load_ea_trail_500(tf: str) -> pd.DataFrame:
    """Load EA 500-bar trail dump."""
    path = f"{EA_DUMPS}/XAUUSD_utbot_trail_{tf}.csv"
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc)
            if "time" in df.columns:
                return df
        except Exception:
            continue
    raise ValueError(f"Cannot read {path}")


for tf in ["M2", "M3", "M5"]:
    print(f"\n{'='*80}")
    print(f"  {tf} TRAIL COMPARISON")
    print(f"{'='*80}")

    # Load EA trails
    try:
        ea_full = load_ea_trail(tf)
    except Exception as e:
        print(f"  Cannot load FULL trail: {e}")
        continue
    ea_500 = load_ea_trail_500(tf)

    print(f"  EA FULL: {len(ea_full)} bars, {ea_full['time'].iloc[0]} → {ea_full['time'].iloc[-1]}")
    print(f"  EA 500:  {len(ea_500)} bars, {ea_500['time'].iloc[0]} → {ea_500['time'].iloc[-1]}")

    # Find where ATR becomes valid (not inf or huge)
    atr_col = pd.to_numeric(ea_full["atr"], errors="coerce").values
    ea_full["atr"] = atr_col
    valid_mask = np.isfinite(atr_col) & (atr_col < 1000) & (atr_col > 0)
    first_valid = np.argmax(valid_mask)
    print(f"  ATR becomes valid at bar {first_valid}: {ea_full['time'].iloc[first_valid]}")

    # Load our bars and compute trail
    bars_path = f"{BARS_DIR}/{tf}.csv"
    try:
        df_bars = load_ohlc(bars_path)
    except Exception:
        print(f"  No bars file at {bars_path}, skipping")
        continue

    our_utbot = compute_utbot(df_bars)
    our_times = pd.to_datetime(df_bars["time"])
    our_trail = our_utbot["closed_trail_stop"].values.astype(float)
    our_dir = np.where(our_utbot["closed_bias"].values == "BULLISH", 1.0, -1.0)

    # Parse EA times
    ea_full["time_dt"] = pd.to_datetime(ea_full["time"], format="%Y.%m.%d %H:%M")
    ea_500["time_dt"] = pd.to_datetime(ea_500["time"], format="%Y.%m.%d %H:%M")

    # EA 500-bar comparison (this is what the EA ACTUALLY uses for decisions)
    print(f"\n  --- EA 500-bar window comparison ---")
    ea500_times = ea_500["time_dt"].values
    ea500_trail = ea_500["trail_stop"].values.astype(float)
    ea500_dir = ea_500["direction"].values.astype(float)

    # Match by time
    our_time_idx = pd.DatetimeIndex(our_times)
    matched = 0
    dir_diffs = 0
    trail_diffs = 0
    first_dir_diff = None
    first_trail_diff = None

    for i in range(len(ea_500)):
        t = ea500_times[i]
        idx = our_time_idx.get_indexer([t], method=None)[0]
        if idx < 0:
            continue
        matched += 1

        ea_d = ea500_dir[i]
        our_d = our_dir[idx]
        ea_t = ea500_trail[i]
        our_t = our_trail[idx]

        if ea_d != our_d:
            dir_diffs += 1
            if first_dir_diff is None:
                first_dir_diff = (i, t, ea_d, our_d, ea_t, our_t)

        if abs(ea_t - our_t) > 0.01:
            trail_diffs += 1
            if first_trail_diff is None:
                first_trail_diff = (i, t, ea_t, our_t, ea_d, our_d)

    print(f"  Matched bars: {matched}/{len(ea_500)}")
    print(f"  Direction differences: {dir_diffs}")
    print(f"  Trail value differences (>0.01): {trail_diffs}")

    if first_dir_diff:
        i, t, ea_d, our_d, ea_t, our_t = first_dir_diff
        d_ea = "BULL" if ea_d > 0 else "BEAR"
        d_our = "BULL" if our_d > 0 else "BEAR"
        print(f"\n  FIRST direction diff at {t}:")
        print(f"    EA:  dir={d_ea}, trail={ea_t:.4f}")
        print(f"    BT:  dir={d_our}, trail={our_t:.4f}")

    if first_trail_diff:
        i, t, ea_t, our_t, ea_d, our_d = first_trail_diff
        print(f"\n  FIRST trail diff at {t}:")
        print(f"    EA trail:  {ea_t:.4f} (dir={'BULL' if ea_d > 0 else 'BEAR'})")
        print(f"    BT trail:  {our_t:.4f} (dir={'BULL' if our_d > 0 else 'BEAR'})")
        print(f"    Gap: {ea_t - our_t:.4f}")

    # Show all direction differences
    if dir_diffs > 0 and dir_diffs <= 30:
        print(f"\n  All direction differences:")
        for i in range(len(ea_500)):
            t = ea500_times[i]
            idx = our_time_idx.get_indexer([t], method=None)[0]
            if idx < 0:
                continue
            if ea500_dir[i] != our_dir[idx]:
                ea_d = "BULL" if ea500_dir[i] > 0 else "BEAR"
                our_d = "BULL" if our_dir[idx] > 0 else "BEAR"
                close_val = ea_500["close"].iloc[i]
                print(f"    {t}  close={close_val:.2f}  EA={ea_d}(trail={ea500_trail[i]:.4f})  BT={our_d}(trail={our_trail[idx]:.4f})")

    # Now check the FULL trail for divergence origin
    print(f"\n  --- FULL trail analysis (origin of divergence) ---")
    ea_full_valid = ea_full[valid_mask].reset_index(drop=True)
    print(f"  Valid ATR bars: {len(ea_full_valid)} (from {ea_full_valid['time'].iloc[0]})")

    # Find overlap with our data
    ea_full_times = ea_full_valid["time_dt"].values
    ea_full_trail = ea_full_valid["trail_stop"].values.astype(float)
    ea_full_dir = ea_full_valid["direction"].values.astype(float)

    # Check the overlap region
    our_start = our_times.iloc[0]
    overlap_mask = ea_full_times >= np.datetime64(our_start)
    overlap_indices = np.where(overlap_mask)[0]

    if len(overlap_indices) > 0:
        print(f"  Overlap starts at EA bar {overlap_indices[0]}: {ea_full_times[overlap_indices[0]]}")

        first_overlap_diff = None
        overlap_dir_diffs = 0
        for oi in overlap_indices:
            t = ea_full_times[oi]
            idx = our_time_idx.get_indexer([t], method=None)[0]
            if idx < 0:
                continue
            if ea_full_dir[oi] != our_dir[idx]:
                overlap_dir_diffs += 1
                if first_overlap_diff is None:
                    first_overlap_diff = (oi, t, ea_full_dir[oi], our_dir[idx],
                                          ea_full_trail[oi], our_trail[idx],
                                          ea_full_valid["close"].iloc[oi])

        print(f"  Direction diffs in overlap: {overlap_dir_diffs}")
        if first_overlap_diff:
            oi, t, ea_d, our_d, ea_t, our_t, close_v = first_overlap_diff
            print(f"  First diff at {t} (EA bar {oi}):")
            print(f"    close={close_v:.2f}")
            print(f"    EA:  dir={'BULL' if ea_d>0 else 'BEAR'}, trail={ea_t:.4f}")
            print(f"    BT:  dir={'BULL' if our_d>0 else 'BEAR'}, trail={our_t:.4f}")

            # Show a few bars before/after
            print(f"\n  Context around first divergence:")
            for delta in range(-5, 6):
                j = oi + delta
                if j < 0 or j >= len(ea_full_valid):
                    continue
                t2 = ea_full_times[j]
                idx2 = our_time_idx.get_indexer([t2], method=None)[0]
                marker = " <<<" if delta == 0 else ""
                if idx2 >= 0:
                    d_ea = "BULL" if ea_full_dir[j] > 0 else "BEAR"
                    d_bt = "BULL" if our_dir[idx2] > 0 else "BEAR"
                    print(f"    {t2}  close={ea_full_valid['close'].iloc[j]:.2f}  "
                          f"EA={d_ea}({ea_full_trail[j]:.4f})  "
                          f"BT={d_bt}({our_trail[idx2]:.4f})  "
                          f"atr={ea_full_valid['atr'].iloc[j]:.4f}{marker}")
                else:
                    d_ea = "BULL" if ea_full_dir[j] > 0 else "BEAR"
                    print(f"    {t2}  close={ea_full_valid['close'].iloc[j]:.2f}  "
                          f"EA={d_ea}({ea_full_trail[j]:.4f})  BT=no_data{marker}")
    else:
        print(f"  No overlap with our bar data (our data starts at {our_start})")
