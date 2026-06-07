from __future__ import annotations

import logging
from pathlib import Path

from core.config import Config
from core.models import Signal, SignalDirection
from signals.base import BaseSignal

log = logging.getLogger(__name__)


class DonchianChannelSignal(BaseSignal):
    """Reads Donchian Channel EA signal from CSV.

    The EA writes dc_channels_<SYMBOL>.csv with channel data, wick detection, etc.
    This plugin reports:
      - UPPER_WICK_REJECTION → potential SELL signal
      - LOWER_WICK_REJECTION → potential BUY signal
      - Otherwise NEUTRAL

    This signal alone doesn't trigger trades — it's combined with UT Bot
    via the DCReversalStrategy.
    """

    name = "dc_channels"

    def read(self) -> Signal:
        csv_dir = self.config.get("signals.csv_dir", "../MetaTrader5-Docker/data/signals")
        symbol = self.config.get("trading.symbol", "BTCUSDT")
        path = Path(csv_dir) / f"dc_channels_{symbol}.csv"
        data = self._read_csv(path)

        if not data:
            return Signal(source=self.name, direction=SignalDirection.NEUTRAL)

        upper_wick = data.get("upper_wick_rejection", "").upper() == "TRUE"
        lower_wick = data.get("lower_wick_rejection", "").upper() == "TRUE"

        metadata = {
            "upper_band": data.get("upper_band", ""),
            "lower_band": data.get("lower_band", ""),
            "mid_band": data.get("mid_band", ""),
            "channel_width": data.get("channel_width", ""),
            "price_zone": data.get("price_zone", ""),
            "pct_in_channel": data.get("pct_in_channel", ""),
            "touched_upper": data.get("touched_upper", ""),
            "touched_lower": data.get("touched_lower", ""),
            "upper_wick_rejection": data.get("upper_wick_rejection", ""),
            "lower_wick_rejection": data.get("lower_wick_rejection", ""),
        }

        if upper_wick:
            direction = SignalDirection.SELL
        elif lower_wick:
            direction = SignalDirection.BUY
        else:
            direction = SignalDirection.NEUTRAL

        return Signal(
            source=self.name,
            direction=direction,
            metadata=metadata,
        )
