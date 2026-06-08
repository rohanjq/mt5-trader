#!/usr/bin/env python3
"""MT5 Auto-Trader — entry point.

Starts the engine, connects to MT5, and launches the TUI dashboard.
Usage: python main.py --config config-btc.yaml
       python main.py --config config-gold.yaml
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from core.config import Config
from core.engine import Engine
from ui.dashboard import TradingDashboard


def setup_logging(level: str = "INFO", log_file: str = "trader.log") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="MT5 Auto-Trader")
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config file (e.g. config-btc.yaml, config-gold.yaml)",
    )
    args = parser.parse_args()

    config_path = Path(__file__).parent / args.config
    config = Config(config_path)

    symbol = config.get("trading.symbol", "UNKNOWN")
    log_file = f"trader-{symbol.lower()}.log"
    setup_logging(config.get("logging.level", "INFO"), log_file)
    log = logging.getLogger("main")

    log.info("=== MT5 Auto-Trader starting [%s] ===", symbol)

    engine = Engine(config)
    connected = engine.setup()

    if not connected:
        log.warning("Starting in disconnected mode — will retry when MT5 is available")

    engine.start()

    try:
        app = TradingDashboard(engine)
        app.run()
    except KeyboardInterrupt:
        log.info("Interrupted — shutting down")
    finally:
        engine.stop()
        log.info("=== MT5 Auto-Trader stopped ===")


if __name__ == "__main__":
    main()
