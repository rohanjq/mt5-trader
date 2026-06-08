"""Backtest each old hardcoded rule as a YAML expression config."""
import copy, subprocess, sys, re, yaml
from pathlib import Path

BASE = {
    "mt5": {"host": "localhost", "port": 8001},
    "trading": {"symbol": "XAUUSD", "volume": 0.25, "risk_pct": 5.0, "max_volume": 10.0,
                "min_volume": 0.01, "magic": 310, "deviation": 20, "filling": "FOK",
                "multi_position": True, "sl_dollars": 5.0, "reward_ratio": 1.0},
    "signals": {"poll_interval": 2.0, "csv_dir": "../MetaTrader5-Docker/data/signals", "sources": [
        {"indicator": "utbot", "timeframes": ["M1","M2","M3","M5","M10","M15","M30","M45","H1","H4"]},
        {"indicator": "dc", "timeframes": ["M1","M2","M3","M5","M10","M15","M30","M45","H1","H4"]},
        {"indicator": "ema9", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema21", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema50", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "ema200", "timeframes": ["M1","M2","M5","M15"]},
        {"indicator": "rsi14", "timeframes": ["M1","M5","M15"]},
        {"indicator": "adx14", "timeframes": ["M1","M5","M15"]},
        {"indicator": "vwap", "timeframes": ["M1","M5","M15"]},
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

RULES = [
    {
        "name": "dc_confluence",
        "description": "DC M15 zone + UT Bot M1 signal + UT Bot M45 trend (5+ bars)",
        "sl_dollars": 5.0,
        "buy": [
            "dc_M15.closed_price_zone in LOWER,LOWER_MID",
            "utbot_M1.closed_signal == BUY",
            "utbot_M45.consecutive_bull_bars >= 5",
        ],
        "sell": [
            "dc_M15.closed_price_zone in UPPER,UPPER_MID",
            "utbot_M1.closed_signal == SELL",
            "utbot_M45.consecutive_bear_bars >= 5",
        ],
    },
    {
        "name": "dc_wick_rejection",
        "description": "DC M15 wick rejection + UT Bot M3 bias",
        "sl_dollars": 5.0,
        "buy": [
            "dc_M15.closed_lower_wick_rej is TRUE",
            "utbot_M3.closed_bias == BULLISH",
        ],
        "sell": [
            "dc_M15.closed_upper_wick_rej is TRUE",
            "utbot_M3.closed_bias == BEARISH",
        ],
    },
    {
        "name": "utbot_multi_tf",
        "description": "UT Bot M1 signal + M15 bias + M45 bias alignment",
        "sl_dollars": 5.0,
        "buy": [
            "utbot_M1.closed_signal == BUY",
            "utbot_M15.closed_bias == BULLISH",
            "utbot_M45.closed_bias == BULLISH",
        ],
        "sell": [
            "utbot_M1.closed_signal == SELL",
            "utbot_M15.closed_bias == BEARISH",
            "utbot_M45.closed_bias == BEARISH",
        ],
    },
    {
        "name": "utbot_simple",
        "description": "UT Bot M1 signal only (no filters)",
        "sl_dollars": 5.0,
        "buy": [
            "utbot_M1.closed_signal == BUY",
        ],
        "sell": [
            "utbot_M1.closed_signal == SELL",
        ],
    },
]

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "sampledata" / "sample.csv"
TMPDIR = Path("/tmp/old_rules_yaml")
TMPDIR.mkdir(exist_ok=True)

PF_RE = re.compile(r"Profit Factor\s+([\d.]+|inf)")
TR_RE = re.compile(r"Total Trades\s+(\d+)")
WR_RE = re.compile(r"Win Rate\s+([\d.]+)%")
NT_RE = re.compile(r"Final Balance\s+\$([\d.,+-]+)")
DD_RE = re.compile(r"Max Drawdown\s+([\d.]+)%")
DIR_RE = re.compile(r"LONG:\s+(\d+)\s+trades.*\$([-+\d.,]+)\s*\n\s*SHORT:\s+(\d+)\s+trades.*\$([-+\d.,]+)")

for rule in RULES:
    cfg = copy.deepcopy(BASE)
    cfg["trading"]["sl_dollars"] = rule["sl_dollars"]
    cfg["rules"] = {"expressions": [{
        "name": rule["name"], "enabled": True, "priority": 50,
        "sl_dollars": rule["sl_dollars"], "reward_ratio": 1.0,
        "breakeven_pct": 0.0, "partial_tp": False,
        "description": rule["description"],
        "buy": rule["buy"], "sell": rule["sell"],
    }]}
    cfg_path = TMPDIR / f"{rule['name']}.yaml"
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

    # Direction breakdown
    dm = DIR_RE.search(out)
    if dm:
        long_tr, long_pnl = dm.group(1), dm.group(2).replace(",", "")
        short_tr, short_pnl = dm.group(3), dm.group(4).replace(",", "")
        dir_info = f"  LONG: {long_tr} trades ${long_pnl} | SHORT: {short_tr} trades ${short_pnl}"
    else:
        dir_info = ""

    print(f"\n{'='*60}")
    print(f"  {rule['name']}")
    print(f"  {rule['description']}")
    print(f"{'='*60}")
    print(f"  Trades: {tr}  |  WR: {wr:.1f}%  |  PF: {pf:.2f}  |  Net: {net:+.2f}  |  DD: {dd:.1f}%")
    if dir_info:
        print(dir_info)
    print(f"  BUY:  {rule['buy']}")
    print(f"  SELL: {rule['sell']}")
