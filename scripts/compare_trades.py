"""Side-by-side comparison of live MT5 trades vs tick backtest trades.

Usage:
    PYTHONPATH=. uv run python scripts/compare_trades.py [bt_output.json]

Matches trades by open time (within 2 min tolerance) and same direction.
"""
import json
import sys

import pandas as pd

# ── Load live trades ─────────────────────────────────────────────────────
live = pd.read_csv("logs/mt5_trades.csv")
live["open_time"] = pd.to_datetime(live["open_time"])
live = live[live["open_time"] >= "2026-06-09 17:00"].copy()
live = live.sort_values("open_time").reset_index(drop=True)

# ── Load BT trades from JSON output ─────────────────────────────────────
bt_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bt_trades.csv"
with open(bt_path) as f:
    bt_data = json.load(f)

bt_trades = []
for t in bt_data["trades"]:
    bt_trades.append({
        "time": pd.to_datetime(t["entry_time"]),
        "dir": t["direction"],
        "strategy": t["rule"],
        "entry": t["entry_price"],
        "exit": t["exit_price"],
        "pnl": t["profit"],
        "exit_reason": t["exit_reason"],
        "volume": t["volume"],
    })
bt = pd.DataFrame(bt_trades)

# ── Match trades ─────────────────────────────────────────────────────────
TOLERANCE = pd.Timedelta("2min")

matched = []
bt_used = set()
live_used = set()

for li, lr in live.iterrows():
    best_bi = None
    best_dt = pd.Timedelta("999h")
    for bi, br in bt.iterrows():
        if bi in bt_used:
            continue
        if lr["direction"] != br["dir"]:
            continue
        dt = abs(lr["open_time"] - br["time"])
        if dt <= TOLERANCE and dt < best_dt:
            best_dt = dt
            best_bi = bi
    if best_bi is not None:
        matched.append((li, best_bi))
        bt_used.add(best_bi)
        live_used.add(li)

# ── Print results ────────────────────────────────────────────────────────
print("=" * 130)
print(f"{'LIVE':^55s} | {'BACKTEST':^70s}")
print(f"{'Time':16s} {'Dir':5s} {'Entry':>8s} {'Vol':>5s} {'P&L':>9s} | "
      f"{'Time':16s} {'Dir':5s} {'Entry':>8s} {'Strategy':25s} {'P&L':>9s} {'Exit':>4s} {'Match':>6s}")
print("-" * 130)

live_total = 0
bt_total = 0

# Print matched + live-only in chronological order
for li, lr in live.iterrows():
    live_total += lr["profit"]
    bi_match = None
    for a, b in matched:
        if a == li:
            bi_match = b
            break

    lt = lr["open_time"].strftime("%m/%d %H:%M")
    lp = f"{lr['profit']:+.2f}"

    if bi_match is not None:
        br = bt.iloc[bi_match]
        bt_total += br["pnl"]
        btime = br["time"].strftime("%m/%d %H:%M")
        pnl_diff = abs(lr["profit"] - br["pnl"])
        match_label = "OK" if pnl_diff < 50 else f"~{pnl_diff:.0f}"
        print(
            f"{lt:16s} {lr['direction']:5s} {lr['entry_price']:8.2f} {lr['volume']:5.2f} {lp:>9s} | "
            f"{btime:16s} {br['dir']:5s} {br['entry']:8.2f} {br['strategy']:25s} {br['pnl']:+9.2f} {br['exit_reason']:>4s} {match_label:>6s}"
        )
    else:
        print(
            f"{lt:16s} {lr['direction']:5s} {lr['entry_price']:8.2f} {lr['volume']:5.2f} {lp:>9s} | "
            f"{'--- MISSING ---':>70s}"
        )

# Print BT-only trades
for bi, br in bt.iterrows():
    if bi not in bt_used:
        bt_total += br["pnl"]
        btime = br["time"].strftime("%m/%d %H:%M")
        print(
            f"{'':16s} {'':5s} {'':>8s} {'':>5s} {'':>9s} | "
            f"{btime:16s} {br['dir']:5s} {br['entry']:8.2f} {br['strategy']:25s} {br['pnl']:+9.2f} {br['exit_reason']:>4s} {'EXTRA':>6s}"
        )

print("-" * 130)
print(f"Live: {len(live)} trades, P&L=${live_total:+,.2f}")
print(f"BT:   {len(bt)} trades, P&L=${bt_total:+,.2f}")
print(f"Matched: {len(matched)}, Live-only: {len(live) - len(matched)}, BT-only: {len(bt) - len(matched)}")
print(f"P&L gap: ${live_total - bt_total:+,.2f}")
