from __future__ import annotations

import logging
import time

from core.config import Config
from core.models import FilterResult, FilterVerdict, TradeDirection, TradeRequest
from filters.base import BaseFilter

log = logging.getLogger(__name__)


class ReversalCooldownFilter(BaseFilter):
    """Block reverse-direction trades for X seconds after a trade closes.

    If the last trade was BUY, blocks SELL for the cooldown period (and vice versa).
    Same-direction re-entry is allowed immediately.
    """

    name = "reversal_cooldown"
    description = "Block reverse trades for 1 min after close"

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def evaluate(self, request: TradeRequest) -> FilterResult:
        if self._trade_manager is None:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        cooldown_seconds = self.config.get("filters.reversal_cooldown_seconds", 60)
        last_dir = self._trade_manager.last_trade_direction
        last_close = self._trade_manager.last_close_time

        if last_dir is None or last_close is None:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        # Only block the OPPOSITE direction
        is_reverse = (
            (last_dir == TradeDirection.BUY and request.direction == TradeDirection.SELL)
            or (last_dir == TradeDirection.SELL and request.direction == TradeDirection.BUY)
        )
        if not is_reverse:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        elapsed = time.time() - last_close
        remaining = cooldown_seconds - elapsed

        if remaining > 0:
            return FilterResult(
                verdict=FilterVerdict.BLOCK,
                reason=f"Reversal blocked — last trade was {last_dir.value}, "
                       f"wait {remaining:.0f}s before {request.direction.value}",
            )

        return FilterResult(verdict=FilterVerdict.ALLOW)
