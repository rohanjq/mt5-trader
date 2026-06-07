from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from core.events import EventLog
from core.models import Signal, TradeDirection, TradeRecord, TradeState
from exits.base import BaseExitRule, ExitAction

if TYPE_CHECKING:
    from core.config import Config
    from core.mt5_client import MT5Client

log = logging.getLogger(__name__)


class TradeManager:
    """Tracks open and closed trades, monitors positions, runs exit rules."""

    def __init__(self, config: Config, mt5_client: MT5Client) -> None:
        self._config = config
        self._mt5 = mt5_client
        self._lock = threading.RLock()

        self._open_trades: dict[str, TradeRecord] = {}  # rule_name → TradeRecord
        self._trade_history: list[TradeRecord] = []
        self._last_loss_time: float | None = None
        self._consecutive_losses: int = 0

        self._exit_rules: list[BaseExitRule] = []
        self._latest_signals: dict[str, Signal] = {}
        self._on_close_callbacks: list = []

        # For reversal cooldown filter
        self._last_trade_direction: TradeDirection | None = None
        self._last_close_time: float | None = None

        self._notifier = None

        self._events = EventLog.get()

    # ── notifications ──────────────────────────────────────────────────────

    def set_notifier(self, notifier) -> None:
        self._notifier = notifier

    # ── properties ─────────────────────────────────────────────────────────

    @property
    def multi_position(self) -> bool:
        return bool(self._config.get("trading.multi_position", False))

    @property
    def has_open_position(self) -> bool:
        with self._lock:
            return len(self._open_trades) > 0

    @property
    def open_trade(self) -> TradeRecord | None:
        """First open trade (backward compat for single-position UI)."""
        with self._lock:
            if not self._open_trades:
                return None
            return next(iter(self._open_trades.values()))

    @property
    def open_trades(self) -> list[TradeRecord]:
        with self._lock:
            return list(self._open_trades.values())

    def has_position_for_rule(self, rule_name: str) -> bool:
        with self._lock:
            return rule_name in self._open_trades or f"{rule_name}_runner" in self._open_trades

    @property
    def trade_history(self) -> list[TradeRecord]:
        with self._lock:
            return list(self._trade_history)

    @property
    def last_loss_time(self) -> float | None:
        with self._lock:
            return self._last_loss_time

    @property
    def consecutive_losses(self) -> int:
        with self._lock:
            return self._consecutive_losses

    @property
    def last_trade_direction(self) -> TradeDirection | None:
        with self._lock:
            return self._last_trade_direction

    @property
    def last_close_time(self) -> float | None:
        with self._lock:
            return self._last_close_time

    # ── exit rules ─────────────────────────────────────────────────────────

    def set_exit_rules(self, rules: list[BaseExitRule]) -> None:
        self._exit_rules = rules
        log.info("Exit rules loaded: %s", [r.name for r in rules])

    def update_signals(self, signals: dict[str, Signal]) -> None:
        """Called by the engine to keep the manager aware of latest signals."""
        self._latest_signals = signals

    def on_trade_closed(self, callback) -> None:
        """Register a callback fired after a trade is closed (for signal reset)."""
        self._on_close_callbacks.append(callback)

    # ── trade lifecycle ────────────────────────────────────────────────────

    def adopt_existing_positions(self) -> None:
        """Check MT5 for open positions and adopt them on startup.

        Adopted trades are tracked for P&L display and close detection.
        Breakeven is managed using SL distance as risk and global breakeven_pct.
        """
        if not self._mt5.connected:
            return

        symbol = self._config.get("trading.symbol", "BTCUSDT")
        magic = self._config.get("trading.magic", 100)
        positions = self._mt5.get_positions(symbol)
        breakeven_pct = float(self._config.get("exit_rules.breakeven_pct", 0.0))

        for pos in positions:
            if hasattr(pos, "magic") and pos.magic != magic:
                continue

            direction = (
                TradeDirection.BUY if pos.type == 0
                else TradeDirection.SELL
            )

            # Estimate risk from SL distance so breakeven can work
            if pos.sl and pos.sl > 0:
                risk_dollars = abs(pos.price_open - pos.sl)
            else:
                risk_dollars = 0.0

            record = TradeRecord(
                id=f"adopted_{pos.ticket}",
                direction=direction,
                symbol=symbol,
                volume=pos.volume,
                entry_price=pos.price_open,
                entry_time=datetime.now(),
                signal_source=f"adopted_{pos.ticket}",
                ticket=pos.ticket,
                sl=pos.sl if pos.sl else 0.0,
                tp=pos.tp if pos.tp else 0.0,
                risk_dollars=risk_dollars,
                breakeven_pct=breakeven_pct,
                state=TradeState.MONITORING,
            )
            record.profit = pos.profit

            with self._lock:
                key = record.signal_source
                if key in self._open_trades:
                    continue
                if not self.multi_position and self._open_trades:
                    log.warning("Single-position mode, already tracking — skipping ticket=%s", pos.ticket)
                    continue
                self._open_trades[key] = record

            log.info(
                "Adopted existing position: ticket=%s %s @ %.2f SL=%.2f TP=%.2f P&L=%.2f",
                pos.ticket, direction.value, pos.price_open, record.sl, record.tp, pos.profit,
            )
            self._events.trade(
                f"Adopted {direction.value} @ {pos.price_open:.2f} "
                f"ticket={pos.ticket} P&L={pos.profit:+.2f}"
            )

    def register_trade(self, record: TradeRecord) -> None:
        with self._lock:
            record.state = TradeState.MONITORING
            self._open_trades[record.signal_source] = record
            log.info("Trade %s registered under rule '%s' and monitoring", record.id, record.signal_source)

        if self._notifier:
            tp_str = f"TP={record.tp:.2f}" if record.tp > 0 else "no TP"
            self._notifier.send(
                f"{record.direction.value} {record.symbol} @ {record.entry_price:.2f}\n"
                f"SL={record.sl:.2f} {tp_str} vol={record.volume:.2f}\n"
                f"Rule: {record.signal_source}",
                title="Trade Opened",
            )

    def close_trade(self, profit: float, exit_price: float, rule_name: str | None = None) -> TradeRecord | None:
        with self._lock:
            # Find the trade to close
            if rule_name and rule_name in self._open_trades:
                trade = self._open_trades.pop(rule_name)
            elif not rule_name and self._open_trades:
                # Fallback: close first (for manual close / single mode)
                key = next(iter(self._open_trades))
                trade = self._open_trades.pop(key)
            else:
                return None
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            trade.profit = profit
            trade.state = TradeState.CLOSED

            self._trade_history.append(trade)
            self._last_trade_direction = trade.direction
            self._last_close_time = time.time()

            if profit < 0:
                self._last_loss_time = time.time()
                self._consecutive_losses += 1
                log.info(
                    "Trade %s CLOSED with LOSS: %.2f (consecutive: %d)",
                    trade.id, profit, self._consecutive_losses,
                )
                self._events.trade(
                    f"{trade.direction.value} CLOSED — LOSS: {profit:+.2f}"
                )
            elif profit == 0:
                self._consecutive_losses = 0
                log.info("Trade %s CLOSED at BREAKEVEN", trade.id)
                self._events.trade(
                    f"{trade.direction.value} CLOSED — BREAKEVEN"
                )
            else:
                self._consecutive_losses = 0
                log.info("Trade %s CLOSED with PROFIT: %.2f", trade.id, profit)
                self._events.trade(
                    f"{trade.direction.value} CLOSED — PROFIT: {profit:+.2f}"
                )

            # Notify listeners (e.g., initiator resets signal tracking)
            for cb in self._on_close_callbacks:
                try:
                    cb(trade)
                except Exception:
                    log.exception("on_trade_closed callback error")

            # Push notification
            if self._notifier:
                result_str = "WIN" if profit > 0 else ("LOSS" if profit < 0 else "BE")
                self._notifier.send(
                    f"{trade.direction.value} {trade.symbol} closed\n"
                    f"P&L: {profit:+.2f} ({result_str})\n"
                    f"Entry: {trade.entry_price:.2f} → Exit: {exit_price:.2f}\n"
                    f"Rule: {trade.signal_source}",
                    title=f"Trade Closed ({result_str})",
                    priority=-1 if profit > 0 else 0,
                )

            return trade

    def close_current_position(self, rule_name: str | None = None) -> TradeRecord | None:
        """Close an open position via MT5. If rule_name given, close that specific one."""
        with self._lock:
            if rule_name and rule_name in self._open_trades:
                trade = self._open_trades[rule_name]
            elif self._open_trades:
                trade = next(iter(self._open_trades.values()))
                rule_name = trade.signal_source
            else:
                log.info("No open position to close")
                return None

        if not self._mt5.connected:
            log.error("MT5 not connected — cannot close position")
            return None

        result = self._mt5.close_position(
            ticket=trade.ticket,
            volume=trade.volume,
            direction=trade.direction.value,
            symbol=trade.symbol,
        )

        if result and result.retcode == 10009:
            tick = self._mt5.get_tick(trade.symbol)
            if tick:
                exit_price = tick.bid if trade.direction == TradeDirection.BUY else tick.ask
                if trade.direction == TradeDirection.BUY:
                    profit = (exit_price - trade.entry_price) * trade.volume
                else:
                    profit = (trade.entry_price - exit_price) * trade.volume
            else:
                exit_price = trade.entry_price
                profit = 0.0
            return self.close_trade(profit, exit_price, rule_name=rule_name)
        else:
            retcode = result.retcode if result else "N/A"
            log.error("Failed to close position ticket=%s: retcode=%s", trade.ticket, retcode)
            return None

    def update_open_position(self) -> None:
        """Update unrealized P&L and run exit rules for ALL open positions."""
        with self._lock:
            trades = list(self._open_trades.items())  # [(rule_name, record), ...]
            if not trades:
                return

        if not self._mt5.connected:
            return

        tick = self._mt5.get_tick()
        if not tick:
            return

        for rule_name, trade in trades:
            with self._lock:
                if rule_name not in self._open_trades:
                    continue  # closed in the meantime
                if trade.direction == TradeDirection.BUY:
                    self._open_trades[rule_name].profit = (tick.bid - trade.entry_price) * trade.volume
                else:
                    self._open_trades[rule_name].profit = (trade.entry_price - tick.ask) * trade.volume

            # Run exit rules per position
            self._evaluate_exit_rules(trade, tick)

    def sync_positions_from_mt5(self) -> None:
        """Detect if MT5 positions were closed externally."""
        if not self._mt5.connected:
            return

        mt5_positions = self._mt5.get_positions()
        tickets = {p.ticket for p in mt5_positions}

        with self._lock:
            closed_rules: list[str] = []
            for rule_name, trade in self._open_trades.items():
                if trade.ticket and trade.ticket not in tickets:
                    closed_rules.append(rule_name)

        for rule_name in closed_rules:
            with self._lock:
                trade = self._open_trades.get(rule_name)
                if not trade:
                    continue

            log.warning(
                "Tracked position ticket=%s (rule=%s) no longer in MT5 — marking closed",
                trade.ticket, rule_name,
            )
            tick = self._mt5.get_tick(trade.symbol)
            if tick:
                if trade.direction == TradeDirection.BUY:
                    exit_price = tick.bid
                    profit = (exit_price - trade.entry_price) * trade.volume
                else:
                    exit_price = tick.ask
                    profit = (trade.entry_price - exit_price) * trade.volume
            else:
                exit_price = trade.entry_price
                profit = 0.0
            self.close_trade(profit=profit, exit_price=exit_price, rule_name=rule_name)

    # ── statistics ─────────────────────────────────────────────────────────

    def today_stats(self) -> dict:
        today = datetime.now().date()
        with self._lock:
            today_trades = [
                t for t in self._trade_history
                if t.entry_time.date() == today
            ]
        wins = [t for t in today_trades if t.profit > 0]
        losses = [t for t in today_trades if t.profit < 0]
        breakevens = [t for t in today_trades if t.profit == 0.0]
        total_profit = sum(t.profit for t in today_trades)

        return {
            "total": len(today_trades),
            "wins": len(wins),
            "losses": len(losses),
            "avg_profit": sum(t.profit for t in wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(t.profit for t in losses) / len(losses) if losses else 0.0,
            "net_pnl": total_profit,
        }

    # ── exit rule evaluation ───────────────────────────────────────────────

    def _evaluate_exit_rules(self, trade: TradeRecord, tick: Any) -> None:
        """Run all exit rules against an open position. CLOSE wins over MODIFY."""
        rule_name = trade.signal_source
        for rule in self._exit_rules:
            try:
                result = rule.evaluate(trade, self._latest_signals, tick)
            except Exception:
                log.exception("Exit rule %s raised an exception — skipping", rule.name)
                continue

            if result.action == ExitAction.CLOSE:
                log.info("Exit rule %s: CLOSE — %s", rule.name, result.reason)
                self._events.exit_event(f"Exit [{rule.name}]: CLOSE — {result.reason}")
                self.close_current_position(rule_name=rule_name)
                return

            if result.action == ExitAction.MODIFY_SL and result.new_sl is not None:
                with self._lock:
                    if rule_name not in self._open_trades:
                        return
                    old_sl = self._open_trades[rule_name].sl
                    self._open_trades[rule_name].sl = result.new_sl
                # Runners have TP=0 on broker; don't accidentally set internal TP
                mt5_tp = 0.0 if rule_name.endswith("_runner") else trade.tp
                self._mt5.modify_position(
                    ticket=trade.ticket, sl=result.new_sl, tp=mt5_tp, symbol=trade.symbol,
                )
                log.info(
                    "Exit rule %s: SL moved %.2f → %.2f — %s",
                    rule.name, old_sl, result.new_sl, result.reason,
                )
                self._events.exit_event(
                    f"Exit [{rule.name}]: SL {old_sl:.2f} → {result.new_sl:.2f}"
                )

            if result.action == ExitAction.MODIFY_TP and result.new_tp is not None:
                with self._lock:
                    if rule_name not in self._open_trades:
                        return
                    old_tp = self._open_trades[rule_name].tp
                    self._open_trades[rule_name].tp = result.new_tp
                sl = trade.sl
                self._mt5.modify_position(
                    ticket=trade.ticket, sl=sl, tp=result.new_tp, symbol=trade.symbol,
                )
                log.info(
                    "Exit rule %s: TP moved %.2f → %.2f — %s",
                    rule.name, old_tp, result.new_tp, result.reason,
                )
                self._events.exit_event(
                    f"Exit [{rule.name}]: TP {old_tp:.2f} → {result.new_tp:.2f}"
                )
