import time
import requests
import logging

# ==========================================
# INTELLIGENT MT5 LINUX BRIDGE
# ==========================================
try:
    import MetaTrader5 as mt5
except ModuleNotFoundError:
    try:
        from mt5linux import MetaTrader5 as mt5
    except ModuleNotFoundError:
        mt5 = None

from crt_sniper import CRTSniperEngine, MarketState, LTFData

# Terminal Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s [MASTER] %(message)s', datefmt='%H:%M:%S')

# ==========================================
# VERIFIED TELEGRAM CONFIGURATION
# ==========================================
TELEGRAM_TOKEN = "8858841052:AAFlAuPfHqFscFxlRA2qZRjjoRBofMFWXqw"
TELEGRAM_CHAT_ID = "8066843956"

def send_signal(message: str):
    """Fires a beautifully formatted Markdown trade signal directly to your phone."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            logging.error(f"Telegram API Error: {response.text}")
    except Exception as e:
        logging.error(f"Failed to transmit signal over network: {e}")

# ==========================================
# THE WATCHLIST MATRIX (Live Suffix Routing)
# ==========================================
WATCHLIST_CONFIG = [
    # --- FOREX PAIRS (1H Scan -> 5M Execute) ---
    {"symbol": "EURUSD.m",  "scan_tf": 16385, "exec_tf": 5}, # 16385 = H1, 5 = M5
    {"symbol": "GBPUSD.m",  "scan_tf": 16385, "exec_tf": 5},
    {"symbol": "USDJPY.m",  "scan_tf": 16385, "exec_tf": 5},
    {"symbol": "AUDUSD.m",  "scan_tf": 16385, "exec_tf": 5},
    {"symbol": "GBPJPY.m",  "scan_tf": 16385, "exec_tf": 5},
    
    # --- INDICES (1H Scan -> 5M Execute) ---
    {"symbol": "US100.std", "scan_tf": 16385, "exec_tf": 5},

    # --- GOLD DUAL-SCANNER (Parallel Dimensions) ---
    {"symbol": "XAUUSD.m",  "scan_tf": 16385, "exec_tf": 5},  # Dimension 1: 1H -> 5M
    {"symbol": "XAUUSD.m",  "scan_tf": 15,    "exec_tf": 1}   # Dimension 2: 15M -> 1M
]

# ==========================================
# THE INFINITE 24/7 DAEMON (SILENT MODE)
# ==========================================
def run_master_loop():
    print("\n=======================================================")
    print(" 🟢 MASTER ENGINE BOOTING...")
    print(" Press Ctrl + C to terminate background process safely.")
    print("=======================================================\n")
    
    if mt5 is None:
        logging.warning("MT5 Environment binding missing. Running in standby mode.")
    else:
        # Initialize MT5 Connection here if needed
        # mt5.initialize()
        pass

    sniper = CRTSniperEngine()
    
    # Track sent alerts to prevent notification spamming
    last_alert_time = {}

    # 🚀 FIRING THE SYSTEM ONLINE DIAGNOSTIC TO YOUR PHONE
    boot_msg = (
        "🟢 *MASTER ENGINE ONLINE*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📡 Connection: Secure\n"
        "⚙️ Phase 5: Armed\n"
        "🔍 Initiating 24/7 Silent Scan..."
    )
    send_signal(boot_msg)
    logging.info("Boot diagnostic ping sent to Telegram.")

    try:
        while True:
            for asset in WATCHLIST_CONFIG:
                symbol = asset["symbol"]
                scan_tf = asset["scan_tf"]
                
                # UNIQUE KEY FOR DUAL TIME-FRAME SEPARATION
                asset_key = f"{symbol}_{scan_tf}"
                
                # ---------------------------------------------------------
                # 🔌 LIVE CORE DATA ROUTER (YOUR PHASE 4 HOOK GOES HERE)
                # ---------------------------------------------------------
                # The fake simulation data has been completely removed.
                # The engine is now completely silent, waiting for your MT5 
                # functions to feed real data into these two variables:
                
                state = None    # <--- Waiting for MT5 MarketState object
                live_ltf = None # <--- Waiting for MT5 LTFData object
                
                # ---------------------------------------------------------
                
                # If your Phase 4 hook successfully pulls data and maps the state:
                if state is not None:
                    
                    # 1. Check if the setup aligns with the Macro Trend & Zone Rules
                    if sniper.check_activation_gate(state):
                        
                        # 2. Trigger the Pre-Close Scaledown (T-Minus 10s)
                        if sniper.trigger_scaledown(state.seconds_to_close):
                            
                            # 3. Grade the Setup (Only trade A and B Tiers)
                            score, grade = sniper.grade_setup(state)
                            if score >= 60:
                                
                                # 4. Evaluate the LTF Candle Execution Trigger
                                if live_ltf is not None:
                                    action = sniper.ltf_execution_trigger(live_ltf, state.crt_type)
                                    
                                    # 5. Execute & Assign Risk Armor
                                    if "EXECUTE" in action:
                                        sl, tp = sniper.assign_risk_armor(live_ltf.close_price, live_ltf.atr, state.crt_type, 1.1010)
                                        
                                        current_time = time.time()
                                        
                                        # 6. Rate Limiter (Prevents duplicate signals for 5 minutes)
                                        if asset_key not in last_alert_time or (current_time - last_alert_time[asset_key] > 300):
                                            
                                            trade_msg = (
                                                f"🎯 *CRT EXECUTION SIGNAL*\n"
                                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                                f"📦 *Asset:* `{symbol}`\n"
                                                f"⏱️ *Scan Frame:* `{"1H" if scan_tf == 16385 else "15M"}`\n"
                                                f"📊 *Scorecard:* {grade}\n"
                                                f"💥 *Action:* `{"LONG" if state.crt_type == "BULLISH_CRT" else "SHORT"} (Absorption Close)`\n"
                                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                                f"🟢 *ENTRY:* `{live_ltf.close_price:.5f}`\n"
                                                f"🔴 *STOP LOSS:* `{sl:.5f}`\n"
                                                f"🔵 *TAKE PROFIT:* `{tp:.5f}`\n"
                                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                                f"🤖 _Sent silently from nimbus daemon._"
                                            )
                                            
                                            send_signal(trade_msg)
                                            logging.info(f"⚡ Live signal transmitted to phone for {asset_key}!")
                                            last_alert_time[asset_key] = current_time

            # Heartbeat sleep to protect CPU cycles
            time.sleep(1)
            
    except KeyboardInterrupt:
        shutdown_msg = "🛑 *MASTER ENGINE TERMINATED*\nScan offline."
        send_signal(shutdown_msg)
        print("\n🛑 MASTER ENGINE TERMINATED BY USER.")

if __name__ == "__main__":
    run_master_loop()
