import pandas as pd
from datetime import datetime
from crt_sniper import MarketState, LTFData

# We import your exact Phase 4 algorithms so we don't have to rewrite the math
from bias_engine import get_macro_trend, get_internal_structure_and_zones

class CRTDataBridge:
    def __init__(self, mt5_client):
        self.mt5 = mt5_client

    def get_seconds_to_close(self, symbol: str, timeframe: int) -> int:
        """Calculates exact seconds remaining until the HTF candle closes."""
        rates = self.mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
        if rates is None or len(rates) == 0: return 9999
        
        candle_open_time = rates[0]['time']
        
        # Calculate timeframe duration in seconds
        if timeframe == 16385: tf_seconds = 3600  # H1
        elif timeframe == 15: tf_seconds = 900    # M15
        else: tf_seconds = 3600

        candle_close_time = candle_open_time + tf_seconds
        current_time = datetime.utcnow().timestamp()
        
        return int(candle_close_time - current_time)

    def build_htf_state(self, symbol: str, scan_tf: int, macro_tf: int) -> MarketState:
        """
        THE ENVIRONMENT: Maps the HTF SMC to lock the directional bias and find the overarching trap.
        """
        # 1. Pull Phase 4 Trend (e.g., D1 or H4)
        trend = get_macro_trend(self.mt5, symbol, macro_tf)
        
        # 2. Pull Phase 4 HTF SMC Structure (e.g., H1 or M15)
        structure = get_internal_structure_and_zones(self.mt5, symbol, scan_tf)
        if structure is None or len(structure['zones']) == 0:
            return None # Blind, no zones found
            
        current_price = structure['price']
        closest_zone = structure['zones'][0] # Grabs the absolute closest unmitigated HTF zone
        
        # 3. Translate string data to Phase 5 Engine Enums
        # (e.g., "BEARISH OB" -> "BEARISH_OB", "BULLISH FVG" -> "BULLISH_FVG")
        poi_type = closest_zone['type'].replace(" ", "_")
        
        # 4. Proximity & Location Tagging
        if closest_zone['bot'] <= current_price <= closest_zone['top']:
            location = "INSIDE_ORIGIN"
        elif closest_zone['dist'] < 0.0010: # Within 10 pips
            location = "NEAR_ORIGIN"
        else:
            location = "NEAR_TARGET" # Too far away, likely hitting opposite liquidity

        # 5. Live Candle Countdown
        sec_to_close = self.get_seconds_to_close(symbol, scan_tf)

        # 6. Assume a CRT is forming (Phase 5 will filter it out if invalid)
        crt_type = "BEARISH_CRT" if "SUPPLY" in poi_type or "BEARISH" in poi_type else "BULLISH_CRT"

        return MarketState(
            macro_trend=trend,
            current_poi=poi_type,
            seconds_to_close=sec_to_close,
            crt_type=crt_type,
            location_status=location
        )

    def build_ltf_execution_data(self, symbol: str, exec_tf: int) -> LTFData:
        """
        THE SURGERY: Maps the LTF SMC specifically looking for the micro-FVG or micro-OB 
        created during the manipulation wick to be used as the strict execution zone.
        """
        # Run the exact same Phase 4 math, but strictly on the 5Min or 1Min chart
        ltf_structure = get_internal_structure_and_zones(self.mt5, symbol, exec_tf)
        if ltf_structure is None or len(ltf_structure['zones']) == 0:
            return None
            
        current_price = ltf_structure['price']
        ltf_atr = ltf_structure['atr']
        
        # Find the immediate LTF SMC zone created by the CRT drop/pump
        micro_zone = ltf_structure['zones'][0] 
        
        return LTFData(
            close_price=current_price,
            zone_high=micro_zone['top'],
            zone_low=micro_zone['bot'],
            atr=ltf_atr
        )
