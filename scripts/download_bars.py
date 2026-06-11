"""Download OHLC bars for ALL timeframes from MT5 via rpyc bridge.

Downloads native MT5 bars for every TF used in the trading config, so the
backtester can use exact MT5 bars instead of resampling from M1.

Usage:
    uv run python scripts/download_bars.py --symbol XAUUSD --days 60
    uv run python scripts/download_bars.py --symbol XAUUSD --from 2026-04-09 --to 2026-06-12
    uv run python scripts/download_bars.py --symbol XAUUSD --days 60 --config config-gold.yaml

Output:
    sampledata/XAUUSD_<range>/M1.csv
    sampledata/XAUUSD_<range>/M2.csv
    sampledata/XAUUSD_<range>/M5.csv
    ...
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml
from mt5linux import MetaTrader5

# MT5 native timeframe constants (minutes → ENUM_TIMEFRAMES int value)
# These match MetaTrader5's PERIOD_* enum values.
_MT5_TF = {
    "M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6,
    "M10": 10, "M12": 12, "M15": 15, "M20": 20, "M30": 30,
    "H1": 16385, "H2": 16386, "H3": 16387, "H4": 16388,
    "H6": 16390, "H8": 16392, "H12": 16396,
    "D1": 16408, "W1": 32769, "MN1": 49153,
}

# Non-native TFs that MT5 doesn't have (EA builds them synthetically from M1)
_SYNTHETIC_TFS = {"M45"}


def _parse_dt(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    print(f"ERROR: Cannot parse date '{s}'. Use YYYY-MM-DD or YYYY-MM-DD HH:MM")
    sys.exit(1)


def _timeframes_from_config(config_path: str) -> set[str]:
    """Extract all unique timeframes from a config YAML."""
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    tfs: set[str] = set()
    for src in cfg.get("signals", {}).get("sources", []):
        for tf in src.get("timeframes", []):
            tfs.add(tf)
    return tfs


def _download_tf(
    mt5: MetaTrader5,
    symbol: str,
    tf_name: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame | None:
    """Download bars for a single timeframe. Returns DataFrame or None."""
    tf_enum = _MT5_TF.get(tf_name)
    if tf_enum is None:
        print(f"  SKIP {tf_name}: not a native MT5 timeframe")
        return None

    rates = mt5.copy_rates_range(symbol, tf_enum, start, end)
    if rates is None or len(rates) == 0:
        print(f"  SKIP {tf_name}: no data returned")
        return None

    df = pd.DataFrame(rates)

    # Rename columns
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
            col_map[col] = "volume"
        elif lc == "spread":
            col_map[col] = "spread"
        elif lc == "real_volume":
            col_map[col] = "real_volume"
    df = df.rename(columns=col_map)

    # Convert epoch → datetime string
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit="s").dt.strftime("%Y.%m.%d %H:%M:%S")

    keep = [c for c in ["time", "open", "high", "low", "close", "volume", "spread"] if c in df.columns]
    return df[keep]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download MT5 bars for all timeframes")
    parser.add_argument("--symbol", "-s", default="XAUUSD")
    parser.add_argument("--days", "-d", type=int, default=None,
                        help="Days of history (default: 60 if no --from/--to)")
    parser.add_argument("--from", dest="from_date", default=None)
    parser.add_argument("--to", dest="to_date", default=None)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--config", "-c", default=None,
                        help="Config YAML to extract timeframes from (default: download common set)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: sampledata/<SYMBOL>_bars_<range>/)")
    parser.add_argument("--timeframes", "-t", nargs="+", default=None,
                        help="Specific timeframes to download (e.g. M1 M5 M15)")
    args = parser.parse_args()

    # Determine time range
    if args.from_date and args.to_date:
        start = _parse_dt(args.from_date)
        end = _parse_dt(args.to_date)
    elif args.from_date:
        start = _parse_dt(args.from_date)
        end = datetime.now(timezone.utc)
    else:
        days = args.days or 60
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

    range_label = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"

    # Determine which TFs to download
    if args.timeframes:
        timeframes = set(args.timeframes)
    elif args.config:
        timeframes = _timeframes_from_config(args.config)
    else:
        # Default: all common TFs
        timeframes = {"M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1", "H4"}

    # Remove synthetic TFs
    synthetic = timeframes & _SYNTHETIC_TFS
    native_tfs = timeframes - _SYNTHETIC_TFS

    if synthetic:
        print(f"Note: {synthetic} are synthetic (built from M1 in backtester)")
        if "M1" not in native_tfs:
            native_tfs.add("M1")
            print("  → Added M1 to download list (needed to build synthetic TFs)")

    # Sort for consistent ordering
    def _tf_sort_key(tf: str) -> int:
        if tf.startswith("M"):
            return int(tf[1:])
        elif tf.startswith("H"):
            return int(tf[1:]) * 60
        elif tf == "D1":
            return 1440
        return 99999
    sorted_tfs = sorted(native_tfs, key=_tf_sort_key)

    # Output directory
    out_dir = Path(args.output) if args.output else Path(f"sampledata/{args.symbol}_bars_{range_label}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Connect
    print(f"Connecting to MT5 at {args.host}:{args.port}...")
    mt5 = MetaTrader5(host=args.host, port=args.port)
    if not mt5.initialize():
        print("ERROR: MT5 initialize() failed")
        sys.exit(1)
    info = mt5.terminal_info()
    if info:
        print(f"Connected: {info.name}")

    print(f"\nDownloading {args.symbol} bars: {start:%Y-%m-%d} → {end:%Y-%m-%d}")
    print(f"Timeframes: {', '.join(sorted_tfs)}")
    print(f"Output: {out_dir}/\n")

    total_bars = 0
    for tf in sorted_tfs:
        df = _download_tf(mt5, args.symbol, tf, start, end)
        if df is None:
            continue
        out_path = out_dir / f"{tf}.csv"
        df.to_csv(out_path, index=False)
        total_bars += len(df)
        print(f"  {tf}: {len(df):>6d} bars → {out_path.name}  ({df['time'].iloc[0]} — {df['time'].iloc[-1]})")

    mt5.shutdown()

    print(f"\nDone! {total_bars:,} total bars across {len(sorted_tfs)} timeframes in {out_dir}/")
    if synthetic:
        print(f"Synthetic TFs {synthetic} will be built from M1 bars in the backtester.")


if __name__ == "__main__":
    main()
