from __future__ import annotations

import logging

from core.models import Signal
from rules.base import BaseRule, TriggerAction, TriggerResult

log = logging.getLogger(__name__)


class UTBotSimpleRule(BaseRule):
    """Trade on UT Bot 1min signal alone. Good for testing.

    BUY: UT Bot 1min closed_signal is BUY
    SELL: UT Bot 1min closed_signal is SELL
    """

    name = "utbot_simple"
    description = "UT Bot 1m signal only"
    priority = 200  # lowest priority — other rules take precedence

    def evaluate(self, signals: dict[str, Signal]) -> TriggerResult:
        if not self.config.get("rules.utbot_simple.enabled", False):
            self._last_result = TriggerResult()
            return self._last_result

        tf = self.config.get("rules.utbot_simple.timeframe", "M1")
        signal = self._val(signals, f"utbot_{tf}", "closed_signal").upper()

        if signal == "BUY":
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_BUY,
                reason=f"UT Bot {tf} signal=BUY",
                rule_name=self.name,
            )
            return self._last_result

        if signal == "SELL":
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_SELL,
                reason=f"UT Bot {tf} signal=SELL",
                rule_name=self.name,
            )
            return self._last_result

        self._last_result = TriggerResult(rule_name=self.name)
        return self._last_result
