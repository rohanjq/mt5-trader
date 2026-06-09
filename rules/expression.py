"""Expression-based trigger rules defined in YAML.

Instead of writing Python, define rules like:

    rules:
      expressions:
        - name: dc_zone_entry
          enabled: true
          priority: 130
          description: "DC low zone + UT Bot entry"
          buy:
            - utbot_M1.closed_signal == BUY
            - utbot_M15.closed_bias == BULLISH
            - dc_M15.closed_price_zone in LOWER,LOWER_MID
            - utbot_M45.consecutive_bull_bars >= 5
          sell:
            - utbot_M1.closed_signal == SELL
            - utbot_M15.closed_bias == BEARISH
            - dc_M15.closed_price_zone in UPPER,UPPER_MID
            - utbot_M45.consecutive_bear_bars >= 5

Expression format:
    signal_name.field_name OPERATOR value

Operators:
    ==          equals (case-insensitive string compare)
    !=          not equals
    >           greater than (numeric)
    >=          greater or equal (numeric)
    <           less than (numeric)
    <=          less or equal (numeric)
    in          value is one of comma-separated list
    not_in      value is NOT one of comma-separated list
    is          alias for == TRUE (boolean check)
    is_not      alias for != TRUE

All conditions in a buy/sell block are ANDed together.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models import Signal
from rules.base import BaseRule, TriggerAction, TriggerResult

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)

# Regex: signal.field  operator  value
# Examples:
#   utbot_M1.closed_signal == BUY
#   utbot_M45.consecutive_bull_bars >= 5
#   dc_M15.closed_price_zone in LOWER,LOWER_MID
#   dc_M15.closed_lower_wick_rej is TRUE
#   bb20d2_M1.bb_squeeze is TRUE  (dot in signal name)
_EXPR_RE = re.compile(
    r"^([\w.]+)\.(\w+)\s+(==|!=|>=|<=|>|<|in|not_in|is|is_not)\s+(.+)$"
)


@dataclass
class Condition:
    """A single parsed condition."""
    signal: str       # e.g. "utbot_M1"
    field: str        # e.g. "closed_signal"
    operator: str     # e.g. "==", ">=", "in"
    value: str        # raw value string, e.g. "BUY", "5", "LOWER,LOWER_MID"

    def evaluate(self, signals: dict[str, Signal]) -> bool:
        """Evaluate this condition against live signals."""
        sig = signals.get(self.signal)
        if sig is None:
            return False

        raw = sig.metadata.get(self.field, "").strip()

        if self.operator == "==" or self.operator == "is":
            return raw.upper() == self.value.upper()

        if self.operator == "!=" or self.operator == "is_not":
            return raw.upper() != self.value.upper()

        if self.operator == "in":
            allowed = {v.strip().upper() for v in self.value.split(",")}
            return raw.upper() in allowed

        if self.operator == "not_in":
            blocked = {v.strip().upper() for v in self.value.split(",")}
            return raw.upper() not in blocked

        # Numeric comparisons
        try:
            num_raw = float(raw)
            num_val = float(self.value)
        except (ValueError, TypeError):
            return False

        if self.operator == ">":
            return num_raw > num_val
        if self.operator == ">=":
            return num_raw >= num_val
        if self.operator == "<":
            return num_raw < num_val
        if self.operator == "<=":
            return num_raw <= num_val

        return False

    def describe(self, signals: dict[str, Signal]) -> str:
        """Human-readable description of current state."""
        sig = signals.get(self.signal)
        actual = sig.metadata.get(self.field, "?").strip() if sig else "?"
        return f"{self.signal}.{self.field}={actual}"

    def snapshot(self, signals: dict[str, Signal]) -> dict:
        """Return evaluation details for this condition."""
        sig = signals.get(self.signal)
        actual = sig.metadata.get(self.field, "").strip() if sig else ""
        passed = self.evaluate(signals)
        return {
            "expr": f"{self.signal}.{self.field} {self.operator} {self.value}",
            "actual": actual if actual else "N/A",
            "pass": passed,
        }


def parse_condition(expr: str) -> Condition | None:
    """Parse a condition string into a Condition object."""
    expr = expr.strip()
    m = _EXPR_RE.match(expr)
    if not m:
        log.error("Invalid expression: %r", expr)
        return None
    return Condition(
        signal=m.group(1),
        field=m.group(2),
        operator=m.group(3),
        value=m.group(4).strip(),
    )


class ExpressionRule(BaseRule):
    """A trigger rule defined by YAML expressions instead of Python code."""

    def __init__(
        self,
        config: Config,
        rule_name: str,
        description: str,
        priority_val: int,
        buy_conditions: list[Condition],
        sell_conditions: list[Condition],
        sl_dollars: float | None = None,
        reward_ratio: float | None = None,
        breakeven_pct: float | None = None,
        partial_tp: bool | None = None,
    ) -> None:
        super().__init__(config)
        self.name = rule_name
        self.description = description
        self.priority = priority_val
        self._buy_conditions = buy_conditions
        self._sell_conditions = sell_conditions
        self._sl_dollars = sl_dollars
        self._reward_ratio = reward_ratio
        self._breakeven_pct = breakeven_pct
        self._partial_tp = partial_tp
        # Rising-edge detection: only fire on False→True transition
        self._prev_buy_met = False
        self._prev_sell_met = False

    def evaluate(self, signals: dict[str, Signal]) -> TriggerResult:
        if not self.config.get(f"rules.{self.name}.enabled", True):
            self._last_result = TriggerResult()
            return self._last_result

        # Also check under rules.expressions list for enabled flag
        for rule_cfg in self.config.get("rules.expressions", []):
            if isinstance(rule_cfg, dict) and rule_cfg.get("name") == self.name:
                if not rule_cfg.get("enabled", True):
                    self._last_result = TriggerResult()
                    return self._last_result
                break

        # Evaluate BUY conditions (all must be true)
        buy_met = bool(self._buy_conditions and all(c.evaluate(signals) for c in self._buy_conditions))
        sell_met = bool(self._sell_conditions and all(c.evaluate(signals) for c in self._sell_conditions))

        # Rising-edge: only trigger on the False→True transition.
        # If conditions were already met last cycle, don't re-fire.
        # When at least one condition drops and comes back, it fires again.
        buy_edge = buy_met and not self._prev_buy_met
        sell_edge = sell_met and not self._prev_sell_met

        self._prev_buy_met = buy_met
        self._prev_sell_met = sell_met

        if buy_edge:
            parts = [c.describe(signals) for c in self._buy_conditions]
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_BUY,
                reason=", ".join(parts),
                rule_name=self.name,
                sl_dollars=self._sl_dollars,
                reward_ratio=self._reward_ratio,
                breakeven_pct=self._breakeven_pct,
                partial_tp=self._partial_tp,
            )
            return self._last_result

        if sell_edge:
            parts = [c.describe(signals) for c in self._sell_conditions]
            self._last_result = TriggerResult(
                action=TriggerAction.TRIGGER_SELL,
                reason=", ".join(parts),
                rule_name=self.name,
                sl_dollars=self._sl_dollars,
                reward_ratio=self._reward_ratio,
                breakeven_pct=self._breakeven_pct,
                partial_tp=self._partial_tp,
            )
            return self._last_result

        self._last_result = TriggerResult(rule_name=self.name)
        return self._last_result

    def snapshot(self, signals: dict[str, Signal]) -> dict:
        """Return detailed evaluation state for both buy and sell sides."""
        buy_details = [c.snapshot(signals) for c in self._buy_conditions]
        sell_details = [c.snapshot(signals) for c in self._sell_conditions]
        buy_passed = sum(1 for d in buy_details if d["pass"])
        sell_passed = sum(1 for d in sell_details if d["pass"])
        buy_total = len(buy_details)
        sell_total = len(sell_details)

        return {
            "rule": self.name,
            "description": self.description,
            "sl": self._sl_dollars,
            "rr": self._reward_ratio,
            "buy": {
                "score": f"{buy_passed}/{buy_total}",
                "conditions": buy_details,
            },
            "sell": {
                "score": f"{sell_passed}/{sell_total}",
                "conditions": sell_details,
            },
        }


def load_expression_rules(config: Config) -> list[BaseRule]:
    """Load expression-based rules from config.yaml under rules.expressions."""
    expr_rules: list[BaseRule] = []
    definitions = config.get("rules.expressions", [])

    if not definitions or not isinstance(definitions, list):
        return expr_rules

    for defn in definitions:
        if not isinstance(defn, dict):
            continue

        name = defn.get("name", "")
        if not name:
            log.error("Expression rule missing 'name': %s", defn)
            continue

        description = defn.get("description", name)
        priority = defn.get("priority", 150)
        enabled = defn.get("enabled", True)

        if not enabled:
            log.info("Expression rule %s is disabled — skipping", name)
            continue

        # Parse buy conditions
        buy_conds: list[Condition] = []
        for expr in defn.get("buy", []):
            if isinstance(expr, bool):
                continue  # skip YAML-converted FALSE/TRUE
            cond = parse_condition(str(expr))
            if cond:
                buy_conds.append(cond)
            else:
                log.error("Rule %s: failed to parse buy condition: %r", name, expr)

        # Parse sell conditions
        sell_conds: list[Condition] = []
        for expr in defn.get("sell", []):
            if isinstance(expr, bool):
                continue  # skip YAML-converted FALSE/TRUE
            cond = parse_condition(str(expr))
            if cond:
                sell_conds.append(cond)
            else:
                log.error("Rule %s: failed to parse sell condition: %r", name, expr)

        if not buy_conds and not sell_conds:
            log.warning("Rule %s has no valid conditions — skipping", name)
            continue

        raw_sl = defn.get("sl_dollars")
        raw_rr = defn.get("reward_ratio")
        raw_be = defn.get("breakeven_pct")
        raw_ptp = defn.get("partial_tp")
        rule = ExpressionRule(
            config=config,
            rule_name=name,
            description=description,
            priority_val=priority,
            buy_conditions=buy_conds,
            sell_conditions=sell_conds,
            sl_dollars=float(raw_sl) if raw_sl is not None else None,
            reward_ratio=float(raw_rr) if raw_rr is not None else None,
            breakeven_pct=float(raw_be) if raw_be is not None else None,
            partial_tp=bool(raw_ptp) if raw_ptp is not None else None,
        )
        expr_rules.append(rule)
        log.info(
            "Loaded expression rule: %s (priority=%d, buy=%d conds, sell=%d conds)",
            name, priority, len(buy_conds), len(sell_conds),
        )

    return expr_rules


def validate_expression_rules(config: Config, rules: list[BaseRule]) -> list[str]:
    """Validate that all signal references in expression rules match configured sources.

    Returns a list of warning strings for any unresolvable references.
    """
    # Build set of configured signal names: e.g. {"utbot_M1", "dc_M15", "ema50_H1"}
    configured: set[str] = set()
    for src in config.get("signals.sources", []):
        indicator = src.get("indicator", "")
        for tf in src.get("timeframes", []):
            configured.add(f"{indicator}_{tf}")

    if not configured:
        return []

    warnings: list[str] = []
    for rule in rules:
        if not isinstance(rule, ExpressionRule):
            continue
        for cond in rule._buy_conditions + rule._sell_conditions:
            if cond.signal not in configured:
                msg = f"Rule '{rule.name}': references '{cond.signal}' which is not in signals.sources"
                warnings.append(msg)

    return warnings
