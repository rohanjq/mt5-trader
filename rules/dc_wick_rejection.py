from __future__ import annotations

import logging

from core.models import Signal
from rules.base import BaseRule, TriggerAction, TriggerResult

log = logging.getLogger(__name__)


class DCWickRejectionRule(BaseRule):
    """DC wick rejection + UT Bot bias confirmation.

    BUY: DC 15min closed_lower_wick_rej is TRUE
         AND UT Bot 3min closed_bias is BULLISH

    SELL: DC 15min closed_upper_wick_rej is TRUE
          AND UT Bot 3min closed_bias is BEARISH
    """

    name = "dc_wick_rejection"
    description = "DC wick rejection + UT Bot bias"
    priority = 110

    def evaluate(self, signals: dict[str, Signal]) -> TriggerResult:
        if not self.config.get("rules.dc_wick_rejection.enabled", True):
            self._last_result = TriggerResult()
            return self._last_result

        dc_tf = self.config.get("rules.dc_wick_rejection.dc_timeframe", "M15")
        ut_tf = self.config.get("rules.dc_wick_rejection.ut_timeframe", "M3")

        lower_wick = self._is_true(signals, f"dc_{dc_tf}", "closed_lower_wick_rej")
        upper_wick = self._is_true(signals, f"dc_{dc_tf}", "closed_upper_wick_rej")
        ut_bias = self._val(signals, f"utbot_{ut_tf}", "closed_bias").upper()

        # BUY
        if lower_wick and ut_bias == "BULLISH":
            band = self._val(signals, f"dc_{dc_tf}", "lower_band")
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_BUY,
                reason=f"DC {dc_tf} lower wick rej (band={band}), UT {ut_tf} BULLISH",
                rule_name=self.name,
            )
            return self._last_result

        # SELL
        if upper_wick and ut_bias == "BEARISH":
            band = self._val(signals, f"dc_{dc_tf}", "upper_band")
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_SELL,
                reason=f"DC {dc_tf} upper wick rej (band={band}), UT {ut_tf} BEARISH",
                rule_name=self.name,
            )
            return self._last_result

        self._last_result = TriggerResult(rule_name=self.name)
        return self._last_result
