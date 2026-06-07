from __future__ import annotations

import logging
import time

from core.config import Config
from core.models import FilterResult, FilterVerdict, TradeRequest
from filters.base import BaseFilter

log = logging.getLogger(__name__)


class ConsecutiveLossFilter(BaseFilter):
    """Blocks trading after N consecutive losses, with a configurable pause."""

    name = "consecutive_loss"
    description = "Pause after consecutive losses"

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def evaluate(self, request: TradeRequest) -> FilterResult:
        if self._trade_manager is None:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        max_losses = self.config.get("filters.max_consecutive_losses", 0)
        if max_losses <= 0:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        current = self._trade_manager.consecutive_losses
        if current < max_losses:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        # Check if pause period has elapsed since last loss
        pause_minutes = self.config.get("filters.pause_after_consecutive_minutes", 15)
        last_loss_time = self._trade_manager.last_loss_time
        if last_loss_time is not None:
            elapsed = time.time() - last_loss_time
            remaining = (pause_minutes * 60) - elapsed
            if remaining > 0:
                return FilterResult(
                    verdict=FilterVerdict.BLOCK,
                    reason=(
                        f"{current} consecutive losses — paused for "
                        f"{remaining / 60:.1f}min"
                    ),
                )

        return FilterResult(verdict=FilterVerdict.ALLOW)
