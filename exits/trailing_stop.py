from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class TrailingStopExit(BaseExitRule):
    """Trail the stop loss at a fixed $ distance below (above) the current price.

    When trailing_stop_dollars > 0, the SL is moved to:
      BUY: current_bid - trailing_stop_dollars
      SELL: current_ask + trailing_stop_dollars

    SL only moves in the profitable direction — never backwards.
    Only activates once price is past breakeven.
    """

    name = "trailing_stop"
    description = "Trail SL at fixed $ distance from price"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        trail_dollars = self.config.get("exit_rules.trailing_stop_dollars", 0.0)
        if not trail_dollars or float(trail_dollars) <= 0:
            return ExitResult(action=ExitAction.HOLD)
        trail_dollars = float(trail_dollars)

        if not tick:
            return ExitResult(action=ExitAction.HOLD)

        if trade.direction == TradeDirection.BUY:
            current_price = tick.bid
            if current_price <= 0:
                return ExitResult(action=ExitAction.HOLD)
            new_sl = current_price - trail_dollars
            # Only move SL up, never down
            if new_sl <= trade.sl:
                return ExitResult(action=ExitAction.HOLD)
            # Don't trail until we're past breakeven
            if new_sl <= trade.entry_price:
                return ExitResult(action=ExitAction.HOLD)
        else:
            current_price = tick.ask
            if current_price <= 0:
                return ExitResult(action=ExitAction.HOLD)
            new_sl = current_price + trail_dollars
            # Only move SL down, never up
            if trade.sl != 0 and new_sl >= trade.sl:
                return ExitResult(action=ExitAction.HOLD)
            if new_sl >= trade.entry_price:
                return ExitResult(action=ExitAction.HOLD)

        log.info(
            "Trailing stop: moving SL from %.2f to %.2f (trail $%.2f)",
            trade.sl, new_sl, trail_dollars,
        )
        return ExitResult(
            action=ExitAction.MODIFY_SL,
            reason=f"Trailing SL to {new_sl:.2f}",
            new_sl=new_sl,
        )
