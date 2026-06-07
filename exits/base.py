from __future__ import annotations

import abc
import enum
import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.models import Signal, TradeRecord

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)


class ExitAction(enum.Enum):
    HOLD = "HOLD"
    MODIFY_SL = "MODIFY_SL"
    MODIFY_TP = "MODIFY_TP"
    CLOSE = "CLOSE"


@dataclass
class ExitResult:
    action: ExitAction
    reason: str = ""
    new_sl: float | None = None
    new_tp: float | None = None


class BaseExitRule(abc.ABC):
    """Base class for exit rule plugins.

    Subclass this in ``exits/<name>.py`` and implement ``evaluate()``.
    The monitor loop calls evaluate() every tick while a position is open.
    """

    name: str = "unnamed"
    description: str = ""

    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def evaluate(
        self,
        trade: TradeRecord,
        signals: dict[str, Signal],
        tick: Any,
    ) -> ExitResult:
        """Evaluate whether to exit, hold, or modify the open position.

        Args:
            trade: The current open trade with live P&L.
            signals: Latest signals from all sources.
            tick: Current MT5 tick (has .bid, .ask).

        Returns:
            ExitResult with the recommended action.
        """
        ...


def discover_exit_rules(config: Config) -> list[BaseExitRule]:
    """Auto-discover all BaseExitRule subclasses in the ``exits`` package."""
    import exits as pkg

    plugins: list[BaseExitRule] = []
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_") or modname == "base":
            continue
        try:
            mod = importlib.import_module(f"exits.{modname}")
        except Exception:
            log.exception("Failed to import exit rule exits.%s", modname)
            continue
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseExitRule) and obj is not BaseExitRule:
                try:
                    instance = obj(config)
                    plugins.append(instance)
                    log.info("Loaded exit rule: %s", instance.name)
                except Exception:
                    log.exception("Failed to instantiate exit rule %s", _name)
    return plugins
