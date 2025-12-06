import MetaTrader5 as mt5
import sys
import os

# Setup des chemins pour importer la config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import settings

print("--- 🕵️ DÉTECTIVE DE SYMBOLES ---")

if not mt5.initialize():
    print("❌ Erreur Init MT5")
    exit()

if not mt5.login(settings.MT5_LOGIN, password=settings.MT5_PASSWORD, server=settings.MT5_SERVER):
    print("❌ Erreur Login")
    exit()

print(f"✅ Connecté à {settings.MT5_SERVER}")

# 1. Chercher tout ce qui contient "EURUSD"
print("\n🔍 Recherche de 'EURUSD' dans la base de données du courtier...")
all_symbols = mt5.symbols_get()
matches = [s.name for s in all_symbols if "EUR" in s.name and "USD" in s.name]

if matches:
    print(f"✅ J'ai trouvé {len(matches)} variantes possibles :")
    for name in matches:
        print(f"   👉 '{name}'")
        
    print("\n⚠️ REGARDE BIEN : Est-ce que c'est 'EURUSD' ou 'EURUSD.m' ou 'EURUSDpro' ?")
else:
    print("❌ AUCUN symbole EUR/USD trouvé ! Ton courtier est vide ?")

# 2. Test spécifique sur ta config actuelle
target = settings.SYMBOLS[0]
print(f"\n🎯 Test sur ton réglage actuel : '{target}'")
selected = mt5.symbol_select(target, True)

if selected:
    print(f"   ✅ VICTOIRE : MT5 a réussi à sélectionner '{target}' !")
else:
    print(f"   ❌ ÉCHEC : MT5 refuse de sélectionner '{target}'.")
    err = mt5.last_error()
    print(f"   Code erreur MT5 : {err}")

mt5.shutdown()