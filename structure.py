import pandas as pd
import numpy as np
from mt5linux import MetaTrader5

# 🏛️ Multi-Asset Timeframe Matrix
WATCHLIST_CONFIG = {
    "XAUUSD.m":  {"ltf_name": "H1", "mt5_tf": MetaTrader5.TIMEFRAME_H1, "lookback_bars": 250},
    "EURUSD.m":  {"ltf_name": "H4", "mt5_tf": MetaTrader5.TIMEFRAME_H4, "lookback_bars": 200},
    "GBPUSD.m":  {"ltf_name": "H4", "mt5_tf": MetaTrader5.TIMEFRAME_H4, "lookback_bars": 200},
    "USDJPY.m":  {"ltf_name": "H4", "mt5_tf": MetaTrader5.TIMEFRAME_H4, "lookback_bars": 200},
    "AUDUSD.m":  {"ltf_name": "H4", "mt5_tf": MetaTrader5.TIMEFRAME_H4, "lookback_bars": 200},
    "GBPJPY.m":  {"ltf_name": "H4", "mt5_tf": MetaTrader5.TIMEFRAME_H4, "lookback_bars": 200},
    "US100.std": {"ltf_name": "H4", "mt5_tf": MetaTrader5.TIMEFRAME_H4, "lookback_bars": 200}
}

def analyze_merged_geometry(df, lookback_bars):
    total_bars = len(df)
    df.bfill(inplace=True)
    start_idx = max(20, total_bars - lookback_bars)
    
    # LUXALGO FVG ARRAYS
    active_fvgs = []
    
    # VEGALGO OB/BREAKER ARRAYS
    swing_length = 5
    last_sh = None; last_sh_bar = None; sh_breached = False
    last_sl = None; last_sl_bar = None; sl_breached = False
    pending_obs = []
    confirmed_obs = []

    # --- HISTORICAL ENGINE: SCAN FOR FORMATIONS ---
    for i in range(start_idx, total_bars):
        c_low = df['low'].iloc[i]
        c_high = df['high'].iloc[i]
        c_close = df['close'].iloc[i]
        
        prev_close = df['close'].iloc[i-1]
        past_high = df['high'].iloc[i-2]
        past_low = df['low'].iloc[i-2]

        # -------------------------------------------------------------
        # A. LUXALGO FVG LOGIC
        # -------------------------------------------------------------
        if c_low > past_high and prev_close > past_high:
            active_fvgs.append({"type": "BULLISH", "max": c_low, "min": past_high, "origin_bar": i, "consecutive_count": 1})
        elif c_high < past_low and prev_close < past_low:
            active_fvgs.append({"type": "BEARISH", "max": past_low, "min": c_high, "origin_bar": i, "consecutive_count": 1})

        # -------------------------------------------------------------
        # B. VEGALGO OB & BREAKER LOGIC
        # -------------------------------------------------------------
        # 1. Pivot Swing High/Low Detection (Rolling 5-bar window)
        if i >= swing_length * 2:
            window_highs = df['high'].iloc[i - (swing_length*2) : i + 1]
            if df['high'].iloc[i - swing_length] == window_highs.max():
                last_sh = df['high'].iloc[i - swing_length]
                last_sh_bar = i - swing_length
                sh_breached = False
            
            window_lows = df['low'].iloc[i - (swing_length*2) : i + 1]
            if df['low'].iloc[i - swing_length] == window_lows.min():
                last_sl = df['low'].iloc[i - swing_length]
                last_sl_bar = i - swing_length
                sl_breached = False

        # 2. Breach Detection
        high_breached = False
        low_breached = False
        
        if last_sh is not None and not sh_breached and c_high > last_sh:
            high_breached = True
            sh_breached = True
        if last_sl is not None and not sl_breached and c_low < last_sl:
            low_breached = True
            sl_breached = True

        # 3. Store Pending Orderblocks
        if high_breached:
            already_pending = any(p['is_bullish'] and abs(p['level'] - last_sh) < 0.0001 for p in pending_obs)
            if not already_pending:
                # Look back up to 50 bars, stopping at the swing high
                for j in range(1, 51):
                    chk_bar = i - j
                    if chk_bar <= last_sh_bar: break
                    if df['close'].iloc[chk_bar] < df['open'].iloc[chk_bar]: # Bear candle origin
                        pending_obs.append({
                            'level': last_sh, 'ob_bar': chk_bar,
                            'top': df['high'].iloc[chk_bar], 'bottom': df['low'].iloc[chk_bar],
                            'is_bullish': True
                        })
                        break

        if low_breached:
            already_pending = any(not p['is_bullish'] and abs(p['level'] - last_sl) < 0.0001 for p in pending_obs)
            if not already_pending:
                for j in range(1, 51):
                    chk_bar = i - j
                    if chk_bar <= last_sl_bar: break
                    if df['close'].iloc[chk_bar] > df['open'].iloc[chk_bar]: # Bull candle origin
                        pending_obs.append({
                            'level': last_sl, 'ob_bar': chk_bar,
                            'top': df['high'].iloc[chk_bar], 'bottom': df['low'].iloc[chk_bar],
                            'is_bullish': False
                        })
                        break

        # 4. Confirmation via Market Structure Break (Body Close)
        bullish_msb = last_sh is not None and c_close > last_sh and prev_close <= last_sh
        bearish_msb = last_sl is not None and c_close < last_sl and prev_close >= last_sl
        
        active_pending = []
        for p in pending_obs:
            confirmed = False
            if p['is_bullish'] and bullish_msb and abs(p['level'] - last_sh) < 0.0001:
                confirmed_obs.append({
                    'top': p['top'], 'bottom': p['bottom'], 'ob_bar': p['ob_bar'], 'conf_bar': i,
                    'is_bullish': True, 'is_breaker': False, 'was_bullish': True
                })
                confirmed = True
            elif not p['is_bullish'] and bearish_msb and abs(p['level'] - last_sl) < 0.0001:
                confirmed_obs.append({
                    'top': p['top'], 'bottom': p['bottom'], 'ob_bar': p['ob_bar'], 'conf_bar': i,
                    'is_bullish': False, 'is_breaker': False, 'was_bullish': False
                })
                confirmed = True
            if not confirmed:
                active_pending.append(p)
        pending_obs = active_pending

        # 5. Breakers & Chop Control
        surviving_obs = []
        for ob in confirmed_obs:
            chop = False
            if not ob['is_breaker']:
                if ob['is_bullish'] and c_close < ob['bottom']:
                    ob['is_breaker'] = True
                    ob['flip_bar'] = i
                elif not ob['is_bullish'] and c_close > ob['top']:
                    ob['is_breaker'] = True
                    ob['flip_bar'] = i
            elif ob['is_breaker']:
                # Chop Control Validation
                if ob['was_bullish'] and c_close > ob['top']: chop = True
                elif not ob['was_bullish'] and c_close < ob['bottom']: chop = True
                    
            if not chop:
                surviving_obs.append(ob)
        confirmed_obs = surviving_obs

    # --- MITIGATION FILTERS & DISPLAY OUTPUT ---
    
    # 1. LuxAlgo FVGs
    valid_fvg_list = []
    for fvg in active_fvgs:
        ramped = False
        wick_mitigated = False
        for j in range(fvg["origin_bar"], total_bars):
            chk_c = df['close'].iloc[j]
            if fvg["type"] == "BULLISH":
                if chk_c < fvg["min"]: ramped = True; break
                if df['low'].iloc[j] < fvg["max"]: wick_mitigated = True
            else:
                if chk_c > fvg["max"]: ramped = True; break
                if df['high'].iloc[j] > fvg["min"]: wick_mitigated = True
                    
        if not ramped:
            fvg["mitigated"] = wick_mitigated
            valid_fvg_list.append(fvg)

    if len(valid_fvg_list) >= 2:
        for k in range(1, len(valid_fvg_list)):
            if abs(valid_fvg_list[k]["origin_bar"] - valid_fvg_list[k-1]["origin_bar"]) <= 2:
                valid_fvg_list[k]["consecutive_count"] = 2

    fvg_strings = []
    for fvg in reversed(valid_fvg_list):
        status = "WICK MITIGATED" if fvg["mitigated"] else "UNMITIGATED 🔥"
        prefix = "IMBALANCE [2+ Stacked]" if fvg.get("consecutive_count", 1) >= 2 else f"{fvg['type']} FVG"
        fvg_strings.append(f"{prefix} ({status}) at {fvg['min']:.5f} - {fvg['max']:.5f}")

    # 2. VEGAlgo OBs & Breakers
    ob_strings = []
    for ob in reversed(confirmed_obs):
        wick_mitigated = False
        
        # Check mitigation status based on current state (OB or Breaker)
        track_start = ob.get('flip_bar', ob['conf_bar'])
        for j in range(track_start + 1, total_bars):
            if not ob['is_breaker']:
                if ob['is_bullish'] and df['low'].iloc[j] <= ob['top']: wick_mitigated = True
                elif not ob['is_bullish'] and df['high'].iloc[j] >= ob['bottom']: wick_mitigated = True
            else:
                if ob['was_bullish'] and df['high'].iloc[j] >= ob['bottom']: wick_mitigated = True # Bearish Breaker
                elif not ob['was_bullish'] and df['low'].iloc[j] <= ob['top']: wick_mitigated = True # Bullish Breaker
                
        status = "WICK MITIGATED" if wick_mitigated else "UNMITIGATED 🔥"
        
        if ob['is_breaker']:
            label = "BEARISH BREAKER" if ob['was_bullish'] else "BULLISH BREAKER"
        else:
            label = "BULLISH OB" if ob['is_bullish'] else "BEARISH OB"
            
        ob_strings.append(f"{label} ({status}) at {ob['bottom']:.5f} - {ob['top']:.5f}")

    # Define Key Target
    key_zone_str = "NO ACTIVE ZONES DETECTED"
    if fvg_strings:
        key_zone_str = f"GAP TARGET: {valid_fvg_list[-1]['min']:.5f}"
    elif confirmed_obs:
        key_zone_str = f"STRUCTURAL TARGET: {confirmed_obs[-1]['top']:.5f}"

    return {
        "fvgs": fvg_strings,
        "obs": ob_strings,
        "key_zone": key_zone_str
    }

# --- EXECUTIVE EXECUTION BRIDGE ---
print("🟢 Booting MSB Structural Tracker (LuxAlgo + VEGAlgo)...")

mt5 = MetaTrader5()
if not mt5.initialize():
    print("🚨 MetaTrader5 Terminal Sync Failed.")
    quit()

print("\n======================================================================")
print(" 🛰️ SMC PINE-REPLICA ENGINE TERMINAL RUN (H1/H4)")
print("======================================================================\n")

for asset, config in WATCHLIST_CONFIG.items():
    rates = mt5.copy_rates_from_pos(asset, config["mt5_tf"], 0, config["lookback_bars"] + 20)
    if rates is None:
        print(f"📡 ASSET: {asset:<10} │ 🚨 DATA FETCH ERROR\n")
        continue
        
    df = pd.DataFrame(rates)
    geo = analyze_merged_geometry(df, config["lookback_bars"])
    
    print(f"📡 ASSET: {asset} ({config['ltf_name']})")
    
    if geo['fvgs']:
        print(f" ├── FVGs:        {geo['fvgs'][0]}")
        for f in geo['fvgs'][1:]:
            print(f" │                {f}")
    else:
        print(f" ├── FVGs:        NO FVG DETECTED")

    if geo['obs']:
        print(f" ├── OB/BREAKERS: {geo['obs'][0]}")
        for s in geo['obs'][1:]:
            print(f" │                {s}")
    else:
        print(f" ├── OB/BREAKERS: NO STRUCTURAL BLOCKS DETECTED")

    print(f" └── KEY LEVEL:   {geo['key_zone']}\n")

print("======================================================================")
mt5.shutdown()
