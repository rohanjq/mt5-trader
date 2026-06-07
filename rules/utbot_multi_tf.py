from __future__ import annotations

import logging

from core.models import Signal
from rules.base import BaseRule, TriggerAction, TriggerResult

log = logging.getLogger(__name__)


class UTBotMultiTFRule(BaseRule):
    """UT Bot multi-timeframe alignment.

    BUY: UT Bot 1min closed_signal is BUY
         AND UT Bot 15min closed_bias is BULLISH
         AND UT Bot 45min closed_bias is BULLISH

    SELL: UT Bot 1min closed_signal is SELL
          AND UT Bot 15min closed_bias is BEARISH
          AND UT Bot 45min closed_bias is BEARISH
    """

    name = "utbot_multi_tf"
    description = "UT Bot 1m signal + 15m + 45m bias alignment"
    priority = 120

    def evaluate(self, signals: dict[str, Signal]) -> TriggerResult:
        if not self.config.get("rules.utbot_multi_tf.enabled", True):
            self._last_result = TriggerResult()
            return self._last_result

        entry_tf = self.config.get("rules.utbot_multi_tf.entry_timeframe", "M1")
        mid_tf = self.config.get("rules.utbot_multi_tf.mid_timeframe", "M15")
        trend_tf = self.config.get("rules.utbot_multi_tf.trend_timeframe", "M45")

        entry_signal = self._val(signals, f"utbot_{entry_tf}", "closed_signal").upper()
        mid_bias = self._val(signals, f"utbot_{mid_tf}", "closed_bias").upper()
        trend_bias = self._val(signals, f"utbot_{trend_tf}", "closed_bias").upper()

        # BUY
        if entry_signal == "BUY" and mid_bias == "BULLISH" and trend_bias == "BULLISH":
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_BUY,
                reason=f"UT {entry_tf} BUY + UT {mid_tf} BULLISH + UT {trend_tf} BULLISH",
                rule_name=self.name,
            )
            return self._last_result

        # SELL
        if entry_signal == "SELL" and mid_bias == "BEARISH" and trend_bias == "BEARISH":
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_SELL,
                reason=f"UT {entry_tf} SELL + UT {mid_tf} BEARISH + UT {trend_tf} BEARISH",
                rule_name=self.name,
            )
            return self._last_result

        self._last_result = TriggerResult(rule_name=self.name)
        return self._last_result
