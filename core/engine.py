from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from core.config import Config
from core.models import Signal, SignalDirection
from core.mt5_client import MT5Client
from exits.base import discover_exit_rules
from filters.base import BaseFilter, FilterChain, discover_filters
from filters.manual_switch import ManualSwitchFilter
from signals.base import BaseSignal, discover_signals
from strategies.base import discover_strategies
from trade.initiator import TradeInitiator
from trade.manager import TradeManager

log = logging.getLogger(__name__)


class Engine:
    """Main orchestrator — wires up all components and runs background loops."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.mt5_client = MT5Client(config)
        self.trade_manager = TradeManager(config, self.mt5_client)
        self.filter_chain = FilterChain()
        self.trade_initiator = TradeInitiator(
            config, self.mt5_client, self.filter_chain, self.trade_manager,
        )

        self._signal_plugins: list[BaseSignal] = []
        self._latest_signals: dict[str, Signal] = {}
        self._signals_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

        # The manual switch filter is special — we keep a reference for the UI
        self.manual_switch: ManualSwitchFilter | None = None

        self._signal_callbacks: list[Callable[[dict[str, Signal]], None]] = []

    # ── setup ──────────────────────────────────────────────────────────────

    def setup(self) -> bool:
        """Discover plugins, connect MT5, wire everything together."""
        # Discover signal plugins
        self._signal_plugins = discover_signals(self.config)
        if not self._signal_plugins:
            log.warning("No signal plugins discovered")

        # Discover filter plugins
        filter_plugins = discover_filters(self.config)
        for fp in filter_plugins:
            fp.set_trade_manager(self.trade_manager)
            self.filter_chain.add(fp)
            if isinstance(fp, ManualSwitchFilter):
                self.manual_switch = fp

        # Ensure we have a manual switch
        if self.manual_switch is None:
            self.manual_switch = ManualSwitchFilter(self.config)
            self.manual_switch.set_trade_manager(self.trade_manager)
            self.filter_chain.add(self.manual_switch)

        # Discover exit rules
        exit_rules = discover_exit_rules(self.config)
        self.trade_manager.set_exit_rules(exit_rules)

        # Discover strategies
        strategies = discover_strategies(self.config)
        self.trade_initiator.set_strategies(strategies)

        # When a trade closes, reset signal tracking so the next signal is acted on
        self.trade_manager.on_trade_closed(
            lambda _trade: self.trade_initiator.reset_signal_tracking()
        )

        # Connect to MT5
        if not self.mt5_client.connect():
            log.error("Failed to connect to MT5 — engine will run in disconnected mode")
            return False

        # Start config hot-reload
        self.config.start_watching()
        return True

    def on_signals_update(self, callback: Callable[[dict[str, Signal]], None]) -> None:
        self._signal_callbacks.append(callback)

    # ── background loops ───────────────────────────────────────────────────

    def start(self) -> None:
        """Start background threads for signal polling and position monitoring."""
        self._stop_event.clear()

        t1 = threading.Thread(target=self._signal_loop, daemon=True, name="signal-loop")
        t2 = threading.Thread(target=self._monitor_loop, daemon=True, name="monitor-loop")
        self._threads = [t1, t2]
        for t in self._threads:
            t.start()
        log.info("Engine started — %d signal sources, %d filters",
                 len(self._signal_plugins), len(self.filter_chain.filters))

    def stop(self) -> None:
        """Gracefully stop the engine."""
        log.info("Engine stopping...")
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=5)
        self.config.stop_watching()
        self.mt5_client.disconnect()
        log.info("Engine stopped")

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    @property
    def latest_signals(self) -> dict[str, Signal]:
        with self._signals_lock:
            return dict(self._latest_signals)

    def _signal_loop(self) -> None:
        interval = self.config.get("signals.poll_interval", 2.0)
        while not self._stop_event.is_set():
            try:
                for plugin in self._signal_plugins:
                    signal = plugin.read()
                    with self._signals_lock:
                        self._latest_signals[plugin.name] = signal

                # Pass all signals to the initiator (strategies evaluate them)
                snapshot = self.latest_signals
                self.trade_initiator.on_signals(snapshot)

                # Update trade manager with latest signals (for exit rules)
                self.trade_manager.update_signals(snapshot)

                # Notify UI callbacks
                for cb in self._signal_callbacks:
                    try:
                        cb(snapshot)
                    except Exception:
                        log.exception("Signal callback error")

            except Exception:
                log.exception("Signal loop error")

            # Re-read interval in case config changed
            interval = self.config.get("signals.poll_interval", 2.0)
            self._stop_event.wait(interval)

    def _monitor_loop(self) -> None:
        """Monitor open position P&L and sync with MT5 state."""
        while not self._stop_event.is_set():
            try:
                self.trade_manager.update_open_position()
                self.trade_manager.sync_positions_from_mt5()
            except Exception:
                log.exception("Monitor loop error")
            self._stop_event.wait(1.0)
