"""Chart-derived second-wave strategies.

Patterns observed on M5 XAUUSD chart (2026-06-09):
A) EMA50 bounce: price pulls back to EMA50, forms reversal candle, continues
B) DC mid-band pullback: price overshoots, reverts to mid, re-enters trend
C) EMA9/21 cross + pullback: cross fires, price pulls back 2+ bars, candle confirms
D) RSI pullback to neutral: RSI dips from trending to 40-50, bounces
E) EMA50 slope + candle: EMA50 rising/falling = trend, candle at EMA = entry
F) Strong body after pullback: marubozu/strong body after pullback = conviction re-entry
"""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 300, "deviation": 20, "filling": "FOK",
                "multi_position": False, "sl_dollars": 7.5, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "../MetaTrader5-Docker/data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M2", "M3", "M5", "M15", "M45"]},
        {"indicator": "dc", "timeframes": ["M5", "M15"]},
        {"indicator": "candle", "timeframes": ["M3", "M5"]},
        {"indicator": "ema9", "timeframes": ["M5"]},
        {"indicator": "ema21", "timeframes": ["M5"]},
        {"indicator": "ema50", "timeframes": ["M5", "M15"]},
        {"indicator": "vwap", "timeframes": ["M1"]},
        {"indicator": "rsi14", "timeframes": ["M5"]},
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
# A) EMA50 BOUNCE + CANDLE + PULLBACK (2nd wave off dynamic support)
#    Chart: ~12:00 and ~16:00 — price pulled back to EMA50, bounced
# ════════════════════════════════════════════════════════════════

# BUY: Price above EMA50 M5 (structure bullish), M5 pullback, M3 hammer
COMBOS.append(("BUY", "ema50_hammer_2w_m15",
    "M5 above EMA50 + M5 pullback + M3 hammer + M15 bull",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: Price below EMA50 M5, M5 bounce, M3 shooting star
COMBOS.append(("SELL", "ema50_shstar_2w_m15",
    "M5 below EMA50 + M5 bounce + M3 shstar + M15 bear",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# BUY: EMA50 above + pullback + long lower wick
COMBOS.append(("BUY", "ema50_lwick_2w_m15",
    "M5 above EMA50 + M5 pullback + M3 long lower wick + M15 bull",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: EMA50 below + bounce + long upper wick
COMBOS.append(("SELL", "ema50_uwick_2w_m15",
    "M5 below EMA50 + M5 bounce + M3 long upper wick + M15 bear",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# BUY: EMA50 above + pullback + wick ratio 2x
COMBOS.append(("BUY", "ema50_wick2x_2w_m15",
    "M5 above EMA50 + M5 pullback + M3 wick>=2x + M15 bull",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: EMA50 below + bounce + wick ratio 2x
COMBOS.append(("SELL", "ema50_wick2x_2w_m15_s",
    "M5 below EMA50 + M5 bounce + M3 wick>=2x + M15 bear",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ════════════════════════════════════════════════════════════════
# B) DC MID-BAND PULLBACK (price pulls back from extreme to mid)
#    Chart: price shot to DC upper, pulled back to mid, continued
# ════════════════════════════════════════════════════════════════

# BUY: DC M5 at mid after being at lower, M15 bullish, hammer
COMBOS.append(("BUY", "dc_mid_hammer_2w_m15",
    "DC M5 mid zone + M5 pullback + M3 hammer + M15 bull",
    [],
    ["dc_M5.closed_price_zone == MIDDLE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: DC M5 at mid after being at upper, M15 bearish, shstar
COMBOS.append(("SELL", "dc_mid_shstar_2w_m15",
    "DC M5 mid zone + M5 bounce + M3 shstar + M15 bear",
    ["dc_M5.closed_price_zone == MIDDLE",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# BUY: DC M5 lower_mid (pulled back deeper), M15 bull, hammer
COMBOS.append(("BUY", "dc_lowmid_hammer_2w_m15",
    "DC M5 lower_mid + M5 pullback + M3 hammer + M15 bull",
    [],
    ["dc_M5.closed_price_zone in LOWER_MID,MIDDLE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: DC M5 upper_mid (bounced to deeper), M15 bear, shstar
COMBOS.append(("SELL", "dc_upmid_shstar_2w_m15",
    "DC M5 upper_mid + M5 bounce + M3 shstar + M15 bear",
    ["dc_M5.closed_price_zone in UPPER_MID,MIDDLE",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ════════════════════════════════════════════════════════════════
# C) EMA9/21 ALIGNMENT + PULLBACK + CANDLE
#    Chart: EMA9 > EMA21 shown in status panel, price pulled back
# ════════════════════════════════════════════════════════════════

# BUY: EMA9 above, EMA21 above (ribbon bullish), pullback, hammer
COMBOS.append(("BUY", "ema_ribbon_hammer_2w_m15",
    "M5 EMA9>price>EMA21 isn't needed, EMA9+21 above + pullback + hammer + M15",
    [],
    ["ema9_M5.closed_price_vs_ema == ABOVE",
     "ema21_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: EMA9 below, EMA21 below (ribbon bearish), bounce, shstar
COMBOS.append(("SELL", "ema_ribbon_shstar_2w_m15",
    "M5 EMA9+21 below + bounce + shstar + M15 bear",
    ["ema9_M5.closed_price_vs_ema == BELOW",
     "ema21_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# BUY: EMA9+21 above + pullback + wick 2x
COMBOS.append(("BUY", "ema_ribbon_wick2x_2w_m15",
    "M5 EMA9+21 above + pullback + wick>=2x + M15 bull",
    [],
    ["ema9_M5.closed_price_vs_ema == ABOVE",
     "ema21_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: EMA9+21 below + bounce + wick 2x
COMBOS.append(("SELL", "ema_ribbon_wick2x_2w_m15_s",
    "M5 EMA9+21 below + bounce + wick>=2x + M15 bear",
    ["ema9_M5.closed_price_vs_ema == BELOW",
     "ema21_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ════════════════════════════════════════════════════════════════
# D) RSI PULLBACK TO NEUTRAL + CANDLE (momentum reset, then continue)
#    Chart: RSI at 60, was likely higher → pullback to 50 = buy zone
# ════════════════════════════════════════════════════════════════

# BUY: RSI M5 neutral (pulled back from bullish), M5 pullback, hammer, M15 bull
COMBOS.append(("BUY", "rsi_neutral_hammer_2w_m15",
    "RSI M5 neutral + M5 pullback + M3 hammer + M15 bull",
    [],
    ["rsi14_M5.closed_zone == NEUTRAL",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: RSI M5 neutral (pulled back from bearish), M5 bounce, shstar, M15 bear
COMBOS.append(("SELL", "rsi_neutral_shstar_2w_m15",
    "RSI M5 neutral + M5 bounce + M3 shstar + M15 bear",
    ["rsi14_M5.closed_zone == NEUTRAL",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# BUY: RSI M5 neutral + pullback + wick 2x
COMBOS.append(("BUY", "rsi_neutral_wick2x_2w_m15",
    "RSI M5 neutral + M5 pullback + wick>=2x + M15 bull",
    [],
    ["rsi14_M5.closed_zone == NEUTRAL",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: RSI M5 neutral + bounce + wick 2x
COMBOS.append(("SELL", "rsi_neutral_wick2x_2w_m15_s",
    "RSI M5 neutral + M5 bounce + wick>=2x + M15 bear",
    ["rsi14_M5.closed_zone == NEUTRAL",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# ════════════════════════════════════════════════════════════════
# E) EMA50 SLOPE + CANDLE (trending EMA50 = trend confirmation)
#    Chart: EMA50 was clearly rising during bull phase, falling during bear
# ════════════════════════════════════════════════════════════════

# BUY: EMA50 M5 rising + above + pullback + hammer
COMBOS.append(("BUY", "ema50_rising_hammer_2w",
    "EMA50 M5 rising + above + M5 pullback + M3 hammer",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "ema50_M5.ema_slope == RISING",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER"]))

# SELL: EMA50 M5 falling + below + bounce + shstar
COMBOS.append(("SELL", "ema50_falling_shstar_2w",
    "EMA50 M5 falling + below + M5 bounce + M3 shstar",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "ema50_M5.ema_slope == FALLING",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR"],
    []))

# BUY: EMA50 rising + pullback + wick 2x
COMBOS.append(("BUY", "ema50_rising_wick2x_2w",
    "EMA50 M5 rising + above + M5 pullback + wick>=2x",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "ema50_M5.ema_slope == RISING",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE"]))

# SELL: EMA50 falling + bounce + wick 2x
COMBOS.append(("SELL", "ema50_falling_wick2x_2w",
    "EMA50 M5 falling + below + M5 bounce + wick>=2x",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "ema50_M5.ema_slope == FALLING",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE"],
    []))

# ════════════════════════════════════════════════════════════════
# F) STRONG BODY (MARUBOZU) AFTER PULLBACK = CONVICTION RE-ENTRY
#    Chart: after pullbacks, big green/red candles marked continuation
# ════════════════════════════════════════════════════════════════

# BUY: M5 pullback + M3 marubozu bullish + EMA50 above + M15 bull
COMBOS.append(("BUY", "marubozu_ema50_2w_m15",
    "M3 marubozu bull + EMA50 above + M5 pullback + M15 bull",
    [],
    ["candle_M3.closed_candle_type == MARUBOZU",
     "candle_M3.closed_is_bullish is TRUE",
     "ema50_M5.closed_price_vs_ema == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: M5 bounce + M3 marubozu bearish + EMA50 below + M15 bear
COMBOS.append(("SELL", "marubozu_ema50_2w_m15_s",
    "M3 marubozu bear + EMA50 below + M5 bounce + M15 bear",
    ["candle_M3.closed_candle_type == MARUBOZU",
     "candle_M3.closed_is_bearish is TRUE",
     "ema50_M5.closed_price_vs_ema == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# BUY: M5 pullback + M3 body>=60% + EMA50 above + VWAP above
COMBOS.append(("BUY", "strongbody_ema50_vwap_2w",
    "M3 body>=60% bull + EMA50 above + VWAP above + M5 pullback",
    [],
    ["candle_M3.closed_body_pct >= 60",
     "candle_M3.closed_is_bullish is TRUE",
     "ema50_M5.closed_price_vs_ema == ABOVE",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2"]))

# SELL: M5 bounce + M3 body>=60% + EMA50 below + VWAP below
COMBOS.append(("SELL", "strongbody_ema50_vwap_2w_s",
    "M3 body>=60% bear + EMA50 below + VWAP below + M5 bounce",
    ["candle_M3.closed_body_pct >= 60",
     "candle_M3.closed_is_bearish is TRUE",
     "ema50_M5.closed_price_vs_ema == BELOW",
     "vwap_M1.closed_price_vs_vwap == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2"],
    []))

# ════════════════════════════════════════════════════════════════
# G) COMBINED: EMA50 + DC + CANDLE (chart showed EMA50 and DC
#    converging as support/resistance)
# ════════════════════════════════════════════════════════════════

# BUY: EMA50 above + DC M5 lower_mid/mid + pullback + hammer
COMBOS.append(("BUY", "ema50_dc_hammer_2w",
    "EMA50 above + DC M5 lower half + pullback + M3 hammer",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "dc_M5.closed_price_zone in LOWER,LOWER_MID,MIDDLE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER"]))

# SELL: EMA50 below + DC M5 upper_mid/mid + bounce + shstar
COMBOS.append(("SELL", "ema50_dc_shstar_2w",
    "EMA50 below + DC M5 upper half + bounce + M3 shstar",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "dc_M5.closed_price_zone in UPPER,UPPER_MID,MIDDLE",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR"],
    []))

# BUY: EMA50 + DC + wick 2x
COMBOS.append(("BUY", "ema50_dc_wick2x_2w",
    "EMA50 above + DC M5 lower half + pullback + wick>=2x",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "dc_M5.closed_price_zone in LOWER,LOWER_MID,MIDDLE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE"]))

# SELL: EMA50 + DC + wick 2x
COMBOS.append(("SELL", "ema50_dc_wick2x_2w_s",
    "EMA50 below + DC M5 upper half + bounce + wick>=2x",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "dc_M5.closed_price_zone in UPPER,UPPER_MID,MIDDLE",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE"],
    []))

# ════════════════════════════════════════════════════════════════
# H) EMA50 + VWAP DOUBLE CONFIRMATION + PULLBACK
# ════════════════════════════════════════════════════════════════

# BUY: EMA50 above + VWAP above + pullback + hammer + M15 bull
COMBOS.append(("BUY", "ema50_vwap_hammer_2w_m15",
    "EMA50+VWAP above + pullback + hammer + M15 bull",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_candle_type == HAMMER",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: EMA50 below + VWAP below + bounce + shstar + M15 bear
COMBOS.append(("SELL", "ema50_vwap_shstar_2w_m15",
    "EMA50+VWAP below + bounce + shstar + M15 bear",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "vwap_M1.closed_price_vs_vwap == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_candle_type == SHOOTING_STAR",
     "utbot_M15.closed_bias == BEARISH"],
    []))

# BUY: EMA50 + VWAP + pullback + wick 2x + M15 bull
COMBOS.append(("BUY", "ema50_vwap_wick2x_2w_m15",
    "EMA50+VWAP above + pullback + wick>=2x + M15 bull",
    [],
    ["ema50_M5.closed_price_vs_ema == ABOVE",
     "vwap_M1.closed_price_vs_vwap == ABOVE",
     "utbot_M5.consecutive_bear_bars >= 2",
     "candle_M3.closed_lower_wick_ratio >= 2",
     "candle_M3.closed_is_bullish is TRUE",
     "utbot_M15.closed_bias == BULLISH"]))

# SELL: EMA50 + VWAP + bounce + wick 2x + M15 bear
COMBOS.append(("SELL", "ema50_vwap_wick2x_2w_m15_s",
    "EMA50+VWAP below + bounce + wick>=2x + M15 bear",
    ["ema50_M5.closed_price_vs_ema == BELOW",
     "vwap_M1.closed_price_vs_vwap == BELOW",
     "utbot_M5.consecutive_bull_bars >= 2",
     "candle_M3.closed_upper_wick_ratio >= 2",
     "candle_M3.closed_is_bearish is TRUE",
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
TMPDIR = Path("/tmp/chart_2w_configs")
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
print(f"Chart-derived second-wave strategies, SL $7.5, multi_position OFF\n")

print(f"{'='*90}")
print(f"  Chart-Derived Second-Wave Strategies")
print(f"{'='*90}")
print(f"{'#':<3} {'Dir':<5} {'Name':<34} {'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
print("-" * 90)

for i, combo in enumerate(COMBOS, 1):
    direction, name, desc = combo[0], combo[1], combo[2]
    sell_conds, buy_conds = combo[3], combo[4]
    tr, wr, pf, net, dd = run_one(name, desc, sell_conds, buy_conds)
    flag = " ★" if pf >= 1.3 and tr >= 15 else " ✓" if pf >= 1.1 and tr >= 10 else ""
    print(f"{i:<3} {direction:<5} {name:<34} {tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
