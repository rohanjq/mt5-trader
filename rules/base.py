from __future__ import annotations

import abc
import enum
import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.models import Signal, TradeDirection

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)


class TriggerAction(enum.Enum):
    NO_ACTION = "NO_ACTION"
    TRIGGER_BUY = "TRIGGER_BUY"
    TRIGGER_SELL = "TRIGGER_SELL"


@dataclass
class TriggerResult:
    action: TriggerAction = TriggerAction.NO_ACTION
    reason: str = ""
    rule_name: str = ""
    sl_dollars: float | None = None
    reward_ratio: float | None = None

    @property
    def should_trade(self) -> bool:
        return self.action in (TriggerAction.TRIGGER_BUY, TriggerAction.TRIGGER_SELL)

    @property
    def direction(self) -> TradeDirection | None:
        if self.action == TriggerAction.TRIGGER_BUY:
            return TradeDirection.BUY
        if self.action == TriggerAction.TRIGGER_SELL:
            return TradeDirection.SELL
        return None


class BaseRule(abc.ABC):
    """Base class for trigger rule plugins.

    Subclass this in ``rules/<name>.py`` and implement ``evaluate()``.
    Rules are auto-discovered at startup and evaluated in priority order.
    First rule that returns TRIGGER_BUY or TRIGGER_SELL wins.

    Rules only fire when no position is open.
    """

    name: str = "unnamed"
    description: str = ""
    priority: int = 100  # lower = evaluated first

    def __init__(self, config: Config) -> None:
        self.config = config
        self._last_result: TriggerResult = TriggerResult()

    @abc.abstractmethod
    def evaluate(self, signals: dict[str, Signal]) -> TriggerResult:
        """Evaluate all available signals and decide whether to trade.

        Args:
            signals: dict of signal_name → Signal. Names follow the pattern:
                     ``utbot_M1``, ``utbot_M15``, ``dc_M15``, ``dc_M45``, etc.
                     Each signal's ``.metadata`` dict has ALL CSV key-value pairs.

        Returns:
            TriggerResult with action, reason, and rule_name.
        """
        ...

    @property
    def last_result(self) -> TriggerResult:
        return self._last_result

    def _get(self, signals: dict[str, Signal], name: str) -> dict[str, str]:
        """Helper: get metadata dict for a signal source, or empty dict."""
        sig = signals.get(name)
        if sig is None:
            return {}
        return sig.metadata

    def _val(self, signals: dict[str, Signal], name: str, key: str, default: str = "") -> str:
        """Helper: get a specific metadata value from a signal source."""
        return self._get(signals, name).get(key, default).strip()

    def _is_true(self, signals: dict[str, Signal], name: str, key: str) -> bool:
        """Helper: check if a metadata value is TRUE."""
        return self._val(signals, name, key).upper() == "TRUE"

    def _int_val(self, signals: dict[str, Signal], name: str, key: str, default: int = 0) -> int:
        """Helper: get an integer metadata value."""
        try:
            return int(self._val(signals, name, key))
        except (ValueError, TypeError):
            return default


def discover_rules(config: Config) -> list[BaseRule]:
    """Auto-discover all BaseRule subclasses in the ``rules`` package,
    plus load expression-based rules from config YAML."""
    import rules as pkg

    plugins: list[BaseRule] = []
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_") or modname in ("base", "expression"):
            continue
        try:
            mod = importlib.import_module(f"rules.{modname}")
        except Exception:
            log.exception("Failed to import rule rules.%s", modname)
            continue
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseRule) and obj is not BaseRule:
                try:
                    instance = obj(config)
                    plugins.append(instance)
                    log.info("Loaded rule: %s (priority=%d)", instance.name, instance.priority)
                except Exception:
                    log.exception("Failed to instantiate rule %s", _name)

    # Load expression-based rules from YAML config
    from rules.expression import load_expression_rules
    expr_rules = load_expression_rules(config)
    plugins.extend(expr_rules)

    plugins.sort(key=lambda r: r.priority)
    return plugins
