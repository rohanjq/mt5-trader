"""Download tick-by-tick data from MT5 via rpyc bridge and save to CSV.

Usage:
    uv run python scripts/download_ticks.py --symbol XAUUSD --days 7
    uv run python scripts/download_ticks.py --symbol XAUUSD --from 2026-06-04 --to 2026-06-11
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from mt5linux import MetaTrader5


def main() -> None:
    parser = argparse.ArgumentParser(description="Download tick data from MT5")
    parser.add_argument("--symbol", "-s", default="XAUUSD", help="Symbol (default: XAUUSD)")
    parser.add_argument("--days", "-d", type=int, default=None, help="Number of days back (default: 7)")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD or YYYY-MM-DD HH:MM")
    parser.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD or YYYY-MM-DD HH:MM")
    parser.add_argument("--host", default="localhost", help="MT5 rpyc host (default: localhost)")
    parser.add_argument("--port", type=int, default=8001, help="MT5 rpyc port (default: 8001)")
    parser.add_argument("--output", "-o", default=None, help="Output CSV path")
    parser.add_argument("--chunk-hours", type=int, default=6,
                        help="Download in chunks of N hours (avoids timeout, default: 6)")
    args = parser.parse_args()

    def parse_dt(s: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        print(f"ERROR: Cannot parse date '{s}'")
        sys.exit(1)

    if args.from_date and args.to_date:
        start = parse_dt(args.from_date)
        end = parse_dt(args.to_date)
    elif args.from_date:
        start = parse_dt(args.from_date)
        end = datetime.now(timezone.utc)
    else:
        days = args.days or 7
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

    range_label = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
    output = Path(args.output) if args.output else Path(f"sampledata/{args.symbol}_ticks_{range_label}.csv")
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to MT5 at {args.host}:{args.port}...")
    mt5 = MetaTrader5(host=args.host, port=args.port)
    if not mt5.initialize():
        print("ERROR: MT5 initialize() failed")
        sys.exit(1)

    info = mt5.terminal_info()
    if info:
        print(f"Connected: {info.name}")

    # Download in chunks to avoid rpyc timeout on large ranges
    # COPY_TICKS_ALL = 1
    chunk_delta = timedelta(hours=args.chunk_hours)
    all_frames: list[pd.DataFrame] = []
    chunk_start = start
    chunk_num = 0

    total_hours = (end - start).total_seconds() / 3600
    print(f"Downloading {args.symbol} ticks: {start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M} ({total_hours:.0f}h)")

    while chunk_start < end:
        chunk_end = min(chunk_start + chunk_delta, end)
        chunk_num += 1

        ticks = mt5.copy_ticks_range(args.symbol, chunk_start, chunk_end, 1)  # COPY_TICKS_ALL

        if ticks is not None and len(ticks) > 0:
            df_chunk = pd.DataFrame(ticks)
            all_frames.append(df_chunk)
            print(f"  Chunk {chunk_num}: {chunk_start:%m/%d %H:%M} → {chunk_end:%m/%d %H:%M} = {len(df_chunk):,} ticks")
        else:
            print(f"  Chunk {chunk_num}: {chunk_start:%m/%d %H:%M} → {chunk_end:%m/%d %H:%M} = 0 ticks (market closed?)")

        chunk_start = chunk_end

    mt5.shutdown()

    if not all_frames:
        print("ERROR: No tick data returned")
        sys.exit(1)

    df = pd.concat(all_frames, ignore_index=True)

    # Rename columns
    col_map = {}
    for col in df.columns:
        lc = str(col).lower()
        if lc == "time":
            col_map[col] = "time_epoch"
        elif lc == "bid":
            col_map[col] = "bid"
        elif lc == "ask":
            col_map[col] = "ask"
        elif lc == "last":
            col_map[col] = "last"
        elif lc == "volume":
            col_map[col] = "volume"
        elif lc == "time_msc":
            col_map[col] = "time_msc"
        elif lc == "flags":
            col_map[col] = "flags"
        elif lc == "volume_real":
            col_map[col] = "volume_real"
    df = df.rename(columns=col_map)

    # Convert time — use time_msc for millisecond precision if available
    if "time_msc" in df.columns:
        df["time"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True).dt.strftime("%Y.%m.%d %H:%M:%S.%f")
    elif "time_epoch" in df.columns:
        df["time"] = pd.to_datetime(df["time_epoch"], unit="s", utc=True).dt.strftime("%Y.%m.%d %H:%M:%S")

    # Drop duplicate epoch columns, keep useful ones
    keep = [c for c in ["time", "bid", "ask", "last", "volume", "flags"] if c in df.columns]
    df = df[keep]

    # Remove exact duplicate rows (same time + same price)
    df = df.drop_duplicates()

    df.to_csv(output, index=False)
    print(f"\nSaved {len(df):,} ticks to {output}")
    print(f"  First: {df['time'].iloc[0]}")
    print(f"  Last:  {df['time'].iloc[-1]}")
    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"  Size:  {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
