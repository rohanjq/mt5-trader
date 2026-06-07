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
    """Current signals from all sources."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self._engine = engine

    def compose(self) -> ComposeResult:
        table = DataTable(id="signal-table")
        table.add_columns("Source", "Direction", "Bias/Zone", "Signal", "Detail", "Updated")
        yield table

    def refresh_content(self) -> None:
        table = self.query_one("#signal-table", DataTable)
        table.clear()

        signals = self._engine.latest_signals
        for name, sig in signals.items():
            if sig.direction == SignalDirection.BUY:
                direction = "[green]▲ BUY[/]"
            elif sig.direction == SignalDirection.SELL:
                direction = "[red]▼ SELL[/]"
            else:
                direction = "[yellow]— NEUTRAL[/]"

            meta = sig.metadata
            ts = datetime.fromtimestamp(sig.timestamp).strftime("%H:%M:%S")

            if name.startswith("utbot_"):
                bias = meta.get('closed_bias', '—')
                sig_val = meta.get('closed_signal', 'NONE')
                if sig_val.upper() == "BUY":
                    sig_col = f"[green]{sig_val}[/]"
                elif sig_val.upper() == "SELL":
                    sig_col = f"[red]{sig_val}[/]"
                else:
                    sig_col = f"[dim]{sig_val}[/]"
                atr = meta.get('closed_atr', '—')
                trail = meta.get('closed_trail_stop', '—')
                bull = meta.get('consecutive_bull_bars', '—')
                bear = meta.get('consecutive_bear_bars', '—')
                detail = f"ATR={atr} Bull={bull} Bear={bear}"
                table.add_row(name, direction, bias, sig_col, detail, ts)
            elif name.startswith("dc_"):
                zone = meta.get('closed_price_zone', '—')
                uw = meta.get('closed_upper_wick_rej', 'FALSE')
                lw = meta.get('closed_lower_wick_rej', 'FALSE')
                wick = ""
                if lw.upper() == "TRUE":
                    wick = "[green]↓ Lower[/]"
                elif uw.upper() == "TRUE":
                    wick = "[red]↑ Upper[/]"
                else:
                    wick = "[dim]None[/]"
                upper = meta.get('upper_band', '—')
                lower = meta.get('lower_band', '—')
                detail = f"U={upper} L={lower}"
                table.add_row(name, direction, zone, wick, detail, ts)
            else:
                info = " ".join(f"{k}={v}" for k, v in list(meta.items())[:3])
                table.add_row(name, direction, "—", "—", info, ts)


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


# ── Main App ───────────────────────────────────────────────────────────────────

DASHBOARD_CSS = """
Screen {
    layout: vertical;
}

#status-panel {
    height: 3;
    border: solid $primary;
    padding: 0 1;
}

#signal-panel {
    height: auto;
    max-height: 12;
    border: solid $secondary;
    padding: 0 1;
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

#trade-log-panel {
    height: 1fr;
    border: solid $primary-darken-2;
    padding: 0 1;
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
        yield SignalPanel(self._engine, id="signal-panel")
        yield PositionPanel(self._engine, id="position-panel")
        yield SummaryPanel(self._engine, id="summary-panel")
        yield FilterPanel(self._engine, id="filter-panel")
        yield RulesPanel(self._engine, id="rules-panel")
        yield TradeLogPanel(self._engine, id="trade-log-panel")
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
