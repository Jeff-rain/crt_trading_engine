import pandas as pd
from mt5linux import MetaTrader5

# 🏛️ Watchlist Directory & Structural Anchor Mapping
WATCHLIST = {
    "XAUUSD.m":  {"tf_name": "H4",  "mt5_tf": MetaTrader5.TIMEFRAME_H4},
    "EURUSD.m":  {"tf_name": "D1",  "mt5_tf": MetaTrader5.TIMEFRAME_D1},
    "GBPUSD.m":  {"tf_name": "D1",  "mt5_tf": MetaTrader5.TIMEFRAME_D1},
    "USDJPY.m":  {"tf_name": "D1",  "mt5_tf": MetaTrader5.TIMEFRAME_D1},
    "AUDUSD.m":  {"tf_name": "D1",  "mt5_tf": MetaTrader5.TIMEFRAME_D1},
    "GBPJPY.m":  {"tf_name": "D1",  "mt5_tf": MetaTrader5.TIMEFRAME_D1},
    "US100.std": {"tf_name": "D1",  "mt5_tf": MetaTrader5.TIMEFRAME_D1}
}

def analyze_regime(df):
    """Calculates EMAs and ATR to determine the precise Market State and Regard."""
    # 1. Compute Trend Filters
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

    # 2. Compute Volatility Filters (ATR 14)
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = (df['high'] - df['close'].shift()).abs()
    df['low_close'] = (df['low'] - df['close'].shift()).abs()
    df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr_14'] = df['true_range'].rolling(14).mean()

    latest = df.iloc[-1]
    historical_atr_avg = df['atr_14'].mean()
    
    ema_gap = abs(latest['ema_20'] - latest['ema_50'])
    gap_percentage = (ema_gap / latest['close']) * 100

    # 3. Decision Matrix
    if gap_percentage < 0.05:
        return "RANGING", "⚠️ CAUTION"
    
    elif latest['ema_20'] > latest['ema_50']:
        if latest['atr_14'] > historical_atr_avg * 1.5:
            return "EXPANDING VOLATILITY", "⚠️ HIGH RISK"
        return "TRENDING (Bullish)", "✅ LONGS ONLY"
        
    elif latest['ema_20'] < latest['ema_50']:
        if latest['atr_14'] > historical_atr_avg * 1.5:
            return "EXPANDING VOLATILITY", "⚠️ HIGH RISK"
        return "TRENDING (Bearish)", "✅ SHORTS ONLY"
        
    else:
        return "TRANSITIONAL", "🔍 MONITORING"

# --- ENGINE EXECUTION LINK ---
print("🟢 Booting Regime Engine Multi-Asset Core...")

mt5 = MetaTrader5()
if not mt5.initialize():
    print("🚨 Bridge Connection Failed")
    quit()

print("\n======================================================================")
print(" 🏛️ SYSTEM REGIME ENGINE: WATCHLIST SCREENING ACTIVE")
print("======================================================================")
print(f" {'ASSET':<12} │ {'TIMEFRAME':<9} │ {'STATE':<23} │ {'REGARD'}")
print("──────────────────────────────────────────────────────────────────────")

for asset, config in WATCHLIST.items():
    # Request 200 bars of historical data based on the assigned anchor timeframe
    rates = mt5.copy_rates_from_pos(asset, config["mt5_tf"], 0, 200)
    
    if rates is None:
        print(f" {asset:<12} │ {config['tf_name']:<9} │ 🚨 DATA FETCH FAILED       │ ❌ SKIP")
        continue
        
    df = pd.DataFrame(rates)
    state, regard = analyze_regime(df)
    
    print(f" {asset:<12} │ {config['tf_name']:<9} │ {state:<23} │ {regard}")

print("======================================================================\n")

mt5.shutdown()
