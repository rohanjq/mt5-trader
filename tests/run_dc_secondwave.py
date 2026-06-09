"""DC Channel second wave variants — use DC zones to detect pullbacks in trend."""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 300, "deviation": 20, "filling": "FOK",
                "multi_position": True, "sl_dollars": 5.0, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "../MetaTrader5-Docker/data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M1","M2","M3","M5","M10","M15","M30","M45","H1","H4"]},
        {"indicator": "dc", "timeframes": ["M1","M2","M3","M5","M10","M15","M30","M45","H1","H4"]},
        {"indicator": "ema9", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema21", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema50", "timeframes": ["M1","M2","M5","M15","M30","H1"]},
        {"indicator": "ema200", "timeframes": ["M1","M5","M15","H1"]},
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

# ══════════════════════════════════════════════════════════════════════
# DC Second Wave Logic:
#
# SELL: Higher TF bearish → price pulls back UP into DC upper zone
#       (UPPER or UPPER_MID on M15/M5) → M3 SELL signal = second wave
#       DC wick rejection at upper band = extra confirmation
#
# BUY:  Higher TF bullish → price dips DOWN into DC lower zone
#       (LOWER or LOWER_MID) → M3 BUY signal = second wave
#       DC wick rejection at lower band = extra confirmation
# ══════════════════════════════════════════════════════════════════════

COMBOS = []

# ────────────────────────────────────────────
# SELL variants — DC pullback into upper zone
# ────────────────────────────────────────────

# 1. M3 SELL + H1 bearish + DC M15 upper zone (pullback detected)
COMBOS.append(("SELL", "dc2w_m3_h1bear_dcupper",
    "M3 SELL + H1 bearish + DC M15 in UPPER/UPPER_MID",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID"],
    "M3", 7.5))

# 2. M3 SELL + H1 bearish + DC M15 upper zone + VWAP below
COMBOS.append(("SELL", "dc2w_m3_h1bear_dcupper_vwap",
    "M3 SELL + H1 bearish + DC M15 upper + VWAP below",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M3", 7.5))

# 3. M3 SELL + H4 bearish + DC M15 upper zone
COMBOS.append(("SELL", "dc2w_m3_h4bear_dcupper",
    "M3 SELL + H4 bearish + DC M15 in UPPER/UPPER_MID",
    ["utbot_H4.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID"],
    "M3", 7.5))

# 4. M3 SELL + H1 bearish + DC M15 upper wick rejection
COMBOS.append(("SELL", "dc2w_m3_h1bear_wickrej",
    "M3 SELL + H1 bearish + DC M15 upper wick rejection",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_upper_wick_rej is TRUE"],
    "M3", 7.5))

# 5. M3 SELL + H1 bearish + DC M15 upper wick rej + VWAP
COMBOS.append(("SELL", "dc2w_m3_h1bear_wickrej_vwap",
    "M3 SELL + H1 bearish + DC M15 upper wick rej + VWAP",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_upper_wick_rej is TRUE",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M3", 7.5))

# 6. M3 SELL + M15 bearish + DC M5 upper zone (faster DC pullback)
COMBOS.append(("SELL", "dc2w_m3_m15bear_dc5upper",
    "M3 SELL + M15 bearish + DC M5 in UPPER/UPPER_MID",
    ["utbot_M15.closed_bias == BEARISH",
     "dc_M5.closed_price_zone in UPPER,UPPER_MID"],
    "M3", 7.5))

# 7. M3 SELL + M15 bearish + DC M5 upper + VWAP
COMBOS.append(("SELL", "dc2w_m3_m15bear_dc5upper_vwap",
    "M3 SELL + M15 bearish + DC M5 upper + VWAP",
    ["utbot_M15.closed_bias == BEARISH",
     "dc_M5.closed_price_zone in UPPER,UPPER_MID",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M3", 7.5))

# 8. M3 SELL + H1 bearish + DC M5 upper zone
COMBOS.append(("SELL", "dc2w_m3_h1bear_dc5upper",
    "M3 SELL + H1 bearish + DC M5 in UPPER/UPPER_MID",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M5.closed_price_zone in UPPER,UPPER_MID"],
    "M3", 7.5))

# 9. M3 SELL + H1 bearish + DC M5 upper + VWAP
COMBOS.append(("SELL", "dc2w_m3_h1bear_dc5upper_vwap",
    "M3 SELL + H1 bearish + DC M5 upper + VWAP below",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M5.closed_price_zone in UPPER,UPPER_MID",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M3", 7.5))

# 10. M3 SELL + H1 bearish + DC M15 upper + M5 bounce (bull_bars >= 2)
COMBOS.append(("SELL", "dc2w_m3_h1bear_dcupper_bounce",
    "M3 SELL + H1 bearish + DC M15 upper + M5 bounce 2+",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M5.consecutive_bull_bars >= 2"],
    "M3", 7.5))

# 11. M3 SELL + M45 bearish + DC M15 upper zone
COMBOS.append(("SELL", "dc2w_m3_m45bear_dcupper",
    "M3 SELL + M45 bearish + DC M15 in UPPER/UPPER_MID",
    ["utbot_M45.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID"],
    "M3", 7.5))

# 12. M3 SELL + M45 bearish + DC M15 upper + VWAP
COMBOS.append(("SELL", "dc2w_m3_m45bear_dcupper_vwap",
    "M3 SELL + M45 bearish + DC M15 upper + VWAP",
    ["utbot_M45.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    "M3", 7.5))

# 13. M3 SELL + H1 bearish + DC M15 upper + EMA50 M5 below
COMBOS.append(("SELL", "dc2w_m3_h1bear_dcupper_ema50",
    "M3 SELL + H1 bearish + DC M15 upper + EMA50 M5 below",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "ema50_M5.closed_price_vs_ema == BELOW"],
    "M3", 7.5))

# 14. M3 SELL + H1 bearish + DC M15 NOT lower (middle or above = pullback)
COMBOS.append(("SELL", "dc2w_m3_h1bear_dcnotlower",
    "M3 SELL + H1 bearish + DC M15 not in LOWER (mid or above)",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_price_zone not_in LOWER,LOWER_MID"],
    "M3", 7.5))

# 15. M3 SELL + H1 bearish + DC M15 upper wick rej + bounce 2+
COMBOS.append(("SELL", "dc2w_m3_h1bear_wickrej_bounce",
    "M3 SELL + H1 bearish + DC M15 wick rej + M5 bounce 2+",
    ["utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_upper_wick_rej is TRUE",
     "utbot_M5.consecutive_bull_bars >= 2"],
    "M3", 7.5))

# ────────────────────────────────────────────
# BUY variants — DC pullback into lower zone
# ────────────────────────────────────────────

# 16. M3 BUY + H1 bullish + DC M15 lower zone
COMBOS.append(("BUY", "dc2w_m3_h1bull_dclower",
    "M3 BUY + H1 bullish + DC M15 in LOWER/LOWER_MID",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"],
    "M3", 7.5))

# 17. M3 BUY + H1 bullish + DC M15 lower + VWAP
COMBOS.append(("BUY", "dc2w_m3_h1bull_dclower_vwap",
    "M3 BUY + H1 bullish + DC M15 lower + VWAP above",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "vwap_M1.closed_price_vs_vwap == ABOVE"],
    "M3", 7.5))

# 18. M3 BUY + H4 bullish + DC M15 lower zone
COMBOS.append(("BUY", "dc2w_m3_h4bull_dclower",
    "M3 BUY + H4 bullish + DC M15 in LOWER/LOWER_MID",
    ["utbot_H4.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"],
    "M3", 7.5))

# 19. M3 BUY + H1 bullish + DC M15 lower wick rejection
COMBOS.append(("BUY", "dc2w_m3_h1bull_wickrej",
    "M3 BUY + H1 bullish + DC M15 lower wick rej",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_lower_wick_rej is TRUE"],
    "M3", 7.5))

# 20. M3 BUY + H1 bullish + DC M15 lower wick rej + VWAP
COMBOS.append(("BUY", "dc2w_m3_h1bull_wickrej_vwap",
    "M3 BUY + H1 bullish + DC M15 lower wick rej + VWAP",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_lower_wick_rej is TRUE",
     "vwap_M1.closed_price_vs_vwap == ABOVE"],
    "M3", 7.5))

# 21. M3 BUY + H1 bullish + DC M5 lower zone
COMBOS.append(("BUY", "dc2w_m3_h1bull_dc5lower",
    "M3 BUY + H1 bullish + DC M5 in LOWER/LOWER_MID",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M5.closed_price_zone in LOWER,LOWER_MID"],
    "M3", 7.5))

# 22. M3 BUY + H1 bullish + DC M5 lower + VWAP
COMBOS.append(("BUY", "dc2w_m3_h1bull_dc5lower_vwap",
    "M3 BUY + H1 bullish + DC M5 lower + VWAP above",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M5.closed_price_zone in LOWER,LOWER_MID",
     "vwap_M1.closed_price_vs_vwap == ABOVE"],
    "M3", 7.5))

# 23. M3 BUY + M45 bullish + DC M15 lower zone
COMBOS.append(("BUY", "dc2w_m3_m45bull_dclower",
    "M3 BUY + M45 bullish + DC M15 in LOWER/LOWER_MID",
    ["utbot_M45.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"],
    "M3", 7.5))

# 24. M3 BUY + M45 bullish + DC M15 lower + VWAP
COMBOS.append(("BUY", "dc2w_m3_m45bull_dclower_vwap",
    "M3 BUY + M45 bullish + DC M15 lower + VWAP above",
    ["utbot_M45.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "vwap_M1.closed_price_vs_vwap == ABOVE"],
    "M3", 7.5))

# 25. M3 BUY + H1 bullish + DC M15 lower + M5 dip (bear_bars >= 2)
COMBOS.append(("BUY", "dc2w_m3_h1bull_dclower_dip",
    "M3 BUY + H1 bullish + DC M15 lower + M5 dip 2+",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M5.consecutive_bear_bars >= 2"],
    "M3", 7.5))

# 26. M3 BUY + H1 bullish + DC M15 lower + EMA50 above
COMBOS.append(("BUY", "dc2w_m3_h1bull_dclower_ema50",
    "M3 BUY + H1 bullish + DC M15 lower + EMA50 M5 above",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "ema50_M5.closed_price_vs_ema == ABOVE"],
    "M3", 7.5))

# 27. M3 BUY + H1 bullish + DC M15 lower wick rej + M5 dip 2+
COMBOS.append(("BUY", "dc2w_m3_h1bull_wickrej_dip",
    "M3 BUY + H1 bullish + DC M15 wick rej + M5 dip 2+",
    ["utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_lower_wick_rej is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2"],
    "M3", 7.5))


def build_config(direction, name, desc, extra_filters, signal_tf="M3", sl=7.5):
    cfg = copy.deepcopy(BASE)
    cfg["trading"]["sl_dollars"] = sl
    sig_field = f"utbot_{signal_tf}.closed_signal"
    if direction == "BUY":
        buy_expr = [f"{sig_field} == BUY"] + extra_filters
        sell_expr = []
    else:
        buy_expr = []
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
DATA = ROOT / "sampledata" / "XAUUSD_M1_60d.csv"
TMPDIR = Path("/tmp/dc_secondwave_configs")
TMPDIR.mkdir(exist_ok=True)

PF_RE = re.compile(r"Profit Factor\s+([\d.]+|inf)")
TR_RE = re.compile(r"Total Trades\s+(\d+)")
WR_RE = re.compile(r"Win Rate\s+([\d.]+)%")
NT_RE = re.compile(r"Final Balance\s+\$([\d.,+-]+)")
DD_RE = re.compile(r"Max Drawdown\s+([\d.]+)%")


def run_one(direction, name, desc, extra_filters, signal_tf="M3", sl=7.5):
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
print(f"\nData: {DATA}")
print(f"All variants use M3 signal trigger, SL $7.5\n")

for section, label in [("SELL", "DC Second Wave SELL"),
                        ("BUY", "DC Second Wave BUY")]:
    items = [c for c in COMBOS if c[0] == section]
    if not items:
        continue
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}")
    print(f"{'#':<3} {'Name':<42} {'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
    print("-" * 80)
    for i, combo in enumerate(items, 1):
        direction, name, desc, filters = combo[0], combo[1], combo[2], combo[3]
        signal_tf = combo[4] if len(combo) > 4 else "M3"
        sl = combo[5] if len(combo) > 5 else 7.5
        tr, wr, pf, net, dd = run_one(direction, name, desc, filters, signal_tf, sl)
        flag = " ★" if pf >= 1.3 and tr >= 20 else " ✓" if pf >= 1.1 and tr >= 10 else ""
        print(f"{i:<3} {name:<42} {tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
