from __future__ import annotations

import abc
import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models import Signal, TradeDirection

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    """A strategy's recommendation to trade (or not)."""
    should_trade: bool = False
    direction: TradeDirection | None = None
    reason: str = ""
    strategy_name: str = ""


class BaseStrategy(abc.ABC):
    """Base class for trade entry strategies.

    Each strategy examines the latest signals from all sources and decides
    whether to initiate a trade. Strategies are evaluated in priority order
    by the initiator — first one that says ``should_trade=True`` wins.

    A strategy does NOT manage open trades. Once a trade is open, only
    exit rules (SL/TP/breakeven/trailing/reversal) handle it.
    """

    name: str = "unnamed"
    description: str = ""
    priority: int = 100  # lower = evaluated first

    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def evaluate(self, signals: dict[str, Signal]) -> StrategySignal:
        """Examine latest signals and decide whether to open a trade.

        Args:
            signals: dict of signal_name → latest Signal from each source.

        Returns:
            StrategySignal with should_trade=True if entry conditions are met.
        """
        ...


def discover_strategies(config: Config) -> list[BaseStrategy]:
    """Auto-discover all BaseStrategy subclasses in the ``strategies`` package."""
    import strategies as pkg

    plugins: list[BaseStrategy] = []
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_") or modname == "base":
            continue
        try:
            mod = importlib.import_module(f"strategies.{modname}")
        except Exception:
            log.exception("Failed to import strategy strategies.%s", modname)
            continue
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                try:
                    instance = obj(config)
                    plugins.append(instance)
                    log.info("Loaded strategy: %s (priority=%d)", instance.name, instance.priority)
                except Exception:
                    log.exception("Failed to instantiate strategy %s", _name)

    # Sort by priority (lower first)
    plugins.sort(key=lambda s: s.priority)
    return plugins
