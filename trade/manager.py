from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

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

        self._open_trade: TradeRecord | None = None
        self._trade_history: list[TradeRecord] = []
        self._last_loss_time: float | None = None
        self._consecutive_losses: int = 0

        self._exit_rules: list[BaseExitRule] = []
        self._latest_signals: dict[str, Signal] = {}
        self._on_close_callbacks: list = []

    # ── properties ─────────────────────────────────────────────────────────

    @property
    def has_open_position(self) -> bool:
        with self._lock:
            return self._open_trade is not None

    @property
    def open_trade(self) -> TradeRecord | None:
        with self._lock:
            return self._open_trade

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

    def register_trade(self, record: TradeRecord) -> None:
        with self._lock:
            record.state = TradeState.MONITORING
            self._open_trade = record
            log.info("Trade %s registered and monitoring", record.id)

    def close_trade(self, profit: float, exit_price: float) -> TradeRecord | None:
        with self._lock:
            if self._open_trade is None:
                return None

            trade = self._open_trade
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            trade.profit = profit
            trade.state = TradeState.CLOSED

            self._trade_history.append(trade)
            self._open_trade = None

            if profit < 0:
                self._last_loss_time = time.time()
                self._consecutive_losses += 1
                log.info(
                    "Trade %s CLOSED with LOSS: %.2f (consecutive: %d)",
                    trade.id, profit, self._consecutive_losses,
                )
            else:
                self._consecutive_losses = 0
                log.info("Trade %s CLOSED with PROFIT: %.2f", trade.id, profit)

            # Notify listeners (e.g., initiator resets signal tracking)
            for cb in self._on_close_callbacks:
                try:
                    cb(trade)
                except Exception:
                    log.exception("on_trade_closed callback error")

            return trade

    def close_current_position(self) -> TradeRecord | None:
        """Close the current open position via MT5."""
        with self._lock:
            trade = self._open_trade
            if trade is None:
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
            if trade.direction == TradeDirection.BUY:
                exit_price = tick.bid
                profit = (exit_price - trade.entry_price) * trade.volume
            else:
                exit_price = tick.ask
                profit = (trade.entry_price - exit_price) * trade.volume

            return self.close_trade(profit, exit_price)
        else:
            retcode = result.retcode if result else "N/A"
            log.error("Failed to close position: retcode=%s", retcode)
            return None

    def update_open_position(self) -> None:
        """Update unrealized P&L and run exit rules."""
        with self._lock:
            trade = self._open_trade
            if trade is None:
                return

        if not self._mt5.connected:
            return

        tick = self._mt5.get_tick(trade.symbol)
        if not tick:
            return

        # Update P&L
        with self._lock:
            if self._open_trade is None:
                return
            if trade.direction == TradeDirection.BUY:
                self._open_trade.profit = (tick.bid - trade.entry_price) * trade.volume
            else:
                self._open_trade.profit = (trade.entry_price - tick.ask) * trade.volume

        # Run exit rules
        self._evaluate_exit_rules(trade, tick)

    def sync_positions_from_mt5(self) -> None:
        """Detect if MT5 has positions we don't know about, or if our tracked
        position was closed externally."""
        if not self._mt5.connected:
            return

        mt5_positions = self._mt5.get_positions()

        with self._lock:
            if self._open_trade and self._open_trade.ticket:
                # Check if our tracked position still exists
                tickets = {p.ticket for p in mt5_positions}
                if self._open_trade.ticket not in tickets:
                    log.warning(
                        "Tracked position ticket=%s no longer in MT5 — marking closed",
                        self._open_trade.ticket,
                    )
                    self.close_trade(profit=0.0, exit_price=self._open_trade.entry_price)

    # ── statistics ─────────────────────────────────────────────────────────

    def today_stats(self) -> dict:
        today = datetime.now().date()
        with self._lock:
            today_trades = [
                t for t in self._trade_history
                if t.entry_time.date() == today
            ]
        wins = [t for t in today_trades if t.profit > 0]
        losses = [t for t in today_trades if t.profit <= 0]
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
        """Run all exit rules against the open position. CLOSE wins over MODIFY."""
        for rule in self._exit_rules:
            try:
                result = rule.evaluate(trade, self._latest_signals, tick)
            except Exception:
                log.exception("Exit rule %s raised an exception — skipping", rule.name)
                continue

            if result.action == ExitAction.CLOSE:
                log.info("Exit rule %s: CLOSE — %s", rule.name, result.reason)
                self.close_current_position()
                return

            if result.action == ExitAction.MODIFY_SL and result.new_sl is not None:
                with self._lock:
                    if self._open_trade is None:
                        return
                    old_sl = self._open_trade.sl
                    self._open_trade.sl = result.new_sl
                tp = trade.tp
                self._mt5.modify_position(
                    ticket=trade.ticket, sl=result.new_sl, tp=tp, symbol=trade.symbol,
                )
                log.info(
                    "Exit rule %s: SL moved %.2f → %.2f — %s",
                    rule.name, old_sl, result.new_sl, result.reason,
                )

            if result.action == ExitAction.MODIFY_TP and result.new_tp is not None:
                with self._lock:
                    if self._open_trade is None:
                        return
                    old_tp = self._open_trade.tp
                    self._open_trade.tp = result.new_tp
                sl = trade.sl
                self._mt5.modify_position(
                    ticket=trade.ticket, sl=sl, tp=result.new_tp, symbol=trade.symbol,
                )
                log.info(
                    "Exit rule %s: TP moved %.2f → %.2f — %s",
                    rule.name, old_tp, result.new_tp, result.reason,
                )
