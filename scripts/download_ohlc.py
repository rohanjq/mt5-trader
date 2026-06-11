"""Download OHLC data from MT5 via rpyc bridge and save to CSV.

Usage:
    uv run python scripts/download_ohlc.py --symbol XAUUSD --days 7
    uv run python scripts/download_ohlc.py --symbol XAUUSD --days 30 --output data/XAUUSD_M1_30d.csv
    uv run python scripts/download_ohlc.py --symbol XAUUSD --from 2026-06-09 --to 2026-06-11
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from mt5linux import MetaTrader5


def main() -> None:
    parser = argparse.ArgumentParser(description="Download OHLC from MT5")
    parser.add_argument("--symbol", "-s", default="XAUUSD", help="Symbol (default: XAUUSD)")
    parser.add_argument("--days", "-d", type=int, default=None, help="Number of days back (default: 7 if no --from/--to)")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD (or YYYY-MM-DD HH:MM)")
    parser.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD (or YYYY-MM-DD HH:MM)")
    parser.add_argument("--host", default="localhost", help="MT5 rpyc host (default: localhost)")
    parser.add_argument("--port", type=int, default=8001, help="MT5 rpyc port (default: 8001)")
    parser.add_argument("--output", "-o", default=None, help="Output CSV path (default: sampledata/<SYMBOL>_M1_<range>.csv)")
    args = parser.parse_args()

    # Determine time range
    def parse_dt(s: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        print(f"ERROR: Cannot parse date '{s}'. Use YYYY-MM-DD or YYYY-MM-DD HH:MM")
        sys.exit(1)

    if args.from_date and args.to_date:
        start = parse_dt(args.from_date)
        end = parse_dt(args.to_date)
        range_label = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
    elif args.from_date:
        start = parse_dt(args.from_date)
        end = datetime.now(timezone.utc)
        range_label = f"{start.strftime('%Y%m%d')}_now"
    else:
        days = args.days or 7
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        range_label = f"{days}d"

    output = Path(args.output) if args.output else Path(f"sampledata/{args.symbol}_M1_{range_label}.csv")
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to MT5 at {args.host}:{args.port}...")
    mt5 = MetaTrader5(host=args.host, port=args.port)
    if not mt5.initialize():
        print("ERROR: MT5 initialize() failed")
        sys.exit(1)

    info = mt5.terminal_info()
    if info:
        print(f"Connected: {info.name}")

    # Time range
    print(f"Downloading {args.symbol} M1 from {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')}...")

    # TIMEFRAME_M1 = 1
    rates = mt5.copy_rates_range(args.symbol, 1, start, end)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("ERROR: No data returned. Check symbol name and MT5 connection.")
        sys.exit(1)

    # Convert to DataFrame
    df = pd.DataFrame(rates)

    # Rename columns to standard format
    col_map = {}
    for col in df.columns:
        lc = str(col).lower()
        if lc == "time":
            col_map[col] = "time"
        elif lc == "open":
            col_map[col] = "open"
        elif lc == "high":
            col_map[col] = "high"
        elif lc == "low":
            col_map[col] = "low"
        elif lc == "close":
            col_map[col] = "close"
        elif lc in ("tick_volume", "tickvol"):
            col_map[col] = "tick_volume"
        elif lc == "spread":
            col_map[col] = "spread"
        elif lc == "real_volume":
            col_map[col] = "real_volume"

    df = df.rename(columns=col_map)

    # Convert epoch time to datetime string
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit="s").dt.strftime("%Y.%m.%d %H:%M:%S")

    # Keep essential columns
    keep = [c for c in ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"] if c in df.columns]
    df = df[keep]

    df.to_csv(output, index=False)
    print(f"Saved {len(df)} bars to {output}")
    print(f"  First: {df['time'].iloc[0]}")
    print(f"  Last:  {df['time'].iloc[-1]}")


if __name__ == "__main__":
    main()
