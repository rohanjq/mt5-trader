"""Main backtest runner — bar-by-bar replay through historical data.

Uses the same Config, Signal, and ExpressionRule classes as the live trader.

Fill model matches live behaviour:
  • The EA writes CSV at candle close.
  • Python polls every 2 s → signal detected within 2 s of close.
  • Trade fills at market price ≈ bar close.
  Therefore: signal evaluated on bar-close data → fill at that bar's close.
  SL/TP monitoring starts from the NEXT bar.

UTBot HTF boundary fix:
  At M1 bars that fall on an HTF boundary (e.g. M1 11:04 is the last bar
  of M5 11:00), the forward-fill shows the just-completed HTF bar as
  closed.  But the EA evaluates ~1s after bar close, when that HTF bar is
  still "running".  So for UTBot consecutive bar counts, we use bar i-1's
  trail_stop and raw consecutive counts at HTF boundaries, matching the
  EA's view of the last *closed* HTF bar.

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
from core.models import Signal, SignalDirection
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
        ea_atr_dir: str | None = None,
        ticks: pd.DataFrame | None = None,
    ) -> None:
        super().__init__(config, trade_from=trade_from)
        self.df = df_m1
        self.native_bars = native_bars
        self.ea_atr_dir = ea_atr_dir
        self.ticks = ticks
        self.total_bars = 0

    def run(self) -> "Simulator":
        """Execute the backtest. Returns the simulator with all results."""

        all_indicators = self._compute_indicators(self.df, native_bars=self.native_bars,
                                                   ea_atr_dir=self.ea_atr_dir)
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

            # UTBot consecutive-bar override: the EA evaluates ~1s after M1
            # bar close.  At that instant, CopyRates(M5) still shows the
            # current M5 bar as "running" — the last closed M5 is the
            # previous one.  Our forward-fill already shows the new M5 bar
            # as closed at the HTF boundary M1 bar, so the trail_stop and
            # consecutive counts are off by one HTF bar.
            #
            # Fix: always use bar i-1's trail_stop (which at boundary bars
            # points to the previous HTF bar — matching the EA), and use
            # the M1 close price as the "current bid" for the direction check.
            self._override_utbot_consecutive(signals, closes[i], all_indicators, i)

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

    @staticmethod
    def _override_utbot_consecutive(
        signals: dict[str, Signal],
        bid: float,
        all_indicators: dict[str, pd.DataFrame],
        bar_idx: int,
    ) -> None:
        """Override UTBot consecutive bar counts using tick-level running direction.

        The EA counts consecutive bars from the running bar backward.  The
        running bar's direction is determined by ``bid > trail_stop``.

        Critical timing detail: the EA evaluates ~1s after M1 bar close.
        For M1 bar i that is the LAST bar of an HTF period (e.g. M1 11:04
        is the last of M5 11:00), the forward-fill at bar i shows the
        just-closed HTF bar (M5 11:00).  But the EA at 11:04:12 still
        sees M5 11:00 as the running bar — the last closed M5 is 10:55.

        So for the running-bar direction check, we use bar (i-1)'s
        trail_stop.  If bar i-1 and bar i show the same HTF bar (mid-period),
        the trail is the same.  If they differ (boundary), bar i-1 has the
        previous HTF bar's trail — which is what the EA's running bar
        would compare against.
        """
        prev_idx = max(0, bar_idx - 1)
        for sig_name, sig in list(signals.items()):
            if not sig_name.startswith("utbot_"):
                continue
            ind_df = all_indicators.get(sig_name)
            if ind_df is None or bar_idx >= len(ind_df):
                continue

            # Use bar i-1's trail_stop for the running-bar direction check
            prev_row = ind_df.iloc[prev_idx]
            trail_stop = prev_row.get("closed_trail_stop")
            if trail_stop is None or pd.isna(trail_stop):
                continue

            # Use bar i-1's raw consecutive counts (from the previous closed HTF bar)
            raw_bull = prev_row.get("_closed_consec_bull", 0)
            raw_bear = prev_row.get("_closed_consec_bear", 0)
            if pd.isna(raw_bull):
                raw_bull = 0
            if pd.isna(raw_bear):
                raw_bear = 0
            raw_bull = int(raw_bull)
            raw_bear = int(raw_bear)

            # Running bar direction: EA does close > trail → BULL, else BEAR
            running_bull = bid > trail_stop

            if running_bull:
                consec_bull = raw_bull + 1
                consec_bear = 0
            else:
                consec_bull = 0
                consec_bear = raw_bear + 1

            # Patch metadata
            md = dict(sig.metadata)
            md["consecutive_bull_bars"] = str(consec_bull)
            md["consecutive_bear_bars"] = str(consec_bear)
            md["running_bias"] = "BULLISH" if running_bull else "BEARISH"

            signals[sig_name] = Signal(
                source=sig.source,
                direction=SignalDirection.NEUTRAL,
                metadata=md,
            )
