from __future__ import annotations

import logging
from pathlib import Path

from core.config import Config
from core.models import Signal, SignalDirection
from signals.base import BaseSignal

log = logging.getLogger(__name__)


class LiqGrabSignal(BaseSignal):
    """Reads Liquidity Grab signal from SignalMaster CSV.

    File: ``<SYMBOL>_liqgrab_<TF>.csv`` (e.g. ``BTCUSDT_liqgrab_M15.csv``)

    Uses the composite ``liq_signal`` field for direction:
      - liq_signal=BUY → BUY (rejection up + breakout up + above MA)
      - liq_signal=SELL → SELL (rejection down + breakout down + below MA)
      - Otherwise NEUTRAL

    All CSV fields are passed through as metadata for trigger rules.
    """

    def __init__(self, config: Config, timeframe: str = "M15") -> None:
        super().__init__(config)
        self._timeframe = timeframe
        self.name = f"liqgrab_{timeframe}"

    def read(self) -> Signal:
        csv_dir = self.config.get("signals.csv_dir", "data/signals")
        symbol = self.config.get("trading.symbol", "BTCUSDT")
        path = Path(csv_dir) / f"{symbol}_liqgrab_{self._timeframe}.csv"
        data = self._read_csv(path)

        if not data:
            return Signal(source=self.name, direction=SignalDirection.NEUTRAL)

        metadata = dict(data)

        liq_signal = data.get("liq_signal", "").upper()

        if liq_signal == "BUY":
            direction = SignalDirection.BUY
        elif liq_signal == "SELL":
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        return Signal(
            source=self.name,
            direction=direction,
            metadata=metadata,
        )
