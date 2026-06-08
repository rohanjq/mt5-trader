"""Run UT Bot M1 SELL permutations with 2/3/4-condition combos.

Generates temporary configs, runs backtests, and writes a ranked markdown report.
Usage:
  UV_CACHE_DIR=/tmp/uv-cache uv run python tests/run_utbot_sell_permutations.py \
    --data sampledata/sample.csv
"""
from __future__ import annotations

import argparse
import copy
import itertools
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class FilterOption:
    key: str
    description: str
    condition: str


BASE_CONFIG = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {
        "symbol": "XAUUSD",
        "volume": 0.25,
        "risk_pct": 5.0,
        "max_volume": 10.0,
        "min_volume": 0.01,
        "magic": 290,
        "deviation": 20,
        "filling": "FOK",
        "multi_position": True,
        "sl_dollars": 5.0,
        "reward_ratio": 1.0,
    },
    "signals": {
        "poll_interval": 2.0,
        "csv_dir": "../MetaTrader5-Docker/data/signals",
        "sources": [
            {"indicator": "utbot", "timeframes": ["M1", "M3", "M5", "M15", "M45", "H1"]},
            {"indicator": "dc", "timeframes": ["M1", "M5", "M15", "M45", "H1"]},
            {"indicator": "ema9", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "ema21", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "ema50", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "ema200", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "rsi14", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "rsi2", "timeframes": ["M1", "M5"]},
            {"indicator": "adx14", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "macd12_26_9", "timeframes": ["M1", "M5"]},
            {"indicator": "stoch5_3_3", "timeframes": ["M1", "M5"]},
            {"indicator": "bb20d2", "timeframes": ["M1", "M5"]},
            {"indicator": "atr14", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "vwap", "timeframes": ["M1", "M5", "M15"]},
        ],
    },
    "filters": {
        "cooldown_seconds": 30,
        "max_consecutive_losses": 0,
        "pause_after_consecutive_minutes": 0,
        "max_daily_loss": -1,
        "reversal_cooldown_seconds": 30,
    },
    "exit_rules": {
        "signal_reversal_exit": False,
        "breakeven_pct": 0.0,
        "partial_tp": False,
        "tp_close_pct": 100.0,
        "trailing_stop_dollars": 0.0,
    },
    "notifications": {"enabled": False},
}


SELL_FILTERS: list[FilterOption] = [
    FilterOption("m5_bias", "UTBot M5 bearish bias", "utbot_M5.closed_bias == BEARISH"),
    FilterOption("m15_bias", "UTBot M15 bearish bias", "utbot_M15.closed_bias == BEARISH"),
    FilterOption("vwap_below", "Price below VWAP M1", "vwap_M1.closed_price_vs_vwap == BELOW"),
    FilterOption("ema9_below", "Price below EMA9 M1", "ema9_M1.closed_price_vs_ema == BELOW"),
    FilterOption("ema21_below", "Price below EMA21 M1", "ema21_M1.closed_price_vs_ema == BELOW"),
    FilterOption("ema50_m5", "Price below EMA50 M5", "ema50_M5.closed_price_vs_ema == BELOW"),
    FilterOption("ema200_m5", "Price below EMA200 M5", "ema200_M5.closed_price_vs_ema == BELOW"),
    FilterOption("rsi14_lt50", "RSI14 M1 below 50", "rsi14_M1.closed_rsi < 50"),
    FilterOption("rsi14_lt45", "RSI14 M1 below 45", "rsi14_M1.closed_rsi < 45"),
    FilterOption("rsi2_lt20", "RSI2 M1 oversold impulse", "rsi2_M1.closed_rsi <= 20"),
    FilterOption("macd_flip_bear", "MACD bearish histogram flip", "macd12_26_9_M1.closed_hist_cross == BEARISH_FLIP"),
    FilterOption("stoch_cross_dn", "Stoch bearish cross", "stoch5_3_3_M1.closed_cross in BEARISH,BEARISH_OB"),
    FilterOption("bb_reenter_above", "BB re-enter from above", "bb20d2_M1.closed_reenter_from_above is TRUE"),
    FilterOption("dc_lower", "Donchian lower zone", "dc_M1.closed_price_zone in LOWER,LOWER_MID"),
    FilterOption("dc_break_below", "Donchian lower wick rejection", "dc_M1.closed_lower_wick_rej is TRUE"),
    FilterOption("atr_expand", "ATR expanding/above avg", "atr14_M1.volatility_state in EXPANDING,ABOVE_AVG"),
    FilterOption("adx_trending", "ADX trending", "adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND"),
    FilterOption("adx_di_bear", "DI bearish", "adx14_M1.closed_di_bias == BEARISH"),
]

SL_VALUES = [4.0, 5.0, 6.0, 7.5]
REWARD_RATIO = 1.0


def build_candidates() -> list[dict]:
    candidates: list[dict] = []
    idx = 1
    base = "utbot_M1.closed_signal == SELL"

    for size in (2, 3, 4):
        for combo in itertools.combinations(SELL_FILTERS, size - 1):
            for sl in SL_VALUES:
                key = "_".join(c.key for c in combo)
                name = f"sell_{idx:04d}_{size}c_{key}_sl{str(sl).replace('.', 'p')}"
                conditions = [base, *[c.condition for c in combo]]
                desc = f"SELL UTBot M1 + {', '.join(c.description for c in combo)}"
                candidates.append({
                    "name": name,
                    "description": desc,
                    "sell": conditions,
                    "sl_dollars": float(sl),
                    "reward_ratio": REWARD_RATIO,
                    "condition_count": size,
                    "combo_keys": [c.key for c in combo],
                })
                idx += 1
    return candidates


def write_config(path: Path, candidate: dict) -> None:
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["rules"] = {
        "expressions": [
            {
                "name": candidate["name"],
                "enabled": True,
                "priority": 50,
                "sl_dollars": candidate["sl_dollars"],
                "reward_ratio": candidate["reward_ratio"],
                "breakeven_pct": 0.0,
                "partial_tp": False,
                "description": candidate["description"],
                "buy": ["utbot_M1.closed_signal == BUY", "utbot_M1.closed_signal == SELL"],
                "sell": candidate["sell"],
            }
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def run_backtest(config_path: Path, data_path: str, balance: float) -> dict | None:
    cmd = [
        sys.executable, "-m", "backtest",
        "--config", str(config_path),
        "--data", data_path,
        "--balance", str(balance),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(Path(__file__).resolve().parent.parent),
            env={**os.environ, "UV_CACHE_DIR": "/tmp/uv-cache"},
        )
    except subprocess.TimeoutExpired:
        return None

    output = (result.stdout or "") + "\n" + (result.stderr or "")
    patterns = {
        "trades": r"Total Trades\s+(\d+)",
        "win_rate": r"Win Rate\s+([\d.]+)%",
        "net_profit": r"Net Profit\s+\$([+-]?[\d,.]+)",
        "pf": r"Profit Factor\s+([\d.]+)",
        "max_dd": r"Max Drawdown\s+([\d.]+)%",
        "expectancy": r"Expectancy\s+\$([+-]?[\d,.]+)",
    }
    metrics: dict[str, float | int] = {}
    for key, pat in patterns.items():
        m = re.search(pat, output)
        if not m:
            continue
        val = m.group(1).replace(",", "")
        metrics[key] = float(val) if ("." in val or "+" in val or "-" in val) else int(val)

    if not metrics:
        return None
    return metrics


def write_report(path: Path, results: list[dict], total: int, failed: int) -> None:
    lines: list[str] = []
    lines.append("# UTBot SELL Permutation Report")
    lines.append("")
    lines.append(f"- Total candidates: **{total}**")
    lines.append(f"- Successful runs: **{len(results)}**")
    lines.append(f"- Failed runs: **{failed}**")
    lines.append("")

    if not results:
        lines.append("No successful backtest results.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    lines.append("## Top 30 by Net Profit")
    lines.append("")
    lines.append("| Rank | Name | Conds | SL$ | Trades | Win% | PF | Net P&L | MaxDD% |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for i, r in enumerate(results[:30], 1):
        lines.append(
            f"| {i} | {r['name']} | {r['condition_count']} | {r['sl_dollars']:.1f} | "
            f"{int(r.get('trades', 0))} | {float(r.get('win_rate', 0)):.1f} | {float(r.get('pf', 0)):.2f} | "
            f"{float(r.get('net_profit', 0)):+.2f} | {float(r.get('max_dd', 0)):.1f} |"
        )

    lines.append("")
    lines.append("## Best by Condition Count")
    lines.append("")
    for cond_count in (2, 3, 4):
        subset = [r for r in results if r["condition_count"] == cond_count]
        if not subset:
            continue
        best = subset[0]
        lines.append(f"- **{cond_count} conditions**: `{best['name']}` | Net {best['net_profit']:+.2f} | PF {best['pf']:.2f} | Win {best['win_rate']:.1f}%")
        lines.append(f"  - Filters: {', '.join(best['combo_keys'])}")

    lines.append("")
    lines.append("## Full Results")
    lines.append("")
    lines.append("| Name | Conds | SL$ | Trades | Win% | PF | Net P&L | MaxDD% |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in results:
        lines.append(
            f"| {r['name']} | {r['condition_count']} | {r['sl_dollars']:.1f} | {int(r.get('trades', 0))} | "
            f"{float(r.get('win_rate', 0)):.1f} | {float(r.get('pf', 0)):.2f} | {float(r.get('net_profit', 0)):+.2f} | {float(r.get('max_dd', 0)):.1f} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UTBot SELL permutations")
    parser.add_argument("--data", required=True, help="Path to OHLC CSV")
    parser.add_argument("--balance", type=float, default=10000.0)
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on candidates for quick runs")
    args = parser.parse_args()

    candidates = build_candidates()
    if args.limit > 0:
        candidates = candidates[:args.limit]

    cfg_dir = Path(__file__).resolve().parent / "sell_configs"
    report_path = Path(__file__).resolve().parent / "reports" / "utbot_sell_permutation_report.md"
    live_log = Path(__file__).resolve().parent / "reports" / "sell_live_results.csv"

    print(f"Generating {len(candidates)} SELL candidates...")
    cfg_dir.mkdir(parents=True, exist_ok=True)
    live_log.parent.mkdir(parents=True, exist_ok=True)
    for old in cfg_dir.glob("*.yaml"):
        old.unlink()

    for c in candidates:
        write_config(cfg_dir / f"{c['name']}.yaml", c)

    # Write live CSV header — tail -f this file to watch progress
    with open(live_log, "w", encoding="utf-8") as f:
        f.write("idx,name,conds,sl,trades,win_rate,pf,net_profit,max_dd,expectancy,status\n")

    print(f"Running backtests... (tail -f {live_log})")
    results: list[dict] = []
    failed = 0
    for i, candidate in enumerate(candidates, 1):
        cfg_path = cfg_dir / f"{candidate['name']}.yaml"
        metrics = run_backtest(cfg_path, args.data, args.balance)

        # Write every result immediately to live log
        with open(live_log, "a", encoding="utf-8") as f:
            if metrics is None:
                failed += 1
                f.write(f"{i},{candidate['name']},{candidate['condition_count']},{candidate['sl_dollars']},,,,,,,FAIL\n")
            else:
                row = {**candidate, **metrics}
                results.append(row)
                f.write(
                    f"{i},{row['name']},{row['condition_count']},{row['sl_dollars']},"
                    f"{int(row.get('trades', 0))},{float(row.get('win_rate', 0)):.1f},"
                    f"{float(row.get('pf', 0)):.2f},{float(row.get('net_profit', 0)):+.2f},"
                    f"{float(row.get('max_dd', 0)):.1f},{float(row.get('expectancy', 0)):+.2f},OK\n"
                )

        if i % 25 == 0 or i == len(candidates):
            print(f"  {i}/{len(candidates)} done | ok={len(results)} fail={failed}")

    results.sort(key=lambda r: (float(r.get("net_profit", -1e9)), float(r.get("pf", 0))), reverse=True)
    write_report(report_path, results, len(candidates), failed)

    print(f"Done. Report: {report_path}")
    print(f"Live log: {live_log}")
    if results:
        top = results[0]
        print(
            "Best:",
            top["name"],
            f"Net={float(top['net_profit']):+.2f}",
            f"PF={float(top['pf']):.2f}",
            f"Win={float(top['win_rate']):.1f}%",
            f"Trades={int(top['trades'])}",
        )


if __name__ == "__main__":
    main()
