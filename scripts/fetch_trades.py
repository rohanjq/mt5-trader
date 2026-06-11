"""Fetch recent closed trades from MT5 and save to CSV.

Usage:
    uv run python scripts/fetch_trades.py
    uv run python scripts/fetch_trades.py --count 100 --days 30
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from mt5linux import MetaTrader5


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch closed trades from MT5")
    parser.add_argument("--count", "-n", type=int, default=50, help="Max trades to fetch (default: 50)")
    parser.add_argument("--days", "-d", type=int, default=14, help="Look back N days (default: 14)")
    parser.add_argument("--symbol", "-s", default=None, help="Filter by symbol (default: all)")
    parser.add_argument("--host", default="localhost", help="MT5 rpyc host")
    parser.add_argument("--port", type=int, default=8001, help="MT5 rpyc port")
    parser.add_argument("--output", "-o", default=None, help="Output CSV path")
    args = parser.parse_args()

    print(f"Connecting to MT5 at {args.host}:{args.port}...")
    mt5 = MetaTrader5(host=args.host, port=args.port)
    if not mt5.initialize():
        print("ERROR: MT5 initialize() failed")
        sys.exit(1)

    info = mt5.terminal_info()
    if info:
        print(f"Connected: {info.name}")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    # Fetch deals (closed trades)
    # DEAL_TYPE_BUY = 0, DEAL_TYPE_SELL = 1
    # We get all deals then filter to entry/exit pairs
    deals = mt5.history_deals_get(start, end)

    if deals is None or len(deals) == 0:
        print("No deals found")
        mt5.shutdown()
        sys.exit(0)

    df = pd.DataFrame(list(deals))

    # Column names from MT5 deal structure
    # Rename for clarity
    col_rename = {}
    for col in df.columns:
        lc = str(col).lower()
        col_rename[col] = lc
    df = df.rename(columns=col_rename)

    print(f"Raw deals: {len(df)}")

    # Filter by symbol if specified
    if args.symbol and "symbol" in df.columns:
        df = df[df["symbol"] == args.symbol]

    # Convert time
    if "time" in df.columns:
        df["time_str"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")

    # Filter to trade deals only (type 0=buy, 1=sell; skip balance/commission deals)
    # Deal entry: 0=in, 1=out, 2=inout, 3=out_by
    if "entry" in df.columns:
        trade_deals = df[df["entry"].isin([0, 1])].copy()
    else:
        trade_deals = df.copy()

    # Build matched trades from position IDs
    if "position_id" in trade_deals.columns:
        entries = trade_deals[trade_deals["entry"] == 0].copy()
        exits = trade_deals[trade_deals["entry"] == 1].copy()

        trades = []
        for _, ex in exits.iterrows():
            pos_id = ex["position_id"]
            entry_row = entries[entries["position_id"] == pos_id]
            if entry_row.empty:
                continue
            entry_row = entry_row.iloc[0]

            direction = "BUY" if entry_row.get("type", 0) == 0 else "SELL"
            trades.append({
                "position_id": int(pos_id),
                "symbol": ex.get("symbol", ""),
                "direction": direction,
                "open_time": pd.to_datetime(entry_row["time"], unit="s", utc=True).strftime("%Y-%m-%d %H:%M:%S"),
                "close_time": pd.to_datetime(ex["time"], unit="s", utc=True).strftime("%Y-%m-%d %H:%M:%S"),
                "entry_price": entry_row.get("price", 0),
                "exit_price": ex.get("price", 0),
                "volume": entry_row.get("volume", 0),
                "profit": ex.get("profit", 0),
                "commission": entry_row.get("commission", 0) + ex.get("commission", 0),
                "swap": ex.get("swap", 0),
                "comment": entry_row.get("comment", ""),
            })

        df_trades = pd.DataFrame(trades)
    else:
        # Fallback: just dump the deals
        df_trades = trade_deals

    if df_trades.empty:
        print("No matched trades found")
        mt5.shutdown()
        sys.exit(0)

    # Sort by open time descending, take last N
    if "open_time" in df_trades.columns:
        df_trades = df_trades.sort_values("open_time", ascending=False).head(args.count)
        df_trades = df_trades.sort_values("open_time", ascending=True)

    mt5.shutdown()

    # Output
    output = Path(args.output) if args.output else Path("logs/mt5_trades.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    df_trades.to_csv(output, index=False)

    print(f"\nSaved {len(df_trades)} trades to {output}")
    print(df_trades.to_string(index=False))


if __name__ == "__main__":
    main()
