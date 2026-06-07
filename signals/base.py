from __future__ import annotations

import abc
import csv
import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.models import Signal, SignalDirection

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)


class BaseSignal(abc.ABC):
    """Base class for all signal plugins.

    Subclass this in ``signals/<name>.py`` and implement ``read()``.
    The plugin will be auto-discovered at startup.
    """

    name: str = "unnamed"

    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def read(self) -> Signal:
        """Read the latest indicator state and return a normalised Signal."""
        ...

    # helper for CSV-based signal sources
    def _read_csv(self, path: str | Path) -> dict[str, str]:
        """Read a key,value CSV into a dict. Returns empty dict on error."""
        p = Path(path)
        if not p.exists():
            log.warning("Signal CSV not found: %s", p)
            return {}
        try:
            with open(p, newline="") as f:
                reader = csv.DictReader(f)
                data: dict[str, str] = {}
                for row in reader:
                    k = row.get("key", "").strip()
                    v = row.get("value", "").strip()
                    if k:
                        data[k] = v
                return data
        except Exception:
            log.exception("Error reading CSV %s", p)
            return {}


def discover_signals(config: Config) -> list[BaseSignal]:
    """Auto-discover all BaseSignal subclasses in the ``signals`` package."""
    import signals as pkg

    plugins: list[BaseSignal] = []
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"signals.{modname}")
        except Exception:
            log.exception("Failed to import signal plugin signals.%s", modname)
            continue
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseSignal) and obj is not BaseSignal:
                try:
                    instance = obj(config)
                    plugins.append(instance)
                    log.info("Loaded signal plugin: %s", instance.name)
                except Exception:
                    log.exception("Failed to instantiate signal plugin %s", _name)
    return plugins
