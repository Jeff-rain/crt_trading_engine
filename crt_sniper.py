import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

# Terminal Output Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s [PHASE 5] %(message)s', datefmt='%H:%M:%S')

@dataclass
class MarketState:
    macro_trend: str          # "BULLISH" or "BEARISH"
    current_poi: str          # "SUPPLY", "DEMAND", "BEARISH_OB", "BULLISH_OB", "NONE"
    seconds_to_close: int     # Live countdown of the HTF candle
    crt_type: str             # "BULLISH_CRT" or "BEARISH_CRT"
    location_status: str      # "INSIDE_ORIGIN", "NEAR_ORIGIN", "NEAR_TARGET"

@dataclass
class LTFData:
    close_price: float
    zone_high: float
    zone_low: float
    atr: float

class CRTSniperEngine:
    def __init__(self):
        self.active_scan = None
        self.risk_reward_minimum = 3.0

    # ==========================================
    # MODULE 1: DUAL-SCAN ACTIVATION GATE
    # ==========================================
    def check_activation_gate(self, state: MarketState) -> bool:
        """Determines if the engine should actively hunt based on Trend & HTF POI Collision."""
        if state.macro_trend == "BULLISH":
            if state.current_poi in ["SUPPLY", "BEARISH_OB", "BEARISH_FVG"]:
                self.active_scan = "BEARISH_CRT"
                logging.info(f"Counter-Trend Gate OPEN: Scanning for Bearish CRT at {state.current_poi}.")
                return True
            else:
                self.active_scan = "BULLISH_CRT"
                logging.info("Pro-Trend Gate OPEN: Scanning for Bullish CRT.")
                return True

        elif state.macro_trend == "BEARISH":
            if state.current_poi in ["DEMAND", "BULLISH_OB", "BULLISH_FVG"]:
                self.active_scan = "BULLISH_CRT"
                logging.info(f"Counter-Trend Gate OPEN: Scanning for Bullish CRT at {state.current_poi}.")
                return True
            else:
                self.active_scan = "BEARISH_CRT"
                logging.info("Pro-Trend Gate OPEN: Scanning for Bearish CRT.")
                return True
        return False

    # ==========================================
    # MODULE 2: PRE-CLOSE SCALEDOWN
    # ==========================================
    def trigger_scaledown(self, seconds_to_close: int) -> bool:
        """Drops to LTF 5-10 seconds before the HTF candle closes (The Front-Runner)."""
        if 0 < seconds_to_close <= 10:
            logging.info(f"⏳ Scaledown Ignited! T-Minus {seconds_to_close}s. Dropping to LTF mapping...")
            return True
        return False

    # ==========================================
    # MODULE 3: CRT ALIGNMENT & LOCATION SCORECARD
    # ==========================================
    def grade_setup(self, state: MarketState) -> Tuple[int, str]:
        """Calculates the 100-point metric and assigns A, B, or C tier."""
        trend_score = 0
        location_score = 0

        # Part 1: Trend Alignment (Max 40 Points)
        is_pro_trend = (state.macro_trend == "BULLISH" and state.crt_type == "BULLISH_CRT") or \
                       (state.macro_trend == "BEARISH" and state.crt_type == "BEARISH_CRT")
        
        if is_pro_trend:
            trend_score = 40
        elif state.current_poi != "NONE":
            trend_score = 20  # Counter-trend at valid POI
        else:
            return 0, "INVALID" # Suppressed: Counter-trend in the middle of nowhere

        # Part 2: Spatial Location (Max 60 Points)
        if state.location_status == "INSIDE_ORIGIN":
            location_score = 60
        elif state.location_status == "NEAR_ORIGIN":
            location_score = 40
        elif state.location_status == "NEAR_TARGET":
            location_score = 10

        total_score = trend_score + location_score

        # 3-Tier Grading Matrix
        if total_score >= 80:
            grade = "🟢 [GRADE 1] A-TIER: PRISTINE"
        elif 60 <= total_score <= 79:
            grade = "🟡 [GRADE 2] B-TIER: STANDARD"
        else:
            grade = "🔴 [GRADE 3] C-TIER: CAUTION / TRUNCATION RISK"

        logging.info(f"Scorecard Evaluated: [{total_score}/100] -> {grade}")
        return total_score, grade

    # ==========================================
    # MODULE 4: MICRO "TAP & CLOSE" TRIGGER
    # ==========================================
    def ltf_execution_trigger(self, ltf: LTFData, crt_direction: str) -> str:
        """Evaluates LTF candle close for Perfect Absorption, Heavy Rejection, or Deep Penetration."""
        # --- BULLISH LTF LOGIC ---
        if crt_direction == "BULLISH_CRT":
            if ltf.zone_low <= ltf.close_price <= ltf.zone_high:
                return "EXECUTE: Perfect Absorption (Closed Inside)"
            elif ltf.close_price > ltf.zone_high + 0.0002: # Spiked but closed > 2 pips away
                return "HALT: Heavy Rejection (Patience Protocol)"
            elif ltf.close_price < ltf.zone_low: # Closed below the zone completely
                return "FREEZE: Deep Penetration (Wait for recovery)"
                
        # --- BEARISH LTF LOGIC ---
        elif crt_direction == "BEARISH_CRT":
            if ltf.zone_low <= ltf.close_price <= ltf.zone_high:
                return "EXECUTE: Perfect Absorption (Closed Inside)"
            elif ltf.close_price < ltf.zone_low - 0.0002: # Spiked but closed > 2 pips below
                return "HALT: Heavy Rejection (Patience Protocol)"
            elif ltf.close_price > ltf.zone_high: # Closed above the zone completely
                return "FREEZE: Deep Penetration (Wait for recovery)"
                
        return "WAITING_FOR_DATA"

    # ==========================================
    # MODULE 5: DYNAMIC RISK ARMOR & RR ENFORCER
    # ==========================================
    def assign_risk_armor(self, entry_price: float, ltf_atr: float, crt_direction: str, htf_target: float):
        """Attaches dynamic SL and mathematically enforces the 1:3 RR minimum."""
        # Calculate Dynamic SL: Zone Boundary +/- (0.5 * LTF ATR)
        atr_fraction = ltf_atr * 0.5 
        
        if crt_direction == "BULLISH_CRT":
            stop_loss = entry_price - atr_fraction
            risk = entry_price - stop_loss
            reward = htf_target - entry_price
        else:
            stop_loss = entry_price + atr_fraction
            risk = stop_loss - entry_price
            reward = entry_price - htf_target

        current_rr = reward / risk if risk > 0 else 0

        if current_rr < self.risk_reward_minimum:
            logging.warning(f"Natural RR ({current_rr:.2f}) < 1:3. Enforcing mathematical RR boundary.")
            if crt_direction == "BULLISH_CRT":
                htf_target = entry_price + (risk * self.risk_reward_minimum)
            else:
                htf_target = entry_price - (risk * self.risk_reward_minimum)
        
        logging.info(f"Risk Armor Attached | ENTRY: {entry_price:.5f} | SL: {stop_loss:.5f} | TP: {htf_target:.5f}")
        return stop_loss, htf_target

# ==========================================
# DAEMON EXECUTION LOOP (Local Testing Block)
# ==========================================
if __name__ == "__main__":
    print("\n=======================================================")
    print(" 🎯 BOOTING PHASE 5: CRT SNIPER EXECUTION ENGINE")
    print("=======================================================\n")
    
    engine = CRTSniperEngine()
    
    # 1. Simulating a live market feed collision (e.g., Bearish CRT at a Bullish Trend Supply Zone)
    current_market = MarketState(
        macro_trend="BULLISH",
        current_poi="SUPPLY",
        seconds_to_close=8,
        crt_type="BEARISH_CRT",
        location_status="INSIDE_ORIGIN"
    )

    # 2. Run the Engine Pipeline
    if engine.check_activation_gate(current_market):
        if engine.trigger_scaledown(current_market.seconds_to_close):
            score, grade = engine.grade_setup(current_market)
            
            if score >= 60: # Only execute A and B tiers systematically
                # 3. Simulate LTF Price Action pulling back into the mapped zone
                ltf_feed = LTFData(close_price=1.1050, zone_high=1.1060, zone_low=1.1040, atr=0.0010)
                
                trigger_action = engine.ltf_execution_trigger(ltf_feed, current_market.crt_type)
                logging.info(f"LTF Trigger Status: {trigger_action}")
                
                # 4. Fire Execution and Risk Parameters
                if "EXECUTE" in trigger_action:
                    engine.assign_risk_armor(
                        entry_price=1.1050, 
                        ltf_atr=0.0010, 
                        crt_direction=current_market.crt_type, 
                        htf_target=1.1010 # Original opposing CRT boundary
                    )
    print("\n=======================================================")
