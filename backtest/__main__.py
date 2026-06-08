"""CLI entry point for the backtester.

Usage:
    uv run python -m backtest --config config-gold.yaml --data data/XAUUSD_M1.csv
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
        description="MT5 Signal-Replay Backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to YAML config (e.g. config-gold.yaml)",
    )
    parser.add_argument(
        "--data", "-d",
        required=True,
        help="Path to OHLC CSV file (e.g. data/XAUUSD_M1.csv)",
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
        help="Path to save JSON results (e.g. output/results.json)",
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

    # Load data
    data_path = Path(args.data).resolve()
    if not data_path.exists():
        print(f"Error: Data file not found: {data_path}")
        sys.exit(1)
    df = load_ohlc(data_path, start=start, end=end)
    if len(df) == 0:
        print("Error: No data rows after filtering")
        sys.exit(1)

    symbol = config.get("trading.symbol", "UNKNOWN")
    print(f"Data: {len(df)} M1 bars for {symbol}")
    print(f"Period: {df['time'].iloc[0]} → {df['time'].iloc[-1]}")

    # Run backtest
    t0 = time.time()
    runner = BacktestRunner(config, df)
    simulator = runner.run()
    elapsed = time.time() - t0
    print(f"Backtest completed in {elapsed:.1f}s")

    # Compute stats and print report
    stats = compute_stats(simulator)
    print_report(stats, simulator)
    print_trade_log(simulator, limit=args.trades)

    # Save results if requested
    if args.output:
        save_results(stats, simulator, args.output)


if __name__ == "__main__":
    main()
