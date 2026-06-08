"""Trade filters for backtesting — reads the same config as live filters.

Implements cooldown, consecutive loss pause, daily loss limit,
and reversal cooldown against the backtest simulator state.
"""
from __future__ import annotations

import logging
from datetime import datetime

from core.config import Config

log = logging.getLogger(__name__)


class BacktestFilterChain:
    """Evaluates trade requests against configured filters using simulator state."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def evaluate(
        self,
        direction: str,
        rule_name: str,
        bar_time: datetime,
        simulator,
    ) -> tuple[bool, str]:
        """Returns (allowed, reason). If allowed=False, trade is blocked."""

        # 1. Cooldown filter
        cooldown_s = self._config.get("filters.cooldown_seconds", 30)
        if cooldown_s > 0 and simulator.closed_trades:
            last_trade = simulator.closed_trades[-1]
            elapsed = (bar_time - last_trade.exit_time).total_seconds()
            if elapsed < cooldown_s:
                return False, f"Cooldown: {elapsed:.0f}s < {cooldown_s}s"

        # 2. Consecutive loss filter
        max_losses = self._config.get("filters.max_consecutive_losses", 3)
        if max_losses > 0 and simulator.consecutive_losses >= max_losses:
            pause_min = self._config.get("filters.pause_after_consecutive_minutes", 15)
            if simulator.last_loss_time:
                elapsed = (bar_time - simulator.last_loss_time).total_seconds() / 60
                if elapsed < pause_min:
                    return False, (
                        f"Paused after {simulator.consecutive_losses} consecutive losses "
                        f"({elapsed:.0f}m < {pause_min}m)"
                    )

        # 3. Daily loss filter
        max_daily = self._config.get("filters.max_daily_loss", -1)
        if max_daily > 0:
            today_start = bar_time.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_pnl = sum(
                t.profit for t in simulator.closed_trades
                if t.exit_time >= today_start
            )
            if daily_pnl <= -max_daily:
                return False, f"Daily loss limit: ${daily_pnl:.2f} <= -${max_daily:.2f}"

        # 4. Reversal cooldown
        rev_cooldown = self._config.get("filters.reversal_cooldown_seconds", 30)
        if rev_cooldown > 0 and simulator.closed_trades:
            last = simulator.closed_trades[-1]
            if not last.is_runner and last.direction != direction:
                elapsed = (bar_time - last.exit_time).total_seconds()
                if elapsed < rev_cooldown:
                    return False, f"Reversal cooldown: {elapsed:.0f}s < {rev_cooldown}s"

        return True, ""
