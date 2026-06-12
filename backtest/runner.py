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

import pandas as pd

from core.config import Config
from backtest.base_runner import BaseBacktestRunner, compute_warmup

log = logging.getLogger(__name__)

# Re-export for backward compat
_compute_warmup = compute_warmup


class BacktestRunner(BaseBacktestRunner):
    """Orchestrates the entire backtest: indicators → signals → strategies → fills."""

    def __init__(
        self,
        config: Config,
        df_m1: pd.DataFrame,
        *,
        trade_from: datetime | None = None,
        native_bars: dict[str, pd.DataFrame] | None = None,
    ) -> None:
        super().__init__(config, trade_from=trade_from)
        self.df = df_m1
        self.native_bars = native_bars
        self.total_bars = 0

    def run(self) -> "Simulator":
        """Execute the backtest. Returns the simulator with all results."""

        all_indicators = self._compute_indicators(self.df, native_bars=self.native_bars)
        if all_indicators is None:
            return self.simulator
        log.info("Indicators computed: %s", list(all_indicators.keys()))

        warmup_map = compute_warmup(all_indicators, self.strategies)
        global_warmup = max(warmup_map.values()) if warmup_map else 0
        log.info("Per-strategy warmup computed — global max: %d bars", global_warmup)

        times = pd.to_datetime(self.df["time"])
        opens = self.df["open"].values
        highs = self.df["high"].values
        lows = self.df["low"].values
        closes = self.df["close"].values

        n_bars = len(self.df)
        log_interval = max(1, n_bars // 20)
        log.info("Starting bar-by-bar replay (%d bars)...", n_bars)

        edge_reset_done = self.trade_from is None

        for i in range(n_bars):
            self.total_bars += 1
            bar_time = times.iloc[i].to_pydatetime()

            # Reset rising-edge state at trade_from boundary
            if not edge_reset_done and self.trade_from is not None and bar_time >= self.trade_from:
                self._reset_edge_state(bar_time.strftime("%Y-%m-%d %H:%M"))
                edge_reset_done = True

            # Check SL/TP on existing positions FIRST (uses this bar's OHLC)
            closed = self.simulator.process_bar(bar_time, opens[i], highs[i], lows[i], closes[i])
            for trade in closed:
                log.debug(
                    "[%s] %s %s closed @ %.2f P&L=%.2f (%s)",
                    bar_time.strftime("%Y-%m-%d %H:%M"),
                    trade.rule_name, trade.direction,
                    trade.exit_price, trade.profit, trade.exit_reason,
                )

            # Build signal snapshot and evaluate strategies.
            # ALL rules evaluate every bar so rising-edge state stays current.
            signals = self._build_signals(all_indicators, i)
            self._try_open_trades(signals, bar_time, closes[i], i, warmup_map)

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
