from mt5linux import MetaTrader5
import pandas as pd

# 1. Connect the Ubuntu client to the Windows server
mt5 = MetaTrader5()
if not mt5.initialize():
    print("🚨 Bridge Connection Failed")
    quit()

print("🟢 Bridge Active. Pinging MT5 for XAUUSD.m...")

# 2. Request the last 10 candles (15-minute timeframe)
rates = mt5.copy_rates_from_pos("XAUUSD.m", mt5.TIMEFRAME_M15, 0, 10)

if rates is None:
    print("🚨 Failed to get data. Check MT5 connection.")
    print(f"🛠️ MT5 Error Code: {mt5.last_error()}")
else:
    # 3. Format the raw tick data into a Pandas DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print("\n📊 SUCCESS! LIVE MARKET DATA INGESTED:\n")
    print(df[['time', 'open', 'high', 'low', 'close', 'tick_volume']])

# 4. Close the connection gracefully
mt5.shutdown()
