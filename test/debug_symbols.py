import MetaTrader5 as mt5
from config import settings

print("--- 🕵️ DIAGNOSTIC SYMBOLES MT5 ---")

if not mt5.initialize():
    print("❌ Erreur init MT5")
    quit()

if not mt5.login(settings.MT5_LOGIN, password=settings.MT5_PASSWORD, server=settings.MT5_SERVER):
    print("❌ Erreur Login")
    quit()

print("✅ Connecté. Recherche des symboles...")

# 1. Lister tous les symboles disponibles
symbols = mt5.symbols_get()
print(f"📦 Total symboles trouvés chez le courtier : {len(symbols)}")

# 2. Chercher ceux qui contiennent "EURUSD"
found = [s.name for s in symbols if "EURUSD" in s.name]
print(f"🔎 Variantes de EURUSD trouvées : {found}")

# 3. Vérifier si le symbole configuré existe
target = settings.SYMBOLS[0] # Le premier de ta liste
info = mt5.symbol_info(target)

if info:
    print(f"✅ Le symbole '{target}' EXISTE bien.")
    print(f"   - Visible dans le Market Watch ? {info.visible}")
    print(f"   - Données dispos ? {info.select}")
    
    # Tentative de forcer la visibilité
    if not info.visible:
        print("   ⚠️ Le symbole était caché. Tentative d'activation...")
        if mt5.symbol_select(target, True):
            print("   ✅ Symbole activé avec succès !")
        else:
            print("   ❌ Impossible d'activer le symbole.")
else:
    print(f"❌ LE SYMBOLE '{target}' N'EXISTE PAS SOUS CE NOM !")
    print("👉 Modifie ton fichier .env avec le nom trouvé en point 2.")

mt5.shutdown()