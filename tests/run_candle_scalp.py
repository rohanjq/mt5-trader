"""Candle + DC + UT Bot scalping strategy variants.

Uses candle patterns (hammer, shooting star, marubozu, wick ratios)
combined with DC channel zones and UT Bot trend bias for entries.
Tests BUY and SELL independently.
"""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 300, "deviation": 20, "filling": "FOK",
                "multi_position": False, "sl_dollars": 7.5, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "../MetaTrader5-Docker/data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M3","M5","M15","M45"]},
        {"indicator": "dc", "timeframes": ["M15"]},
        {"indicator": "candle", "timeframes": ["M3","M5"]},
        {"indicator": "ema50", "timeframes": ["M5"]},
        {"indicator": "vwap", "timeframes": ["M1"]},
    ]},
    "filters": {"cooldown_seconds": 30, "max_consecutive_losses": 0,
                "pause_after_consecutive_minutes": 0, "max_daily_loss": -1,
                "reversal_cooldown_seconds": 30},
    "exit_rules": {"signal_reversal_exit": False, "breakeven_pct": 0.0, "partial_tp": False,
                   "tp_close_pct": 100.0, "trailing_stop_dollars": 0.0},
    "notifications": {"enabled": False},
}

# ══════════════════════════════════════════════════════════════════════
# Strategy concepts:
#
# A) CANDLE PATTERN AT DC EXTREME
#    Hammer at DC lower band + M15 bullish bias → buy the rejection
#    Shooting star at DC upper band + M15 bearish bias → sell
#
# B) STRONG CANDLE WITH TREND (Marubozu)
#    Marubozu/big-body in trend direction after counter-move
#
# C) WICK RATIO SCALP
#    Long wick (ratio >= 2) against trend → reversal entry
#
# D) CANDLE TYPE + VWAP + BIAS
#    Pattern + VWAP confluence + higher TF alignment
# ══════════════════════════════════════════════════════════════════════

COMBOS = []

# ────────────────────────────────────────────────────────────────
# 1. Hammer at DC M15 Lower + M15 Bullish
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "hammer_dc_lower_m15",
    "M3 hammer at DC lower + M15 bullish",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M15.closed_bias == BULLISH"]))

# 2. Same but M5 candle
COMBOS.append(("BUY", "hammer_dc_lower_m15_m5c",
    "M5 hammer at DC lower + M15 bullish",
    [],
    ["candle_M5.closed_candle_type == HAMMER",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M15.closed_bias == BULLISH"]))

# 3. Shooting Star at DC M15 Upper + M15 Bearish
COMBOS.append(("SELL", "shstar_dc_upper_m15",
    "M3 shooting star at DC upper + M15 bearish",
    ["candle_M3.closed_candle_type == SHOOTING_STAR",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# 4. Same but M5 candle
COMBOS.append(("SELL", "shstar_dc_upper_m15_m5c",
    "M5 shooting star at DC upper + M15 bearish",
    ["candle_M5.closed_candle_type == SHOOTING_STAR",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 5-6. Long wick rejection at DC band + M15 bias (more flexible than candle_type)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "longwick_dc_lower_m15",
    "M3 long lower wick + DC lower + M15 bullish",
    [],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_is_bullish is TRUE",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "longwick_dc_upper_m15",
    "M3 long upper wick + DC upper + M15 bearish",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_is_bearish is TRUE",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 7-8. Marubozu with trend after pullback
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "marubozu_bounce_m15",
    "M3 bullish marubozu + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_candle_type == MARUBOZU",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "marubozu_bounce_m15_s",
    "M3 bearish marubozu + M5 pullback + M15 bear",
    ["candle_M3.closed_candle_type == MARUBOZU",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M5.consecutive_bull_bars >= 2",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 9-10. Strong body candle (body >= 60%) + M15 bias + VWAP
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "strongbody_vwap_m15",
    "M3 bullish body>=60% + VWAP above + M15 bull",
    [],
    ["candle_M3.closed_body_pct >= 60",
     "candle_M3.closed_is_bullish is TRUE",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "strongbody_vwap_m15_s",
    "M3 bearish body>=60% + VWAP below + M15 bear",
    ["candle_M3.closed_body_pct >= 60",
     "candle_M3.closed_is_bearish is TRUE",
     "vwap_M1.closed_price_vs_vwap == BELOW",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 11-12. Hammer/ShStar + M15 bias + VWAP (no DC filter → more trades)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "hammer_vwap_m15",
    "M3 hammer + VWAP above + M15 bullish",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "shstar_vwap_m15",
    "M3 shooting star + VWAP below + M15 bearish",
    ["candle_M3.closed_candle_type == SHOOTING_STAR",
     "vwap_M1.closed_price_vs_vwap == BELOW",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 13-14. Doji at DC extreme + M15 bias (indecision → trend continues)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "doji_dc_lower_m15",
    "M3 doji at DC lower + M15 bullish",
    [],
    ["candle_M3.closed_candle_type == DOJI",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "doji_dc_upper_m15",
    "M3 doji at DC upper + M15 bearish",
    ["candle_M3.closed_candle_type == DOJI",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 15-16. Long wick ratio >=2 + M15 bias only (simplest, most trades)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "wick2x_m15_buy",
    "M3 lower_wick_ratio>=2 + bullish + M15 bull",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "wick2x_m15_sell",
    "M3 upper_wick_ratio>=2 + bearish + M15 bear",
    ["candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 17-18. Wick 2x + M15 bias + VWAP
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "wick2x_vwap_m15_buy",
    "M3 lower_wick>=2x + bullish + VWAP above + M15",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "wick2x_vwap_m15_sell",
    "M3 upper_wick>=2x + bearish + VWAP below + M15",
    ["candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "vwap_M1.closed_price_vs_vwap == BELOW",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 19-20. Wick 2x + DC zone + M15 bias (triple filter)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "wick2x_dc_m15_buy",
    "M3 wick>=2x + DC lower + M15 bullish",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "wick2x_dc_m15_sell",
    "M3 wick>=2x + DC upper + M15 bearish",
    ["candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 21-22. Marubozu + M15 bias + VWAP (strong trending candle)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "marubozu_vwap_m15_buy",
    "M3 marubozu bullish + VWAP above + M15 bull",
    [],
    ["candle_M3.closed_candle_type == MARUBOZU",
     "candle_M3.closed_is_bullish is TRUE",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "marubozu_vwap_m15_sell",
    "M3 marubozu bearish + VWAP below + M15 bear",
    ["candle_M3.closed_candle_type == MARUBOZU",
     "candle_M3.closed_is_bearish is TRUE",
     "vwap_M1.closed_price_vs_vwap == BELOW",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 23-24. Hammer/ShStar at DC + M15 + EMA50 alignment
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "hammer_dc_ema50_m15",
    "M3 hammer + DC lower + EMA50 above + M15 bull",
    [],
    ["candle_M3.closed_candle_type == HAMMER",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "ema50_M5.closed_price_vs_ema == ABOVE",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "shstar_dc_ema50_m15",
    "M3 shstar + DC upper + EMA50 below + M15 bear",
    ["candle_M3.closed_candle_type == SHOOTING_STAR",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 25-26. Strong body (>=70%) with M3 UT Bot signal + M15 bias
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "strongbody70_ut_m15_buy",
    "M3 body>=70% + M3 UT buy signal + M15 bull",
    [],
    ["candle_M3.closed_body_pct >= 70",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M3.closed_signal == BUY",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "strongbody70_ut_m15_sell",
    "M3 body>=70% + M3 UT sell signal + M15 bear",
    ["candle_M3.closed_body_pct >= 70",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M3.closed_signal == SELL",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 27-28. Hammer/ShStar on M5 + M15 bias (slower candle, less noise)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "hammer_m5_m15",
    "M5 hammer + M15 bullish",
    [],
    ["candle_M5.closed_candle_type == HAMMER",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "shstar_m5_m15",
    "M5 shooting star + M15 bearish",
    ["candle_M5.closed_candle_type == SHOOTING_STAR",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 29-30. SpinTop at DC edge → reversal (indecision at extreme)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "spintop_dc_lower_m15",
    "M3 spinning top at DC lower + M15 bullish",
    [],
    ["candle_M3.closed_candle_type == SPINNING_TOP",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "spintop_dc_upper_m15",
    "M3 spinning top at DC upper + M15 bearish",
    ["candle_M3.closed_candle_type == SPINNING_TOP",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 31-32. Wick rejection + M45 bias (slower trend filter)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "wick2x_m45_buy",
    "M3 lower_wick>=2x + bullish + M45 bullish",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M45.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "wick2x_m45_sell",
    "M3 upper_wick>=2x + bearish + M45 bearish",
    ["candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M45.closed_bias == BEARISH"],
    []))

# ────────────────────────────────────────────────────────────────
# 33-34. Wick2x + DC + M45 + VWAP (maximum confluence)
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "wick2x_dc_m45_vwap_buy",
    "M3 wick>=2x + DC lower + M45 bull + VWAP",
    [],
    ["candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID",
     "utbot_M45.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

COMBOS.append(("SELL", "wick2x_dc_m45_vwap_sell",
    "M3 wick>=2x + DC upper + M45 bear + VWAP",
    ["candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID",
     "utbot_M45.closed_bias == BEARISH",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    []))

# ────────────────────────────────────────────────────────────────
# 35-36. M5 body >= 60% bullish + M3 UT buy signal + M15 trend
# ────────────────────────────────────────────────────────────────
COMBOS.append(("BUY", "m5body_m3ut_m15_buy",
    "M5 body>=60% bull + M3 UT buy + M15 bull",
    [],
    ["candle_M5.closed_body_pct >= 60",
     "candle_M5.closed_is_bullish is TRUE",
     "utbot_M3.closed_signal == BUY",
     "utbot_M15.closed_bias == BULLISH"]))

COMBOS.append(("SELL", "m5body_m3ut_m15_sell",
    "M5 body>=60% bear + M3 UT sell + M15 bear",
    ["candle_M5.closed_body_pct >= 60",
     "candle_M5.closed_is_bearish is TRUE",
     "utbot_M3.closed_signal == SELL",
     "utbot_M15.closed_bias == BEARISH"],
    []))


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
TMPDIR = Path("/tmp/candle_scalp_configs")
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
print(f"Candle + DC + UT Bot scalping strategies, SL $7.5, multi_position OFF\n")

print(f"{'='*90}")
print(f"  Candle Scalping Strategies — BUY and SELL")
print(f"{'='*90}")
print(f"{'#':<3} {'Dir':<5} {'Name':<34} {'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
print("-" * 90)

for i, combo in enumerate(COMBOS, 1):
    direction, name, desc = combo[0], combo[1], combo[2]
    sell_conds, buy_conds = combo[3], combo[4]
    tr, wr, pf, net, dd = run_one(name, desc, sell_conds, buy_conds)
    flag = " ★" if pf >= 1.3 and tr >= 15 else " ✓" if pf >= 1.1 and tr >= 10 else ""
    print(f"{i:<3} {direction:<5} {name:<34} {tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
