"""M2 UT Bot second wave variants — BUY + SELL."""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 290, "deviation": 20, "filling": "FOK",
                "multi_position": True, "sl_dollars": 7.5, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "../MetaTrader5-Docker/data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M1","M2","M3","M5","M10","M15","M45","H1"]},
        {"indicator": "dc", "timeframes": ["M1","M5","M15"]},
        {"indicator": "ema9", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema21", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema50", "timeframes": ["M1","M5","M15"]},
        {"indicator": "ema200", "timeframes": ["M1","M5","M15"]},
        {"indicator": "rsi14", "timeframes": ["M1","M2","M5","M15"]},
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

# Second wave logic:
#   BUY: HTF bullish, M5 dipped (bear bars = bounce happened), M2 fires BUY = resumption
#   SELL: HTF bearish, M5 bounced (bull bars = bounce happened), M2 fires SELL = resumption

COMBOS = [
    # ── BUY 2nd wave variants ──
    # Base winner: m2buy_vwap_m5_m15 (PF 1.51) — can't add M5 bounce to this since it requires M5 BULLISH
    # So we build from m2buy_vwap_m15 (PF 1.36) + add M5 dip as bounce filter

    ("BUY", "m2buy_2w_m15_dip2_vwap",
     "M2 BUY + M15 bull + M5 dipped 2+ bars + VWAP",
     ["utbot_M15.closed_bias == BULLISH", "utbot_M5.consecutive_bear_bars >= 2",
      "vwap_M1.closed_price_vs_vwap == ABOVE"]),

    ("BUY", "m2buy_2w_m15_dip3_vwap",
     "M2 BUY + M15 bull + M5 dipped 3+ bars + VWAP",
     ["utbot_M15.closed_bias == BULLISH", "utbot_M5.consecutive_bear_bars >= 3",
      "vwap_M1.closed_price_vs_vwap == ABOVE"]),

    ("BUY", "m2buy_2w_m15_m5bear_vwap",
     "M2 BUY + M15 bull + M5 BEARISH (bounced) + VWAP",
     ["utbot_M15.closed_bias == BULLISH", "utbot_M5.closed_bias == BEARISH",
      "vwap_M1.closed_price_vs_vwap == ABOVE"]),

    ("BUY", "m2buy_2w_m15_dip2",
     "M2 BUY + M15 bull + M5 dipped 2+ bars (no VWAP)",
     ["utbot_M15.closed_bias == BULLISH", "utbot_M5.consecutive_bear_bars >= 2"]),

    ("BUY", "m2buy_2w_m15_m5bear",
     "M2 BUY + M15 bull + M5 BEARISH (no VWAP)",
     ["utbot_M15.closed_bias == BULLISH", "utbot_M5.closed_bias == BEARISH"]),

    ("BUY", "m2buy_2w_m15_dip2_ema50",
     "M2 BUY + M15 bull + M5 dipped 2+ + EMA50 M5 above",
     ["utbot_M15.closed_bias == BULLISH", "utbot_M5.consecutive_bear_bars >= 2",
      "ema50_M5.closed_price_vs_ema == ABOVE"]),

    ("BUY", "m2buy_2w_m15_m5bear_ema50",
     "M2 BUY + M15 bull + M5 BEARISH + EMA50 M5 above",
     ["utbot_M15.closed_bias == BULLISH", "utbot_M5.closed_bias == BEARISH",
      "ema50_M5.closed_price_vs_ema == ABOVE"]),

    ("BUY", "m2buy_2w_ema50_dip2_vwap",
     "M2 BUY + EMA50 M5 above + M5 dipped 2+ + VWAP",
     ["ema50_M5.closed_price_vs_ema == ABOVE", "utbot_M5.consecutive_bear_bars >= 2",
      "vwap_M1.closed_price_vs_vwap == ABOVE"]),

    # ── SELL 2nd wave variants ──
    # Base winners: m2sell_ema50_m5 (PF 1.49), m2sell_vwap_ema21 (PF 1.44)

    ("SELL", "m2sell_2w_ema50_bounce2",
     "M2 SELL + EMA50 M5 below + M5 bounced 2+ bars",
     ["ema50_M5.closed_price_vs_ema == BELOW", "utbot_M5.consecutive_bull_bars >= 2"]),

    ("SELL", "m2sell_2w_ema50_bounce3",
     "M2 SELL + EMA50 M5 below + M5 bounced 3+ bars",
     ["ema50_M5.closed_price_vs_ema == BELOW", "utbot_M5.consecutive_bull_bars >= 3"]),

    ("SELL", "m2sell_2w_ema50_m5bull",
     "M2 SELL + EMA50 M5 below + M5 BULLISH (bounced)",
     ["ema50_M5.closed_price_vs_ema == BELOW", "utbot_M5.closed_bias == BULLISH"]),

    ("SELL", "m2sell_2w_m15_bounce2_vwap",
     "M2 SELL + M15 bear + M5 bounced 2+ + VWAP below",
     ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 2",
      "vwap_M1.closed_price_vs_vwap == BELOW"]),

    ("SELL", "m2sell_2w_m15_bounce2",
     "M2 SELL + M15 bear + M5 bounced 2+ bars",
     ["utbot_M15.closed_bias == BEARISH", "utbot_M5.consecutive_bull_bars >= 2"]),

    ("SELL", "m2sell_2w_m15_m5bull",
     "M2 SELL + M15 bear + M5 BULLISH (bounced)",
     ["utbot_M15.closed_bias == BEARISH", "utbot_M5.closed_bias == BULLISH"]),

    ("SELL", "m2sell_2w_m15_m5bull_vwap",
     "M2 SELL + M15 bear + M5 BULLISH + VWAP below",
     ["utbot_M15.closed_bias == BEARISH", "utbot_M5.closed_bias == BULLISH",
      "vwap_M1.closed_price_vs_vwap == BELOW"]),

    ("SELL", "m2sell_2w_ema50_bounce2_vwap",
     "M2 SELL + EMA50 M5 below + M5 bounced 2+ + VWAP",
     ["ema50_M5.closed_price_vs_ema == BELOW", "utbot_M5.consecutive_bull_bars >= 2",
      "vwap_M1.closed_price_vs_vwap == BELOW"]),

    ("SELL", "m2sell_2w_ema21_bounce2_vwap",
     "M2 SELL + EMA21 below + M5 bounced 2+ + VWAP",
     ["ema21_M1.closed_price_vs_ema == BELOW", "utbot_M5.consecutive_bull_bars >= 2",
      "vwap_M1.closed_price_vs_vwap == BELOW"]),

    ("SELL", "m2sell_2w_ema50_m5bull_vwap",
     "M2 SELL + EMA50 M5 below + M5 BULLISH + VWAP",
     ["ema50_M5.closed_price_vs_ema == BELOW", "utbot_M5.closed_bias == BULLISH",
      "vwap_M1.closed_price_vs_vwap == BELOW"]),
]

tmpdir = Path("/tmp/m2_2w_configs")
tmpdir.mkdir(exist_ok=True)
cwd = Path(__file__).resolve().parent.parent

cur_dir = None
for direction, name, desc, filters in COMBOS:
    if direction != cur_dir:
        cur_dir = direction
        print(f"\n{'='*70}")
        print(f"  M2 UT Bot {direction} — Second Wave — SL $7.5, RR 1:1")
        print(f"{'='*70}")
        print(f"{'Name':<30} {'Trades':>6} {'WR%':>6} {'PF':>6} {'Net':>10} {'DD%':>6}")
        print("-" * 70)

    cfg = copy.deepcopy(BASE)
    sig = "BUY" if direction == "BUY" else "SELL"
    active_conds = [f"utbot_M2.closed_signal == {sig}"] + filters
    dead_conds = ["utbot_M2.closed_signal == BUY", "utbot_M2.closed_signal == SELL"]

    if direction == "BUY":
        buy_conds, sell_conds = active_conds, dead_conds
    else:
        buy_conds, sell_conds = dead_conds, active_conds

    cfg["rules"] = {"expressions": [{
        "name": name, "enabled": True, "priority": 50,
        "sl_dollars": 7.5, "reward_ratio": 1.0,
        "breakeven_pct": 0.0, "partial_tp": False,
        "description": desc, "buy": buy_conds, "sell": sell_conds,
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
        print(f"{name:<30} {'TIMEOUT':>6}")
        continue

    def grab(pat):
        m = re.search(pat, out)
        return m.group(1).replace(",", "") if m else ""

    t = grab(r"Total Trades\s+(\d+)")
    wr = grab(r"Win Rate\s+([\d.]+)%")
    pf = grab(r"Profit Factor\s+([\d.]+)")
    net = grab(r"Net Profit\s+\$([+-]?[\d,.]+)")
    dd = grab(r"Max Drawdown\s+([\d.]+)%")

    if t and int(t) > 0:
        print(f"{name:<30} {t:>6} {wr:>6} {pf:>6} {net:>10} {dd:>6}")
    else:
        print(f"{name:<30} {'0':>6} {'--':>6} {'--':>6} {'--':>10} {'--':>6}")
