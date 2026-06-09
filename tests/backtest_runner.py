"""Shared backtest runner for strategy variant testing.

Usage:
    from tests.backtest_runner import StrategyRunner, combo

    runner = StrategyRunner(
        title="My Strategy Variants",
        sources=[
            {"indicator": "utbot", "timeframes": ["M3", "M5", "M15"]},
            {"indicator": "candle", "timeframes": ["M3"]},
        ],
    )

    runner.add("BUY", "my_strategy_name", "Description",
        buy=["candle_M3.closed_candle_type == HAMMER",
             "utbot_M15.closed_bias == BULLISH"],
    )
    runner.add("SELL", "my_sell_strategy", "Description",
        sell=["candle_M3.closed_candle_type == SHOOTING_STAR",
              "utbot_M15.closed_bias == BEARISH"],
    )

    runner.run()
"""
from __future__ import annotations

import copy
import re
import subprocess
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "sampledata" / "XAUUSD_M1_60d.csv"

_BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {
        "symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0,
        "max_volume": 10.0, "min_volume": 0.01, "magic": 300,
        "deviation": 20, "filling": "FOK", "multi_position": False,
        "sl_dollars": 7.5, "reward_ratio": 1.0,
    },
    "filters": {
        "cooldown_seconds": 30, "max_consecutive_losses": 0,
        "pause_after_consecutive_minutes": 0, "max_daily_loss": -1,
        "reversal_cooldown_seconds": 30,
    },
    "exit_rules": {
        "signal_reversal_exit": False, "breakeven_pct": 0.0,
        "partial_tp": False, "tp_close_pct": 100.0,
        "trailing_stop_dollars": 0.0,
    },
    "notifications": {"enabled": False},
}

PF_RE = re.compile(r"Profit Factor\s+([\d.]+|inf)")
TR_RE = re.compile(r"Total Trades\s+(\d+)")
WR_RE = re.compile(r"Win Rate\s+([\d.]+)%")
NT_RE = re.compile(r"Final Balance\s+\$([\d.,+-]+)")
DD_RE = re.compile(r"Max Drawdown\s+([\d.]+)%")


class StrategyRunner:
    """Reusable strategy variant backtester.

    Args:
        title: Display title for the report header.
        sources: List of indicator sources (only include what strategies need).
        sl: Default stop loss in dollars (default 7.5).
        data: Path to M1 OHLC CSV. Defaults to XAUUSD_M1_60d.csv.
        balance: Starting balance (default 10000).
    """

    def __init__(
        self,
        title: str = "Strategy Variants",
        sources: list[dict] | None = None,
        sl: float = 7.5,
        data: Path | str | None = None,
        balance: float = 10000,
    ):
        self.title = title
        self.sources = sources or [
            {"indicator": "utbot", "timeframes": ["M1", "M2", "M3", "M5", "M15", "M45"]},
            {"indicator": "dc", "timeframes": ["M5", "M15"]},
            {"indicator": "candle", "timeframes": ["M3", "M5"]},
            {"indicator": "ema50", "timeframes": ["M5"]},
            {"indicator": "vwap", "timeframes": ["M1"]},
        ]
        self.sl = sl
        self.data = Path(data) if data else DEFAULT_DATA
        self.balance = balance
        self.combos: list[tuple] = []
        self._tmpdir = Path("/tmp/strategy_runner_configs")
        self._tmpdir.mkdir(exist_ok=True)

    def add(
        self,
        direction: str,
        name: str,
        description: str,
        buy: list[str] | None = None,
        sell: list[str] | None = None,
        sl: float | None = None,
    ):
        """Add a strategy variant to test.

        Args:
            direction: "BUY" or "SELL" (for display only).
            name: Unique strategy name.
            description: Short description.
            buy: List of buy condition expressions.
            sell: List of sell condition expressions.
            sl: Override stop loss for this variant.
        """
        self.combos.append((direction, name, description,
                            sell or [], buy or [], sl or self.sl))

    def _build_config(self, name, desc, sell_conds, buy_conds, sl):
        cfg = copy.deepcopy(_BASE)
        cfg["trading"]["sl_dollars"] = sl
        cfg["signals"] = {
            "poll_interval": 2.0,
            "csv_dir": "../MetaTrader5-Docker/data/signals",
            "sources": self.sources,
        }
        rule = {
            "name": name, "enabled": True, "priority": 50,
            "sl_dollars": sl, "reward_ratio": 1.0,
            "breakeven_pct": 0.0, "partial_tp": False,
            "description": desc,
        }
        if buy_conds:
            rule["buy"] = buy_conds
        if sell_conds:
            rule["sell"] = sell_conds
        cfg["rules"] = {"expressions": [rule]}
        return cfg

    def _run_one(self, name, desc, sell_conds, buy_conds, sl):
        cfg = self._build_config(name, desc, sell_conds, buy_conds, sl)
        cfg_path = self._tmpdir / f"{name}.yaml"
        cfg_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
        r = subprocess.run(
            [sys.executable, "-m", "backtest",
             "--config", str(cfg_path), "--data", str(self.data),
             "--balance", str(self.balance)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        out = r.stdout + r.stderr
        pf = float(m.group(1)) if (m := PF_RE.search(out)) else 0
        tr = int(m.group(1)) if (m := TR_RE.search(out)) else 0
        wr = float(m.group(1)) if (m := WR_RE.search(out)) else 0
        bal = m.group(1).replace(",", "") if (m := NT_RE.search(out)) else str(self.balance)
        net = float(bal) - self.balance
        dd = float(m.group(1)) if (m := DD_RE.search(out)) else 0
        if tr == 0 and pf == 0:
            for line in (r.stderr or "").split("\n")[-5:]:
                if line.strip():
                    print(f"  DBG: {line.strip()}")
        return tr, wr, pf, net, dd

    def run(self):
        """Execute all variants and print results table."""
        print(f"\nData: {self.data}")
        print(f"{self.title}, SL ${self.sl}, multi_position OFF\n")
        print(f"{'=' * 90}")
        print(f"  {self.title}")
        print(f"{'=' * 90}")
        print(f"{'#':<3} {'Dir':<5} {'Name':<34} {'Trades':>6}  "
              f"{'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
        print("-" * 90)

        for i, combo in enumerate(self.combos, 1):
            direction, name, desc = combo[0], combo[1], combo[2]
            sell_conds, buy_conds, sl = combo[3], combo[4], combo[5]
            tr, wr, pf, net, dd = self._run_one(name, desc, sell_conds, buy_conds, sl)
            flag = (" ★" if pf >= 1.3 and tr >= 15
                    else " ✓" if pf >= 1.1 and tr >= 10
                    else "")
            print(f"{i:<3} {direction:<5} {name:<34} {tr:>6}  "
                  f"{wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
