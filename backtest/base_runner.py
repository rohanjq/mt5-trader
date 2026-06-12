"""Shared base class for bar-by-bar and tick-by-tick backtest runners.

Extracts all duplicated init, signal-building, strategy-evaluation,
and position-opening logic into one place.
"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from core.config import Config
from core.models import Signal, SignalDirection
from rules.expression import ExpressionRule, load_expression_rules
from backtest.indicators import compute_all_indicators
from backtest.simulator import Simulator
from backtest.filters import BacktestFilterChain

log = logging.getLogger(__name__)


# ── Warmup computation ─────────────────────────────────────────────────────────

def compute_warmup(
    all_indicators: dict[str, pd.DataFrame],
    strategies: list[ExpressionRule],
) -> dict[str, int]:
    """Return per-strategy warmup bar index.

    Each strategy gets its own warmup threshold — the first M1 bar where
    ALL of that strategy's referenced indicators have valid values.

    Returns: {rule_name: first_valid_bar_index}
    """
    sig_first_valid: dict[str, int] = {}
    for sig_name, ind_df in all_indicators.items():
        if ind_df.empty:
            sig_first_valid[sig_name] = len(ind_df)
            continue
        valid_mask = ind_df.notna().all(axis=1)
        if valid_mask.any():
            first_valid = valid_mask.idxmax()
            idx = (
                int(first_valid)
                if isinstance(first_valid, (np.integer, int))
                else ind_df.index.get_loc(first_valid)
            )
        else:
            idx = len(ind_df)
        sig_first_valid[sig_name] = idx

    warmups: dict[str, int] = {}
    for rule in strategies:
        needed_sigs = {c.signal for c in rule._buy_conditions + rule._sell_conditions}
        worst = 0
        for sig in needed_sigs:
            bar = sig_first_valid.get(sig, 0)
            if bar > worst:
                worst = bar
        warmups[rule.name] = worst
        if worst > 0:
            log.info("Strategy %s warmup: %d bars", rule.name, worst)

    return warmups


# ── Base runner ────────────────────────────────────────────────────────────────

class BaseBacktestRunner:
    """Common init, signal building, strategy evaluation, and position opening."""

    def __init__(self, config: Config, *, trade_from: datetime | None = None, spread_points: float | None = None) -> None:
        self.config = config
        self.trade_from = trade_from

        self.strategies: list[ExpressionRule] = load_expression_rules(config)
        self.strategies.sort(key=lambda r: r.priority)

        bt = config.get("backtest", {}) or {}
        self.simulator = Simulator(
            initial_balance=bt.get("initial_balance", 10000.0),
            tick_size=bt.get("tick_size", 0.01),
            tick_value=bt.get("tick_value", 1.0),
            volume_step=bt.get("volume_step", 0.01),
            commission_per_lot=bt.get("commission_per_lot", 0.0),
            spread_points=spread_points if spread_points is not None else bt.get("spread_points", 0.0),
        )

        self.filter_chain = BacktestFilterChain(config)

        self.risk_pct = float(config.get("trading.risk_pct", 5.0))
        self.default_sl = float(config.get("trading.sl_dollars", 5.0))
        self.default_rr = float(config.get("trading.reward_ratio", 1.2))
        self.default_be_pct = float(config.get("exit_rules.breakeven_pct", 0.0))
        self.default_trailing = float(config.get("exit_rules.trailing_stop_dollars", 0.0))
        self.default_partial_tp = bool(config.get("exit_rules.partial_tp", True))
        self.tp_close_pct = float(config.get("exit_rules.tp_close_pct", 80.0))
        self.multi_position = bool(config.get("trading.multi_position", True))

        self.signals_fired = 0
        self.trades_blocked = 0

    # ── Shared helpers ─────────────────────────────────────────────────

    def _compute_indicators(
        self,
        df_m1: pd.DataFrame,
        native_bars: dict[str, pd.DataFrame] | None = None,
        ea_atr_dir: str | None = None,
    ) -> dict[str, pd.DataFrame] | None:
        """Compute all indicators.  Returns None if no sources configured."""
        sources = self.config.get("signals.sources", [])
        if not sources:
            log.error("No signal sources configured")
            return None
        log.info("Computing indicators for %d sources across %d M1 bars...",
                 len(sources), len(df_m1))
        return compute_all_indicators(df_m1, sources, native_bars=native_bars,
                                       ea_atr_dir=ea_atr_dir)

    def _reset_edge_state(self, label: str) -> None:
        """Reset rising-edge state to simulate a live cold-start."""
        for rule in self.strategies:
            rule._prev_buy_met = False
            rule._prev_sell_met = False
        log.info("[%s] Rising-edge state reset (simulates live cold-start)", label)

    @staticmethod
    def _build_signals(
        all_indicators: dict[str, pd.DataFrame],
        bar_idx: int,
    ) -> dict[str, Signal]:
        """Build Signal objects for completed M1 bar *bar_idx*."""
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

    def _try_open_trades(
        self,
        signals: dict[str, Signal],
        time_val: datetime,
        entry_price: float,
        bar_idx: int,
        warmup_map: dict[str, int],
    ) -> None:
        """Evaluate all strategies and open positions for those that fire.

        ``entry_price`` is the fill price (bar close for bar mode,
        ask/bid for tick mode — caller decides).
        """
        for rule in self.strategies:
            result = rule.evaluate(signals)

            if not result.should_trade or result.direction is None:
                continue
            if bar_idx < warmup_map.get(rule.name, 0):
                continue
            if self.trade_from is not None and time_val < self.trade_from:
                continue
            if self.simulator.has_position_for_rule(rule.name):
                continue
            if not self.multi_position and self.simulator.has_open_positions:
                continue

            direction = result.direction.value
            self.signals_fired += 1

            sl_dollars = result.sl_dollars or self.default_sl
            reward_ratio = result.reward_ratio or self.default_rr

            allowed, _ = self.filter_chain.evaluate(
                direction, rule.name, time_val, self.simulator,
            )
            if not allowed:
                self.trades_blocked += 1
                continue

            breakeven_pct = result.breakeven_pct if result.breakeven_pct is not None else self.default_be_pct
            partial_tp = result.partial_tp if result.partial_tp is not None else self.default_partial_tp

            positions = self.simulator.open_position(
                direction=direction,
                price=entry_price,
                time=time_val,
                rule_name=rule.name,
                sl_dollars=sl_dollars,
                reward_ratio=reward_ratio,
                risk_pct=self.risk_pct,
                breakeven_pct=breakeven_pct,
                trailing_stop_dollars=self.default_trailing,
                partial_tp=partial_tp,
                tp_close_pct=self.tp_close_pct,
            )

            for pos in positions:
                log.info(
                    "[%s] OPEN %s %s @ %.2f SL=%.2f TP=%.2f vol=%.2f (%s)",
                    time_val.strftime("%Y-%m-%d %H:%M:%S"),
                    pos.direction, rule.name,
                    pos.entry_price, pos.sl, pos.tp, pos.volume,
                    "runner" if pos.is_runner else "main",
                )
