"""
test_oanda.py - ETAPE 1 : valide la connexion OANDA + la recuperation des donnees.

Avant de lancer le vrai bot, on confirme que le compte demo OANDA repond.

Usage (apres avoir rempli .env avec OANDA_API_TOKEN + OANDA_ACCOUNT_ID) :
    python tools/test_oanda.py
"""

import os
import sys

# Permet d'importer 'config' / 'infrastructure' quel que soit le repertoire d'execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from infrastructure.oanda_client import OandaClient, to_oanda_symbol


def main():
    token = settings.OANDA_API_TOKEN
    account_id = settings.OANDA_ACCOUNT_ID

    if not token or not account_id:
        print("❌ OANDA_API_TOKEN ou OANDA_ACCOUNT_ID manquant dans .env")
        print("   Cree un compte pratique gratuit sur oanda.com, puis :")
        print("   Settings -> API Access -> Generate token. Colle token + account ID dans .env")
        return

    print(f" Connexion OANDA ({'PRATIQUE/démo' if settings.OANDA_PRACTICE else 'RÉEL'}) ...")
    client = OandaClient(token, account_id, practice=settings.OANDA_PRACTICE)

    # 1) Compte
    acc = client.account()
    print(f"✅ Compte connecté : {acc.get('id')} | "
          f"Solde = {acc.get('balance')} {acc.get('currency')} | NAV = {acc.get('NAV')}")

    # 2) Tick (prix live)
    for sym in ["EUR_USD", "XAU_USD"]:
        try:
            px = client.pricing(sym)
            print(f"✅ Prix {sym} : bid={px['bid']} ask={px['ask']} (spread {(px['ask']-px['bid']):.5f})")
        except Exception as e:
            print(f"⚠️ Prix {sym} indisponible (marché fermé ?) : {e}")

    # 3) Bougies H1
    df = client.candles("EUR_USD", "H1", 5)
    if df.empty:
        print("⚠️ Aucune bougie H1 reçue (vérifie le symbole / le marché).")
    else:
        print(f"✅ Bougies H1 EUR/USD reçues ({len(df)}):\n{df}")

    print("\n🎉 ÉTAPE 1 OK : OANDA fonctionne. On peut passer aux ordres (étape 2).")


if __name__ == "__main__":
    main()
