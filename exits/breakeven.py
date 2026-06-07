from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class BreakevenExit(BaseExitRule):
    """Move SL to entry price (breakeven) when price moves a fixed $ amount.

    e.g. breakeven_trigger_dollars=1.75 means: when price is $1.75 above entry
    (for BUY), move SL to entry price.
    """

    name = "breakeven"
    description = "Move SL to entry at $ threshold"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        trigger = self.config.get("exit_rules.breakeven_trigger_dollars", 0.0)
        if not trigger or float(trigger) <= 0:
            return ExitResult(action=ExitAction.HOLD)
        trigger = float(trigger)

        if trade.sl == 0 or not tick:
            return ExitResult(action=ExitAction.HOLD)

        # Already at or past breakeven — don't move SL backwards
        if trade.direction == TradeDirection.BUY and trade.sl >= trade.entry_price:
            return ExitResult(action=ExitAction.HOLD)
        if trade.direction == TradeDirection.SELL and trade.sl <= trade.entry_price:
            return ExitResult(action=ExitAction.HOLD)

        # Check price movement from entry
        if trade.direction == TradeDirection.BUY:
            price_move = tick.bid - trade.entry_price
        else:
            price_move = trade.entry_price - tick.ask

        if price_move >= trigger:
            log.info(
                "Breakeven triggered: price moved $%.2f >= $%.2f threshold — moving SL to %.2f",
                price_move, trigger, trade.entry_price,
            )
            return ExitResult(
                action=ExitAction.MODIFY_SL,
                reason=f"Price moved ${price_move:.2f} >= ${trigger:.2f} — SL to breakeven",
                new_sl=trade.entry_price,
            )

        return ExitResult(action=ExitAction.HOLD)
