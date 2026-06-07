from __future__ import annotations

import logging
from pathlib import Path

from core.config import Config
from core.models import Signal, SignalDirection
from signals.base import BaseSignal

log = logging.getLogger(__name__)


class UTBotSignal(BaseSignal):
    """Reads UT Bot signal from SignalMaster CSV.

    File: ``<SYMBOL>_utbot_<TF>.csv`` (e.g. ``BTCUSDT_utbot_M1.csv``)

    Uses closed bar data for confirmed signals:
      - closed_bias=BULLISH + closed_signal=BUY → BUY
      - closed_bias=BEARISH + closed_signal=SELL → SELL
      - Otherwise NEUTRAL

    All key-value pairs from the CSV are passed through as metadata.
    """

    def __init__(self, config: Config, timeframe: str = "M1") -> None:
        super().__init__(config)
        self._timeframe = timeframe
        self.name = f"utbot_{timeframe}"

    def read(self) -> Signal:
        csv_dir = self.config.get("signals.csv_dir", "../MetaTrader5-Docker/data/signals")
        symbol = self.config.get("trading.symbol", "BTCUSDT")
        path = Path(csv_dir) / f"{symbol}_utbot_{self._timeframe}.csv"
        data = self._read_csv(path)

        if not data:
            return Signal(source=self.name, direction=SignalDirection.NEUTRAL)

        # Pass ALL fields as metadata — rules can access anything
        metadata = dict(data)

        bias = data.get("closed_bias", "").upper()
        signal = data.get("closed_signal", "").upper()

        if bias == "BULLISH" and signal == "BUY":
            direction = SignalDirection.BUY
        elif bias == "BEARISH" and signal == "SELL":
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        return Signal(
            source=self.name,
            direction=direction,
            metadata=metadata,
        )
