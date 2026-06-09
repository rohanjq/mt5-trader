"""Candle wick rejection strategy variants — wick at opposite side of trend."""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 300, "deviation": 20, "filling": "FOK",
                "multi_position": False, "sl_dollars": 7.5, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "../MetaTrader5-Docker/data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M1","M2","M3","M5","M10","M15","M30","M45","H1","H4"]},
        {"indicator": "dc", "timeframes": ["M1","M2","M3","M5","M10","M15","M30","M45","H1","H4"]},
        {"indicator": "candle", "timeframes": ["M1","M2","M3","M5"]},
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
# Wick Rejection Strategy Logic:
#
# BUY:  M15 bullish + H1 bullish → M3 candle closed with lower wick
#       (price dipped down, got rejected, closed up = buyers stepped in)
#
# SELL: M15 bearish + H1 bearish → M3 candle closed with upper wick
#       (price spiked up, got rejected, closed down = sellers stepped in)
# ══════════════════════════════════════════════════════════════════════

COMBOS = []

# ────────────────────────────────────────────
# SELL variants — upper wick in downtrend
# ────────────────────────────────────────────

# 1. M3 upper wick + M3 closed DOWN + M15 bearish + H1 bearish
COMBOS.append(("BOTH", "wick_m3_m15h1",
    "M3 wick + M3 dir + M15 + H1 aligned",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH"]))

# 2. Same but add VWAP
COMBOS.append(("BOTH", "wick_m3_m15h1_vwap",
    "M3 wick + dir + M15 + H1 + VWAP",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 3. Without candle direction check (just wick + trend)
COMBOS.append(("BOTH", "wick_m3_m15h1_nodir",
    "M3 wick only + M15 + H1 (no dir check)",
    ["candle_M3.closed_has_long_upper is TRUE",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH"]))

# 4. M3 wick + M15 + M45 (instead of H1)
COMBOS.append(("BOTH", "wick_m3_m15m45",
    "M3 wick + dir + M15 + M45 aligned",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_M45.closed_bias == BEARISH"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_M45.closed_bias == BULLISH"]))

# 5. M3 wick + M15 + M45 + VWAP
COMBOS.append(("BOTH", "wick_m3_m15m45_vwap",
    "M3 wick + dir + M15 + M45 + VWAP",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_M45.closed_bias == BEARISH",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_M45.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 6. M3 wick + H1 only (simpler — no M15)
COMBOS.append(("BOTH", "wick_m3_h1only",
    "M3 wick + dir + H1 only",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_H1.closed_bias == BEARISH"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_H1.closed_bias == BULLISH"]))

# 7. M3 wick + H1 + VWAP
COMBOS.append(("BOTH", "wick_m3_h1_vwap",
    "M3 wick + dir + H1 + VWAP",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_H1.closed_bias == BEARISH",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_H1.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 8. M3 wick + H4 only (very slow trend)
COMBOS.append(("BOTH", "wick_m3_h4only",
    "M3 wick + dir + H4 only",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_H4.closed_bias == BEARISH"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_H4.closed_bias == BULLISH"]))

# 9. M3 wick + M15 + H1 + EMA50 M5 alignment
COMBOS.append(("BOTH", "wick_m3_m15h1_ema50",
    "M3 wick + dir + M15 + H1 + EMA50 M5",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH",
     "ema50_M5.closed_price_vs_ema == BELOW"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH",
     "ema50_M5.closed_price_vs_ema == ABOVE"]))

# 10. M3 wick + M15 + H1 + fresh M15 bias (≤10 bars)
COMBOS.append(("BOTH", "wick_m3_m15h1_fresh",
    "M3 wick + dir + M15 + H1 + fresh M15 ≤10",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_M15.consecutive_bear_bars <= 10",
     "utbot_H1.closed_bias == BEARISH"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_M15.consecutive_bull_bars <= 10",
     "utbot_H1.closed_bias == BULLISH"]))

# 11. M3 wick + M15 + H1 + M5 bounce (second wave wick)
COMBOS.append(("BOTH", "wick_m3_m15h1_bounce",
    "M3 wick + dir + M15 + H1 + M5 counter 2+",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH",
     "utbot_M5.consecutive_bull_bars >= 2"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH",
     "utbot_M5.consecutive_bear_bars >= 2"]))

# 12. M3 wick + M15 + H1 + DC M15 zone (wick at channel edge)
COMBOS.append(("BOTH", "wick_m3_m15h1_dczone",
    "M3 wick + dir + M15 + H1 + DC M15 upper/lower",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH",
     "dc_M15.closed_price_zone in UPPER,UPPER_MID"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH",
     "dc_M15.closed_price_zone in LOWER,LOWER_MID"]))

# 13. M5 wick instead of M3 (slower candle)
COMBOS.append(("BOTH", "wick_m5_m15h1",
    "M5 wick + dir + M15 + H1",
    ["candle_M5.closed_has_long_upper is TRUE",
     "candle_M5.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH"],
    ["candle_M5.closed_has_long_lower is TRUE",
     "candle_M5.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH"]))

# 14. M5 wick + M15 + H1 + VWAP
COMBOS.append(("BOTH", "wick_m5_m15h1_vwap",
    "M5 wick + dir + M15 + H1 + VWAP",
    ["candle_M5.closed_has_long_upper is TRUE",
     "candle_M5.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "utbot_H1.closed_bias == BEARISH",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    ["candle_M5.closed_has_long_lower is TRUE",
     "candle_M5.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "utbot_H1.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))

# 15. M3 wick + M15 only (simplest — no H1)
COMBOS.append(("BOTH", "wick_m3_m15only",
    "M3 wick + dir + M15 only",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH"]))

# 16. M3 wick + M15 + VWAP (no H1)
COMBOS.append(("BOTH", "wick_m3_m15_vwap",
    "M3 wick + dir + M15 + VWAP",
    ["candle_M3.closed_has_long_upper is TRUE",
     "candle_M3.closed_candle_dir == DOWN",
     "utbot_M15.closed_bias == BEARISH",
     "vwap_M1.closed_price_vs_vwap == BELOW"],
    ["candle_M3.closed_has_long_lower is TRUE",
     "candle_M3.closed_candle_dir == UP",
     "utbot_M15.closed_bias == BULLISH",
     "vwap_M1.closed_price_vs_vwap == ABOVE"]))


def build_config(name, desc, sell_conds, buy_conds, sl=7.5):
    cfg = copy.deepcopy(BASE)
    cfg["trading"]["sl_dollars"] = sl
    cfg["rules"] = {"expressions": [{
        "name": name, "enabled": True, "priority": 50,
        "sl_dollars": sl, "reward_ratio": 1.0,
        "breakeven_pct": 0.0, "partial_tp": False,
        "description": desc,
        "buy": buy_conds,
        "sell": sell_conds,
    }]}
    return cfg


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "sampledata" / "XAUUSD_M1_60d.csv"
TMPDIR = Path("/tmp/wick_strategy_configs")
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
        # Print stderr for debugging
        for line in (r.stderr or "").split("\n")[-5:]:
            if line.strip():
                print(f"  DBG: {line.strip()}")
    return tr, wr, pf, net, dd


# ── Run ──
print(f"\nData: {DATA}")
print(f"All variants BUY+SELL, SL $7.5, multi_position OFF\n")

print(f"{'='*85}")
print(f"  Candle Wick Rejection Strategies (BUY + SELL)")
print(f"{'='*85}")
print(f"{'#':<3} {'Name':<34} {'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'Net':>10}  {'DD%':>5}")
print("-" * 85)

for i, combo in enumerate(COMBOS, 1):
    _, name, desc, sell_conds, buy_conds = combo
    tr, wr, pf, net, dd = run_one(name, desc, sell_conds, buy_conds)
    flag = " ★" if pf >= 1.3 and tr >= 20 else " ✓" if pf >= 1.1 and tr >= 10 else ""
    print(f"{i:<3} {name:<34} {tr:>6}  {wr:>5.1f}  {pf:>5.2f}  {net:>+10.2f}  {dd:>5.1f}{flag}")
