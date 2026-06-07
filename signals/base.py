from __future__ import annotations

import abc
import csv
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.models import Signal, SignalDirection

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)


class BaseSignal(abc.ABC):
    """Base class for all signal plugins."""

    name: str = "unnamed"

    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def read(self) -> Signal:
        """Read the latest indicator state and return a normalised Signal."""
        ...

    def _read_csv(self, path: str | Path) -> dict[str, str]:
        """Read a key,value CSV into a dict. Returns empty dict on error.

        Handles UTF-16 LE files (common from Wine/MetaEditor) by trying
        utf-8 first, then utf-16, then latin-1 as fallback.
        """
        p = Path(path)
        if not p.exists():
            return {}
        for encoding in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                with open(p, newline="", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    data: dict[str, str] = {}
                    for row in reader:
                        k = row.get("key", "").strip()
                        v = row.get("value", "").strip()
                        if k:
                            data[k] = v
                    return data
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                log.exception("Error reading CSV %s", p)
                return {}
        return {}


def build_signal_plugins(config: Config) -> list[BaseSignal]:
    """Build signal plugin instances from config.

    Config format under ``signals.sources``:
      - indicator: utbot
        timeframes: [M1, M3, M10, M15, M45]
      - indicator: dc
        timeframes: [M1, M3, M5, M15, M45]
    """
    from signals.donchian import DonchianSignal
    from signals.generic import GenericCSVSignal
    from signals.liq_grab import LiqGrabSignal
    from signals.ut_bot import UTBotSignal

    indicator_classes = {
        "utbot": UTBotSignal,
        "dc": DonchianSignal,
        "liqgrab": LiqGrabSignal,
    }

    sources = config.get("signals.sources", [])
    if not sources:
        # Fallback: single UT Bot M1 for backwards compat
        log.warning("No signals.sources in config — using default utbot M1")
        return [UTBotSignal(config, "M1")]

    plugins: list[BaseSignal] = []
    for src in sources:
        indicator = src.get("indicator", "")
        cls = indicator_classes.get(indicator)
        for tf in src.get("timeframes", []):
            if cls is not None:
                instance = cls(config, tf)
            else:
                # Generic CSV reader for unregistered indicator types
                instance = GenericCSVSignal(config, indicator, tf)
            plugins.append(instance)
            log.info("Signal source: %s", instance.name)

    return plugins
