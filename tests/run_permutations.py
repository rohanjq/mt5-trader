"""Run UT Bot M1 BUY permutations with various indicator combos.

Generates test configs, runs backtests, and compares results.
Usage: uv run python tests/run_permutations.py --data sampledata/sample.csv
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import re
import yaml
from pathlib import Path

# ── Base config template (shared across all tests) ─────────────────────────────

BASE_CONFIG = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {
        "symbol": "XAUUSD",
        "volume": 0.25,
        "risk_pct": 5.0,
        "max_volume": 10.0,
        "min_volume": 0.01,
        "magic": 200,
        "deviation": 20,
        "filling": "FOK",
        "multi_position": True,
        "sl_dollars": 5.0,
        "reward_ratio": 1.25,
    },
    "signals": {
        "poll_interval": 2.0,
        "csv_dir": "../MetaTrader5-Docker/data/signals",
        "sources": [
            {"indicator": "utbot", "timeframes": ["M1", "M3", "M5", "M15"]},
            {"indicator": "dc", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "ema9", "timeframes": ["M1"]},
            {"indicator": "ema21", "timeframes": ["M1", "M5"]},
            {"indicator": "ema50", "timeframes": ["M5", "M15"]},
            {"indicator": "ema200", "timeframes": ["M5", "M15"]},
            {"indicator": "rsi14", "timeframes": ["M1", "M5", "M15"]},
            {"indicator": "rsi2", "timeframes": ["M1"]},
            {"indicator": "adx14", "timeframes": ["M1", "M5"]},
            {"indicator": "macd12_26_9", "timeframes": ["M1"]},
            {"indicator": "stoch5_3_3", "timeframes": ["M1"]},
            {"indicator": "bb20d2", "timeframes": ["M1"]},
            {"indicator": "atr14", "timeframes": ["M1", "M5"]},
            {"indicator": "vwap", "timeframes": ["M1", "M5"]},
        ],
    },
    "filters": {
        "cooldown_seconds": 30,
        "max_consecutive_losses": 0,
        "pause_after_consecutive_minutes": 15,
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

# ── UT Bot M1 BUY filter combos to test ────────────────────────────────────────
# Each entry: (name, description, extra_buy_conditions)
# Base condition is always: utbot_M1.closed_signal == BUY
# Sell is disabled (contradictory conditions).

COMBOS = [
    (
        "01_bare",
        "UT Bot M1 signal only — no filters",
        [],
    ),
    (
        "02_current",
        "Current prod: M5+M15 bias + VWAP",
        [
            "utbot_M5.closed_bias == BULLISH",
            "utbot_M15.closed_bias == BULLISH",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "03_ema_trend",
        "EMA200 M5 + EMA50 M5 above",
        [
            "ema200_M5.closed_price_vs_ema == ABOVE",
            "ema50_M5.closed_price_vs_ema == ABOVE",
        ],
    ),
    (
        "04_ema200_vwap",
        "EMA200 M5 above + VWAP above",
        [
            "ema200_M5.closed_price_vs_ema == ABOVE",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "05_rsi_ema21",
        "RSI14 M1 > 50 + EMA21 M5 above",
        [
            "rsi14_M1.closed_rsi > 50",
            "ema21_M5.closed_price_vs_ema == ABOVE",
        ],
    ),
    (
        "06_adx_di",
        "ADX14 M1 trending + DI bullish",
        [
            "adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND",
            "adx14_M1.closed_di_bias == BULLISH",
        ],
    ),
    (
        "07_m5bias_ema200",
        "M5 UT Bot bias + EMA200 M5 above",
        [
            "utbot_M5.closed_bias == BULLISH",
            "ema200_M5.closed_price_vs_ema == ABOVE",
        ],
    ),
    (
        "08_m5bias_rsi",
        "M5 UT Bot bias + RSI14 M5 > 50",
        [
            "utbot_M5.closed_bias == BULLISH",
            "rsi14_M5.closed_rsi > 50",
        ],
    ),
    (
        "09_m15bias_ema50",
        "M15 UT Bot bias + EMA50 M15 above",
        [
            "utbot_M15.closed_bias == BULLISH",
            "ema50_M15.closed_price_vs_ema == ABOVE",
        ],
    ),
    (
        "10_vwap_rsi",
        "VWAP above + RSI14 M1 > 50",
        [
            "vwap_M1.closed_price_vs_vwap == ABOVE",
            "rsi14_M1.closed_rsi > 50",
        ],
    ),
    (
        "11_m5_adx_vwap",
        "M5 bias + ADX trending + VWAP",
        [
            "utbot_M5.closed_bias == BULLISH",
            "adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "12_ema200_adx_vwap",
        "EMA200 M5 + ADX DI bullish + VWAP",
        [
            "ema200_M5.closed_price_vs_ema == ABOVE",
            "adx14_M1.closed_di_bias == BULLISH",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "13_m3_m5",
        "M3 + M5 UT Bot bias (faster alignment)",
        [
            "utbot_M3.closed_bias == BULLISH",
            "utbot_M5.closed_bias == BULLISH",
        ],
    ),
    (
        "14_m5bias_atr",
        "M5 bias + ATR expanding/above",
        [
            "utbot_M5.closed_bias == BULLISH",
            "atr14_M1.volatility_state in EXPANDING,ABOVE_AVG",
        ],
    ),
    (
        "15_m5_ema50slope_vwap",
        "M5 bias + EMA50 M5 rising + VWAP",
        [
            "utbot_M5.closed_bias == BULLISH",
            "ema50_M5.ema_slope == RISING",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "16_m5_m15_ema200",
        "M5+M15 bias + EMA200 M5 (trend stack)",
        [
            "utbot_M5.closed_bias == BULLISH",
            "utbot_M15.closed_bias == BULLISH",
            "ema200_M5.closed_price_vs_ema == ABOVE",
        ],
    ),
    (
        "17_m5_rsi_vwap",
        "M5 bias + RSI14 M1>50 + VWAP",
        [
            "utbot_M5.closed_bias == BULLISH",
            "rsi14_M1.closed_rsi > 50",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "18_ema200_ema50slope_vwap",
        "EMA200 M5 + EMA50 rising + VWAP",
        [
            "ema200_M5.closed_price_vs_ema == ABOVE",
            "ema50_M5.ema_slope == RISING",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "19_adx_vwap",
        "ADX DI bullish + VWAP above",
        [
            "adx14_M1.closed_di_bias == BULLISH",
            "vwap_M1.closed_price_vs_vwap == ABOVE",
        ],
    ),
    (
        "20_m5_adx_di",
        "M5 bias + ADX DI bullish",
        [
            "utbot_M5.closed_bias == BULLISH",
            "adx14_M1.closed_di_bias == BULLISH",
        ],
    ),
]


def make_config(name: str, desc: str, extra_buy: list[str]) -> dict:
    """Build a full config dict with a single BUY-only UT Bot strategy."""
    import copy

    cfg = copy.deepcopy(BASE_CONFIG)

    buy_conditions = ["utbot_M1.closed_signal == BUY"] + extra_buy
    # Sell disabled: contradictory conditions that can never both be true
    sell_conditions = [
        "utbot_M1.closed_signal == BUY",
        "utbot_M1.closed_signal == SELL",
    ]

    cfg["rules"] = {
        "expressions": [
            {
                "name": f"utbot_buy_{name}",
                "enabled": True,
                "priority": 50,
                "sl_dollars": 5.0,
                "reward_ratio": 1.25,
                "breakeven_pct": 0.0,
                "partial_tp": False,
                "description": desc,
                "buy": buy_conditions,
                "sell": sell_conditions,
            }
        ]
    }
    return cfg


def generate_configs(config_dir: Path) -> list[tuple[str, Path]]:
    """Generate all test config YAML files. Returns list of (name, path)."""
    config_dir.mkdir(parents=True, exist_ok=True)
    configs = []
    for name, desc, extra_buy in COMBOS:
        cfg = make_config(name, desc, extra_buy)
        path = config_dir / f"{name}.yaml"
        with open(path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        configs.append((name, path))
    return configs


def run_backtest(config_path: Path, data_path: str, balance: float) -> dict | None:
    """Run a single backtest and parse the summary output."""
    cmd = [
        sys.executable, "-m", "backtest",
        "--config", str(config_path),
        "--data", data_path,
        "--balance", str(balance),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return None

    # Parse key metrics from output
    metrics = {}
    patterns = {
        "trades": r"Total Trades\s+(\d+)",
        "win_rate": r"Win Rate\s+([\d.]+)%",
        "net_profit": r"Net Profit\s+\$([+-]?[\d,.]+)",
        "pf": r"Profit Factor\s+([\d.]+)",
        "max_dd": r"Max Drawdown\s+([\d.]+)%",
        "expectancy": r"Expectancy\s+\$([+-]?[\d,.]+)",
        "wins": r"Wins / Losses / BE\s+(\d+)",
        "losses": r"Wins / Losses / BE\s+\d+ / (\d+)",
        "avg_win": r"Avg Win\s+\$([\d,.]+)",
        "avg_loss": r"Avg Loss\s+\$([\d,.]+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, output)
        if m:
            val = m.group(1).replace(",", "")
            metrics[key] = float(val) if "." in val or "+" in val or "-" in val else int(val)

    if not metrics:
        print(f"  ⚠ Could not parse output for {config_path.name}")
        if result.returncode != 0:
            # Print last few lines of error
            lines = output.strip().split("\n")
            for line in lines[-5:]:
                print(f"    {line}")
        return None

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Run UT Bot BUY permutations")
    parser.add_argument("--data", required=True, help="Path to OHLC CSV")
    parser.add_argument("--balance", type=float, default=10000.0)
    args = parser.parse_args()

    config_dir = Path(__file__).resolve().parent / "configs"
    print(f"Generating {len(COMBOS)} test configs in {config_dir}/\n")
    configs = generate_configs(config_dir)

    # Run all backtests
    results = []
    for name, path in configs:
        desc = next(d for n, d, _ in COMBOS if n == name)
        print(f"Running {name}... ", end="", flush=True)
        metrics = run_backtest(path, args.data, args.balance)
        if metrics:
            metrics["name"] = name
            metrics["desc"] = desc
            results.append(metrics)
            pf = metrics.get("pf", 0)
            wr = metrics.get("win_rate", 0)
            profit = metrics.get("net_profit", 0)
            trades = metrics.get("trades", 0)
            print(f"{trades} trades, WR {wr}%, PF {pf:.2f}, ${profit:+.0f}")
        else:
            print("FAILED")

    if not results:
        print("\nNo results to compare!")
        return

    # Sort by profit factor descending
    results.sort(key=lambda r: r.get("pf", 0), reverse=True)

    # Print comparison table
    print("\n" + "=" * 110)
    print("PERMUTATION RESULTS — UT Bot M1 BUY only (sorted by Profit Factor)")
    print("=" * 110)
    header = f"{'#':<4} {'Name':<28} {'Trades':>6} {'WR%':>6} {'PF':>6} {'Net P&L':>10} {'Exp':>8} {'MaxDD%':>7} {'AvgW':>7} {'AvgL':>7}"
    print(header)
    print("-" * 110)

    for i, r in enumerate(results, 1):
        print(
            f"{i:<4} {r['name']:<28} {r.get('trades', 0):>6} "
            f"{r.get('win_rate', 0):>5.1f}% {r.get('pf', 0):>6.2f} "
            f"${r.get('net_profit', 0):>+9.0f} "
            f"${r.get('expectancy', 0):>+7.1f} "
            f"{r.get('max_dd', 0):>6.1f}% "
            f"${r.get('avg_win', 0):>6.0f} "
            f"${r.get('avg_loss', 0):>6.0f}"
        )

    print("=" * 110)

    # Highlight top 3
    print("\n🏆 TOP 3:")
    for i, r in enumerate(results[:3], 1):
        print(f"  {i}. {r['name']} — PF {r.get('pf', 0):.2f}, "
              f"WR {r.get('win_rate', 0):.1f}%, "
              f"${r.get('net_profit', 0):+.0f}, "
              f"{r.get('trades', 0)} trades, "
              f"DD {r.get('max_dd', 0):.1f}%")
        print(f"     {r['desc']}")


if __name__ == "__main__":
    main()
