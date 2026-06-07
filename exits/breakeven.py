from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class BreakevenExit(BaseExitRule):
    """Move SL to entry price (breakeven) when profit reaches a threshold.

    Threshold is expressed as a multiple of the risk (R).
    e.g. breakeven_at_r=1.75 means: when unrealized profit >= 1.75 × risk_dollars,
    move SL to entry price.
    """

    name = "breakeven"
    description = "Move SL to entry at R threshold"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        threshold_r = self.config.get("exit_rules.breakeven_at_r", 0.0)
        if threshold_r <= 0:
            return ExitResult(action=ExitAction.HOLD)

        if trade.risk_dollars <= 0 or trade.sl == 0:
            return ExitResult(action=ExitAction.HOLD)

        # Already at or past breakeven — don't move SL backwards
        if trade.direction == TradeDirection.BUY and trade.sl >= trade.entry_price:
            return ExitResult(action=ExitAction.HOLD)
        if trade.direction == TradeDirection.SELL and trade.sl != 0 and trade.sl <= trade.entry_price:
            return ExitResult(action=ExitAction.HOLD)

        # Calculate current profit in R multiples
        current_r = trade.profit / trade.risk_dollars if trade.risk_dollars else 0

        if current_r >= threshold_r:
            log.info(
                "Breakeven triggered: profit=%.2f (%.1fR) >= threshold %.1fR — moving SL to %.2f",
                trade.profit, current_r, threshold_r, trade.entry_price,
            )
            return ExitResult(
                action=ExitAction.MODIFY_SL,
                reason=f"Profit {current_r:.1f}R >= {threshold_r:.1f}R — SL to breakeven",
                new_sl=trade.entry_price,
            )

        return ExitResult(action=ExitAction.HOLD)
