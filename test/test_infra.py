from infrastructure.mt5_connector import MT5Connector
from config import settings

print("--- 🏗️ TEST INFRASTRUCTURE GEMINI GOLD EYE ---")

# 1. Test Config
print(f"🔑 Clé API chargée : {'OK' if settings.GEMINI_API_KEY else 'MANQUANTE'}")
print(f"📈 Paires à trader : {settings.SYMBOLS}")
print(f"💰 Risque : {settings.RISK_PER_TRADE}%")

# 2. Test MT5
mt5_app = MT5Connector()
if mt5_app.start():
    info = mt5_app.get_account_info()
    if info:
        print(f"💵 Solde du compte : {info.balance} {info.currency}")
        print(f"✅ Levier : 1:{info.leverage}")
    mt5_app.shutdown()
else:
    print("❌ ECHEC Connexion MT5")