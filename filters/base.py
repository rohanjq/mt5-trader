from __future__ import annotations

import abc
import importlib
import inspect
import logging
import pkgutil
from typing import TYPE_CHECKING

from core.models import FilterResult, FilterVerdict, TradeRequest

if TYPE_CHECKING:
    from core.config import Config
    from trade.manager import TradeManager

log = logging.getLogger(__name__)


class BaseFilter(abc.ABC):
    """Base class for trade filter plugins.

    Subclass this in ``filters/<name>.py`` and implement ``evaluate()``.
    """

    name: str = "unnamed"
    description: str = ""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._trade_manager: TradeManager | None = None

    def set_trade_manager(self, manager: TradeManager) -> None:
        self._trade_manager = manager

    @abc.abstractmethod
    def evaluate(self, request: TradeRequest) -> FilterResult:
        """Evaluate whether a proposed trade should be allowed."""
        ...


class FilterChain:
    """Runs a trade request through a sequence of filters."""

    def __init__(self) -> None:
        self._filters: list[BaseFilter] = []

    @property
    def filters(self) -> list[BaseFilter]:
        return list(self._filters)

    def add(self, f: BaseFilter) -> None:
        self._filters.append(f)
        log.info("Filter added: %s", f.name)

    def evaluate(self, request: TradeRequest) -> tuple[FilterVerdict, str]:
        """Run *request* through all filters. Returns on first BLOCK."""
        for f in self._filters:
            try:
                result = f.evaluate(request)
            except Exception:
                log.exception("Filter %s raised an exception — skipping", f.name)
                continue
            if result.verdict == FilterVerdict.BLOCK:
                log.info("Trade %s BLOCKED by %s: %s", request.id, f.name, result.reason)
                return FilterVerdict.BLOCK, f"{f.name}: {result.reason}"
            if result.verdict == FilterVerdict.MODIFY:
                for k, v in result.modifications.items():
                    setattr(request, k, v)
                log.info("Trade %s MODIFIED by %s: %s", request.id, f.name, result.modifications)
        return FilterVerdict.ALLOW, ""


def discover_filters(config: Config) -> list[BaseFilter]:
    """Auto-discover all BaseFilter subclasses in the ``filters`` package."""
    import filters as pkg

    plugins: list[BaseFilter] = []
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_") or modname == "base":
            continue
        try:
            mod = importlib.import_module(f"filters.{modname}")
        except Exception:
            log.exception("Failed to import filter plugin filters.%s", modname)
            continue
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseFilter) and obj is not BaseFilter:
                try:
                    instance = obj(config)
                    plugins.append(instance)
                    log.info("Loaded filter plugin: %s", instance.name)
                except Exception:
                    log.exception("Failed to instantiate filter plugin %s", _name)
    return plugins
