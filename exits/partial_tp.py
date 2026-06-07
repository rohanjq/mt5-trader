from __future__ import annotations

import logging
from typing import Any

from core.config import Config
from core.models import Signal, TradeRecord
from exits.base import BaseExitRule, ExitAction, ExitResult

log = logging.getLogger(__name__)


class PartialTPExit(BaseExitRule):
    """Deprecated — partial TP is now handled via dual-order placement.

    The initiator places two orders (main with TP + runner without TP) and
    the manager handles TP-hit detection via sync_positions_from_mt5().
    This rule is kept as a no-op for backward compatibility.
    """

    name = "partial_tp"
    description = "Partial TP (handled by dual-order system)"

    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        return ExitResult(action=ExitAction.HOLD)
