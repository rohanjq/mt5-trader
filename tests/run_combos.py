#!/usr/bin/env python3
"""Run strategy files from a folder with extra filters and SL/RR combos.

Loops through all strategy YAML files in a folder (default: strategies/buy/).
For each strategy, ANDs the extra --filter conditions onto the buy expressions,
then runs all combinations of --sl and --rr values.

Usage:
    # Run all buy strategies with default SL=7.5 and RR=1.0:
    uv run python tests/run_combos.py

    # Try multiple SL and RR combos:
    uv run python tests/run_combos.py --sl 5,7.5,10 --rr 1.0,1.5,2.0

    # Add extra filters (ANDed to every strategy):
    uv run python tests/run_combos.py \\
        --filter "utbot_M15.closed_bias == BULLISH" \\
        --filter "utbot_M5.consecutive_bear_bars >= 2"

    # Combine everything:
    uv run python tests/run_combos.py \\
        --sl 5,7.5 --rr 1.0,1.5 \\
        --filter "dc_M15.closed_price_zone in LOWER,LOWER_MID" \\
        --filter "vwap_M1.closed_price_vs_vwap == ABOVE"

    # Run specific strategies only:
    uv run python tests/run_combos.py --only utbot_m2_buy,candle_m5_hammer

    # Use a different folder:
    uv run python tests/run_combos.py --dir strategies/sell

    # Set breakeven:
    uv run python tests/run_combos.py --breakeven_pct 0.5

    # Run expressions directly from CLI (no files needed):
    uv run python tests/run_combos.py \\
        --expr "macd12_26_9_M15.closed_hist_cross == BULLISH_FLIP" \\
        --expr "ema50_M15.ema_slope == RISING"
"""
from __future__ import annotations

import argparse
import copy
import fnmatch
import re
import subprocess
import sys
import yaml
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
        "breakeven_pct": 0.0,
        "partial_tp": False, "tp_close_pct": 100.0,
        "trailing_stop_dollars": 0.0,
    },
    "notifications": {"enabled": False},
}

COND_RE = re.compile(r"^(\w+?)_(M\d+|H\d+|D1)\.")
PF_RE = re.compile(r"Profit Factor\s+([\d.]+|inf)")
TR_RE = re.compile(r"Total Trades\s+(\d+)")
WR_RE = re.compile(r"Win Rate\s+([\d.]+)%")
NT_RE = re.compile(r"Final Balance\s+\$([\d.,+-]+)")
DD_RE = re.compile(r"Max Drawdown\s+([\d.]+)%")


def _tf_sort_key(tf: str) -> int:
    units = {"M": 1, "H": 60, "D": 1440}
    return units.get(tf[0], 0) * int(tf[1:])


def parse_sources(conditions: list[str]) -> list[dict]:
    indicator_tfs: dict[str, set[str]] = {}
    for cond in conditions:
        m = COND_RE.match(cond)
        if m:
            indicator_tfs.setdefault(m.group(1), set()).add(m.group(2))
    return [
        {"indicator": ind, "timeframes": sorted(tfs, key=_tf_sort_key)}
        for ind, tfs in sorted(indicator_tfs.items())
    ]


def load_strategies(strat_dir: Path, only: list[str] | None = None) -> list[dict]:
    strategies = []
    for f in sorted(strat_dir.glob("*.yaml")):
        strat = yaml.safe_load(f.read_text())
        if only and not any(fnmatch.fnmatch(strat["name"], pat) for pat in only):
            continue
        strategies.append(strat)
    return strategies


def run_backtest(
    name: str, buy_conds: list[str], sl: float, rr: float,
    sources: list[dict], data: Path, balance: float,
    breakeven_pct: float, trailing_stop: float, multi: bool, tmpdir: Path,
) -> tuple[int, float, float, float, float]:
    cfg = copy.deepcopy(_BASE)
    cfg["trading"]["sl_dollars"] = sl
    cfg["trading"]["reward_ratio"] = rr
    cfg["trading"]["multi_position"] = multi
    cfg["exit_rules"]["breakeven_pct"] = breakeven_pct
    cfg["exit_rules"]["trailing_stop_dollars"] = trailing_stop
    cfg["signals"] = {
        "poll_interval": 2.0,
        "csv_dir": "data/signals",
        "sources": sources,
    }
    rule = {
        "name": name, "enabled": True, "priority": 50,
        "sl_dollars": sl, "reward_ratio": rr,
        "breakeven_pct": breakeven_pct, "partial_tp": False,
        "description": name,
    }
    if buy_conds:
        rule["buy"] = buy_conds
    cfg["rules"] = {"expressions": [rule]}

    cfg_path = tmpdir / f"{name}_sl{sl}_rr{rr}.yaml"
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
                print(f"  DBG [{name}]: {line.strip()}")
    return tr, wr, pf, net, dd


def main():
    parser = argparse.ArgumentParser(
        description="Run strategy combos with extra filters and SL/RR grid")
    parser.add_argument("--dir", type=str, default=str(ROOT / "strategies" / "buy"),
                        help="Directory with strategy YAML files")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA))
    parser.add_argument("--balance", type=float, default=10000)
    parser.add_argument("--sl", type=str, default="7.5",
                        help="Comma-separated SL values (e.g. 5,7.5,10)")
    parser.add_argument("--rr", type=str, default="1.0",
                        help="Comma-separated reward ratios (e.g. 1.0,1.5,2.0)")
    parser.add_argument("--filter", action="append", default=[],
                        help="Extra condition ANDed to all strategies (repeatable)")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated strategy names to run")
    parser.add_argument("--expr", action="append", default=[],
                        help="Buy expression to test directly (repeatable, each is a separate strategy)")
    parser.add_argument("--breakeven_pct", type=float, default=0.0)
    parser.add_argument("--trailing", type=float, default=0.0,
                        help="Trailing stop distance in dollars (0 = off)")
    parser.add_argument("--multi", action="store_true", default=False,
                        help="Allow multiple positions at same time")

    args = parser.parse_args()
    strat_dir = Path(args.dir)
    data = Path(args.data)
    sl_values = [float(x) for x in args.sl.split(",")]
    rr_values = [float(x) for x in args.rr.split(",")]
    only = args.only.split(",") if args.only else None
    extra_filters = args.filter

    # Build strategy list: from --expr flags or from files
    if args.expr:
        strategies = []
        for expr in args.expr:
            # Auto-name from expression: "ema50_M15.ema_slope == RISING" -> "ema50_M15_ema_slope_RISING"
            name = expr.replace(".", "_").replace(" ", "_")
            for ch in ">=<!":
                name = name.replace(ch, "")
            name = name.replace("__", "_").strip("_")
            strategies.append({"name": name, "description": expr, "buy": [expr]})
    else:
        strategies = load_strategies(strat_dir, only=only)
    if not strategies:
        print(f"No strategies found in {strat_dir}")
        sys.exit(1)

    # Collect all conditions for source detection
    all_conds = []
    for strat in strategies:
        all_conds.extend(strat.get("buy", []))
    all_conds.extend(extra_filters)
    sources = parse_sources(all_conds)

    tmpdir = Path("/tmp/run_combos")
    tmpdir.mkdir(exist_ok=True)

    # Count total runs
    total_runs = len(strategies) * len(sl_values) * len(rr_values)

    # Header
    filter_str = " AND ".join(extra_filters) if extra_filters else "none"
    print(f"\nData: {data}")
    if args.expr:
        print(f"Strategies: {len(strategies)} from --expr")
    else:
        print(f"Strategies: {len(strategies)} from {strat_dir}/")
    print(f"SL values: {sl_values}")
    print(f"RR values: {rr_values}")
    print(f"Extra filters: {filter_str}")
    print(f"Breakeven: {args.breakeven_pct}%")
    if args.trailing > 0:
        print(f"Trailing stop: ${args.trailing}")
    if args.multi:
        print(f"Multi-position: ON")
    print(f"Total runs: {total_runs}")
    print(f"Sources: {', '.join(s['indicator'] for s in sources)}")
    print(f"\n{'=' * 110}")
    print(f"  Combo Results")
    print(f"{'=' * 110}")
    print(f"{'#':<4} {'Name':<34} {'SL':>5} {'RR':>4}  "
          f"{'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
    print("-" * 110)

    results = []
    run_num = 0
    for strat in strategies:
        base_conds = strat.get("buy", [])
        combined = base_conds + extra_filters

        for sl, rr in product(sl_values, rr_values):
            run_num += 1
            name = strat["name"]
            tr, wr, pf, net, dd = run_backtest(
                name, combined, sl, rr, sources, data,
                args.balance, args.breakeven_pct, args.trailing, args.multi, tmpdir,
            )
            flag = (" ★" if pf >= 1.3 and tr >= 15
                    else " ✓" if pf >= 1.1 and tr >= 10
                    else "")
            print(f"{run_num:<4} {name:<34} {sl:>5.1f} {rr:>4.1f}  "
                  f"{tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
            results.append((name, sl, rr, tr, wr, pf, net, dd))

    # Summary
    print("-" * 110)
    total_net = sum(r[6] for r in results)
    profitable = sum(1 for r in results if r[6] > 0)
    print(f"\n    {profitable}/{len(results)} combos profitable, total net: {total_net:+.2f}")


if __name__ == "__main__":
    main()
