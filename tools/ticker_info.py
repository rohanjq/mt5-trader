"""Get symbol/ticker info and current price via rpyc bridge."""
import sys
from mt5linux import MetaTrader5

symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"

mt5 = MetaTrader5(host="localhost", port=8001)
mt5.initialize()

info = mt5.symbol_info(symbol)
if info is None:
    print(f"Symbol {symbol} not found:", mt5.last_error())
    mt5.shutdown()
    sys.exit(1)

tick = mt5.symbol_info_tick(symbol)

print(f"Symbol:     {info.name}")
print(f"Bid:        {tick.bid}")
print(f"Ask:        {tick.ask}")
print(f"Spread:     {info.spread}")
print(f"Digits:     {info.digits}")
print(f"Trade Mode: {info.trade_mode}")
print(f"Min Lot:    {info.volume_min}")
print(f"Max Lot:    {info.volume_max}")
print(f"Lot Step:   {info.volume_step}")
print(f"Filling:    {info.filling_mode}")

mt5.shutdown()
