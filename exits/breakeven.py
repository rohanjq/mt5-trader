from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class BreakevenExit(BaseExitRule):
    """Move SL to entry price (breakeven) when price moves a % of risk in our favor.

    Uses per-trade ``breakeven_pct`` (set per strategy or global default).
    e.g. breakeven_pct=65 with sl_dollars=$175 → breakeven triggers when price
    moves $113.75 in our favor (65% of $175).
    """

    name = "breakeven"
    description = "Move SL to entry at % of risk"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        # Per-trade pct takes priority, fall back to global config
        be_pct = trade.breakeven_pct
        if not be_pct or be_pct <= 0:
            be_pct = float(self.config.get("exit_rules.breakeven_pct", 0.0))
        if be_pct <= 0:
            return ExitResult(action=ExitAction.HOLD)

        # Need risk_dollars to calculate the trigger threshold
        risk = trade.risk_dollars
        if risk <= 0 or trade.sl == 0 or not tick:
            return ExitResult(action=ExitAction.HOLD)

        trigger_dollars = risk * (be_pct / 100.0)

        # Already at or past breakeven — don't move SL backwards
        if trade.direction == TradeDirection.BUY and trade.sl >= trade.entry_price:
            return ExitResult(action=ExitAction.HOLD)
        if trade.direction == TradeDirection.SELL and trade.sl <= trade.entry_price:
            return ExitResult(action=ExitAction.HOLD)

        # Check price movement from executed entry price
        if trade.direction == TradeDirection.BUY:
            price_move = tick.bid - trade.entry_price
        else:
            price_move = trade.entry_price - tick.ask

        if price_move >= trigger_dollars:
            log.info(
                "Breakeven triggered: price moved $%.2f >= $%.2f (%.0f%% of $%.0f risk) — SL to %.2f",
                price_move, trigger_dollars, be_pct, risk, trade.entry_price,
            )
            from core.events import EventLog
            EventLog.get().info(
                f"Breakeven: moved ${price_move:.1f} >= ${trigger_dollars:.1f} "
                f"({be_pct:.0f}% of ${risk:.0f}) — SL → entry"
            )
            return ExitResult(
                action=ExitAction.MODIFY_SL,
                reason=f"Price moved ${price_move:.2f} >= ${trigger_dollars:.2f} ({be_pct:.0f}% risk) — SL to breakeven",
                new_sl=trade.entry_price,
            )

        return ExitResult(action=ExitAction.HOLD)
