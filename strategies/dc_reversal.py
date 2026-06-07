from __future__ import annotations

import logging

from core.config import Config
from core.models import Signal, SignalDirection, TradeDirection
from strategies.base import BaseStrategy, StrategySignal

log = logging.getLogger(__name__)


class DCReversalStrategy(BaseStrategy):
    """Donchian Channel reversal + UT Bot confirmation.

    BUY conditions:
      - DC channel shows lower_wick_rejection (price touched lower band, wicked)
      - UT Bot 1m says BUY

    SELL conditions:
      - DC channel shows upper_wick_rejection (price touched upper band, wicked)
      - UT Bot 1m says SELL

    Higher priority than plain UT Bot — evaluated first.
    """

    name = "dc_reversal"
    description = "DC channel wick rejection + UT Bot confirmation"
    priority = 100  # higher priority than utbot_simple

    def evaluate(self, signals: dict[str, Signal]) -> StrategySignal:
        if not self.config.get("strategies.dc_reversal.enabled", True):
            return StrategySignal()

        dc = signals.get("dc_channels")
        ut = signals.get("ut_bot_1m")

        if dc is None or ut is None:
            return StrategySignal()

        dc_meta = dc.metadata
        upper_wick = dc_meta.get("upper_wick_rejection", "").upper() == "TRUE"
        lower_wick = dc_meta.get("lower_wick_rejection", "").upper() == "TRUE"

        # BUY: price wicked off lower DC band + UT Bot confirms BUY
        if lower_wick and ut.direction == SignalDirection.BUY:
            log.info(
                "DC Reversal BUY: lower wick rejection at %s, UT Bot confirms BUY",
                dc_meta.get("lower_band", "?"),
            )
            return StrategySignal(
                should_trade=True,
                direction=TradeDirection.BUY,
                reason=f"DC lower wick rejection + UT Bot BUY (band={dc_meta.get('lower_band', '?')})",
                strategy_name=self.name,
            )

        # SELL: price wicked off upper DC band + UT Bot confirms SELL
        if upper_wick and ut.direction == SignalDirection.SELL:
            log.info(
                "DC Reversal SELL: upper wick rejection at %s, UT Bot confirms SELL",
                dc_meta.get("upper_band", "?"),
            )
            return StrategySignal(
                should_trade=True,
                direction=TradeDirection.SELL,
                reason=f"DC upper wick rejection + UT Bot SELL (band={dc_meta.get('upper_band', '?')})",
                strategy_name=self.name,
            )

        return StrategySignal()
