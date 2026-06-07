from __future__ import annotations

import logging
from pathlib import Path

from core.config import Config
from core.models import Signal, SignalDirection
from signals.base import BaseSignal

log = logging.getLogger(__name__)


class DonchianSignal(BaseSignal):
    """Reads Donchian Channel signal from SignalMaster CSV.

    File: ``<SYMBOL>_dc_<TF>.csv`` (e.g. ``BTCUSDT_dc_M15.csv``)

    Uses closed bar data for confirmed signals:
      - closed_lower_wick_rej=TRUE → BUY
      - closed_upper_wick_rej=TRUE → SELL
      - Otherwise NEUTRAL

    All CSV fields are passed through as metadata for trigger rules.
    """

    def __init__(self, config: Config, timeframe: str = "M15") -> None:
        super().__init__(config)
        self._timeframe = timeframe
        self.name = f"dc_{timeframe}"

    def read(self) -> Signal:
        csv_dir = self.config.get("signals.csv_dir", "../MetaTrader5-Docker/data/signals")
        symbol = self.config.get("trading.symbol", "BTCUSDT")
        path = Path(csv_dir) / f"{symbol}_dc_{self._timeframe}.csv"
        data = self._read_csv(path)

        if not data:
            return Signal(source=self.name, direction=SignalDirection.NEUTRAL)

        metadata = dict(data)

        upper_wick = data.get("closed_upper_wick_rej", "").upper() == "TRUE"
        lower_wick = data.get("closed_lower_wick_rej", "").upper() == "TRUE"

        if lower_wick:
            direction = SignalDirection.BUY
        elif upper_wick:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.NEUTRAL

        return Signal(
            source=self.name,
            direction=direction,
            metadata=metadata,
        )
