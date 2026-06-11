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
from backtest.data_loader import load_ohlc, load_ticks
from backtest.runner import BacktestRunner
from backtest.tick_runner import TickBacktestRunner
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
        default=None,
        help="Path to M1 OHLC CSV (bar-by-bar mode)",
    )
    parser.add_argument(
        "--ticks", "-t",
        default=None,
        help="Path to tick CSV with bid/ask (tick-by-tick mode)",
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

    # Determine mode: tick vs bar
    if not args.data and not args.ticks:
        print("Error: Provide --data (bar mode) or --ticks (tick mode)")
        sys.exit(1)
    if args.data and args.ticks:
        print("Error: --data and --ticks are mutually exclusive")
        sys.exit(1)

    tick_mode = args.ticks is not None
    symbol = config.get("trading.symbol", "UNKNOWN")

    if tick_mode:
        tick_path = Path(args.ticks).resolve()
        if not tick_path.exists():
            print(f"Error: Tick file not found: {tick_path}")
            sys.exit(1)
        df_ticks = load_ticks(tick_path, start=start, end=end)
        if len(df_ticks) == 0:
            print("Error: No tick rows after filtering")
            sys.exit(1)
        print(f"Data: {len(df_ticks):,} ticks for {symbol}")
        print(f"Period: {df_ticks['time'].iloc[0]} → {df_ticks['time'].iloc[-1]}")
    else:
        data_path = Path(args.data).resolve()
        if not data_path.exists():
            print(f"Error: Data file not found: {data_path}")
            sys.exit(1)
        df = load_ohlc(data_path, start=start, end=end)
        if len(df) == 0:
            print("Error: No data rows after filtering")
            sys.exit(1)
        print(f"Data: {len(df)} M1 bars for {symbol}")
        print(f"Period: {df['time'].iloc[0]} → {df['time'].iloc[-1]}")

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
    if tick_mode:
        runner = TickBacktestRunner(config, df_ticks, trade_from=trade_from)
    else:
        runner = BacktestRunner(config, df, trade_from=trade_from)
    simulator = runner.run()
    elapsed = time.time() - t0
    mode_label = "tick" if tick_mode else "bar"
    print(f"Backtest completed in {elapsed:.1f}s ({mode_label} mode, {runner.total_ticks if tick_mode else runner.total_bars} {mode_label}s)")

    # Compute stats and print report
    stats = compute_stats(simulator)
    print_report(stats, simulator)
    print_trade_log(simulator, limit=args.trades)

    # Save results if requested
    if args.output:
        save_results(stats, simulator, args.output)


if __name__ == "__main__":
    main()
