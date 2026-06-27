import pandas as pd
import numpy as np
from mt5linux import MetaTrader5

# 🏛️ Multi-Timeframe Asset Matrix
WATCHLIST_CONFIG = {
    "XAUUSD.m":  {"ltf": MetaTrader5.TIMEFRAME_H1, "htf": MetaTrader5.TIMEFRAME_H4, "ltf_name": "H1", "htf_name": "H4", "pip_val": 0.1},
    "EURUSD.m":  {"ltf": MetaTrader5.TIMEFRAME_H4, "htf": MetaTrader5.TIMEFRAME_D1, "ltf_name": "H4", "htf_name": "D1", "pip_val": 0.0001},
    "GBPUSD.m":  {"ltf": MetaTrader5.TIMEFRAME_H4, "htf": MetaTrader5.TIMEFRAME_D1, "ltf_name": "H4", "htf_name": "D1", "pip_val": 0.0001},
    "USDJPY.m":  {"ltf": MetaTrader5.TIMEFRAME_H4, "htf": MetaTrader5.TIMEFRAME_D1, "ltf_name": "H4", "htf_name": "D1", "pip_val": 0.01},
    "AUDUSD.m":  {"ltf": MetaTrader5.TIMEFRAME_H4, "htf": MetaTrader5.TIMEFRAME_D1, "ltf_name": "H4", "htf_name": "D1", "pip_val": 0.0001},
    "US100.std": {"ltf": MetaTrader5.TIMEFRAME_H4, "htf": MetaTrader5.TIMEFRAME_D1, "ltf_name": "H4", "htf_name": "D1", "pip_val": 1.0}
}

def get_macro_trend(mt5, symbol, htf):
    rates = mt5.copy_rates_from_pos(symbol, htf, 0, 100)
    if rates is None: return "UNKNOWN"
    df = pd.DataFrame(rates)
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    if df['close'].iloc[-1] > df['ema50'].iloc[-1] and df['ema20'].iloc[-1] > df['ema50'].iloc[-1]: return "BULLISH"
    elif df['close'].iloc[-1] < df['ema50'].iloc[-1] and df['ema20'].iloc[-1] < df['ema50'].iloc[-1]: return "BEARISH"
    else: return "RANGING"

def get_internal_structure_and_zones(mt5, symbol, ltf):
    """Integrates exact Phase 3 Algorithm (LuxAlgo + VEGAlgo)"""
    rates = mt5.copy_rates_from_pos(symbol, ltf, 0, 250)
    if rates is None: return None
    df = pd.DataFrame(rates)
    total_bars = len(df)
    
    df['hl'] = df['high'] - df['low']
    df['hc'] = (df['high'] - df['close'].shift()).abs()
    df['lc'] = (df['low'] - df['close'].shift()).abs()
    df['tr'] = df[['hl', 'hc', 'lc']].max(axis=1)
    current_atr = df['tr'].rolling(14).mean().iloc[-1]
    current_price = df['close'].iloc[-1]
    
    internal_trend = "BULLISH" if df['close'].iloc[-1] > df['close'].iloc[-5] else "BEARISH"
    
    active_fvgs = []
    swing_length = 5
    last_sh = None; last_sh_bar = None; sh_breached = False
    last_sl = None; last_sl_bar = None; sl_breached = False
    pending_obs = []
    confirmed_obs = []

    # Phase 3 Scanning Engine
    for i in range(20, total_bars):
        c_low = df['low'].iloc[i]; c_high = df['high'].iloc[i]; c_close = df['close'].iloc[i]
        prev_close = df['close'].iloc[i-1]
        past_high = df['high'].iloc[i-2]; past_low = df['low'].iloc[i-2]

        # FVG
        if c_low > past_high and prev_close > past_high:
            active_fvgs.append({"type": "BULLISH FVG", "top": c_low, "bot": past_high, "origin_bar": i})
        elif c_high < past_low and prev_close < past_low:
            active_fvgs.append({"type": "BEARISH FVG", "top": past_low, "bot": c_high, "origin_bar": i})

        # VEGAlgo Swings
        if i >= swing_length * 2:
            window_highs = df['high'].iloc[i - (swing_length*2) : i + 1]
            if df['high'].iloc[i - swing_length] == window_highs.max():
                last_sh = df['high'].iloc[i - swing_length]; last_sh_bar = i - swing_length; sh_breached = False
            window_lows = df['low'].iloc[i - (swing_length*2) : i + 1]
            if df['low'].iloc[i - swing_length] == window_lows.min():
                last_sl = df['low'].iloc[i - swing_length]; last_sl_bar = i - swing_length; sl_breached = False

        if last_sh is not None and not sh_breached and c_high > last_sh: sh_breached = True
        if last_sl is not None and not sl_breached and c_low < last_sl: sl_breached = True

        if sh_breached and not any(p['is_bullish'] and abs(p['level'] - last_sh) < 0.0001 for p in pending_obs):
            for j in range(1, 51):
                chk_bar = i - j
                if chk_bar <= last_sh_bar: break
                if df['close'].iloc[chk_bar] < df['open'].iloc[chk_bar]:
                    pending_obs.append({'level': last_sh, 'ob_bar': chk_bar, 'top': df['high'].iloc[chk_bar], 'bot': df['low'].iloc[chk_bar], 'is_bullish': True})
                    break

        if sl_breached and not any(not p['is_bullish'] and abs(p['level'] - last_sl) < 0.0001 for p in pending_obs):
            for j in range(1, 51):
                chk_bar = i - j
                if chk_bar <= last_sl_bar: break
                if df['close'].iloc[chk_bar] > df['open'].iloc[chk_bar]:
                    pending_obs.append({'level': last_sl, 'ob_bar': chk_bar, 'top': df['high'].iloc[chk_bar], 'bot': df['low'].iloc[chk_bar], 'is_bullish': False})
                    break

        # MSB Confirmations
        bullish_msb = last_sh is not None and c_close > last_sh and prev_close <= last_sh
        bearish_msb = last_sl is not None and c_close < last_sl and prev_close >= last_sl
        
        active_pending = []
        for p in pending_obs:
            if p['is_bullish'] and bullish_msb and abs(p['level'] - last_sh) < 0.0001:
                confirmed_obs.append({'top': p['top'], 'bot': p['bot'], 'conf_bar': i, 'is_bullish': True, 'is_breaker': False, 'was_bullish': True})
            elif not p['is_bullish'] and bearish_msb and abs(p['level'] - last_sl) < 0.0001:
                confirmed_obs.append({'top': p['top'], 'bot': p['bot'], 'conf_bar': i, 'is_bullish': False, 'is_breaker': False, 'was_bullish': False})
            else:
                active_pending.append(p)
        pending_obs = active_pending

        # Breakers
        surviving_obs = []
        for ob in confirmed_obs:
            chop = False
            if not ob['is_breaker']:
                if ob['is_bullish'] and c_close < ob['bot']: ob['is_breaker'] = True; ob['flip_bar'] = i
                elif not ob['is_bullish'] and c_close > ob['top']: ob['is_breaker'] = True; ob['flip_bar'] = i
            elif ob['is_breaker']:
                if ob['was_bullish'] and c_close > ob['top']: chop = True
                elif not ob['was_bullish'] and c_close < ob['bot']: chop = True
            if not chop: surviving_obs.append(ob)
        confirmed_obs = surviving_obs

    # --- Mitigation Filter ---
    unmitigated_zones = []
    
    for fvg in active_fvgs:
        ramped = False
        for j in range(fvg["origin_bar"], total_bars):
            if fvg["type"] == "BULLISH FVG" and df['close'].iloc[j] < fvg["bot"]: ramped = True; break
            elif fvg["type"] == "BEARISH FVG" and df['close'].iloc[j] > fvg["top"]: ramped = True; break
        if not ramped:
            fvg["pos"] = fvg["top"] if "BULLISH" in fvg["type"] else fvg["bot"]
            fvg["dist"] = abs(current_price - fvg["pos"])
            unmitigated_zones.append(fvg)

    for ob in confirmed_obs:
        ramped = False
        track_start = ob.get('flip_bar', ob['conf_bar'])
        for j in range(track_start + 1, total_bars):
            if not ob['is_breaker']:
                if ob['is_bullish'] and df['close'].iloc[j] < ob['bot']: ramped = True; break
                elif not ob['is_bullish'] and df['close'].iloc[j] > ob['top']: ramped = True; break
            else:
                if ob['was_bullish'] and df['close'].iloc[j] > ob['top']: ramped = True; break # Bearish Breaker
                elif not ob['was_bullish'] and df['close'].iloc[j] < ob['bot']: ramped = True; break # Bullish Breaker
        if not ramped:
            z_type = "BEARISH BREAKER" if (ob['is_breaker'] and ob['was_bullish']) else "BULLISH BREAKER" if ob['is_breaker'] else "BULLISH OB" if ob['is_bullish'] else "BEARISH OB"
            pos = ob["top"] if "BULLISH" in z_type else ob["bot"]
            unmitigated_zones.append({"type": z_type, "top": ob['top'], "bot": ob['bot'], "pos": pos, "dist": abs(current_price - pos)})

    return {"trend": internal_trend, "atr": current_atr, "price": current_price, "zones": unmitigated_zones}

def evaluate_setup(macro, struct_data, pip_val):
    internal = struct_data['trend']
    c_price = struct_data['price']
    zones = struct_data['zones']
    
    score = 0
    
    # 1. MACRO & STRUCTURE ALIGNMENT
    if macro == "BULLISH" and internal == "BULLISH":
        score += 35; m_str = "📈 BULLISH | PRO-TREND CONTINUATION (+35 Pts)"; s_str = "📈 SHIFT UP (Bullish Continuation)"; target_bias = "BULLISH" 
    elif macro == "BULLISH" and internal == "BEARISH":
        score += 25; m_str = "📈 BULLISH | PRO-TREND RETRACEMENT (+25 Pts)"; s_str = "📉 SHIFT DOWN (Bearish Retracement to Downside)"; target_bias = "BULLISH"
    elif macro == "BEARISH" and internal == "BEARISH":
        score += 35; m_str = "📉 BEARISH | PRO-TREND CONTINUATION (+35 Pts)"; s_str = "📉 SHIFT DOWN (Bearish Continuation)"; target_bias = "BEARISH" 
    elif macro == "BEARISH" and internal == "BULLISH":
        score += 25; m_str = "📉 BEARISH | PRO-TREND RETRACEMENT (+25 Pts)"; s_str = "📈 SHIFT UP (Bullish Retracement to Upside)"; target_bias = "BEARISH" 
    else:
        m_str = "⚠️ RANGING | CAUTION (0 Pts)"; s_str = f"CHOPPY {internal}"; target_bias = "BULLISH" if internal == "BEARISH" else "BEARISH"

    # 2. ZONE MAPPING (ABOVE & BELOW)
    above_zones = sorted([z for z in zones if z['pos'] > c_price], key=lambda x: x['dist'])
    below_zones = sorted([z for z in zones if z['pos'] < c_price], key=lambda x: x['dist'])

    above_str = ", ".join([f"{z['type']} (UNMITIGATED 🔥){{{z['bot']:.5f} - {z['top']:.5f}}}" for z in above_zones[:2]]) if above_zones else "None"
    below_str = ", ".join([f"{z['type']} (UNMITIGATED 🔥){{{z['bot']:.5f} - {z['top']:.5f}}}" for z in below_zones[:2]]) if below_zones else "None"

    # 3. EXECUTION LOGIC (Target edge of zone, 2 Pips SL, 1:3 RR TP)
    valid_targets = below_zones if target_bias == "BULLISH" else above_zones
    opposing_targets = above_zones if target_bias == "BULLISH" else below_zones
    
    if valid_targets:
        target = valid_targets[0] # Grab the closest unmitigated zone
        score += 30
        
        # Calculate Entry and SL
        entry_price = target['top'] if target_bias == "BULLISH" else target['bot']
        sl_price = target['bot'] - (2 * pip_val) if target_bias == "BULLISH" else target['top'] + (2 * pip_val)
        risk = abs(entry_price - sl_price)
        
        # Calculate TP (Equilibrium of Opposing Zone)
        if opposing_targets:
            tp_zone = opposing_targets[0]
            tp_eq = (tp_zone['top'] + tp_zone['bot']) / 2
            reward = abs(tp_eq - entry_price)
            rr = reward / risk if risk > 0 else 0
            
            # Enforce 1:3 RR
            if rr >= 3:
                tp_price = tp_eq
                tp_str = f"TP: to {tp_zone['type']} Equilibrium at {tp_price:.5f} (1:{rr:.1f} RR)"
            else:
                tp_price = entry_price + (3 * risk) if target_bias == "BULLISH" else entry_price - (3 * risk)
                tp_str = f"TP: Mechanical 1:3 at {tp_price:.5f} (Opposing zone too close)"
        else:
            tp_price = entry_price + (3 * risk) if target_bias == "BULLISH" else entry_price - (3 * risk)
            tp_str = f"TP: Mechanical 1:3 at {tp_price:.5f} (No opposing zones)"

        action_str = f"EXECUTE at {target['type']} (UNMITIGATED 🔥){{{target['bot']:.5f} - {target['top']:.5f}}}\n │              ↳ {tp_str}\n │              ↳ SL: {sl_price:.5f} (2 pips buffer)"
    else:
        action_str = "SIT ON HANDS. NO VALID TARGET ZONES."

    score += 15 
    if score >= 80: grade = f"[{score}/100] 🟢 A+ KILLZONE"
    elif score >= 60: grade = f"[{score}/100] 🟡 B-GRADE SETUP"
    else: grade = f"[{score}/100] 🔴 WEAK TIER (CAUTION)"
        
    return m_str, s_str, above_str, below_str, grade, action_str

# --- EXECUTIVE EXECUTION BRIDGE ---
print("🟢 Booting Phase 4: Macro Bias & Scoring Engine...")

mt5 = MetaTrader5()
if not mt5.initialize():
    print("🚨 MetaTrader5 Terminal Sync Failed.")
    quit()

print("\n======================================================================")
print(" 🧠 ALGORITHMIC EXECUTION MATRIX (H4/D1 MACRO SHIELD)")
print("======================================================================\n")

for asset, config in WATCHLIST_CONFIG.items():
    macro_trend = get_macro_trend(mt5, asset, config['htf'])
    struct_data = get_internal_structure_and_zones(mt5, asset, config['ltf'])
    
    if struct_data is None: continue
        
    m_str, s_str, above_str, below_str, grade, action = evaluate_setup(macro_trend, struct_data, config['pip_val'])
    
    print(f"📡 ASSET: {asset} ({config['ltf_name']}/{config['htf_name']})")
    print(f" ├── MACRO:     {m_str}")
    print(f" ├── STRUCTURE: {s_str}")
    print(f" ├── MAP ABOVE: {above_str}")
    print(f" ├── MAP BELOW: {below_str}")
    print(f" ├── SCORE:     {grade}")
    print(f" └── ACTION:    {action}\n")

print("======================================================================")
mt5.shutdown()
