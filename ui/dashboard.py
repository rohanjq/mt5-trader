from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Label, Static

from core.events import EventLevel, EventLog
from core.models import Signal, SignalDirection, TradeState

if TYPE_CHECKING:
    from core.engine import Engine


class StatusPanel(Static):
    """System status: running/paused, uptime, MT5 connection."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine
        self._start_time = time.time()

    def compose(self) -> ComposeResult:
        yield Label("", id="status-text")

    def refresh_content(self) -> None:
        engine = self._engine
        uptime = timedelta(seconds=int(time.time() - self._start_time))

        mt5_status = "[green]Connected[/]" if engine.mt5_client.connected else "[red]Disconnected[/]"
        trading = "[green]ENABLED[/]" if (engine.manual_switch and engine.manual_switch.is_enabled) else "[red]PAUSED[/]"
        running = "[green]Running[/]" if engine.is_running else "[red]Stopped[/]"

        text = (
            f"Engine: {running}  │  Trading: {trading}  │  "
            f"MT5: {mt5_status}  │  Uptime: {uptime}"
        )
        label = self.query_one("#status-text", Label)
        label.update(text)


class SignalPanel(Static):
    """Vertical signal sidebar grouped by timeframe."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        yield Label("[dim]Waiting for signals...[/]", id="signal-text")

    def refresh_content(self) -> None:
        label = self.query_one("#signal-text", Label)
        signals = self._engine.latest_signals

        if not signals:
            label.update("[dim]No signals[/]")
            return

        # Group signals by timeframe
        tf_order = ["M1", "M3", "M5", "M10", "M15", "M45", "H1", "H4", "D1"]
        groups: dict[str, list[tuple[str, Signal]]] = {}
        for name, sig in signals.items():
            # Extract timeframe from name like utbot_M1, dc_M15
            parts = name.split("_", 1)
            tf = parts[1] if len(parts) > 1 else "?"
            groups.setdefault(tf, []).append((name, sig))

        lines: list[str] = []
        sorted_tfs = sorted(groups.keys(), key=lambda t: tf_order.index(t) if t in tf_order else 99)

        for tf in sorted_tfs:
            lines.append(f"[bold cyan]── {tf} ──[/]")
            for name, sig in groups[tf]:
                meta = sig.metadata
                indicator = name.split("_")[0].upper()

                if indicator == "UTBOT":
                    bias = meta.get("closed_bias", "—")
                    if bias.upper() == "BULLISH":
                        bias_col = f"[green]{bias}[/]"
                    elif bias.upper() == "BEARISH":
                        bias_col = f"[red]{bias}[/]"
                    else:
                        bias_col = f"[dim]{bias}[/]"

                    sig_val = meta.get("closed_signal", "NONE")
                    if sig_val.upper() == "BUY":
                        sig_col = f"[bold green]★ {sig_val}[/]"
                    elif sig_val.upper() == "SELL":
                        sig_col = f"[bold red]★ {sig_val}[/]"
                    else:
                        sig_col = f"[dim]{sig_val}[/]"

                    atr = meta.get("closed_atr", "—")
                    bull = meta.get("consecutive_bull_bars", "0")
                    bear = meta.get("consecutive_bear_bars", "0")
                    lines.append(f"  UT  {bias_col}  {sig_col}")
                    lines.append(f"  [dim]ATR={atr} Bull={bull} Bear={bear}[/]")

                elif indicator == "DC":
                    zone = meta.get("closed_price_zone", "—")
                    if zone.upper() in ("LOWER", "LOWER_MID"):
                        zone_col = f"[green]{zone}[/]"
                    elif zone.upper() in ("UPPER", "UPPER_MID"):
                        zone_col = f"[red]{zone}[/]"
                    else:
                        zone_col = f"[yellow]{zone}[/]"

                    uw = meta.get("closed_upper_wick_rej", "FALSE").upper() == "TRUE"
                    lw = meta.get("closed_lower_wick_rej", "FALSE").upper() == "TRUE"
                    if lw:
                        wick = "[green]↓ LowerWick[/]"
                    elif uw:
                        wick = "[red]↑ UpperWick[/]"
                    else:
                        wick = "[dim]no wick[/]"

                    upper = meta.get("upper_band", "—")
                    lower = meta.get("lower_band", "—")
                    lines.append(f"  DC  {zone_col}  {wick}")
                    lines.append(f"  [dim]U={upper} L={lower}[/]")

                elif indicator == "LIQGRAB":
                    lsig = meta.get("liq_signal", "NONE")
                    if lsig.upper() == "BUY":
                        sig_col = f"[bold green]★ BUY[/]"
                    elif lsig.upper() == "SELL":
                        sig_col = f"[bold red]★ SELL[/]"
                    else:
                        sig_col = f"[dim]{lsig}[/]"

                    rej_up = meta.get("rejection_up", "FALSE")
                    rej_dn = meta.get("rejection_down", "FALSE")
                    bk_up = meta.get("breakout_up", "FALSE")
                    bk_dn = meta.get("breakout_down", "FALSE")
                    ma_trend = meta.get("ma_trend", "—")
                    parts = []
                    if rej_up.upper() == "TRUE":
                        parts.append("[green]RejUp[/]")
                    if rej_dn.upper() == "TRUE":
                        parts.append("[red]RejDn[/]")
                    if bk_up.upper() == "TRUE":
                        parts.append("[green]BrkUp[/]")
                    if bk_dn.upper() == "TRUE":
                        parts.append("[red]BrkDn[/]")
                    flags = " ".join(parts) if parts else "[dim]quiet[/]"
                    lines.append(f"  LG  {sig_col}  MA={ma_trend}")
                    lines.append(f"  [dim]{flags}[/]")

                else:
                    # Compact 1-line rendering for filter/context indicators
                    tag = indicator[:6]
                    if indicator.startswith("EMA"):
                        vs = meta.get("closed_price_vs_ema", "—")
                        slope = meta.get("ema_slope", "")
                        col = "[green]" if vs == "ABOVE" else "[red]" if vs == "BELOW" else "[dim]"
                        lines.append(f"  {tag} {col}{vs}[/] {slope}")
                    elif indicator.startswith("RSI"):
                        val = meta.get("closed_rsi", "—")
                        zone = meta.get("closed_zone", "—")
                        col = "[red]" if "OB" in zone else "[green]" if "OS" in zone else "[dim]"
                        lines.append(f"  {tag} {col}{zone}[/] ({val})")
                    elif indicator == "ADX":
                        ts = meta.get("closed_trend_strength", "—")
                        bias = meta.get("closed_di_bias", "—")
                        col = "[green]" if bias == "BULLISH" else "[red]" if bias == "BEARISH" else "[dim]"
                        lines.append(f"  ADX  {ts} {col}{bias}[/]")
                    elif indicator == "BB":
                        pct = meta.get("closed_pct_in_band", "—")
                        re_up = meta.get("closed_reenter_from_below", "FALSE")
                        re_dn = meta.get("closed_reenter_from_above", "FALSE")
                        flag = "[green]↑ReEntry[/]" if re_up.upper() == "TRUE" else "[red]↓ReEntry[/]" if re_dn.upper() == "TRUE" else ""
                        lines.append(f"  BB   pct={pct} {flag}")
                    elif indicator == "MACD":
                        hc = meta.get("closed_hist_cross", "NONE")
                        col = "[green]" if hc == "BULLISH_FLIP" else "[red]" if hc == "BEARISH_FLIP" else "[dim]"
                        lines.append(f"  MACD {col}{hc}[/]")
                    elif indicator == "STOCH":
                        cr = meta.get("closed_cross", "NONE")
                        col = "[green]" if "BULLISH" in cr else "[red]" if "BEARISH" in cr else "[dim]"
                        lines.append(f"  STCH {col}{cr}[/]")
                    elif indicator == "ATR":
                        vs = meta.get("volatility_state", "—")
                        col = "[yellow]" if vs in ("EXPANDING", "ABOVE_AVG") else "[dim]"
                        lines.append(f"  ATR  {col}{vs}[/]")
                    else:
                        lines.append(f"  {tag}: {sig.direction.value}")

        label.update("\n".join(lines))


class PositionPanel(Static):
    """Active position details."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        yield Label("", id="position-text")

    def refresh_content(self) -> None:
        trade = self._engine.trade_manager.open_trade
        label = self.query_one("#position-text", Label)

        if trade is None:
            label.update("[dim]No open position[/]")
            return

        direction = "[green]BUY[/]" if trade.direction.value == "BUY" else "[red]SELL[/]"
        pnl_color = "green" if trade.profit >= 0 else "red"
        duration = timedelta(seconds=int(trade.duration_seconds))

        sl_str = f"{trade.sl:.2f}" if trade.sl > 0 else "—"
        tp_str = f"{trade.tp:.2f}" if trade.tp > 0 else "—"

        text = (
            f"Direction: {direction}  │  Entry: {trade.entry_price:.2f}  │  "
            f"Vol: {trade.volume}  │  "
            f"SL: {sl_str}  │  TP: {tp_str}  │  "
            f"P&L: [{pnl_color}]{trade.profit:+.2f}[/]  │  "
            f"Duration: {duration}  │  Ticket: {trade.ticket}"
        )
        label.update(text)


class SummaryPanel(Static):
    """Today's trading summary."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        yield Label("", id="summary-text")

    def refresh_content(self) -> None:
        stats = self._engine.trade_manager.today_stats()
        label = self.query_one("#summary-text", Label)

        pnl = stats["net_pnl"]
        pnl_color = "green" if pnl >= 0 else "red"

        text = (
            f"Trades: {stats['total']}  │  "
            f"Wins: [green]{stats['wins']}[/]  │  Losses: [red]{stats['losses']}[/]  │  "
            f"Avg Win: [green]{stats['avg_profit']:+.2f}[/]  │  "
            f"Avg Loss: [red]{stats['avg_loss']:+.2f}[/]  │  "
            f"Net P&L: [{pnl_color}]{pnl:+.2f}[/]"
        )
        label.update(text)


class TradeLogPanel(Static):
    """Scrollable trade history."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        table = DataTable(id="trade-log-table")
        table.add_columns("ID", "Dir", "Entry", "Exit", "Volume", "P&L", "Signal", "Time")
        yield table

    def refresh_content(self) -> None:
        table = self.query_one("#trade-log-table", DataTable)
        table.clear()

        history = self._engine.trade_manager.trade_history
        for trade in reversed(history[-50:]):
            direction = "[green]BUY[/]" if trade.direction.value == "BUY" else "[red]SELL[/]"
            pnl_color = "green" if trade.profit >= 0 else "red"
            exit_t = trade.exit_time.strftime("%H:%M:%S") if trade.exit_time else "—"
            table.add_row(
                trade.id[:8],
                direction,
                f"{trade.entry_price:.2f}",
                f"{trade.exit_price:.2f}" if trade.exit_price else "—",
                f"{trade.volume}",
                f"[{pnl_color}]{trade.profit:+.2f}[/]",
                trade.signal_source,
                trade.entry_time.strftime("%H:%M:%S"),
            )


class FilterPanel(Static):
    """Active filters and their status."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        yield Label("", id="filter-text")

    def refresh_content(self) -> None:
        label = self.query_one("#filter-text", Label)
        parts: list[str] = []

        for f in self._engine.filter_chain.filters:
            status = "[green]●[/]"
            extra = ""
            if hasattr(f, "is_enabled"):
                if not f.is_enabled:
                    status = "[red]●[/]"
                    extra = " (OFF)"
            parts.append(f"{status} {f.name}{extra}")

        label.update("  │  ".join(parts) if parts else "[dim]No filters loaded[/]")


class RulesPanel(Static):
    """Active trigger rules and their last evaluation result."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        yield Label("", id="rules-text")

    def refresh_content(self) -> None:
        label = self.query_one("#rules-text", Label)
        parts: list[str] = []

        for rule in self._engine.trade_initiator.rules:
            result = rule.last_result
            if result.should_trade:
                if result.action.value == "TRIGGER_BUY":
                    icon = "[green]▲ BUY[/]"
                else:
                    icon = "[red]▼ SELL[/]"
                parts.append(f"{icon} {rule.name}")
            else:
                parts.append(f"[dim]● {rule.name}[/]")

        label.update("  │  ".join(parts) if parts else "[dim]No rules loaded[/]")


class RuleDetailPanel(Static):
    """Per-condition evaluation details for expression rules."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        yield Label("[dim]Waiting for signals...[/]", id="rule-detail-text")

    def refresh_content(self) -> None:
        label = self.query_one("#rule-detail-text", Label)
        signals = self._engine.latest_signals

        if not signals:
            label.update("[dim]Waiting for signals...[/]")
            return

        from rules.expression import ExpressionRule

        lines: list[str] = []
        for rule in self._engine.trade_initiator.rules:
            if not isinstance(rule, ExpressionRule):
                continue

            # Evaluate buy side
            buy_conds = rule._buy_conditions
            sell_conds = rule._sell_conditions
            buy_ok = buy_conds and all(c.evaluate(signals) for c in buy_conds)
            sell_ok = sell_conds and all(c.evaluate(signals) for c in sell_conds)

            if buy_ok:
                tag = "[bold green]▲ BUY[/]"
            elif sell_ok:
                tag = "[bold red]▼ SELL[/]"
            else:
                tag = "[dim]—[/]"

            sl = getattr(rule, '_sl_dollars', None)
            rr = getattr(rule, '_reward_ratio', None)
            risk_info = f" SL=${sl:.0f} {rr}R" if sl else ""
            lines.append(f"[bold]{rule.name}[/] {tag}{risk_info}")

            # Show buy conditions
            if buy_conds:
                for c in buy_conds:
                    ok = c.evaluate(signals)
                    sig = signals.get(c.signal)
                    actual = sig.metadata.get(c.field, "?").strip() if sig else "[no data]"
                    icon = "[green]✓[/]" if ok else "[red]✗[/]"
                    lines.append(f"  {icon} {c.signal}.{c.field} {c.operator} {c.value} [dim]({actual})[/]")

        label.update("\n".join(lines) if lines else "[dim]No expression rules[/]")


class EventLogPanel(Static):
    """Live event stream — rule triggers, filter blocks, trade opens/closes."""

    _LEVEL_COLORS = {
        EventLevel.INFO: "dim",
        EventLevel.TRADE: "green",
        EventLevel.BLOCK: "red",
        EventLevel.WARN: "yellow",
        EventLevel.EXIT: "cyan",
    }

    def compose(self) -> ComposeResult:
        yield Label("[dim]Waiting for events...[/]", id="event-text")

    def refresh_content(self) -> None:
        label = self.query_one("#event-text", Label)
        events = EventLog.get().recent(15)
        if not events:
            label.update("[dim]No events yet[/]")
            return

        lines: list[str] = []
        for ev in events:
            ts = datetime.fromtimestamp(ev.timestamp).strftime("%H:%M:%S")
            color = self._LEVEL_COLORS.get(ev.level, "white")
            tag = ev.level.value
            lines.append(f"[dim]{ts}[/] [{color}]{tag:5s}[/] {ev.message}")

        label.update("\n".join(lines))


# ── Main App ───────────────────────────────────────────────────────────────────

DASHBOARD_CSS = """
Screen {
    layout: vertical;
}

#top-bar {
    height: 3;
}

#status-panel {
    height: 3;
    border: solid $primary;
    padding: 0 1;
}

#main-area {
    height: 1fr;
    layout: horizontal;
}

#left-panels {
    width: 1fr;
    layout: vertical;
}

#signal-panel {
    width: 36;
    min-width: 30;
    border: solid $secondary;
    padding: 0 1;
    overflow-y: auto;
}

#position-panel {
    height: 4;
    border: solid $accent;
    padding: 0 1;
}

#summary-panel {
    height: 3;
    border: solid $success;
    padding: 0 1;
}

#filter-panel {
    height: 3;
    border: solid $warning;
    padding: 0 1;
}

#rules-panel {
    height: 3;
    border: solid $accent-darken-1;
    padding: 0 1;
}

#rule-detail-panel {
    height: 1fr;
    border: solid $accent-darken-2;
    padding: 0 1;
    overflow-y: auto;
}

#trade-log-panel {
    height: 1fr;
    border: solid $primary-darken-2;
    padding: 0 1;
}

#event-log-panel {
    height: 1fr;
    border: solid $success-darken-1;
    padding: 0 1;
    overflow-y: auto;
}

Static {
    height: auto;
}
"""


class TradingDashboard(App):
    """MT5 Trading System TUI Dashboard."""

    CSS = DASHBOARD_CSS

    TITLE = "MT5 Auto-Trader"
    SUB_TITLE = "BTCUSDT"

    BINDINGS = [
        Binding("b", "manual_buy", "Manual Buy"),
        Binding("s", "manual_sell", "Manual Sell"),
        Binding("t", "toggle_trading", "Toggle Trading"),
        Binding("c", "close_position", "Close Position"),
        Binding("r", "reconnect_mt5", "Reconnect MT5"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, engine: Engine) -> None:
        super().__init__()
        self._engine = engine

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusPanel(self._engine, id="status-panel")
        with Horizontal(id="main-area"):
            with Vertical(id="left-panels"):
                yield PositionPanel(self._engine, id="position-panel")
                yield SummaryPanel(self._engine, id="summary-panel")
                yield FilterPanel(self._engine, id="filter-panel")
                yield RulesPanel(self._engine, id="rules-panel")
                yield RuleDetailPanel(self._engine, id="rule-detail-panel")
                yield EventLogPanel(id="event-log-panel")
                yield TradeLogPanel(self._engine, id="trade-log-panel")
            yield SignalPanel(self._engine, id="signal-panel")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.5, self._refresh_all)

    def _refresh_all(self) -> None:
        try:
            self.query_one("#status-panel", StatusPanel).refresh_content()
            self.query_one("#signal-panel", SignalPanel).refresh_content()
            self.query_one("#position-panel", PositionPanel).refresh_content()
            self.query_one("#summary-panel", SummaryPanel).refresh_content()
            self.query_one("#filter-panel", FilterPanel).refresh_content()
            self.query_one("#rules-panel", RulesPanel).refresh_content()
            self.query_one("#rule-detail-panel", RuleDetailPanel).refresh_content()
            self.query_one("#event-log-panel", EventLogPanel).refresh_content()
            self.query_one("#trade-log-panel", TradeLogPanel).refresh_content()
        except Exception:
            pass  # UI race conditions during shutdown

    def action_toggle_trading(self) -> None:
        if self._engine.manual_switch:
            enabled = self._engine.manual_switch.toggle()
            state = "ENABLED" if enabled else "PAUSED"
            self.notify(f"Auto-trading {state}", severity="information")

    def action_close_position(self) -> None:
        result = self._engine.trade_manager.close_current_position()
        if result:
            self._engine.trade_initiator.reset_signal_tracking()
            self.notify(f"Position closed: P&L {result.profit:+.2f}", severity="information")
        else:
            self.notify("No open position to close", severity="warning")

    def action_reconnect_mt5(self) -> None:
        self._engine.mt5_client.disconnect()
        if self._engine.mt5_client.connect():
            self.notify("Reconnected to MT5", severity="information")
        else:
            self.notify("Failed to reconnect to MT5", severity="error")

    def action_quit_app(self) -> None:
        self._engine.stop()
        self.exit()

    def action_manual_buy(self) -> None:
        from core.models import TradeDirection
        if self._engine.trade_initiator.manual_trade(TradeDirection.BUY):
            self.notify("Manual BUY placed", severity="information")
        else:
            self.notify("Cannot place BUY — position open or MT5 error", severity="warning")

    def action_manual_sell(self) -> None:
        from core.models import TradeDirection
        if self._engine.trade_initiator.manual_trade(TradeDirection.SELL):
            self.notify("Manual SELL placed", severity="information")
        else:
            self.notify("Cannot place SELL — position open or MT5 error", severity="warning")
