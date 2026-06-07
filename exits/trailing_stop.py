from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class TrailingStopExit(BaseExitRule):
    """Trail the stop loss at a fixed R-distance below (above) the best price.

    When trailing_stop_r > 0, the SL is moved to:
      BUY: max_price - (trailing_stop_r × risk_dollars / volume)
      SELL: min_price + (trailing_stop_r × risk_dollars / volume)

    SL only moves in the profitable direction — never backwards.
    """

    name = "trailing_stop"
    description = "Trail SL at R distance from best price"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        trail_r = self.config.get("exit_rules.trailing_stop_r", 0.0)
        if trail_r <= 0:
            return ExitResult(action=ExitAction.HOLD)

        if trade.risk_dollars <= 0 or trade.volume <= 0:
            return ExitResult(action=ExitAction.HOLD)

        # SL distance in price units for 1R
        r_price = trade.risk_dollars / trade.volume
        trail_distance = trail_r * r_price

        if trade.direction == TradeDirection.BUY:
            current_price = tick.bid if tick else 0
            if current_price <= 0:
                return ExitResult(action=ExitAction.HOLD)
            new_sl = current_price - trail_distance
            # Only move SL up, never down
            if new_sl <= trade.sl:
                return ExitResult(action=ExitAction.HOLD)
            # Don't trail until we're past breakeven
            if new_sl <= trade.entry_price:
                return ExitResult(action=ExitAction.HOLD)
        else:
            current_price = tick.ask if tick else 0
            if current_price <= 0:
                return ExitResult(action=ExitAction.HOLD)
            new_sl = current_price + trail_distance
            # Only move SL down, never up
            if trade.sl != 0 and new_sl >= trade.sl:
                return ExitResult(action=ExitAction.HOLD)
            if new_sl >= trade.entry_price:
                return ExitResult(action=ExitAction.HOLD)

        log.info(
            "Trailing stop: moving SL from %.2f to %.2f (trail %.1fR = %.2f pts)",
            trade.sl, new_sl, trail_r, trail_distance,
        )
        return ExitResult(
            action=ExitAction.MODIFY_SL,
            reason=f"Trailing SL to {new_sl:.2f}",
            new_sl=new_sl,
        )
