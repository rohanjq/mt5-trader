"""Tick-by-tick backtest runner.

Replays raw tick data to achieve maximum fidelity with live trading:

  • M1 candles are built from ticks — identical to MT5.
  • SL / TP is checked at **every tick** using bid / ask prices.
  • Strategies evaluate on every tick so ``running_*`` signals work
    when added later.  For strategies that only use ``closed_*``
    fields the result is identical to evaluating at M1 close because
    the indicator values don't change between closes and rising-edge
    detection prevents duplicate fires.
  • Trade entries fill at the tick price (ask for BUY, bid for SELL).
  • Spread is inherent in bid / ask — no synthetic spread needed.

Architecture
------------
Phase 1 — Build M1 OHLC from ticks (single pass, CandleBuilder).
Phase 2 — Vectorised indicator computation on completed M1 bars
           (reuses ``compute_all_indicators``).
Phase 3 — Replay ticks:
           For each tick:
             1. Check SL / TP at bid / ask.
             2. If an M1 bar just closed → update ``closed_*`` signals.
             3. Evaluate all strategies with latest signals.
             4. If a signal fires → fill at tick bid / ask.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.config import Config
from core.models import Signal
from backtest.base_runner import BaseBacktestRunner, compute_warmup
from backtest.tick_builder import CandleBuilder

log = logging.getLogger(__name__)


class TickBacktestRunner(BaseBacktestRunner):
    """Tick-by-tick backtest engine."""

    def __init__(
        self,
        config: Config,
        df_ticks: pd.DataFrame,
        *,
        trade_from: datetime | None = None,
    ) -> None:
        super().__init__(config, trade_from=trade_from, spread_points=0.0)
        self.df_ticks = df_ticks
        self.total_ticks = 0

    # ── public API ───────────────────────────────────────────────────────

    def run(self) -> "Simulator":
        """Execute the tick-by-tick backtest.  Returns the Simulator."""

        # ── Phase 1: build M1 candles from ticks ─────────────────────
        log.info("Phase 1: Building M1 candles from %d ticks...", len(self.df_ticks))
        m1_builder = CandleBuilder(1)

        tick_times = self.df_ticks["time"].values
        tick_bids = self.df_ticks["bid"].values.astype(np.float64)
        tick_asks = self.df_ticks["ask"].values.astype(np.float64)

        for i in range(len(tick_times)):
            t = pd.Timestamp(tick_times[i]).to_pydatetime()
            m1_builder.on_tick(t, float(tick_bids[i]))
        m1_builder.finalize()

        df_m1 = m1_builder.to_dataframe()
        df_m1["time"] = pd.to_datetime(df_m1["time"])
        log.info("Built %d M1 candles", len(df_m1))

        if df_m1.empty:
            log.error("No M1 candles built from tick data")
            return self.simulator

        # ── Phase 2: compute indicators (vectorised) ─────────────────
        all_indicators = self._compute_indicators(df_m1)
        if all_indicators is None:
            return self.simulator

        warmup_map = compute_warmup(all_indicators, self.strategies)
        global_warmup = max(warmup_map.values()) if warmup_map else 0
        log.info("Indicators ready.  Warmup max: %d bars", global_warmup)

        # Build M1-epoch → row-index lookup
        m1_epochs = (
            pd.DatetimeIndex(df_m1["time"]).astype("int64") // 10**9
        ).astype(int)
        m1_epoch_to_idx: dict[int, int] = {
            int(m1_epochs[j]): j for j in range(len(m1_epochs))
        }

        # ── Phase 3: tick replay ─────────────────────────────────────
        n_ticks = len(tick_times)
        log.info("Phase 3: Replaying %d ticks...", n_ticks)

        tick_epochs = (
            pd.DatetimeIndex(tick_times).astype("int64") // 10**9
        ).astype(np.int64)

        prev_bar_epoch: int = -1
        current_m1_idx: int = -1
        signals: dict[str, Signal] = {}
        signals_dirty = False
        edge_reset_done = self.trade_from is None
        log_interval = max(1, n_ticks // 20)

        for i in range(n_ticks):
            self.total_ticks += 1
            epoch = int(tick_epochs[i])
            bid = float(tick_bids[i])
            ask = float(tick_asks[i])
            bar_epoch = (epoch // 60) * 60

            m1_closed = bar_epoch != prev_bar_epoch and prev_bar_epoch >= 0

            # ── 1. SL / TP check at every tick ───────────────────────
            if self.simulator.has_open_positions:
                tick_dt = datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)
                closed_trades = self.simulator.process_tick(tick_dt, bid, ask)
                for trade in closed_trades:
                    log.debug(
                        "[%s] %s %s closed @ %.2f P&L=%.2f (%s)",
                        tick_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        trade.rule_name, trade.direction,
                        trade.exit_price, trade.profit, trade.exit_reason,
                    )

            # ── 2. Update closed_* signals when M1 bar closes ───────
            if m1_closed:
                idx = m1_epoch_to_idx.get(prev_bar_epoch)
                if idx is not None and idx > current_m1_idx:
                    current_m1_idx = idx
                    signals = self._build_signals(all_indicators, current_m1_idx)
                    signals_dirty = True
                    mid = (bid + ask) / 2.0
                    self.simulator._update_equity(mid)

            # ── 3. Evaluate strategies ───────────────────────────────
            if signals and current_m1_idx >= 0:
                # Rising-edge reset at trade_from boundary
                if m1_closed and not edge_reset_done and self.trade_from is not None:
                    closed_bar_time = df_m1["time"].iloc[current_m1_idx].to_pydatetime()
                    if closed_bar_time >= self.trade_from:
                        self._reset_edge_state(closed_bar_time.strftime("%Y-%m-%d %H:%M"))
                        edge_reset_done = True

                # Evaluate when signals changed.
                # When running_* is implemented, remove this guard to
                # evaluate on every tick.
                if signals_dirty:
                    tick_dt_eval = datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)
                    # BUY fills at ask, SELL fills at bid — _try_open_trades
                    # receives ask as entry_price; override below.
                    self._try_open_tick_trades(
                        signals, tick_dt_eval, bid, ask,
                        current_m1_idx, warmup_map,
                    )
                    signals_dirty = False

            prev_bar_epoch = bar_epoch

            if self.total_ticks % log_interval == 0:
                pct = self.total_ticks / n_ticks * 100
                log.info(
                    "Progress: %d/%d ticks (%.0f%%) | Trades: %d | Balance: $%.2f",
                    self.total_ticks, n_ticks, pct,
                    len(self.simulator.closed_trades),
                    self.simulator.balance,
                )

        # ── Finalize ─────────────────────────────────────────────────
        if prev_bar_epoch >= 0:
            idx = m1_epoch_to_idx.get(prev_bar_epoch)
            if idx is not None and idx > current_m1_idx:
                current_m1_idx = idx
                signals = self._build_signals(all_indicators, current_m1_idx)
                last_dt = datetime.fromtimestamp(
                    int(tick_epochs[-1]), tz=timezone.utc,
                ).replace(tzinfo=None)
                self._try_open_tick_trades(
                    signals, last_dt,
                    float(tick_bids[-1]), float(tick_asks[-1]),
                    current_m1_idx, warmup_map,
                )

        # Close remaining positions at last tick
        if self.simulator.open_positions:
            last_dt = datetime.fromtimestamp(
                int(tick_epochs[-1]), tz=timezone.utc,
            ).replace(tzinfo=None)
            last_bid = float(tick_bids[-1])
            last_ask = float(tick_asks[-1])
            for rule_name in list(self.simulator.open_positions.keys()):
                pos = self.simulator.open_positions[rule_name]
                exit_price = last_bid if pos.direction == "BUY" else last_ask
                self.simulator._close_position(rule_name, exit_price, last_dt, "END_OF_DATA")

        log.info(
            "Tick backtest done: %d ticks, %d M1 bars, %d signals, %d blocked, "
            "%d trades, final $%.2f",
            self.total_ticks, current_m1_idx + 1, self.signals_fired,
            self.trades_blocked, len(self.simulator.closed_trades),
            self.simulator.balance,
        )
        return self.simulator

    # ── private ──────────────────────────────────────────────────────────

    def _try_open_tick_trades(
        self,
        signals: dict[str, Signal],
        tick_dt: datetime,
        bid: float,
        ask: float,
        current_m1_idx: int,
        warmup_map: dict[str, int],
    ) -> None:
        """Evaluate strategies with bid/ask fill prices.

        Calls the shared ``_try_open_trades`` twice with direction-
        appropriate prices isn't needed — instead we override the
        entry price per-direction inside the base method.  Since
        ``_try_open_trades`` uses a single ``entry_price`` we call it
        with the mid and let the base handle it — but for tick mode we
        need BUY→ask, SELL→bid.  We use the mid as a dummy; the
        actual fill is set below.
        """
        # We need direction-aware fill, so we loop here directly
        # using base helpers for the common checks.
        for rule in self.strategies:
            result = rule.evaluate(signals)

            if not result.should_trade or result.direction is None:
                continue
            if current_m1_idx < warmup_map.get(rule.name, 0):
                continue
            if self.trade_from is not None and tick_dt < self.trade_from:
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
                direction, rule.name, tick_dt, self.simulator,
            )
            if not allowed:
                self.trades_blocked += 1
                continue

            entry_price = ask if direction == "BUY" else bid
            breakeven_pct = result.breakeven_pct if result.breakeven_pct is not None else self.default_be_pct
            partial_tp = result.partial_tp if result.partial_tp is not None else self.default_partial_tp

            positions = self.simulator.open_position(
                direction=direction,
                price=entry_price,
                time=tick_dt,
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
                    tick_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    pos.direction, rule.name,
                    pos.entry_price, pos.sl, pos.tp, pos.volume,
                    "runner" if pos.is_runner else "main",
                )
