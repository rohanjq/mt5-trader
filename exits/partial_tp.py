from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class PartialTPExit(BaseExitRule):
    """Monitor runner orders and move SL to midpoint when TP target is reached.

    Runner orders have TP=0 on the broker but store the target TP internally
    in trade.tp. When price reaches that level, this rule moves the runner's
    SL to the midpoint between entry and TP, then clears the internal TP
    so the runner continues with SL only.
    """

    name = "partial_tp"
    description = "Runner: SL to midpoint at TP target"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        # Only applies to runners with an internal TP target
        if not trade.signal_source.endswith("_runner"):
            return ExitResult(action=ExitAction.HOLD)
        if trade.tp <= 0 or not tick:
            return ExitResult(action=ExitAction.HOLD)

        # Check if price has reached the TP target
        if trade.direction == TradeDirection.BUY:
            reached = tick.bid >= trade.tp
        else:
            reached = tick.ask <= trade.tp

        if not reached:
            return ExitResult(action=ExitAction.HOLD)

        # TP target reached — move SL to midpoint, clear internal TP
        midpoint = (trade.entry_price + trade.tp) / 2.0
        log.info(
            "Runner TP target reached (ticket=%s): price hit %.2f — SL → %.2f (midpoint)",
            trade.ticket, trade.tp, midpoint,
        )
        from core.events import EventLog
        EventLog.get().trade(
            f"Runner TP target hit — SL → {midpoint:.2f} (midpoint), let it run"
        )

        # Clear the internal TP so this doesn't re-trigger
        trade.tp = 0.0

        return ExitResult(
            action=ExitAction.MODIFY_SL,
            reason=f"Runner TP target hit — SL to midpoint {midpoint:.2f}",
            new_sl=midpoint,
        )
