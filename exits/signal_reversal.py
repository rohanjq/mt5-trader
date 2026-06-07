from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, SignalDirection, TradeDirection, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class SignalReversalExit(BaseExitRule):
    """Close the position when the entry signal source flips to the opposite direction.

    BUY position + signal flips to SELL → close.
    SELL position + signal flips to BUY → close.

    Does NOT close on NEUTRAL — only on confirmed reversal.
    """

    name = "signal_reversal"
    description = "Close on signal reversal"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        if not self.config.get("exit_rules.signal_reversal_exit", True):
            return ExitResult(action=ExitAction.HOLD)

        sig = signals.get(trade.signal_source)
        if sig is None:
            # Expression rules set signal_source to the rule name (e.g. "ema_pullback"),
            # not a signal key (e.g. "utbot_M1"), so lookup fails. This exit rule only
            # works for Python rules that set signal_source to an actual signal key.
            return ExitResult(action=ExitAction.HOLD)

        if trade.direction == TradeDirection.BUY and sig.direction == SignalDirection.SELL:
            return ExitResult(
                action=ExitAction.CLOSE,
                reason=f"Signal {trade.signal_source} reversed to SELL",
            )
        if trade.direction == TradeDirection.SELL and sig.direction == SignalDirection.BUY:
            return ExitResult(
                action=ExitAction.CLOSE,
                reason=f"Signal {trade.signal_source} reversed to BUY",
            )

        return ExitResult(action=ExitAction.HOLD)
