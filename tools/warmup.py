import sys
import os
import time
import MetaTrader5 as mt5

# Ajout du dossier parent au path pour importer config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import settings

def warmup_symbol(symbol):
    print(f"\n🔥 Préchauffage de : {symbol}...")
    
    # On force la sélection
    if not mt5.symbol_select(symbol, True):
        print(f"   ❌ Impossible de sélectionner {symbol}")
        return False

    # Liste des timeframes à synchroniser
    timeframes = [
        (mt5.TIMEFRAME_W1, "W1"),
        (mt5.TIMEFRAME_D1, "D1"),
        (mt5.TIMEFRAME_H4, "H4"),
        (mt5.TIMEFRAME_M5, "M5")
    ]

    all_good = True

    for tf, name in timeframes:
        print(f"   ⏳ Synchro {name}...", end="", flush=True)
        
        # On essaie de récupérer des données jusqu'à ce que ça marche
        attempts = 0
        max_attempts = 10 # On insiste lourdement (10 secondes max)
        
        data = None
        while attempts < max_attempts:
            # On demande 1000 bougies pour forcer le téléchargement profond
            data = mt5.copy_rates_from_pos(symbol, tf, 0, 1000)
            
            if data is not None and len(data) > 0:
                break # C'est bon, on a les données !
            
            # Si pas de données, on attend que MT5 les télécharge
            time.sleep(1)
            attempts += 1
            print(".", end="", flush=True)
        
        if data is not None:
            print(f" OK ({len(data)} bougies)")
        else:
            print(" ❌ ECHEC (Timeout)")
            all_good = False
            
    return all_good

if __name__ == "__main__":
    print("--- 🔋 OUTIL DE SYNCHRONISATION MT5 ---")
    
    if not mt5.initialize():
        print("❌ Erreur Init MT5")
        exit()
        
    if not mt5.login(settings.MT5_LOGIN, password=settings.MT5_PASSWORD, server=settings.MT5_SERVER):
        print("❌ Erreur Login")
        exit()
        
    print("✅ MT5 Connecté. Démarrage du téléchargement massif...")
    print(f"📋 Paires à traiter : {settings.SYMBOLS}")

    for sym in settings.SYMBOLS:
        warmup_symbol(sym)

    print("\n✅ PRÉCHAUFFAGE TERMINÉ.")
    mt5.shutdown()