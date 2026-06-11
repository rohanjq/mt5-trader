"""Main backtest runner — bar-by-bar replay through historical data.

Uses the same Config, Signal, and ExpressionRule classes as the live trader.

Fill model matches live behaviour:
  • The EA writes CSV at candle close.
  • Python polls every 2 s → signal detected within 2 s of close.
  • Trade fills at market price ≈ bar close.
  Therefore: signal evaluated on bar-close data → fill at that bar's close.
  SL/TP monitoring starts from the NEXT bar.

Warmup:
  Indicators need N bars before they produce valid values.
  During warmup the runner evaluates rules (so rising-edge state builds up)
  but does NOT open trades.
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


def _compute_warmup(
    all_indicators: dict[str, pd.DataFrame],
    strategies: list[ExpressionRule],
) -> dict[str, int]:
    """Return per-strategy warmup bar index.

    Each strategy gets its own warmup threshold — the first M1 bar where
    ALL of that strategy's referenced indicators have valid values.
    Strategies whose indicators never become valid get warmup = inf (they
    simply won't fire).

    Returns: {rule_name: first_valid_bar_index}
    """
    # Pre-compute first-valid bar for each signal indicator
    sig_first_valid: dict[str, int] = {}
    for sig_name, ind_df in all_indicators.items():
        if ind_df.empty:
            sig_first_valid[sig_name] = len(ind_df)
            continue
        valid_mask = ind_df.notna().all(axis=1)
        if valid_mask.any():
            first_valid = valid_mask.idxmax()
            idx = int(first_valid) if isinstance(first_valid, (np.integer, int)) else ind_df.index.get_loc(first_valid)
        else:
            idx = len(ind_df)  # never valid
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


class BacktestRunner:
    """Orchestrates the entire backtest: indicators → signals → strategies → fills."""

    def __init__(self, config: Config, df_m1: pd.DataFrame, *, trade_from: datetime | None = None) -> None:
        self.config = config
        self.df = df_m1
        self.trade_from = trade_from

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
        self.default_trailing = float(config.get("exit_rules.trailing_stop_dollars", 0.0))
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

        # Step 2: Determine per-strategy warmup periods
        warmup_map = _compute_warmup(all_indicators, self.strategies)
        global_warmup = max(warmup_map.values()) if warmup_map else 0
        log.info("Per-strategy warmup computed — global max: %d bars", global_warmup)

        # Step 3: Replay bar by bar
        times = pd.to_datetime(self.df["time"])
        opens = self.df["open"].values
        highs = self.df["high"].values
        lows = self.df["low"].values
        closes = self.df["close"].values

        n_bars = len(self.df)
        log_interval = max(1, n_bars // 20)

        log.info("Starting bar-by-bar replay (%d bars)...", n_bars)

        # Track whether we've reset rising-edge state at trade_from.
        # In live, the system boots with _prev_*_met = False, so the
        # first time conditions are met they fire immediately.
        edge_reset_done = self.trade_from is None

        for i in range(n_bars):
            self.total_bars += 1
            bar_time = times.iloc[i].to_pydatetime()

            # Reset rising-edge state at the trade_from boundary so it
            # matches a live cold-start (all _prev_*_met = False).
            if not edge_reset_done and self.trade_from is not None and bar_time >= self.trade_from:
                for rule in self.strategies:
                    rule._prev_buy_met = False
                    rule._prev_sell_met = False
                edge_reset_done = True
                log.info("[%s] Rising-edge state reset (simulates live cold-start)",
                         bar_time.strftime("%Y-%m-%d %H:%M"))

            # Check SL/TP on existing positions FIRST (uses this bar's OHLC)
            closed = self.simulator.process_bar(bar_time, opens[i], highs[i], lows[i], closes[i])
            for trade in closed:
                log.debug(
                    "[%s] %s %s closed @ %.2f P&L=%.2f (%s)",
                    bar_time.strftime("%Y-%m-%d %H:%M"),
                    trade.rule_name, trade.direction,
                    trade.exit_price, trade.profit, trade.exit_reason,
                )

            # Build signal snapshot for this bar and evaluate strategies.
            # IMPORTANT: ALL rules are evaluated every bar so rising-edge
            # state (_prev_buy_met / _prev_sell_met) stays current — this
            # matches live where evaluate() runs every poll cycle regardless
            # of position state.
            signals = self._build_signals(all_indicators, i)

            for rule in self.strategies:
                # Always evaluate — keeps rising-edge state in sync with live
                result = rule.evaluate(signals)

                # Skip trading when blocked (but evaluation already happened)
                if not result.should_trade or result.direction is None:
                    continue
                # Per-strategy warmup: skip until this strategy's indicators are ready
                if i < warmup_map.get(rule.name, 0):
                    continue
                # --trade-from: skip until we reach the specified start time
                if self.trade_from is not None and bar_time < self.trade_from:
                    continue
                if self.simulator.has_position_for_rule(rule.name):
                    continue
                if not self.multi_position and self.simulator.has_open_positions:
                    continue

                direction = result.direction.value  # "BUY" or "SELL"
                self.signals_fired += 1

                # Per-rule overrides
                sl_dollars = result.sl_dollars or self.default_sl
                reward_ratio = result.reward_ratio or self.default_rr

                # Check filters
                allowed, block_reason = self.filter_chain.evaluate(
                    direction, rule.name, bar_time, self.simulator,
                )
                if not allowed:
                    self.trades_blocked += 1
                    continue

                # Fill at this bar's CLOSE — matches live behaviour
                entry_price = closes[i]
                breakeven_pct = result.breakeven_pct if result.breakeven_pct is not None else self.default_be_pct
                partial_tp = result.partial_tp if result.partial_tp is not None else self.default_partial_tp

                positions = self.simulator.open_position(
                    direction=direction,
                    price=entry_price,
                    time=bar_time,
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
                        bar_time.strftime("%Y-%m-%d %H:%M"),
                        pos.direction, rule.name,
                        pos.entry_price, pos.sl, pos.tp, pos.volume,
                        "runner" if pos.is_runner else "main",
                    )

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
