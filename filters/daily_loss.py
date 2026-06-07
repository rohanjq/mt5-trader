from __future__ import annotations

import logging

from core.config import Config
from core.models import FilterResult, FilterVerdict, TradeRequest
from filters.base import BaseFilter

log = logging.getLogger(__name__)


class DailyLossFilter(BaseFilter):
    """Blocks trading when daily net P&L exceeds the max loss threshold."""

    name = "daily_loss"
    description = "Max daily loss limit"

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def evaluate(self, request: TradeRequest) -> FilterResult:
        if self._trade_manager is None:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        max_daily_loss = self.config.get("filters.max_daily_loss", -1)
        if max_daily_loss < 0:
            return FilterResult(verdict=FilterVerdict.ALLOW)

        stats = self._trade_manager.today_stats()
        net_pnl = stats["net_pnl"]

        if net_pnl <= -max_daily_loss:
            return FilterResult(
                verdict=FilterVerdict.BLOCK,
                reason=(
                    f"Daily loss limit reached: {net_pnl:+.2f} "
                    f"(max: -${max_daily_loss:.0f})"
                ),
            )

        return FilterResult(verdict=FilterVerdict.ALLOW)
