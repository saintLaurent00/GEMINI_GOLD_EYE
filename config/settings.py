import os
from dotenv import load_dotenv
import MetaTrader5 as mt5

# Chargement des variables d'environnement
load_dotenv()

# --- 1. CREDENTIALS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")

MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

# --- OANDA (broker cloud, fonctionne sans MT5/VPS) ---
OANDA_API_TOKEN = os.getenv("OANDA_API_TOKEN", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_PRACTICE = os.getenv("OANDA_PRACTICE", "True") == "True"  # True = compte démo

# --- 2. TRADING SETTINGS ---
# On transforme la string "EURUSD,GBPUSD" en liste ['EURUSD', 'GBPUSD']
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS_LIST", "AUDCAD,USDJPY,USDCHF,XAUUSD").split(",") if s.strip()]

RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "1.0")) # 2.0%
MODE_SNIPER = os.getenv("MODE_SNIPER", "True") == "True"    # Conversion en Booléen

# Seuils de gestion (en Points MT5)
BE_TRIGGER = int(os.getenv("BE_TRIGGER", "300"))
TRAILING_DIST = int(os.getenv("TRAILING_DIST", "300"))

# --- 3. ARCHITECTURE TEMPORELLE ---
# Bougie qui "réveille" le bot (détection de nouvelle bougie)
TIMEFRAME_TRIGGER = mt5.TIMEFRAME_H4
# NB : les timeframes de VISION (images IA) vivent dans config/symbols.py
#     (source de vérité unique -> plus de conflit H4/H1)

# Modèle IA
MODEL_NAME = "gemini-2.5-flash"

# --- 4. PROTECTION COMPTE PROP-FIRM (circuit-breaker) ---
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "4.0"))   # perte journalière max (%)
MAX_DAILY_TRADES   = int(os.getenv("MAX_DAILY_TRADES", "5"))         # trades/jour max
MAX_CONSEC_LOSSES  = int(os.getenv("MAX_CONSEC_LOSSES", "3"))       # pertes consécutives max
MAGIC_NUMBER       = int(os.getenv("MAGIC_NUMBER", "777888"))        # identifiant des ordres du bot