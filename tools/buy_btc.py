"""Buy 0.001 BTCUSDT via rpyc bridge."""
from mt5linux import MetaTrader5

mt5 = MetaTrader5(host="localhost", port=8001)
mt5.initialize()

symbol = "BTCUSDT"
lot = 0.001

tick = mt5.symbol_info_tick(symbol)
if tick is None:
    print(f"Failed to get tick for {symbol}:", mt5.last_error())
    mt5.shutdown()
    exit(1)

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": symbol,
    "volume": lot,
    "type": mt5.ORDER_TYPE_BUY,
    "price": tick.ask,
    "deviation": 20,
    "magic": 100,
    "comment": "test buy",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_FOK,
}

result = mt5.order_send(request)
print(f"Retcode: {result.retcode}")
if result.retcode == 10009:
    print(f"Deal:   #{result.deal}")
    print(f"Price:  {result.price}")
    print(f"Volume: {result.volume}")
else:
    print(f"Failed: {result.comment}")

mt5.shutdown()
