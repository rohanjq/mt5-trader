from __future__ import annotations

import logging
from pathlib import Path

from core.config import Config
from core.models import Signal, SignalDirection
from signals.base import BaseSignal

log = logging.getLogger(__name__)


class UTBotSignal(BaseSignal):
    """Reads UT Bot Alerts EA signal from CSV.

    Emits BUY when current_bias=BULLISH and last_signal_type=BUY,
    SELL when current_bias=BEARISH and last_signal_type=SELL,
    NEUTRAL otherwise.
    """

    name = "ut_bot_1m"

    def read(self) -> Signal:
        csv_dir = self.config.get("signals.csv_dir", "../MetaTrader5-Docker/data/signals")
        path = Path(csv_dir) / "ut_bot_signals.csv"
        data = self._read_csv(path)

        if not data:
            return Signal(source=self.name, direction=SignalDirection.NEUTRAL)

        bias = data.get("current_bias", "").upper()
        last_signal = data.get("last_signal_type", "").upper()

        metadata = {
            "bias": bias,
            "last_signal": last_signal,
            "trail_stop": data.get("trail_stop", ""),
            "bid": data.get("bid", ""),
            "ask": data.get("ask", ""),
            "atr_value": data.get("atr_value", ""),
            "consecutive_bull_bars": data.get("consecutive_bull_bars", ""),
            "consecutive_bear_bars": data.get("consecutive_bear_bars", ""),
            "bars_since_signal": data.get("bars_since_signal", ""),
        }

        if bias == "BULLISH" and last_signal == "BUY":
            direction = SignalDirection.BUY
        elif bias == "BEARISH" and last_signal == "SELL":
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        return Signal(
            source=self.name,
            direction=direction,
            metadata=metadata,
        )
