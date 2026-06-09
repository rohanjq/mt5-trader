"""BUY second-wave candle strategies.

Key concept: Higher TF bullish bias + M5 pullback (consecutive_bear_bars >= 2)
+ M3/M5 bullish candle pattern fires the entry.
Mirror of working SELL 2nd-wave strategies.
"""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 300, "deviation": 20, "filling": "FOK",
                "multi_position": False, "sl_dollars": 7.5, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M2", "M3", "M5", "M15", "M45"]},
        {"indicator": "dc", "timeframes": ["M15"]},
        {"indicator": "candle", "timeframes": ["M3", "M5"]},
        {"indicator": "ema50", "timeframes": ["M5"]},
        {"indicator": "vwap", "timeframes": ["M1"]},
        {"indicator": "rsi14", "timeframes": ["M5"]},
        {"indicator": "stoch5_3_3", "timeframes": ["M5"]},
    ]},
    "filters": {"cooldown_seconds": 30, "max_consecutive_losses": 0,
                "pause_after_consecutive_minutes": 0, "max_daily_loss": -1,
                "reversal_cooldown_seconds": 30},
    "exit_rules": {"signal_reversal_exit": False, "breakeven_pct": 0.0, "partial_tp": False,
                   "tp_close_pct": 100.0, "trailing_stop_dollars": 0.0},
    "notifications": {"enabled": False},
}

COMBOS = []

# ════════════════════════════════════════════════════════════════
# A) HAMMER + 2ND WAVE PULLBACK
# ════════════════════════════════════════════════════════════════

# 1. Hammer M3 + M5 pullback + M15 bull
COMBOS.append(("BUY", "hammer_2w_m15",
    "M3 hammer + M5 pullback 2+ bars + M15 bullish",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 2. Hammer M3 + M5 pullback + M45 bull
COMBOS.append(("BUY", "hammer_2w_m45",
    "M3 hammer + M5 pullback 2+ bars + M45 bullish",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M45.closed_bias == BULLISH"]))

# 3. Hammer M3 + M5 pullback + M15 bull + VWAP
COMBOS.append(("BUY", "hammer_2w_m15_vwap",
    "M3 hammer + M5 pullback + M15 bull + VWAP above",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 4. Hammer M3 + M5 pullback + M15 bull + DC lower
COMBOS.append(("BUY", "hammer_2w_m15_dc",
    "M3 hammer + M5 pullback + M15 bull + DC lower",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"]))

# ════════════════════════════════════════════════════════════════
# B) LONG LOWER WICK + 2ND WAVE
# ════════════════════════════════════════════════════════════════

# 5. Long lower wick M3 + M5 pullback + M15 bull
COMBOS.append(("BUY", "lwick_2w_m15",
    "M3 long lower wick + bullish + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 6. Long lower wick M3 + M5 pullback + M45 bull
COMBOS.append(("BUY", "lwick_2w_m45",
    "M3 long lower wick + bullish + M5 pullback + M45 bull",
    [],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M45.closed_bias == BULLISH"]))

# 7. Long lower wick M3 + M5 pullback + M15 bull + VWAP
COMBOS.append(("BUY", "lwick_2w_m15_vwap",
    "M3 long lower wick + M5 pullback + M15 bull + VWAP",
    [],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 8. Long lower wick M3 + M5 pullback + M15 bull + DC lower
COMBOS.append(("BUY", "lwick_2w_m15_dc",
    "M3 long lower wick + M5 pullback + M15 bull + DC lower",
    [],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"]))

# ════════════════════════════════════════════════════════════════
# C) WICK RATIO >= 2 + 2ND WAVE
# ════════════════════════════════════════════════════════════════

# 9. Wick 2x M3 + M5 pullback + M15 bull
COMBOS.append(("BUY", "wick2x_2w_m15",
    "M3 lower_wick>=2x + bullish + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 10. Wick 2x M3 + M5 pullback + M45 bull
COMBOS.append(("BUY", "wick2x_2w_m45",
    "M3 lower_wick>=2x + bullish + M5 pullback + M45 bull",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M45.closed_bias == BULLISH"]))

# 11. Wick 2x M3 + M5 pullback + M15 bull + VWAP
COMBOS.append(("BUY", "wick2x_2w_m15_vwap",
    "M3 wick>=2x + M5 pullback + M15 bull + VWAP above",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 12. Wick 2x M3 + M5 pullback + M15 bull + DC lower
COMBOS.append(("BUY", "wick2x_2w_m15_dc",
    "M3 wick>=2x + M5 pullback + M15 bull + DC lower",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"]))

# ════════════════════════════════════════════════════════════════
# D) M5 CANDLE + 2ND WAVE (slower candle, less noise)
# ════════════════════════════════════════════════════════════════

# 13. Hammer M5 + M5 pullback + M15 bull
COMBOS.append(("BUY", "hammer_m5_2w_m15",
    "M5 hammer + M5 pullback 2+ bars + M15 bull",
    [],
    ["candle_M5.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 14. Hammer M5 + M5 pullback + M15 bull + VWAP
COMBOS.append(("BUY", "hammer_m5_2w_m15_vwap",
    "M5 hammer + M5 pullback + M15 bull + VWAP",
    [],
    ["candle_M5.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# ════════════════════════════════════════════════════════════════
# E) DOJI / SPINNING TOP AT DC EXTREME + 2ND WAVE
# ════════════════════════════════════════════════════════════════

# 15. Doji M3 + M5 pullback + M15 bull + DC lower
COMBOS.append(("BUY", "doji_2w_m15_dc",
    "M3 doji + M5 pullback + M15 bull + DC lower",
    [],
    ["candle_M3.closed_candle_type == DOJI",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"]))

# 16. SpinTop M3 + M5 pullback + M15 bull + DC lower
COMBOS.append(("BUY", "spintop_2w_m15_dc",
    "M3 spinning top + M5 pullback + M15 bull + DC lower",
    [],
    ["candle_M3.closed_candle_type == SPINNING_TOP",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"]))

# ════════════════════════════════════════════════════════════════
# F) UT BOT SIGNAL + CANDLE + 2ND WAVE (double confirmation)
# ════════════════════════════════════════════════════════════════

# 17. M3 UT Buy + Hammer M3 + M5 pullback + M15 bull
COMBOS.append(("BUY", "ut_hammer_2w_m15",
    "M3 UT buy signal + M3 hammer + M5 pullback + M15 bull",
    [],
    ["utbot_M3.closed_signal == BUY",
     "candle_M3.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 18. M3 UT Buy + wick 2x M3 + M5 pullback + M15 bull
COMBOS.append(("BUY", "ut_wick2x_2w_m15",
    "M3 UT buy + wick>=2x + M5 pullback + M15 bull",
    [],
    ["utbot_M3.closed_signal == BUY",
     "candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# ════════════════════════════════════════════════════════════════
# G) DEEPER PULLBACK (3+ bars) + CANDLE
# ════════════════════════════════════════════════════════════════

# 19. Hammer M3 + M5 deep pullback 3+ bars + M15 bull
COMBOS.append(("BUY", "hammer_deep_2w_m15",
    "M3 hammer + M5 deep pullback 3+ bars + M15 bull",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "utbot_M5.consecutive_bear_bars >= 3",
     "utbot_M15.closed_bias == BULLISH"]))

# 20. Wick 2x M3 + M5 deep pullback 3+ bars + M15 bull
COMBOS.append(("BUY", "wick2x_deep_2w_m15",
    "M3 wick>=2x + M5 deep pullback 3+ bars + M15 bull",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 3",
     "utbot_M15.closed_bias == BULLISH"]))

# ════════════════════════════════════════════════════════════════
# H) RSI/STOCH OVERSOLD + CANDLE + 2ND WAVE
# ════════════════════════════════════════════════════════════════

# 21. Hammer M3 + RSI oversold M5 + M5 pullback + M15 bull
COMBOS.append(("BUY", "hammer_rsi_2w_m15",
    "M3 hammer + RSI M5 oversold + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "rsi14_M5.closed_zone in OVERSOLD,EXTREME_OS",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 22. Wick 2x M3 + RSI oversold M5 + M5 pullback + M15 bull
COMBOS.append(("BUY", "wick2x_rsi_2w_m15",
    "M3 wick>=2x + RSI M5 oversold + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "rsi14_M5.closed_zone in OVERSOLD,EXTREME_OS",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 23. Hammer M3 + stoch oversold M5 + M5 pullback + M15 bull
COMBOS.append(("BUY", "hammer_stoch_2w_m15",
    "M3 hammer + stoch M5 oversold + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "stoch5_3_3_M5.closed_zone == OVERSOLD",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# 24. Wick 2x M3 + stoch oversold M5 + M5 pullback + M15 bull
COMBOS.append(("BUY", "wick2x_stoch_2w_m15",
    "M3 wick>=2x + stoch M5 oversold + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "stoch5_3_3_M5.closed_zone == OVERSOLD",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# ════════════════════════════════════════════════════════════════
# I) M2 UT BUY SIGNAL + 2ND WAVE (mirror of working sell strategy)
# ════════════════════════════════════════════════════════════════

# 25. M2 UT Buy + M5 pullback + EMA50 above + VWAP (exact mirror of strategy 5)
COMBOS.append(("BUY", "ut_m2_2w_ema50_vwap",
    "M2 UT buy + EMA50 M5 above + M5 pullback + VWAP",
    [],
    ["utbot_M2.closed_signal == BUY",
     "ema50_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 26. M2 UT Buy + M15 bull + M5 pullback + VWAP (exact mirror of strategy 6)
COMBOS.append(("BUY", "ut_m2_2w_m15_vwap",
    "M2 UT buy + M15 bull + M5 pullback + VWAP",
    [],
    ["utbot_M2.closed_signal == BUY",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_M5.consecutive_bear_bars >= 2",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# ════════════════════════════════════════════════════════════════
# J) MAX CONFLUENCE: candle + DC + M45 + VWAP + 2nd wave
# ════════════════════════════════════════════════════════════════

# 27. Wick 2x + DC lower + M45 bull + VWAP + M5 pullback
COMBOS.append(("BUY", "wick2x_dc_m45_vwap_2w",
    "M3 wick>=2x + DC lower + M45 bull + VWAP + M5 pullback",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M45.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2"]))

# 28. Hammer M3 + DC lower + M45 bull + M5 pullback
COMBOS.append(("BUY", "hammer_dc_m45_2w",
    "M3 hammer + DC lower + M45 bull + M5 pullback",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M45.closed_bias == BULLISH",
     "utbot_M5.consecutive_bear_bars >= 2"]))


def build_config(name, desc, sell_conds, buy_conds, sl=7.5):
    cfg = copy.deepcopy(BASE)
    cfg["trading"]["sl_dollars"] = sl
    rule = {"name": name, "enabled": True, "priority": 50,
            "sl_dollars": sl, "reward_ratio": 1.0,
            "breakeven_pct": 0.0, "partial_tp": False, "description": desc}
    if buy_conds:
        rule["buy"] = buy_conds
    if sell_conds:
        rule["sell"] = sell_conds
    cfg["rules"] = {"expressions": [rule]}
    return cfg


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "sampledata" / "XAUUSD_M1_60d.csv"
TMPDIR = Path("/tmp/buy_2w_configs")
TMPDIR.mkdir(exist_ok=True)

PF_RE = re.compile(r"Profit Factor\s+([\d.]+|inf)")
TR_RE = re.compile(r"Total Trades\s+(\d+)")
WR_RE = re.compile(r"Win Rate\s+([\d.]+)%")
NT_RE = re.compile(r"Final Balance\s+\$([\d.,+-]+)")
DD_RE = re.compile(r"Max Drawdown\s+([\d.]+)%")


def run_one(name, desc, sell_conds, buy_conds, sl=7.5):
    cfg = build_config(name, desc, sell_conds, buy_conds, sl)
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
    if tr == 0 and pf == 0:
        for line in (r.stderr or "").split("\n")[-5:]:
            if line.strip():
                print(f"  DBG: {line.strip()}")
    return tr, wr, pf, net, dd


# ── Run ──
print(f"\nData: {DATA}")
print(f"BUY 2nd-wave candle strategies, SL $7.5, multi_position OFF\n")

print(f"{'='*90}")
print(f"  BUY Second-Wave Candle Strategies")
print(f"{'='*90}")
print(f"{'#':<3} {'Dir':<5} {'Name':<34} {'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
print("-" * 90)

for i, combo in enumerate(COMBOS, 1):
    direction, name, desc = combo[0], combo[1], combo[2]
    sell_conds, buy_conds = combo[3], combo[4]
    tr, wr, pf, net, dd = run_one(name, desc, sell_conds, buy_conds)
    flag = " ★" if pf >= 1.3 and tr >= 15 else " ✓" if pf >= 1.1 and tr >= 10 else ""
    print(f"{i:<3} {direction:<5} {name:<34} {tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
