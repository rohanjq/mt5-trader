from __future__ import annotations

import logging

from core.models import Signal
from rules.base import BaseRule, TriggerAction, TriggerResult

log = logging.getLogger(__name__)


class DCConfluenceRule(BaseRule):
    """DC Low/High zone + UT Bot 1min signal + UT Bot 45min trend confirmation.

    BUY: DC 15min closed_price_zone is LOWER or LOWER_MID
         AND UT Bot 1min closed_signal is BUY
         AND UT Bot 45min consecutive_bull_bars >= 5

    SELL: DC 15min closed_price_zone is UPPER or UPPER_MID
          AND UT Bot 1min closed_signal is SELL
          AND UT Bot 45min consecutive_bear_bars >= 5
    """

    name = "dc_confluence"
    description = "DC zone + UT Bot 1m signal + 45m trend"
    priority = 100

    def evaluate(self, signals: dict[str, Signal]) -> TriggerResult:
        if not self.config.get("rules.dc_confluence.enabled", True):
            self._last_result = TriggerResult()
            return self._last_result

        dc_tf = self.config.get("rules.dc_confluence.dc_timeframe", "M15")
        ut_entry_tf = self.config.get("rules.dc_confluence.ut_entry_timeframe", "M1")
        ut_trend_tf = self.config.get("rules.dc_confluence.ut_trend_timeframe", "M45")
        min_trend_bars = self.config.get("rules.dc_confluence.min_trend_bars", 5)

        zone = self._val(signals, f"dc_{dc_tf}", "closed_price_zone").upper()
        ut_signal = self._val(signals, f"utbot_{ut_entry_tf}", "closed_signal").upper()
        bull_bars = self._int_val(signals, f"utbot_{ut_trend_tf}", "consecutive_bull_bars")
        bear_bars = self._int_val(signals, f"utbot_{ut_trend_tf}", "consecutive_bear_bars")

        # BUY
        if zone in ("LOWER", "LOWER_MID") and ut_signal == "BUY" and bull_bars >= min_trend_bars:
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_BUY,
                reason=f"DC {dc_tf} zone={zone}, UT {ut_entry_tf} BUY, UT {ut_trend_tf} bull={bull_bars}",
                rule_name=self.name,
            )
            return self._last_result

        # SELL
        if zone in ("UPPER", "UPPER_MID") and ut_signal == "SELL" and bear_bars >= min_trend_bars:
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_SELL,
                reason=f"DC {dc_tf} zone={zone}, UT {ut_entry_tf} SELL, UT {ut_trend_tf} bear={bear_bars}",
                rule_name=self.name,
            )
            return self._last_result

        self._last_result = TriggerResult(rule_name=self.name)
        return self._last_result
