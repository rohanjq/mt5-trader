from __future__ import annotations

import threading

from core.config import Config
from core.models import FilterResult, FilterVerdict, TradeRequest
from filters.base import BaseFilter


class ManualSwitchFilter(BaseFilter):
    """Blocks trading when the manual switch is off (system paused)."""

    name = "manual_switch"
    description = "Toggle auto-trading on/off"

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._enabled = threading.Event()
        self._enabled.set()  # enabled by default

    @property
    def is_enabled(self) -> bool:
        return self._enabled.is_set()

    def enable(self) -> None:
        self._enabled.set()

    def disable(self) -> None:
        self._enabled.clear()

    def toggle(self) -> bool:
        if self._enabled.is_set():
            self._enabled.clear()
            return False
        else:
            self._enabled.set()
            return True

    def evaluate(self, request: TradeRequest) -> FilterResult:
        if not self._enabled.is_set():
            return FilterResult(
                verdict=FilterVerdict.BLOCK,
                reason="Auto-trading is paused (manual switch OFF)",
            )
        return FilterResult(verdict=FilterVerdict.ALLOW)
