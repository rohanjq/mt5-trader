"""CLI entry point for the backtester.

Usage:
    uv run python -m backtest --config config-gold.yaml --bars-dir sampledata/XAUUSD_bars/
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from core.config import Config
from backtest.data_loader import load_ohlc
from backtest.runner import BacktestRunner
from backtest.stats import compute_stats, print_report, print_trade_log, save_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MT5 Signal-Replay Backtester (bar-close mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to YAML config (e.g. config-gold.yaml)",
    )
    parser.add_argument(
        "--bars-dir",
        required=True,
        help="Directory with native MT5 bar CSVs (M1.csv, M5.csv, etc.) "
             "from download_bars.py.  M1.csv is used as the clock; "
             "higher TF bars provide exact indicator values.",
    )
    parser.add_argument(
        "--from", dest="start_date",
        default=None,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to", dest="end_date",
        default=None,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path to save CSV results",
    )
    parser.add_argument(
        "--trades",
        type=int,
        default=50,
        help="Number of trades to show in log (0=all, default=50)",
    )
    parser.add_argument(
        "--balance",
        type=float,
        default=None,
        help="Override initial balance (default: from config or $10,000)",
    )
    parser.add_argument(
        "--trade-from",
        default=None,
        help="Only open trades after this time (YYYY-MM-DD HH:MM). "
             "Indicators and rising-edge state still compute from bar 0.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pandas_ta").setLevel(logging.WARNING)

    # Load config (reuses the same Config class as live trading)
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    config = Config(config_path)
    print(f"Config loaded: {config_path.name}")

    # Override balance if specified
    if args.balance:
        config.set_runtime("backtest.initial_balance", args.balance)

    # Parse dates
    start = datetime.strptime(args.start_date, "%Y-%m-%d") if args.start_date else None
    end = datetime.strptime(args.end_date, "%Y-%m-%d") if args.end_date else None

    # Load native MT5 bars
    bars_dir = Path(args.bars_dir).resolve()
    if not bars_dir.is_dir():
        print(f"Error: Bars directory not found: {bars_dir}")
        sys.exit(1)

    m1_path = bars_dir / "M1.csv"
    if not m1_path.exists():
        print(f"Error: M1.csv not found in {bars_dir}")
        sys.exit(1)

    df_m1 = load_ohlc(m1_path, start=start, end=end)
    if len(df_m1) == 0:
        print("Error: No M1 bars after filtering")
        sys.exit(1)

    symbol = config.get("trading.symbol", "UNKNOWN")
    print(f"Data: {len(df_m1):,} M1 bars for {symbol}")
    print(f"Period: {df_m1['time'].iloc[0]} → {df_m1['time'].iloc[-1]}")

    # Load higher-TF native bars
    native_bars: dict[str, "pd.DataFrame"] = {}
    for csv_file in sorted(bars_dir.glob("*.csv")):
        tf_name = csv_file.stem
        if tf_name == "M1":
            continue
        df_tf = load_ohlc(csv_file, start=start, end=end)
        if len(df_tf) > 0:
            native_bars[tf_name] = df_tf
            print(f"  Native {tf_name}: {len(df_tf):,} bars")
    print(f"Loaded {len(native_bars)} higher timeframes from {bars_dir.name}/")

    # Parse trade-from
    trade_from = None
    if args.trade_from:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                trade_from = datetime.strptime(args.trade_from, fmt)
                break
            except ValueError:
                continue
        if trade_from is None:
            print(f"Error: invalid --trade-from format: {args.trade_from}")
            sys.exit(1)
        print(f"Trading starts from: {trade_from}")

    # Run backtest
    t0 = time.time()
    runner = BacktestRunner(config, df_m1, trade_from=trade_from, native_bars=native_bars)
    simulator = runner.run()
    elapsed = time.time() - t0
    print(f"Backtest completed in {elapsed:.1f}s ({runner.total_bars:,} bars)")

    # Compute stats and print report
    stats = compute_stats(simulator)
    print_report(stats, simulator)
    print_trade_log(simulator, limit=args.trades)

    # Save results if requested
    if args.output:
        save_results(stats, simulator, args.output)


if __name__ == "__main__":
    main()
