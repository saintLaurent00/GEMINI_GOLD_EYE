import os
from dotenv import load_dotenv

load_dotenv()

# --- 1. API KEYS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")

MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

 # --- 2. TRADING SETTINGS ---
 # On transforme la string "EURUSD,GBPUSD" en liste ['EURUSD', 'GBPUSD']
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS_LIST", "AUDCAD,USDJPY,USDCHF,XAUUSD").split(",") if s.strip()]

RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "1.0")) # 2.0%
MODE_SNIPER = os.getenv("MODE_SNIPER", "True") == "True"    # Conversion en Booléen

 # Seuils de gestion (en Points MT5)
BE_TRIGGER = int(os.getenv("BE_TRIGGER", "300"))
TRAILING_DIST = int(os.getenv("TRAILING_DIST", "300"))

 # --- 3. ARCHITECTURE TEMPORELLE (H4 TRIGGER) ---
 # Le bot se réveille sur le H4, mais analyse tout ça :
