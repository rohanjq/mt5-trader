"""Incremental candle builder — constructs OHLCV bars from raw ticks.

Candle OHLC is built from the bid price (matching MT5 for forex/CFD).
Each timeframe gets its own ``CandleBuilder`` that tracks a running
candle and emits completed candles when a tick crosses the boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

_TF_MINUTES: dict[str, int] = {
    "M1": 1, "M2": 2, "M3": 3, "M5": 5, "M10": 10,
    "M15": 15, "M20": 20, "M30": 30, "M45": 45,
    "H1": 60, "H2": 120, "H3": 180, "H4": 240,
    "H6": 360, "H8": 480, "H12": 720, "D1": 1440,
}


class CandleBuilder:
    """Builds OHLCV candles from a stream of ticks for one timeframe.

    The candle boundary is ``floor(minutes_since_midnight / tf_minutes)``,
    which correctly handles all MT5 timeframes including M45 and H4::

        cb = CandleBuilder(5)          # M5
        for time, price in ticks:
            closed = cb.on_tick(time, price)
            if closed:
                bar = cb.closed_candles[-1]
        cb.finalize()                  # flush last in-progress bar
    """

    __slots__ = (
        "tf_minutes", "closed_candles",
        "_bar_start", "_open", "_high", "_low", "_close", "_volume",
    )

    def __init__(self, tf_minutes: int) -> None:
        self.tf_minutes = tf_minutes
        self.closed_candles: list[tuple[datetime, float, float, float, float, int]] = []
        self._bar_start: datetime | None = None
        self._open = self._high = self._low = self._close = 0.0
        self._volume = 0

    # ── core ─────────────────────────────────────────────────────────────

    def bar_start_for(self, dt: datetime) -> datetime:
        """Return the candle-open time that *dt* falls into."""
        midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        mins = dt.hour * 60 + dt.minute
        bar_min = (mins // self.tf_minutes) * self.tf_minutes
        return midnight + timedelta(minutes=bar_min)

    def on_tick(self, tick_time: datetime, price: float) -> bool:
        """Feed one tick.  Returns ``True`` when a candle just closed."""
        bar_start = self.bar_start_for(tick_time)

        if self._bar_start is None:
            self._bar_start = bar_start
            self._open = self._high = self._low = self._close = price
            self._volume = 1
            return False

        if bar_start > self._bar_start:
            # Previous candle is complete — archive it
            self.closed_candles.append((
                self._bar_start, self._open, self._high,
                self._low, self._close, self._volume,
            ))
            self._bar_start = bar_start
            self._open = self._high = self._low = self._close = price
            self._volume = 1
            return True

        # Same candle — update running OHLCV
        if price > self._high:
            self._high = price
        if price < self._low:
            self._low = price
        self._close = price
        self._volume += 1
        return False

    def finalize(self) -> None:
        """Flush the in-progress candle as a closed bar."""
        if self._bar_start is not None:
            self.closed_candles.append((
                self._bar_start, self._open, self._high,
                self._low, self._close, self._volume,
            ))
            self._bar_start = None

    # ── accessors ────────────────────────────────────────────────────────

    @property
    def running(self) -> tuple[datetime, float, float, float, float, int] | None:
        """Current in-progress candle ``(time, O, H, L, C, vol)``."""
        if self._bar_start is None:
            return None
        return (self._bar_start, self._open, self._high,
                self._low, self._close, self._volume)

    @property
    def n_closed(self) -> int:
        return len(self.closed_candles)

    def to_dataframe(self) -> pd.DataFrame:
        cols = ["time", "open", "high", "low", "close", "volume"]
        if not self.closed_candles:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame(self.closed_candles, columns=cols)
