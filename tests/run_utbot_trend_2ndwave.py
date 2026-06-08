"""gold_utbot_trend second wave variants — test adding bounce filters."""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 300, "deviation": 20, "filling": "FOK",
                "multi_position": True, "sl_dollars": 5.0, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "../MetaTrader5-Docker/data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M1","M2","M3","M5","M10","M15","M30","M45","H1","H4"]},
        {"indicator": "dc", "timeframes": ["M1","M5","M15"]},
        {"indicator": "ema9", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema21", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema50", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema200", "timeframes": ["M1","M5","M15"]},
        {"indicator": "rsi14", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "adx14", "timeframes": ["M1","M5","M15"]},
        {"indicator": "vwap", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "atr14", "timeframes": ["M1","M5","M15"]},
        {"indicator": "stoch5_3_3", "timeframes": ["M1","M5","M15"]},
        {"indicator": "bb20d2", "timeframes": ["M1","M5","M15"]},
        {"indicator": "macd12_26_9", "timeframes": ["M1","M5","M15"]},
    ]},
    "filters": {"cooldown_seconds": 30, "max_consecutive_losses": 0,
                "pause_after_consecutive_minutes": 0, "max_daily_loss": -1,
                "reversal_cooldown_seconds": 30},
    "exit_rules": {"signal_reversal_exit": False, "breakeven_pct": 0.0, "partial_tp": False,
                   "tp_close_pct": 100.0, "trailing_stop_dollars": 0.0},
    "notifications": {"enabled": False},
}

# Original gold_utbot_trend (baseline):
#   BUY: M1 BUY + M5 BULLISH + M15 BULLISH + VWAP above
#   SELL: M1 SELL + M5 BEARISH + M15 BEARISH + VWAP below
# Result: PF 0.95, 159 trades — too many whipsaws
#
# Second wave idea: Instead of requiring M5 bias to align (which means first wave),
# wait for M5 to show a counter-trend bounce, THEN enter on M1 signal = second wave.
# Also test: using M2 signal instead of M1, wider SL, adding EMA filters.

COMBOS = []

# ── SELL variants (where second wave works best) ──

# Variant 1: Original but add M5 bounce (bull bars >= 2) — M15 still bearish
COMBOS.append(("SELL", "trend_2w_m15bear_bounce2",
    "M1 SELL + M15 bearish + M5 bounced 2+ bars + VWAP",
    ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == BELOW"]))

# Variant 2: Same but 3+ bars bounce
COMBOS.append(("SELL", "trend_2w_m15bear_bounce3",
    "M1 SELL + M15 bearish + M5 bounced 3+ bars + VWAP",
    ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 3",
     "vwap_M1.closed_price_vs_vwap == BELOW"]))

# Variant 3: M15 bearish + bounce + no VWAP
COMBOS.append(("SELL", "trend_2w_m15bear_bounce2_novwap",
    "M1 SELL + M15 bearish + M5 bounced 2+ bars (no VWAP)",
    ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 2"]))

# Variant 4: M15 bearish + EMA50 M5 below + bounce
COMBOS.append(("SELL", "trend_2w_m15bear_ema50_bounce2",
    "M1 SELL + M15 bearish + EMA50 M5 below + M5 bounced 2+",
    ["utbot_M15.closed_bias == BEARISH", "ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2"]))

# Variant 5: M15 bearish + EMA50 M5 below + bounce + VWAP
COMBOS.append(("SELL", "trend_2w_m15bear_ema50_bounce2_vwap",
    "M1 SELL + M15 bearish + EMA50 M5 below + bounce 2+ + VWAP",
    ["utbot_M15.closed_bias == BEARISH", "ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2", "vwap_M1.closed_price_vs_vwap == BELOW"]))

# Variant 6: Use M2 signal instead of M1 + M15 bearish + bounce
COMBOS.append(("SELL", "trend_2w_m2_m15bear_bounce2_vwap",
    "M2 SELL + M15 bearish + M5 bounced 2+ + VWAP",
    ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M2"))  # override signal TF

# Variant 7: M2 + M15 bearish + EMA50 + bounce + VWAP
COMBOS.append(("SELL", "trend_2w_m2_ema50_bounce2_vwap",
    "M2 SELL + M15 bearish + EMA50 M5 below + bounce 2+ + VWAP",
    ["utbot_M15.closed_bias == BEARISH", "ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2", "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M2"))

# Variant 8: M1 + M15 bearish + EMA21 below + bounce + VWAP
COMBOS.append(("SELL", "trend_2w_m15bear_ema21_bounce2_vwap",
    "M1 SELL + M15 bearish + EMA21 below + bounce 2+ + VWAP",
    ["utbot_M15.closed_bias == BEARISH", "ema21_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2", "vwap_M1.closed_price_vs_vwap == BELOW"]))

# Variant 9: SL $7.5 instead of $5 — M15 bearish + bounce + VWAP
COMBOS.append(("SELL", "trend_2w_m15bear_bounce2_vwap_sl75",
    "M1 SELL + M15 bearish + bounce 2+ + VWAP (SL $7.5)",
    ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M1", 7.5))

# Variant 10: M2 + SL $7.5 + M15 bearish + bounce + VWAP
COMBOS.append(("SELL", "trend_2w_m2_bounce2_vwap_sl75",
    "M2 SELL + M15 bearish + bounce 2+ + VWAP (SL $7.5)",
    ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M2", 7.5))

# Variant 11: Drop M15 — just EMA50 M5 + bounce + VWAP (simpler)
COMBOS.append(("SELL", "trend_2w_ema50_bounce2_vwap",
    "M1 SELL + EMA50 M5 below + bounce 2+ + VWAP (no M15)",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2", "vwap_M1.closed_price_vs_vwap == BELOW"]))

# Variant 12: M2 + just EMA50 M5 + bounce + VWAP (no M15)
COMBOS.append(("SELL", "trend_2w_m2_ema50_bounce2_vwap_nom15",
    "M2 SELL + EMA50 M5 below + bounce 2+ + VWAP (no M15)",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2", "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M2"))

# ── BUY variants (for completeness, likely won't work well) ──

COMBOS.append(("BUY", "trend_2w_m15bull_dip2_vwap",
    "M1 BUY + M15 bullish + M5 dipped 2+ bars + VWAP",
    ["utbot_M15.closed_bias == BULLISH", "utbot_M5.consecutive_bear_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

COMBOS.append(("BUY", "trend_2w_m15bull_ema50_dip2_vwap",
    "M1 BUY + M15 bullish + EMA50 M5 above + dip 2+ + VWAP",
    ["utbot_M15.closed_bias == BULLISH", "ema50_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2", "vwap_M1.closed_price_vs_vwap == ABOVE"]))

COMBOS.append(("BUY", "trend_2w_m2_m15bull_dip2_vwap",
    "M2 BUY + M15 bullish + M5 dipped 2+ + VWAP",
    ["utbot_M15.closed_bias == BULLISH", "utbot_M5.consecutive_bear_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == ABOVE"],
    "M2"))


def build_config(direction: str, name: str, desc: str, extra_filters: list,
                 signal_tf: str = "M1", sl: float = 5.0):
    cfg = copy.deepcopy(BASE)
    cfg["trading"]["sl_dollars"] = sl
    sig_field = f"utbot_{signal_tf}.closed_signal"
    if direction == "BUY":
        buy_expr = [f"{sig_field} == BUY"] + extra_filters
        sell_expr = ["FALSE"]
    else:
        buy_expr = ["FALSE"]
        sell_expr = [f"{sig_field} == SELL"] + extra_filters
    cfg["rules"] = {"expressions": [{
        "name": name, "enabled": True, "priority": 50,
        "sl_dollars": sl, "reward_ratio": 1.0,
        "breakeven_pct": 0.0, "partial_tp": False,
        "description": desc,
        "buy": buy_expr, "sell": sell_expr,
    }]}
    return cfg


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "sampledata" / "sample.csv"
TMPDIR = Path("/tmp/utbot_trend_2w_configs")
TMPDIR.mkdir(exist_ok=True)

PF_RE = re.compile(r"Profit Factor\s+([\d.]+|inf)")
TR_RE = re.compile(r"Total Trades\s+(\d+)")
WR_RE = re.compile(r"Win Rate\s+([\d.]+)%")
NT_RE = re.compile(r"Final Balance\s+\$([\d.,+-]+)")
DD_RE = re.compile(r"Max Drawdown\s+([\d.]+)%")


def run_one(direction, name, desc, extra_filters, signal_tf="M1", sl=5.0):
    cfg = build_config(direction, name, desc, extra_filters, signal_tf, sl)
    cfg_path = TMPDIR / f"{name}.yaml"
    cfg_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
    r = subprocess.run(
        [sys.executable, "-m", "backtest",
         "--config", str(cfg_path), "--data", str(DATA), "--balance", "10000"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    out = r.stdout + r.stderr
    pf = float(m.group(1)) if (m := PF_RE.search(out)) else 0
    tr = int(m.group(1)) if (m := TR_RE.search(out)) else 0
    wr = float(m.group(1)) if (m := WR_RE.search(out)) else 0
    bal = m.group(1).replace(",", "") if (m := NT_RE.search(out)) else "10000"
    net = float(bal) - 10000
    dd = float(m.group(1)) if (m := DD_RE.search(out)) else 0
    return tr, wr, pf, net, dd


# ── Run ──
for section, label in [("BUY", "gold_utbot_trend BUY — Second Wave"),
                        ("SELL", "gold_utbot_trend SELL — Second Wave")]:
    items = [c for c in COMBOS if c[0] == section]
    if not items:
        continue
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"{'Name':<44} {'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
    print("-" * 70)
    for combo in items:
        direction, name, desc, filters = combo[0], combo[1], combo[2], combo[3]
        signal_tf = combo[4] if len(combo) > 4 else "M1"
        sl = combo[5] if len(combo) > 5 else 5.0
        tr, wr, pf, net, dd = run_one(direction, name, desc, filters, signal_tf, sl)
        print(f"{name:<44} {tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}")
