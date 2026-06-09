from __future__ import annotations

import logging
from pathlib import Path

from core.config import Config
from core.models import Signal, SignalDirection
from signals.base import BaseSignal

log = logging.getLogger(__name__)


class GenericCSVSignal(BaseSignal):
    """Generic signal plugin for any CSV indicator type.

    Reads ``<SYMBOL>_<indicator>_<TF>.csv`` and passes all fields as metadata.
    Direction is always NEUTRAL — these are used as conditions in expression
    rules, not as standalone directional signals.

    This class is the fallback for any indicator type not explicitly registered
    (e.g. ema50, rsi14, adx, bb, macd, stoch, atr).
    """

    def __init__(self, config: Config, indicator: str, timeframe: str) -> None:
        super().__init__(config)
        self._indicator = indicator
        self._timeframe = timeframe
        self.name = f"{indicator}_{timeframe}"

    def read(self) -> Signal:
        csv_dir = self.config.get("signals.csv_dir", "../MetaTrader5-Docker/data/signals")
        symbol = self.config.get("trading.symbol", "XAUUSD")
        path = Path(csv_dir) / f"{symbol}_{self._indicator}_{self._timeframe}.csv"
        data = self._read_csv(path)

        if not data:
            return Signal(source=self.name, direction=SignalDirection.NEUTRAL)

        return Signal(
            source=self.name,
            direction=SignalDirection.NEUTRAL,
            metadata=dict(data),
        )
