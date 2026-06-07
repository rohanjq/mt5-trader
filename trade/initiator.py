from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

from core.models import (
    FilterVerdict,
    Signal,
    SignalDirection,
    TradeDirection,
    TradeRecord,
    TradeRequest,
    TradeState,
)

if TYPE_CHECKING:
    from core.config import Config
    from core.mt5_client import MT5Client
    from filters.base import FilterChain
    from trade.manager import TradeManager

log = logging.getLogger(__name__)


class TradeInitiator:
    """Evaluates signals and initiates trades through the filter chain.

    Current rule: UT Bot BUY → open BUY of configured volume.
                  UT Bot SELL → open SELL of configured volume.
    """

    def __init__(
        self,
        config: Config,
        mt5_client: MT5Client,
        filter_chain: FilterChain,
        trade_manager: TradeManager,
    ) -> None:
        self._config = config
        self._mt5 = mt5_client
        self._filters = filter_chain
        self._manager = trade_manager
        self._lock = threading.Lock()
        self._last_signal_direction: SignalDirection | None = None

    def on_signal(self, signal: Signal) -> None:
        """Called by the engine when a new signal is available."""
        if signal.direction == SignalDirection.NEUTRAL:
            return

        with self._lock:
            # Don't re-enter on the same signal direction if we already have a position
            if self._manager.has_open_position:
                return

            # Avoid acting on the same repeated signal
            if signal.direction == self._last_signal_direction:
                return

            self._last_signal_direction = signal.direction

            symbol = self._config.get("trading.symbol", "BTCUSDT")
            volume = float(self._config.get("trading.volume", 0.001))

            direction = (
                TradeDirection.BUY
                if signal.direction == SignalDirection.BUY
                else TradeDirection.SELL
            )

            request = TradeRequest(
                direction=direction,
                symbol=symbol,
                volume=volume,
                signal=signal,
            )
            log.info(
                "Trade request %s: %s %s %.4f (signal: %s)",
                request.id, direction.value, symbol, volume, signal.source,
            )

            # Run through filter chain
            verdict, reason = self._filters.evaluate(request)

            if verdict == FilterVerdict.BLOCK:
                request.state = TradeState.REJECTED
                request.rejection_reason = reason
                log.info("Trade %s rejected: %s", request.id, reason)
                return

            request.state = TradeState.FILTERS_PASSED
            self._execute(request)

    def _execute(self, request: TradeRequest) -> None:
        if not self._mt5.connected:
            log.error("MT5 not connected — cannot execute trade %s", request.id)
            return

        if request.direction == TradeDirection.BUY:
            result = self._mt5.buy(volume=request.volume, symbol=request.symbol)
        else:
            result = self._mt5.sell(volume=request.volume, symbol=request.symbol)

        if result and result.retcode == 10009:
            tick = self._mt5.get_tick(request.symbol)
            entry_price = tick.ask if request.direction == TradeDirection.BUY else tick.bid

            record = TradeRecord(
                id=request.id,
                direction=request.direction,
                symbol=request.symbol,
                volume=request.volume,
                entry_price=entry_price,
                entry_time=datetime.now(),
                signal_source=request.signal.source,
                ticket=result.order,
                state=TradeState.EXECUTED,
            )
            self._manager.register_trade(record)
            log.info(
                "Trade %s EXECUTED: ticket=%s entry=%.2f",
                request.id, result.order, entry_price,
            )
        else:
            retcode = result.retcode if result else "N/A"
            comment = result.comment if result else "no result"
            log.error(
                "Trade %s execution FAILED: retcode=%s comment=%s",
                request.id, retcode, comment,
            )

    def reset_signal_tracking(self) -> None:
        """Reset so the next signal of any direction will be acted on."""
        with self._lock:
            self._last_signal_direction = None
