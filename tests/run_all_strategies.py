#!/usr/bin/env python3
"""Run backtests for all strategies in the strategies/ folder.

Usage:
    # Run all enabled strategies:
    uv run python tests/run_all_strategies.py

    # Override fields (applies to ALL strategies):
    uv run python tests/run_all_strategies.py --sl_dollars 5.0 --reward_ratio 1.5
    uv run python tests/run_all_strategies.py --breakeven_pct 0.5 --partial_tp

    # Include disabled strategies too:
    uv run python tests/run_all_strategies.py --include-disabled

    # Only specific strategies (comma-separated):
    uv run python tests/run_all_strategies.py --only dc_wick_rejection,hammer_2w_m15_dc
"""
from __future__ import annotations

import argparse
import copy
import fnmatch
import re
import subprocess
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = ROOT / "strategies"
DEFAULT_DATA = ROOT / "sampledata" / "XAUUSD_M1_60d.csv"

_BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {
        "symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0,
        "max_volume": 10.0, "min_volume": 0.01, "magic": 300,
        "deviation": 20, "filling": "FOK", "multi_position": False,
    },
    "filters": {
        "cooldown_seconds": 30, "max_consecutive_losses": 0,
        "pause_after_consecutive_minutes": 0, "max_daily_loss": -1,
        "reversal_cooldown_seconds": 30,
    },
    "exit_rules": {
        "signal_reversal_exit": False,
        "partial_tp": False, "tp_close_pct": 100.0,
        "trailing_stop_dollars": 0.0,
    },
    "notifications": {"enabled": False},
}

# Regex to extract indicator_TIMEFRAME from condition strings
COND_RE = re.compile(r"^(\w+?)_(M\d+|H\d+|D1)\.")
PF_RE = re.compile(r"Profit Factor\s+([\d.]+|inf)")
TR_RE = re.compile(r"Total Trades\s+(\d+)")
WR_RE = re.compile(r"Win Rate\s+([\d.]+)%")
NT_RE = re.compile(r"Final Balance\s+\$([\d.,+-]+)")
DD_RE = re.compile(r"Max Drawdown\s+([\d.]+)%")

# Fields that can be overridden via CLI
OVERRIDE_FIELDS = {
    "sl_dollars": float,
    "reward_ratio": float,
    "breakeven_pct": float,
    "partial_tp": bool,
    "trailing_stop_dollars": float,
}


def parse_sources(strategies: list[dict]) -> list[dict]:
    """Auto-detect indicator sources from all strategy conditions."""
    indicator_tfs: dict[str, set[str]] = {}
    for strat in strategies:
        for cond in strat.get("buy", []) + strat.get("sell", []):
            m = COND_RE.match(cond)
            if m:
                ind, tf = m.group(1), m.group(2)
                indicator_tfs.setdefault(ind, set()).add(tf)

    return [
        {"indicator": ind, "timeframes": sorted(tfs, key=_tf_sort_key)}
        for ind, tfs in sorted(indicator_tfs.items())
    ]


def _tf_sort_key(tf: str) -> int:
    """Sort timeframes by minutes."""
    units = {"M": 1, "H": 60, "D": 1440}
    prefix = tf[0]
    num = int(tf[1:])
    return units.get(prefix, 0) * num


def load_strategies(
    include_disabled: bool = False,
    only: list[str] | None = None,
) -> list[dict]:
    """Load strategy YAML files from strategies/ folder."""
    strategies = []
    for f in sorted(STRATEGIES_DIR.glob("*.yaml")):
        strat = yaml.safe_load(f.read_text())
        if only and not any(fnmatch.fnmatch(strat["name"], pat) for pat in only):
            continue
        if not include_disabled and not strat.get("enabled", True):
            continue
        strategies.append(strat)
    return strategies


def apply_overrides(strat: dict, overrides: dict) -> dict:
    """Return a copy of the strategy with overrides applied."""
    strat = copy.deepcopy(strat)
    for field, value in overrides.items():
        if field in strat:
            strat[field] = value
    return strat


def build_config(strat: dict, sources: list[dict], overrides: dict) -> dict:
    """Build a full backtest config from a strategy dict."""
    strat = apply_overrides(strat, overrides)

    cfg = copy.deepcopy(_BASE)
    cfg["trading"]["sl_dollars"] = strat.get("sl_dollars", 7.5)
    cfg["trading"]["reward_ratio"] = strat.get("reward_ratio", 1.0)
    cfg["exit_rules"]["breakeven_pct"] = strat.get("breakeven_pct", 0.0)
    cfg["exit_rules"]["partial_tp"] = strat.get("partial_tp", False)
    if "trailing_stop_dollars" in strat:
        cfg["exit_rules"]["trailing_stop_dollars"] = strat["trailing_stop_dollars"]

    cfg["signals"] = {
        "poll_interval": 2.0,
        "csv_dir": "../MetaTrader5-Docker/data/signals",
        "sources": sources,
    }

    rule = {
        "name": strat["name"],
        "enabled": True,
        "priority": strat.get("priority", 50),
        "sl_dollars": strat.get("sl_dollars", 7.5),
        "reward_ratio": strat.get("reward_ratio", 1.0),
        "breakeven_pct": strat.get("breakeven_pct", 0.0),
        "partial_tp": strat.get("partial_tp", False),
        "description": strat.get("description", ""),
    }
    if strat.get("buy"):
        rule["buy"] = strat["buy"]
    if strat.get("sell"):
        rule["sell"] = strat["sell"]
    cfg["rules"] = {"expressions": [rule]}
    return cfg


def run_backtest(
    strat: dict, sources: list[dict], overrides: dict,
    data: Path, balance: float, tmpdir: Path,
) -> tuple[int, float, float, float, float]:
    """Run a single backtest, return (trades, wr, pf, net, dd)."""
    cfg = build_config(strat, sources, overrides)
    cfg_path = tmpdir / f"{strat['name']}.yaml"
    cfg_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))

    r = subprocess.run(
        [sys.executable, "-m", "backtest",
         "--config", str(cfg_path), "--data", str(data),
         "--balance", str(balance)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    out = r.stdout + r.stderr
    pf = float(m.group(1)) if (m := PF_RE.search(out)) else 0
    tr = int(m.group(1)) if (m := TR_RE.search(out)) else 0
    wr = float(m.group(1)) if (m := WR_RE.search(out)) else 0
    bal = m.group(1).replace(",", "") if (m := NT_RE.search(out)) else str(balance)
    net = float(bal) - balance
    dd = float(m.group(1)) if (m := DD_RE.search(out)) else 0

    if tr == 0 and pf == 0:
        for line in (r.stderr or "").split("\n")[-5:]:
            if line.strip():
                print(f"  DBG [{strat['name']}]: {line.strip()}")
    return tr, wr, pf, net, dd


def main():
    parser = argparse.ArgumentParser(
        description="Backtest all strategies from strategies/ folder")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA),
                        help="Path to M1 OHLC CSV")
    parser.add_argument("--balance", type=float, default=10000,
                        help="Starting balance")
    parser.add_argument("--include-disabled", action="store_true",
                        help="Include disabled strategies")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated strategy names to run")

    # Override fields
    parser.add_argument("--sl_dollars", type=float, default=None)
    parser.add_argument("--reward_ratio", type=float, default=None)
    parser.add_argument("--breakeven_pct", type=float, default=None)
    parser.add_argument("--partial_tp", action="store_true", default=None)
    parser.add_argument("--trailing_stop_dollars", type=float, default=None)

    args = parser.parse_args()
    data = Path(args.data)
    only = args.only.split(",") if args.only else None

    # Build overrides dict from CLI args
    overrides = {}
    for field in OVERRIDE_FIELDS:
        val = getattr(args, field)
        if val is not None:
            overrides[field] = val

    strategies = load_strategies(
        include_disabled=args.include_disabled, only=only)

    if not strategies:
        print("No strategies found.")
        sys.exit(1)

    sources = parse_sources(strategies)
    tmpdir = Path("/tmp/run_all_strategies")
    tmpdir.mkdir(exist_ok=True)

    # Header
    override_str = ", ".join(f"{k}={v}" for k, v in overrides.items())
    print(f"\nData: {data}")
    print(f"Strategies: {len(strategies)} from {STRATEGIES_DIR}/")
    if override_str:
        print(f"Overrides: {override_str}")
    print(f"Sources: {', '.join(s['indicator'] for s in sources)}")
    print(f"\n{'=' * 100}")
    print(f"  All Strategies Report")
    print(f"{'=' * 100}")
    print(f"{'#':<3} {'Dir':<6} {'Name':<36} {'SL':>5} {'RR':>4}  "
          f"{'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
    print("-" * 100)

    results = []
    for i, strat in enumerate(strategies, 1):
        s = apply_overrides(strat, overrides)
        sl = s.get("sl_dollars", 7.5)
        rr = s.get("reward_ratio", 1.0)

        has_buy = bool(strat.get("buy"))
        has_sell = bool(strat.get("sell"))
        if has_buy and has_sell:
            direction = "BOTH"
        elif has_buy:
            direction = "BUY"
        else:
            direction = "SELL"

        tr, wr, pf, net, dd = run_backtest(
            strat, sources, overrides, data, args.balance, tmpdir)

        flag = (" ★" if pf >= 1.3 and tr >= 15
                else " ✓" if pf >= 1.1 and tr >= 10
                else "")
        print(f"{i:<3} {direction:<6} {strat['name']:<36} {sl:>5.1f} {rr:>4.1f}  "
              f"{tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
        results.append((strat["name"], direction, sl, rr, tr, wr, pf, net, dd))

    # Summary
    total_trades = sum(r[4] for r in results)
    total_net = sum(r[7] for r in results)
    profitable = sum(1 for r in results if r[7] > 0)
    print("-" * 100)
    print(f"    {'TOTAL':<36} {'':>5} {'':>4}  {total_trades:>6}  "
          f"{'':>5}  {'':>5}  {total_net:>+10.2f}")
    print(f"\n    {profitable}/{len(results)} strategies profitable")

    # Top strategies by PF (min 10 trades)
    ranked = sorted(
        [r for r in results if r[4] >= 10],
        key=lambda r: r[6], reverse=True,
    )
    if ranked:
        print(f"\n    Top by PF (≥10 trades):")
        for r in ranked[:5]:
            print(f"      {r[0]:<36} PF {r[6]:>5.2f}  ({r[4]} trades, {r[7]:>+.2f})")


if __name__ == "__main__":
    main()
