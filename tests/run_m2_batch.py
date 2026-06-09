"""Quick M2 UT Bot BUY + SELL permutation batch."""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 290, "deviation": 20, "filling": "FOK",
                "multi_position": True, "sl_dollars": 7.5, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M1","M2","M3","M5","M10","M15","M45","H1"]},
        {"indicator": "dc", "timeframes": ["M1","M5","M15"]},
        {"indicator": "ema9", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema21", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema50", "timeframes": ["M1","M5","M15"]},
        {"indicator": "ema200", "timeframes": ["M1","M5","M15"]},
        {"indicator": "rsi14", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "rsi2", "timeframes": ["M1","M2","M5"]},
        {"indicator": "adx14", "timeframes": ["M1","M5","M15"]},
        {"indicator": "vwap", "timeframes": ["M1","M5","M15"]},
        {"indicator": "atr14", "timeframes": ["M1","M5","M15"]},
    ]},
    "filters": {"cooldown_seconds": 30, "max_consecutive_losses": 0,
                "pause_after_consecutive_minutes": 0, "max_daily_loss": -1,
                "reversal_cooldown_seconds": 30},
    "exit_rules": {"signal_reversal_exit": False, "breakeven_pct": 0.0, "partial_tp": False,
                   "tp_close_pct": 100.0, "trailing_stop_dollars": 0.0},
    "notifications": {"enabled": False},
}

# direction: "BUY" or "SELL"
# For BUY: filters use ABOVE/BULLISH/> etc
# For SELL: filters use BELOW/BEARISH/< etc
FILTER_SETS = {
    "BUY": [
        ("m2buy_bare",            []),
        ("m2buy_vwap",            ["vwap_M1.closed_price_vs_vwap == ABOVE"]),
        ("m2buy_ema9",            ["ema9_M1.closed_price_vs_ema == ABOVE"]),
        ("m2buy_ema21",           ["ema21_M1.closed_price_vs_ema == ABOVE"]),
        ("m2buy_m5bias",          ["utbot_M5.closed_bias == BULLISH"]),
        ("m2buy_m15bias",         ["utbot_M15.closed_bias == BULLISH"]),
        ("m2buy_m5_m15",          ["utbot_M5.closed_bias == BULLISH", "utbot_M15.closed_bias == BULLISH"]),
        ("m2buy_vwap_m15",        ["vwap_M1.closed_price_vs_vwap == ABOVE", "utbot_M15.closed_bias == BULLISH"]),
        ("m2buy_vwap_m5",         ["vwap_M1.closed_price_vs_vwap == ABOVE", "utbot_M5.closed_bias == BULLISH"]),
        ("m2buy_vwap_ema9",       ["vwap_M1.closed_price_vs_vwap == ABOVE", "ema9_M1.closed_price_vs_ema == ABOVE"]),
        ("m2buy_vwap_ema21",      ["vwap_M1.closed_price_vs_vwap == ABOVE", "ema21_M1.closed_price_vs_ema == ABOVE"]),
        ("m2buy_ema9_m15",        ["ema9_M1.closed_price_vs_ema == ABOVE", "utbot_M15.closed_bias == BULLISH"]),
        ("m2buy_ema9_m5",         ["ema9_M1.closed_price_vs_ema == ABOVE", "utbot_M5.closed_bias == BULLISH"]),
        ("m2buy_vwap_m5_m15",     ["vwap_M1.closed_price_vs_vwap == ABOVE", "utbot_M5.closed_bias == BULLISH", "utbot_M15.closed_bias == BULLISH"]),
        ("m2buy_ema9_m5_m15",     ["ema9_M1.closed_price_vs_ema == ABOVE", "utbot_M5.closed_bias == BULLISH", "utbot_M15.closed_bias == BULLISH"]),
        ("m2buy_vwap_ema9_m15",   ["vwap_M1.closed_price_vs_vwap == ABOVE", "ema9_M1.closed_price_vs_ema == ABOVE", "utbot_M15.closed_bias == BULLISH"]),
        ("m2buy_rsi14_gt50",      ["rsi14_M1.closed_rsi > 50"]),
        ("m2buy_vwap_rsi",        ["vwap_M1.closed_price_vs_vwap == ABOVE", "rsi14_M1.closed_rsi > 50"]),
        ("m2buy_ema50_m5",        ["ema50_M5.closed_price_vs_ema == ABOVE"]),
        ("m2buy_vwap_ema50m5",    ["vwap_M1.closed_price_vs_vwap == ABOVE", "ema50_M5.closed_price_vs_ema == ABOVE"]),
    ],
    "SELL": [
        ("m2sell_bare",           []),
        ("m2sell_vwap",           ["vwap_M1.closed_price_vs_vwap == BELOW"]),
        ("m2sell_ema9",           ["ema9_M1.closed_price_vs_ema == BELOW"]),
        ("m2sell_ema21",          ["ema21_M1.closed_price_vs_ema == BELOW"]),
        ("m2sell_m5bias",         ["utbot_M5.closed_bias == BEARISH"]),
        ("m2sell_m15bias",        ["utbot_M15.closed_bias == BEARISH"]),
        ("m2sell_m5_m15",         ["utbot_M5.closed_bias == BEARISH", "utbot_M15.closed_bias == BEARISH"]),
        ("m2sell_vwap_m15",       ["vwap_M1.closed_price_vs_vwap == BELOW", "utbot_M15.closed_bias == BEARISH"]),
        ("m2sell_vwap_m5",        ["vwap_M1.closed_price_vs_vwap == BELOW", "utbot_M5.closed_bias == BEARISH"]),
        ("m2sell_vwap_ema9",      ["vwap_M1.closed_price_vs_vwap == BELOW", "ema9_M1.closed_price_vs_ema == BELOW"]),
        ("m2sell_vwap_ema21",     ["vwap_M1.closed_price_vs_vwap == BELOW", "ema21_M1.closed_price_vs_ema == BELOW"]),
        ("m2sell_ema9_m15",       ["ema9_M1.closed_price_vs_ema == BELOW", "utbot_M15.closed_bias == BEARISH"]),
        ("m2sell_ema9_m5",        ["ema9_M1.closed_price_vs_ema == BELOW", "utbot_M5.closed_bias == BEARISH"]),
        ("m2sell_vwap_m5_m15",    ["vwap_M1.closed_price_vs_vwap == BELOW", "utbot_M5.closed_bias == BEARISH", "utbot_M15.closed_bias == BEARISH"]),
        ("m2sell_ema9_m5_m15",    ["ema9_M1.closed_price_vs_ema == BELOW", "utbot_M5.closed_bias == BEARISH", "utbot_M15.closed_bias == BEARISH"]),
        ("m2sell_vwap_ema9_m15",  ["vwap_M1.closed_price_vs_vwap == BELOW", "ema9_M1.closed_price_vs_ema == BELOW", "utbot_M15.closed_bias == BEARISH"]),
        ("m2sell_rsi14_lt50",     ["rsi14_M1.closed_rsi < 50"]),
        ("m2sell_vwap_rsi",       ["vwap_M1.closed_price_vs_vwap == BELOW", "rsi14_M1.closed_rsi < 50"]),
        ("m2sell_ema50_m5",       ["ema50_M5.closed_price_vs_ema == BELOW"]),
        ("m2sell_vwap_ema50m5",   ["vwap_M1.closed_price_vs_vwap == BELOW", "ema50_M5.closed_price_vs_ema == BELOW"]),
    ],
}

tmpdir = Path("/tmp/m2_batch_configs")
tmpdir.mkdir(exist_ok=True)
cwd = Path(__file__).resolve().parent.parent

for direction, combos in FILTER_SETS.items():
    sig = "BUY" if direction == "BUY" else "SELL"
    anti = "SELL" if direction == "BUY" else "BUY"

    print(f"\n{'='*65}")
    print(f"  M2 UT Bot {direction} — SL $7.5, RR 1:1")
    print(f"{'='*65}")
    print(f"{'Name':<25} {'Trades':>6} {'WR%':>6} {'PF':>6} {'Net':>10} {'DD%':>6}")
    print("-" * 65)

    for name, filters in combos:
        cfg = copy.deepcopy(BASE)
        active_conds = [f"utbot_M2.closed_signal == {sig}"] + filters
        dead_conds = [f"utbot_M2.closed_signal == BUY", f"utbot_M2.closed_signal == SELL"]

        if direction == "BUY":
            buy_conds, sell_conds = active_conds, dead_conds
        else:
            buy_conds, sell_conds = dead_conds, active_conds

        cfg["rules"] = {"expressions": [{
            "name": name, "enabled": True, "priority": 50,
            "sl_dollars": 7.5, "reward_ratio": 1.0,
            "breakeven_pct": 0.0, "partial_tp": False,
            "description": name,
            "buy": buy_conds, "sell": sell_conds,
        }]}

        p = tmpdir / f"{name}.yaml"
        p.write_text(yaml.safe_dump(cfg, sort_keys=False))

        try:
            r = subprocess.run(
                [sys.executable, "-m", "backtest", "--config", str(p),
                 "--data", "sampledata/sample.csv", "--balance", "10000"],
                capture_output=True, text=True, timeout=60, cwd=str(cwd),
            )
            out = (r.stdout or "") + "\n" + (r.stderr or "")
        except Exception:
            print(f"{name:<25} {'TIMEOUT':>6}")
            continue

        def grab(pat):
            m = re.search(pat, out)
            return m.group(1).replace(",", "") if m else ""

        t = grab(r"Total Trades\s+(\d+)")
        wr = grab(r"Win Rate\s+([\d.]+)%")
        pf = grab(r"Profit Factor\s+([\d.]+)")
        net = grab(r"Net Profit\s+\$([+-]?[\d,.]+)")
        dd = grab(r"Max Drawdown\s+([\d.]+)%")

        if t:
            print(f"{name:<25} {t:>6} {wr:>6} {pf:>6} {net:>10} {dd:>6}")
        else:
            print(f"{name:<25} {'0':>6} {'--':>6} {'--':>6} {'--':>10} {'--':>6}")
