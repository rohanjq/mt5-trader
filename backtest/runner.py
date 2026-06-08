"""Main backtest runner — bar-by-bar replay through historical data.

Uses the same Config, Signal, and ExpressionRule classes as the live trader.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from core.config import Config
from core.models import Signal, SignalDirection
from rules.expression import ExpressionRule, load_expression_rules
from backtest.indicators import compute_all_indicators
from backtest.simulator import Simulator
from backtest.filters import BacktestFilterChain

log = logging.getLogger(__name__)


class BacktestRunner:
    """Orchestrates the entire backtest: indicators → signals → strategies → fills."""

    def __init__(self, config: Config, df_m1: pd.DataFrame) -> None:
        self.config = config
        self.df = df_m1

        # Load strategies using the same loader as live trading
        self.strategies: list[ExpressionRule] = load_expression_rules(config)
        self.strategies.sort(key=lambda r: r.priority)

        # Backtest settings
        bt = config.get("backtest", {}) or {}
        initial_balance = bt.get("initial_balance", 10000.0)
        tick_size = bt.get("tick_size", 0.01)
        tick_value = bt.get("tick_value", 1.0)   # XAUUSD: $1 per 0.01 move per lot
        volume_step = bt.get("volume_step", 0.01)
        commission = bt.get("commission_per_lot", 0.0)
        spread = bt.get("spread_points", 0.0)

        self.simulator = Simulator(
            initial_balance=initial_balance,
            tick_size=tick_size,
            tick_value=tick_value,
            volume_step=volume_step,
            commission_per_lot=commission,
            spread_points=spread,
        )

        self.filter_chain = BacktestFilterChain(config)

        # Trading settings
        self.risk_pct = float(config.get("trading.risk_pct", 5.0))
        self.default_sl = float(config.get("trading.sl_dollars", 5.0))
        self.default_rr = float(config.get("trading.reward_ratio", 1.2))
        self.default_be_pct = float(config.get("exit_rules.breakeven_pct", 0.0))
        self.default_partial_tp = bool(config.get("exit_rules.partial_tp", True))
        self.tp_close_pct = float(config.get("exit_rules.tp_close_pct", 80.0))
        self.multi_position = bool(config.get("trading.multi_position", True))

        # Stats
        self.total_bars = 0
        self.signals_fired = 0
        self.trades_blocked = 0

    def run(self) -> Simulator:
        """Execute the backtest. Returns the simulator with all results."""

        # Step 1: Compute all indicators
        sources = self.config.get("signals.sources", [])
        if not sources:
            log.error("No signal sources configured")
            return self.simulator

        log.info("Computing indicators for %d sources across %d M1 bars...",
                 len(sources), len(self.df))
        all_indicators = compute_all_indicators(self.df, sources)
        log.info("Indicators computed: %s", list(all_indicators.keys()))

        # Step 2: Replay bar by bar
        times = pd.to_datetime(self.df["time"])
        opens = self.df["open"].values
        highs = self.df["high"].values
        lows = self.df["low"].values
        closes = self.df["close"].values

        n_bars = len(self.df)
        log_interval = max(1, n_bars // 20)

        # Pending entries: signals fire on bar i close, fill at bar i+1 open
        pending_entries: list[tuple[str, str, float, float, float | None, bool | None]] = []

        log.info("Starting bar-by-bar replay (%d bars)...", n_bars)

        for i in range(n_bars):
            self.total_bars += 1
            bar_time = times.iloc[i].to_pydatetime()

            # Check SL/TP on existing positions FIRST
            closed = self.simulator.process_bar(bar_time, opens[i], highs[i], lows[i], closes[i])
            for trade in closed:
                log.debug(
                    "[%s] %s %s closed @ %.2f P&L=%.2f (%s)",
                    bar_time.strftime("%Y-%m-%d %H:%M"),
                    trade.rule_name, trade.direction,
                    trade.exit_price, trade.profit, trade.exit_reason,
                )

            # Fill pending entries from previous bar's signals at this bar's open
            for (p_direction, p_rule, p_sl, p_rr, p_be, p_ptp) in pending_entries:
                if self.simulator.has_position_for_rule(p_rule):
                    continue
                if not self.multi_position and self.simulator.has_open_positions:
                    break

                # Re-check filters at fill time
                allowed, block_reason = self.filter_chain.evaluate(
                    p_direction, p_rule, bar_time, self.simulator,
                )
                if not allowed:
                    self.trades_blocked += 1
                    continue

                entry_price = opens[i]  # fill at this bar's open
                breakeven_pct = p_be if p_be is not None else self.default_be_pct
                partial_tp = p_ptp if p_ptp is not None else self.default_partial_tp

                positions = self.simulator.open_position(
                    direction=p_direction,
                    price=entry_price,
                    time=bar_time,
                    rule_name=p_rule,
                    sl_dollars=p_sl,
                    reward_ratio=p_rr,
                    risk_pct=self.risk_pct,
                    breakeven_pct=breakeven_pct,
                    partial_tp=partial_tp,
                    tp_close_pct=self.tp_close_pct,
                )

                for pos in positions:
                    log.info(
                        "[%s] OPEN %s %s @ %.2f SL=%.2f TP=%.2f vol=%.2f (%s)",
                        bar_time.strftime("%Y-%m-%d %H:%M"),
                        pos.direction, p_rule,
                        pos.entry_price, pos.sl, pos.tp, pos.volume,
                        "runner" if pos.is_runner else "main",
                    )
            pending_entries.clear()

            # Build signal snapshot for this bar and evaluate strategies
            signals = self._build_signals(all_indicators, i)

            for rule in self.strategies:
                if self.simulator.has_position_for_rule(rule.name):
                    continue
                if not self.multi_position and self.simulator.has_open_positions:
                    break

                result = rule.evaluate(signals)
                if not result.should_trade or result.direction is None:
                    continue

                direction = result.direction.value  # "BUY" or "SELL"
                self.signals_fired += 1

                # Per-rule overrides
                sl_dollars = result.sl_dollars or self.default_sl
                reward_ratio = result.reward_ratio or self.default_rr

                # Queue for next bar's open (no look-ahead)
                pending_entries.append((
                    direction, rule.name, sl_dollars, reward_ratio,
                    result.breakeven_pct, result.partial_tp,
                ))

            # Progress logging
            if (i + 1) % log_interval == 0:
                pct = (i + 1) / n_bars * 100
                log.info(
                    "Progress: %d/%d (%.0f%%) | Trades: %d | Balance: $%.2f",
                    i + 1, n_bars, pct,
                    len(self.simulator.closed_trades),
                    self.simulator.balance,
                )

        # Close remaining open positions at last close
        if self.simulator.open_positions:
            last_time = times.iloc[-1].to_pydatetime()
            last_close = closes[-1]
            for rule_name in list(self.simulator.open_positions.keys()):
                self.simulator._close_position(rule_name, last_close, last_time, "END_OF_DATA")

        log.info(
            "Backtest complete: %d bars, %d signals, %d blocked, %d trades, final balance $%.2f",
            self.total_bars, self.signals_fired, self.trades_blocked,
            len(self.simulator.closed_trades), self.simulator.balance,
        )
        return self.simulator

    def _build_signals(
        self,
        all_indicators: dict[str, pd.DataFrame],
        bar_idx: int,
    ) -> dict[str, Signal]:
        """Build Signal objects for bar i — compatible with ExpressionRule.evaluate().

        Returns: {signal_name: Signal} where each Signal.metadata has the indicator fields.
        """
        signals: dict[str, Signal] = {}
        for signal_name, ind_df in all_indicators.items():
            if bar_idx >= len(ind_df):
                continue
            row = ind_df.iloc[bar_idx]
            metadata = {}
            for col in ind_df.columns:
                val = row[col]
                metadata[col] = str(val) if pd.notna(val) else ""
            signals[signal_name] = Signal(
                source=signal_name,
                direction=SignalDirection.NEUTRAL,
                metadata=metadata,
            )
        return signals
