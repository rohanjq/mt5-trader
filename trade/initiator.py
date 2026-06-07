from __future__ import annotations

import logging
import threading
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

    Calculates SL from signal metadata (trail_stop), TP from reward ratio,
    and optionally sizes the position from risk_dollars.
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
            direction = (
                TradeDirection.BUY
                if signal.direction == SignalDirection.BUY
                else TradeDirection.SELL
            )

            # ── Calculate SL, TP, volume from risk ──
            sl, tp, volume, risk_dollars = self._calculate_risk(signal, direction)

            request = TradeRequest(
                direction=direction,
                symbol=symbol,
                volume=volume,
                signal=signal,
                sl=sl,
                tp=tp,
                risk_dollars=risk_dollars,
            )
            log.info(
                "Trade request %s: %s %s vol=%.4f SL=%.2f TP=%.2f risk=$%.2f (signal: %s)",
                request.id, direction.value, symbol, volume, sl, tp, risk_dollars,
                signal.source,
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

    def _calculate_risk(
        self, signal: Signal, direction: TradeDirection,
    ) -> tuple[float, float, float, float]:
        """Calculate SL, TP, volume from config.

        SL/TP are fixed dollar distances from entry price.
        Volume is always the configured fixed value.

        Returns (sl, tp, volume, sl_dollars).
        """
        volume = float(self._config.get("trading.volume", 0.001))
        sl_dollars = float(self._config.get("trading.sl_dollars", 5.0))
        reward_ratio = float(self._config.get("trading.reward_ratio", 1.25))
        tp_dollars = sl_dollars * reward_ratio

        # Get current price
        tick = self._mt5.get_tick() if self._mt5.connected else None
        if not tick:
            return 0.0, 0.0, volume, sl_dollars

        entry_price = tick.ask if direction == TradeDirection.BUY else tick.bid

        if direction == TradeDirection.BUY:
            sl = entry_price - sl_dollars
            tp = entry_price + tp_dollars
        else:
            sl = entry_price + sl_dollars
            tp = entry_price - tp_dollars

        return sl, tp, volume, sl_dollars

    def _execute(self, request: TradeRequest) -> None:
        if not self._mt5.connected:
            log.error("MT5 not connected — cannot execute trade %s", request.id)
            return

        if request.direction == TradeDirection.BUY:
            result = self._mt5.buy(
                volume=request.volume, symbol=request.symbol,
                sl=request.sl, tp=request.tp,
            )
        else:
            result = self._mt5.sell(
                volume=request.volume, symbol=request.symbol,
                sl=request.sl, tp=request.tp,
            )

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
                sl=request.sl,
                tp=request.tp,
                risk_dollars=request.risk_dollars,
                state=TradeState.EXECUTED,
            )
            self._manager.register_trade(record)
            log.info(
                "Trade %s EXECUTED: ticket=%s entry=%.2f SL=%.2f TP=%.2f",
                request.id, result.order, entry_price, request.sl, request.tp,
            )
        else:
            retcode = result.retcode if result else "N/A"
            comment = result.comment if result else "no result"
            log.error(
                "Trade %s execution FAILED: retcode=%s comment=%s",
                request.id, retcode, comment,
            )
            # Reset so the signal can be retried on next poll
            self._last_signal_direction = None

    def reset_signal_tracking(self) -> None:
        """Reset so the next signal of any direction will be acted on."""
        with self._lock:
            self._last_signal_direction = None
