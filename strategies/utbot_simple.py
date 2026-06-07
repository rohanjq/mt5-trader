from __future__ import annotations

import logging

from core.config import Config
from core.models import Signal, SignalDirection, TradeDirection
from strategies.base import BaseStrategy, StrategySignal

log = logging.getLogger(__name__)


class UTBotStrategy(BaseStrategy):
    """Simple strategy: UT Bot BUY → open BUY, UT Bot SELL → open SELL.

    Lower priority than DCReversal — only fires if DC reversal conditions
    aren't met.
    """

    name = "utbot_simple"
    description = "Trade on UT Bot signal alone"
    priority = 200  # lower priority than DC reversal

    def evaluate(self, signals: dict[str, Signal]) -> StrategySignal:
        if not self.config.get("strategies.utbot_simple.enabled", True):
            return StrategySignal()

        sig = signals.get("ut_bot_1m")
        if sig is None or sig.direction == SignalDirection.NEUTRAL:
            return StrategySignal()

        direction = (
            TradeDirection.BUY if sig.direction == SignalDirection.BUY
            else TradeDirection.SELL
        )

        return StrategySignal(
            should_trade=True,
            direction=direction,
            reason=f"UT Bot 1m says {direction.value}",
            strategy_name=self.name,
        )
