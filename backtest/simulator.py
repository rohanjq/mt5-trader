"""Order fill simulation and position management.

Simulates MT5 order execution, tracks open positions, checks SL/TP
against each bar's high/low.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class Position:
    """A simulated open position."""
    id: str
    direction: str  # "BUY" or "SELL"
    entry_price: float
    entry_time: datetime
    volume: float
    sl: float
    tp: float
    rule_name: str
    risk_dollars: float = 0.0
    breakeven_pct: float = 0.0
    trailing_stop_dollars: float = 0.0
    is_runner: bool = False
    breakeven_moved: bool = False
    trail_active: bool = False
    trail_best_price: float = 0.0


@dataclass
class ClosedTrade:
    """A completed (closed) trade."""
    id: str
    direction: str
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    volume: float
    profit: float
    rule_name: str
    exit_reason: str  # "SL", "TP", "BREAKEVEN", "SIGNAL_EXIT"
    risk_dollars: float = 0.0
    is_runner: bool = False


class Simulator:
    """Simulates order fills and position lifecycle.

    For each bar:
    1. Check if existing positions hit SL or TP (using bar high/low)
    2. Process new entry signals
    3. Track P&L

    SL/TP check order: SL is checked first (conservative — assumes worst case).
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        tick_size: float = 0.01,
        tick_value: float = 1.0,  # XAUUSD: $1 per 0.01 move per lot
        volume_step: float = 0.01,
        commission_per_lot: float = 0.0,
        spread_points: float = 0.0,
    ) -> None:
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.volume_step = volume_step
        self.commission = commission_per_lot
        self.spread = spread_points * tick_size

        self.open_positions: dict[str, Position] = {}  # rule_name → Position
        self.closed_trades: list[ClosedTrade] = []
        self._trade_counter = 0

        # Tracking
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0
        self.equity_curve: list[float] = []

        # Consecutive loss tracking
        self.consecutive_losses = 0
        self.last_loss_time: datetime | None = None

    # ── Order execution ────────────────────────────────────────────────────

    def open_position(
        self,
        direction: str,
        price: float,
        time: datetime,
        rule_name: str,
        sl_dollars: float,
        reward_ratio: float,
        risk_pct: float,
        breakeven_pct: float = 0.0,
        trailing_stop_dollars: float = 0.0,
        partial_tp: bool = True,
        tp_close_pct: float = 80.0,
    ) -> list[Position]:
        """Open a new position (with optional runner split).

        Returns list of opened positions (1 or 2 if runner is enabled).
        """
        # Calculate SL/TP prices
        if direction == "BUY":
            sl = price - sl_dollars
            tp = price + sl_dollars * reward_ratio
        else:
            sl = price + sl_dollars
            tp = price - sl_dollars * reward_ratio

        # Risk-based volume sizing
        risk_amount = self.balance * (risk_pct / 100.0)
        if sl_dollars > 0 and self.tick_size > 0 and self.tick_value > 0:
            cash_per_lot = (sl_dollars / self.tick_size) * self.tick_value
            if cash_per_lot > 0:
                raw_volume = risk_amount / cash_per_lot
                volume = max(0.01, round(int(raw_volume / self.volume_step) * self.volume_step, 2))
            else:
                volume = 0.01
        else:
            volume = 0.01

        positions = []

        if partial_tp and volume > 0.01:
            main_volume = round(volume * (tp_close_pct / 100.0), 2)
            runner_volume = round(volume - main_volume, 2)
            if runner_volume < 0.01:
                main_volume = volume
                runner_volume = 0.0
        else:
            main_volume = volume
            runner_volume = 0.0

        # Main position (with TP)
        self._trade_counter += 1
        main_id = f"trade_{self._trade_counter}"
        main_pos = Position(
            id=main_id,
            direction=direction,
            entry_price=price,
            entry_time=time,
            volume=main_volume,
            sl=sl,
            tp=tp,
            rule_name=rule_name,
            risk_dollars=sl_dollars,
            breakeven_pct=breakeven_pct,
            trailing_stop_dollars=trailing_stop_dollars,
        )
        self.open_positions[rule_name] = main_pos
        main_pos.trail_best_price = price  # init trailing baseline
        positions.append(main_pos)

        # Apply spread to entry
        if self.spread > 0:
            if direction == "BUY":
                main_pos.entry_price += self.spread / 2
            else:
                main_pos.entry_price -= self.spread / 2

        log.debug(
            "OPEN %s %s @ %.2f SL=%.2f TP=%.2f vol=%.2f (rule: %s)",
            main_id, direction, price, sl, tp, main_volume, rule_name,
        )

        # Runner position (no TP on MT5, but we track internal target)
        if runner_volume >= 0.01:
            runner_name = f"{rule_name}_runner"
            self._trade_counter += 1
            runner_id = f"trade_{self._trade_counter}"
            runner_pos = Position(
                id=runner_id,
                direction=direction,
                entry_price=price,
                entry_time=time,
                volume=runner_volume,
                sl=sl,
                tp=0.0,  # no TP for runner (rides the trend)
                rule_name=runner_name,
                risk_dollars=sl_dollars,
                breakeven_pct=breakeven_pct,
                trailing_stop_dollars=trailing_stop_dollars,
                is_runner=True,
            )
            self.open_positions[runner_name] = runner_pos
            runner_pos.trail_best_price = price
            positions.append(runner_pos)
            log.debug(
                "OPEN runner %s %s @ %.2f SL=%.2f (no TP) vol=%.2f",
                runner_id, direction, price, sl, runner_volume,
            )

        return positions

    # ── Bar processing ─────────────────────────────────────────────────────

    def process_bar(self, bar_time: datetime, open_: float, high: float, low: float, close: float) -> list[ClosedTrade]:
        """Check all open positions against this bar's high/low for SL/TP hits.

        Uses bar open direction to decide SL/TP priority:
        - If bar opens moving against the position, check SL first.
        - If bar opens moving in favour, check TP first.
        This reduces bias vs always checking SL first.

        Returns list of trades closed during this bar.
        """
        closed_this_bar = []
        to_close = []

        for rule_name, pos in list(self.open_positions.items()):
            # Check breakeven first
            if pos.breakeven_pct > 0 and not pos.breakeven_moved and pos.risk_dollars > 0:
                be_trigger = pos.entry_price + pos.risk_dollars * (pos.breakeven_pct / 100.0) if pos.direction == "BUY" \
                    else pos.entry_price - pos.risk_dollars * (pos.breakeven_pct / 100.0)

                triggered = (pos.direction == "BUY" and high >= be_trigger) or \
                            (pos.direction == "SELL" and low <= be_trigger)
                if triggered:
                    pos.sl = pos.entry_price  # move SL to entry
                    pos.breakeven_moved = True
                    log.debug("Breakeven moved for %s: SL → %.2f", pos.id, pos.sl)

            # Check trailing stop
            if pos.trailing_stop_dollars > 0:
                if pos.direction == "BUY":
                    if high > pos.trail_best_price:
                        pos.trail_best_price = high
                    new_sl = pos.trail_best_price - pos.trailing_stop_dollars
                    if new_sl > pos.sl:
                        log.debug("Trailing SL for %s: %.2f → %.2f (best=%.2f)", pos.id, pos.sl, new_sl, pos.trail_best_price)
                        pos.sl = new_sl
                        pos.trail_active = True
                else:
                    if pos.trail_best_price == 0 or low < pos.trail_best_price:
                        pos.trail_best_price = low
                    new_sl = pos.trail_best_price + pos.trailing_stop_dollars
                    if new_sl < pos.sl:
                        log.debug("Trailing SL for %s: %.2f → %.2f (best=%.2f)", pos.id, pos.sl, new_sl, pos.trail_best_price)
                        pos.sl = new_sl
                        pos.trail_active = True

            sl_hit = False
            tp_hit = False

            if pos.direction == "BUY":
                sl_hit = low <= pos.sl
                tp_hit = pos.tp > 0 and high >= pos.tp
            else:
                sl_hit = high >= pos.sl
                tp_hit = pos.tp > 0 and low <= pos.tp

            if sl_hit and tp_hit:
                # Both hit on same bar — use open direction to decide
                # If bar opens closer to SL side, SL was likely hit first
                if pos.direction == "BUY":
                    check_sl_first = open_ < pos.entry_price  # gap down → SL first
                else:
                    check_sl_first = open_ > pos.entry_price  # gap up → SL first

                if check_sl_first:
                    tp_hit = False
                else:
                    sl_hit = False

            if sl_hit:
                exit_price = pos.sl
                if pos.trail_active:
                    exit_reason = "TRAIL"
                elif pos.breakeven_moved and pos.sl == pos.entry_price:
                    exit_reason = "BREAKEVEN"
                else:
                    exit_reason = "SL"
                to_close.append((rule_name, exit_price, exit_reason, bar_time))
                continue

            if tp_hit:
                to_close.append((rule_name, pos.tp, "TP", bar_time))

        # Close positions
        for rule_name, exit_price, exit_reason, exit_time in to_close:
            trade = self._close_position(rule_name, exit_price, exit_time, exit_reason)
            if trade:
                closed_this_bar.append(trade)

        # Update equity
        self._update_equity(close)

        return closed_this_bar

    # ── Tick-level processing ──────────────────────────────────────────────

    def process_tick(
        self, tick_time: datetime, bid: float, ask: float,
    ) -> list[ClosedTrade]:
        """Check all open positions against tick bid/ask for SL/TP hits.

        • BUY positions are checked against *bid* (sell-side exit price).
        • SELL positions are checked against *ask* (buy-back exit price).

        Fills at the SL/TP level (matching MT5 server-side order behaviour).
        Does NOT update the equity curve — the caller handles that at
        M1-close boundaries.
        """
        if not self.open_positions:
            return []

        closed_this_tick: list[ClosedTrade] = []
        to_close: list[tuple[str, float, str, datetime]] = []

        for rule_name, pos in list(self.open_positions.items()):
            # Exit check price: BUY exits at bid, SELL exits at ask
            if pos.direction == "BUY":
                px = bid
            else:
                px = ask

            # ── Breakeven ────────────────────────────────────────────
            if pos.breakeven_pct > 0 and not pos.breakeven_moved and pos.risk_dollars > 0:
                if pos.direction == "BUY":
                    trigger = pos.entry_price + pos.risk_dollars * (pos.breakeven_pct / 100.0)
                    if px >= trigger:
                        pos.sl = pos.entry_price
                        pos.breakeven_moved = True
                else:
                    trigger = pos.entry_price - pos.risk_dollars * (pos.breakeven_pct / 100.0)
                    if px <= trigger:
                        pos.sl = pos.entry_price
                        pos.breakeven_moved = True

            # ── Trailing stop ────────────────────────────────────────
            if pos.trailing_stop_dollars > 0:
                if pos.direction == "BUY":
                    if px > pos.trail_best_price:
                        pos.trail_best_price = px
                    new_sl = pos.trail_best_price - pos.trailing_stop_dollars
                    if new_sl > pos.sl:
                        pos.sl = new_sl
                        pos.trail_active = True
                else:
                    if pos.trail_best_price == 0 or px < pos.trail_best_price:
                        pos.trail_best_price = px
                    new_sl = pos.trail_best_price + pos.trailing_stop_dollars
                    if new_sl < pos.sl:
                        pos.sl = new_sl
                        pos.trail_active = True

            # ── SL / TP hit ──────────────────────────────────────────
            sl_hit = False
            tp_hit = False
            if pos.direction == "BUY":
                sl_hit = px <= pos.sl
                tp_hit = pos.tp > 0 and px >= pos.tp
            else:
                sl_hit = px >= pos.sl
                tp_hit = pos.tp > 0 and px <= pos.tp

            # With tick data a single price can't straddle both SL
            # and TP (they're on opposite sides), but guard anyway.
            if sl_hit and tp_hit:
                tp_hit = False  # conservative: take the loss

            if sl_hit:
                reason = (
                    "TRAIL" if pos.trail_active
                    else "BREAKEVEN" if pos.breakeven_moved and pos.sl == pos.entry_price
                    else "SL"
                )
                to_close.append((rule_name, pos.sl, reason, tick_time))
            elif tp_hit:
                to_close.append((rule_name, pos.tp, "TP", tick_time))

        for rule_name, exit_price, exit_reason, exit_time in to_close:
            trade = self._close_position(rule_name, exit_price, exit_time, exit_reason)
            if trade:
                closed_this_tick.append(trade)

        return closed_this_tick

    # ── Position lifecycle ─────────────────────────────────────────────────

    def _close_position(
        self, rule_name: str, exit_price: float, exit_time: datetime, exit_reason: str,
    ) -> ClosedTrade | None:
        pos = self.open_positions.pop(rule_name, None)
        if not pos:
            return None

        # Calculate profit
        if pos.direction == "BUY":
            price_diff = exit_price - pos.entry_price
        else:
            price_diff = pos.entry_price - exit_price

        # Profit = (price_diff / tick_size) * tick_value * volume
        if self.tick_size > 0:
            profit = (price_diff / self.tick_size) * self.tick_value * pos.volume
        else:
            profit = price_diff * pos.volume

        # Commission
        profit -= self.commission * pos.volume

        # Update balance
        self.balance += profit

        # Track drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        dd = (self.peak_balance - self.balance) / self.peak_balance * 100
        if dd > self.max_drawdown:
            self.max_drawdown = dd

        # Consecutive loss tracking (skip runners)
        if not pos.is_runner:
            if profit < 0:
                self.consecutive_losses += 1
                self.last_loss_time = exit_time
            elif profit > 0:
                self.consecutive_losses = 0

        trade = ClosedTrade(
            id=pos.id,
            direction=pos.direction,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            exit_price=exit_price,
            exit_time=exit_time,
            volume=pos.volume,
            profit=profit,
            rule_name=pos.rule_name,
            exit_reason=exit_reason,
            risk_dollars=pos.risk_dollars,
            is_runner=pos.is_runner,
        )
        self.closed_trades.append(trade)

        log.debug(
            "CLOSE %s %s @ %.2f → %.2f P&L=%.2f (%s) bal=%.2f",
            trade.id, trade.direction, trade.entry_price, exit_price,
            profit, exit_reason, self.balance,
        )
        return trade

    def _update_equity(self, current_price: float) -> None:
        """Update equity = balance + unrealised P&L."""
        unrealised = 0.0
        for pos in self.open_positions.values():
            if pos.direction == "BUY":
                diff = current_price - pos.entry_price
            else:
                diff = pos.entry_price - current_price
            if self.tick_size > 0:
                unrealised += (diff / self.tick_size) * self.tick_value * pos.volume
            else:
                unrealised += diff * pos.volume
        self.equity = self.balance + unrealised
        self.equity_curve.append(self.equity)

    def has_position_for_rule(self, rule_name: str) -> bool:
        return rule_name in self.open_positions or f"{rule_name}_runner" in self.open_positions

    @property
    def has_open_positions(self) -> bool:
        return len(self.open_positions) > 0
