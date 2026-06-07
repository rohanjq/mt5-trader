from __future__ import annotations

import logging
import time

from core.config import Config
from core.models import FilterResult, FilterVerdict, TradeRequest
from filters.base import BaseFilter

log = logging.getLogger(__name__)


class CooldownFilter(BaseFilter):
    """Blocks trading for X minutes after a losing trade."""

    name = "cooldown"
    description = "Cooldown after a losing trade"

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def evaluate(self, request: TradeRequest) -> FilterResult:
        if self._trade_manager is None:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        cooldown_minutes = self.config.get("filters.cooldown_minutes", 5)
        last_loss_time = self._trade_manager.last_loss_time

        if last_loss_time is None:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        elapsed = time.time() - last_loss_time
        remaining = (cooldown_minutes * 60) - elapsed

        if remaining > 0:
            mins = remaining / 60
            return FilterResult(
                verdict=FilterVerdict.BLOCK,
                reason=f"Cooldown active — {mins:.1f} min remaining after last loss",
            )

        return FilterResult(verdict=FilterVerdict.ALLOW)
