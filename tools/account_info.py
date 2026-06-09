"""Get MT5 account info via rpyc bridge."""
from mt5linux import MetaTrader5

mt5 = MetaTrader5(host="localhost", port=8001)
mt5.initialize()

info = mt5.account_info()
if info:
    print(f"Login:    {info.login}")
    print(f"Server:   {info.server}")
    print(f"Name:     {info.name}")
    print(f"Balance:  {info.balance}")
    print(f"Equity:   {info.equity}")
    print(f"Margin:   {info.margin}")
    print(f"Free Mrg: {info.margin_free}")
    print(f"Leverage: {info.leverage}")
    print(f"Currency: {info.currency}")
else:
    print("Failed to get account info:", mt5.last_error())

mt5.shutdown()
