from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from core.events import EventLog
from core.models import (
    FilterVerdict,
    Signal,
    SignalDirection,
    TradeDirection,
    TradeRecord,
    TradeRequest,
    TradeState,
)
from rules.base import BaseRule, TriggerResult

if TYPE_CHECKING:
    from core.config import Config
    from core.mt5_client import MT5Client
    from filters.base import FilterChain
    from trade.manager import TradeManager

log = logging.getLogger(__name__)

# Max age (seconds) for signal server_time to be considered "fresh"
_WARMUP_MAX_AGE_S = 30


class TradeInitiator:
    """Evaluates trigger rules against latest signals and initiates trades.

    Rules are evaluated in priority order. First one that returns
    TRIGGER_BUY or TRIGGER_SELL wins. Once a position is open, no rule
    can trigger until the position is closed.
    """

    def __init__(
        self,
        config: Config,
        mt5_client: MT5Client,
        filter_chain: FilterChain,
        trade_manager: TradeManager,
    ) -> None:
        self._config = config
        self._mt5 = mt5_client
        self._filters = filter_chain
        self._manager = trade_manager
        self._lock = threading.Lock()
        self._rules: list[BaseRule] = []
        self._events = EventLog.get()
        self._warmed_up = False  # smart warmup: check signal freshness

    @staticmethod
    def _signals_are_fresh(signals: dict[str, Signal]) -> bool:
        """Check if any signal's server_time is within the last 30 seconds."""
        now = datetime.now()
        for sig in signals.values():
            st = sig.metadata.get("server_time", "")
            if not st:
                continue
            try:
                # Format: "2026.06.07 07:30:30"
                sig_time = datetime.strptime(st, "%Y.%m.%d %H:%M:%S")
                age = (now - sig_time).total_seconds()
                if age <= _WARMUP_MAX_AGE_S:
                    return True
            except (ValueError, TypeError):
                continue
        return False

    def set_rules(self, rules: list[BaseRule]) -> None:
        self._rules = rules
        log.info("Rules loaded: %s", [r.name for r in rules])

    @property
    def rules(self) -> list[BaseRule]:
        return list(self._rules)

    def on_signals(self, signals: dict[str, Signal]) -> None:
        """Called by the engine with ALL latest signals each poll cycle."""
        with self._lock:
            if not self._warmed_up:
                if self._signals_are_fresh(signals):
                    self._warmed_up = True
                    log.info("Signals are fresh — skipping warmup, ready to trade")
                    self._events.info("Signals fresh — ready to trade immediately")
                else:
                    self._warmed_up = True
                    log.info("Warmup — signals are stale (>%ds old), skipping first cycle", _WARMUP_MAX_AGE_S)
                    self._events.info("Warmup — stale signals skipped, waiting for fresh data")
                    return

            if not self._manager.multi_position and self._manager.has_open_position:
                return

            # Evaluate rules in priority order
            for rule in self._rules:
                # In multi-position mode, skip rules that already have a position
                if self._manager.multi_position and self._manager.has_position_for_rule(rule.name):
                    continue

                try:
                    result = rule.evaluate(signals)
                except Exception:
                    log.exception("Rule %s raised an exception", rule.name)
                    continue

                if not result.should_trade or result.direction is None:
                    continue

                log.info(
                    "Rule %s triggered: %s — %s",
                    rule.name, result.direction.value, result.reason,
                )
                self._events.trade(
                    f"Rule [{rule.name}] triggered {result.direction.value}: {result.reason}"
                )
                self._initiate_trade(result, signals)
                if not self._manager.multi_position:
                    return  # Single mode: only one trade per cycle

    def _initiate_trade(self, trigger: TriggerResult, signals: dict[str, Signal]) -> None:
        symbol = self._config.get("trading.symbol", "BTCUSDT")
        sl, tp, volume, sl_dollars = self._calculate_risk(trigger.direction, trigger)

        # Per-rule breakeven % (fall back to global config)
        breakeven_pct = trigger.breakeven_pct
        if breakeven_pct is None:
            breakeven_pct = float(self._config.get("exit_rules.breakeven_pct", 0.0))

        source_signal = Signal(
            source=trigger.rule_name,
            direction=(
                SignalDirection.BUY if trigger.direction == TradeDirection.BUY
                else SignalDirection.SELL
            ),
            metadata={"reason": trigger.reason},
        )

        request = TradeRequest(
            direction=trigger.direction,
            symbol=symbol,
            volume=volume,
            signal=source_signal,
            sl=sl,
            tp=tp,
            risk_dollars=sl_dollars,
            breakeven_pct=breakeven_pct,
        )
        log.info(
            "Trade request %s: %s %s vol=%.4f SL=%.2f TP=%.2f (rule: %s)",
            request.id, trigger.direction.value, symbol, volume, sl, tp,
            trigger.rule_name,
        )

        # Run through filter chain
        verdict, reason = self._filters.evaluate(request)
        if verdict == FilterVerdict.BLOCK:
            request.state = TradeState.REJECTED
            request.rejection_reason = reason
            log.info("Trade %s rejected: %s", request.id, reason)
            self._events.block(f"Trade BLOCKED: {reason}")
            return

        request.state = TradeState.FILTERS_PASSED
        self._execute(request)

    def _calculate_risk(
        self, direction: TradeDirection, trigger: TriggerResult | None = None,
    ) -> tuple[float, float, float, float]:
        """Calculate SL, TP, volume from config (with per-rule overrides).

        If the triggering rule specifies ``sl_dollars`` or ``reward_ratio``,
        those values override the global config defaults.

        Returns (sl, tp, volume, sl_dollars).
        """
        volume = float(self._config.get("trading.volume", 0.001))
        sl_dollars = float(self._config.get("trading.sl_dollars", 5.0))
        reward_ratio = float(self._config.get("trading.reward_ratio", 1.25))

        # Per-rule overrides
        if trigger is not None and trigger.sl_dollars is not None:
            sl_dollars = trigger.sl_dollars
        if trigger is not None and trigger.reward_ratio is not None:
            reward_ratio = trigger.reward_ratio

        tp_dollars = sl_dollars * reward_ratio

        # Get current price
        tick = self._mt5.get_tick() if self._mt5.connected else None
        if not tick:
            return 0.0, 0.0, volume, sl_dollars

        entry_price = tick.ask if direction == TradeDirection.BUY else tick.bid

        if direction == TradeDirection.BUY:
            sl = entry_price - sl_dollars
            tp = entry_price + tp_dollars
        else:
            sl = entry_price + sl_dollars
            tp = entry_price - tp_dollars

        return sl, tp, volume, sl_dollars

    def _execute(self, request: TradeRequest) -> None:
        if not self._mt5.connected:
            log.error("MT5 not connected — cannot execute trade %s", request.id)
            return

        if request.direction == TradeDirection.BUY:
            # When partial_tp is enabled, don't set server-side TP — our exit rule handles it
            mt5_tp = 0.0 if self._config.get("exit_rules.partial_tp", False) else request.tp
            result = self._mt5.buy(
                volume=request.volume, symbol=request.symbol,
                sl=request.sl, tp=mt5_tp,
            )
        else:
            mt5_tp = 0.0 if self._config.get("exit_rules.partial_tp", False) else request.tp
            result = self._mt5.sell(
                volume=request.volume, symbol=request.symbol,
                sl=request.sl, tp=mt5_tp,
            )

        if result and result.retcode == 10009:
            tick = self._mt5.get_tick(request.symbol)
            entry_price = tick.ask if request.direction == TradeDirection.BUY else tick.bid

            record = TradeRecord(
                id=request.id,
                direction=request.direction,
                symbol=request.symbol,
                volume=request.volume,
                entry_price=entry_price,
                entry_time=datetime.now(),
                signal_source=request.signal.source,
                ticket=result.order,
                sl=request.sl,
                tp=request.tp,
                risk_dollars=request.risk_dollars,
                breakeven_pct=request.breakeven_pct,
                state=TradeState.EXECUTED,
            )
            self._manager.register_trade(record)
            log.info(
                "Trade %s EXECUTED: ticket=%s entry=%.2f SL=%.2f TP=%.2f",
                request.id, result.order, entry_price, request.sl, request.tp,
            )
            self._events.trade(
                f"{request.direction.value} OPENED @ {entry_price:.2f} "
                f"SL={request.sl:.2f} TP={request.tp:.2f}"
            )
        else:
            retcode = result.retcode if result else "N/A"
            comment = result.comment if result else "no result"
            log.error(
                "Trade %s execution FAILED: retcode=%s comment=%s",
                request.id, retcode, comment,
            )


    def reset_signal_tracking(self) -> None:
        """Reset so the next signal of any direction will be acted on."""
        pass  # Rising-edge detection in ExpressionRule handles dedup now

    def manual_trade(self, direction: TradeDirection) -> bool:
        """Execute a manual trade bypassing all filters.

        SL/TP are auto-calculated from config, same as rule-triggered trades.
        Returns True if the trade was placed.
        """
        with self._lock:
            if not self._manager.multi_position and self._manager.has_open_position:
                self._events.warn("Manual trade rejected — position already open")
                return False
            if self._manager.has_position_for_rule("manual"):
                self._events.warn("Manual trade rejected — manual position already open")
                return False

            symbol = self._config.get("trading.symbol", "BTCUSDT")
            sl, tp, volume, sl_dollars = self._calculate_risk(direction)

            source_signal = Signal(
                source="manual",
                direction=(
                    SignalDirection.BUY if direction == TradeDirection.BUY
                    else SignalDirection.SELL
                ),
                metadata={"reason": "Manual trade"},
            )

            breakeven_pct = float(self._config.get("exit_rules.breakeven_pct", 0.0))
            request = TradeRequest(
                direction=direction,
                symbol=symbol,
                volume=volume,
                signal=source_signal,
                sl=sl,
                tp=tp,
                risk_dollars=sl_dollars,
                breakeven_pct=breakeven_pct,
            )
            request.state = TradeState.FILTERS_PASSED
            self._events.trade(
                f"MANUAL {direction.value} — vol={volume} SL={sl:.2f} TP={tp:.2f}"
            )
            log.info(
                "Manual trade %s: %s %s vol=%.4f SL=%.2f TP=%.2f",
                request.id, direction.value, symbol, volume, sl, tp,
            )
            self._execute(request)
            return True
