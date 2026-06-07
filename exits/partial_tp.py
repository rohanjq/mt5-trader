from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class PartialTPExit(BaseExitRule):
    """Partial take-profit: close most of the position at TP, let the rest run.

    When price hits the TP level:
    1. Close ``tp_close_pct`` (default 80%) of the volume at market
    2. Move SL on the remainder to midpoint between entry and TP
    3. Remove the TP so the remainder runs until SL or manual close

    Config:
        exit_rules.partial_tp: true/false (enable/disable)
        exit_rules.tp_close_pct: 80.0  (% of volume to close at TP)
    """

    name = "partial_tp"
    description = "Partial close at TP, let remainder run"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        if not self.config.get("exit_rules.partial_tp", False):
            return ExitResult(action=ExitAction.HOLD)

        # Only fire once per trade
        if trade.partial_tp_done:
            return ExitResult(action=ExitAction.HOLD)

        if trade.tp <= 0 or not tick:
            return ExitResult(action=ExitAction.HOLD)

        # Check if price has reached the TP level
        if trade.direction == TradeDirection.BUY:
            current_price = tick.bid
            reached_tp = current_price >= trade.tp
        else:
            current_price = tick.ask
            reached_tp = current_price <= trade.tp

        if not reached_tp:
            return ExitResult(action=ExitAction.HOLD)

        # --- TP reached: do the partial close ---
        close_pct = float(self.config.get("exit_rules.tp_close_pct", 80.0))
        close_volume = round(trade.volume * (close_pct / 100.0), 2)
        remain_volume = round(trade.volume - close_volume, 2)

        # Safety: ensure we close at least something and leave at least min lot
        if close_volume <= 0 or remain_volume < 0.01:
            # Volume too small to split — just let normal TP handle it
            return ExitResult(action=ExitAction.HOLD)

        log.info(
            "Partial TP: %s price=%.2f reached TP=%.2f — closing %.2f of %.2f (%.0f%%)",
            trade.direction.value, current_price, trade.tp,
            close_volume, trade.volume, close_pct,
        )

        # Partial close via MT5
        from core.mt5_client import MT5Client
        mt5: MT5Client = self._mt5
        result = mt5.close_position(
            ticket=trade.ticket,
            volume=close_volume,
            direction=trade.direction.value,
            symbol=trade.symbol,
        )

        if not result or result.retcode != 10009:
            retcode = result.retcode if result else "N/A"
            log.error("Partial TP close FAILED: retcode=%s", retcode)
            return ExitResult(action=ExitAction.HOLD)

        # Partial close succeeded
        profit_on_closed = (
            (current_price - trade.entry_price) * close_volume
            if trade.direction == TradeDirection.BUY
            else (trade.entry_price - current_price) * close_volume
        )

        from core.events import EventLog
        EventLog.get().trade(
            f"Partial TP: closed {close_volume:.2f} of {trade.volume:.2f} "
            f"@ {current_price:.2f} (+${profit_on_closed:.2f})"
        )

        # Update the trade record for the remainder
        trade.partial_tp_done = True
        trade.volume = remain_volume

        # New SL = midpoint between entry and TP (lock in ~50% of the full move)
        new_sl = (trade.entry_price + trade.tp) / 2.0

        # Remove TP on remainder — let it run
        mt5.modify_position(
            ticket=trade.ticket,
            sl=new_sl,
            tp=0.0,
            symbol=trade.symbol,
        )

        trade.sl = new_sl
        trade.tp = 0.0

        log.info(
            "Partial TP done: remainder=%.2f lots, new SL=%.2f (midpoint), TP removed — let it run",
            remain_volume, new_sl,
        )
        EventLog.get().info(
            f"Remainder {remain_volume:.2f} lots running — "
            f"SL moved to ${new_sl:.2f} (midpoint), no TP"
        )

        # Return HOLD — we already handled everything directly
        return ExitResult(action=ExitAction.HOLD)
