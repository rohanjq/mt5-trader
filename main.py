#!/usr/bin/env python3
"""MT5 Auto-Trader — entry point.

Starts the engine, connects to MT5, and launches the TUI dashboard.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from core.config import Config
from core.engine import Engine
from ui.dashboard import TradingDashboard


def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=[
            logging.FileHandler("trader.log"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> None:
    config_path = Path(__file__).parent / "config.yaml"
    config = Config(config_path)

    setup_logging(config.get("logging.level", "INFO"))
    log = logging.getLogger("main")

    log.info("=== MT5 Auto-Trader starting ===")

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
