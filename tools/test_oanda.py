"""
test_oanda.py - ETAPE 1 : valide la connexion OANDA + la recuperation des donnees.

Usage (apres avoir renseigne OANDA_API_TOKEN dans .env) :
    python tools/test_oanda.py

Le script liste tes comptes (pour trouver ton Account ID) puis teste les donnees.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from infrastructure.oanda_client import OandaClient


def main():
    token = settings.OANDA_API_TOKEN
    if not token or token == "COLLE_TON_TOKEN":
        print("❌ OANDA_API_TOKEN manquant dans .env (remplace 'COLLE_TON_TOKEN').")
        return

    print(f" Connexion OANDA ({'PRATIQUE/démo' if settings.OANDA_PRACTICE else 'RÉEL'}) ...")
    # account_id peut etre vide : on le decouvre ci-dessous
    client = OandaClient(token, settings.OANDA_ACCOUNT_ID or "x", practice=settings.OANDA_PRACTICE)

    # 1) Liste les comptes accessibles -> trouve l'Account ID
    try:
        accts = client.list_accounts()
    except Exception as e:
        print(f"❌ Token invalide ou erreur : {e}")
        return

    print(f"✅ Token valide. Comptes accessibles :")
    for a in accts:
        print(f"   - Account ID : {a.get('id')}")

    account_id = settings.OANDA_ACCOUNT_ID
    if not account_id or account_id == "COLLE_TON_ACCOUNT_ID":
        print("\n👉 Copie un des Account ID ci-dessus dans OANDA_ACCOUNT_ID, puis relance.")
        return

    # 2) Details du compte
    client.account_id = account_id
    acc = client.account()
    print(f"\n✅ Compte {acc.get('id')} : Solde = {acc.get('balance')} {acc.get('currency')} | NAV = {acc.get('NAV')}")

    # 3) Tick (prix live)
    for sym in ["EUR_USD", "XAU_USD"]:
        try:
            px = client.pricing(sym)
            print(f"✅ Prix {sym} : bid={px['bid']} ask={px['ask']}")
        except Exception as e:
            print(f"⚠️ Prix {sym} indisponible (marché fermé ?) : {e}")

    # 4) Bougies H1
    df = client.candles("EUR_USD", "H1", 5)
    print(f"✅ Bougies H1 EUR/USD ({len(df)}):\n{df}")
    print("\n🎉 ÉTAPE 1 OK : OANDA fonctionne. On passe aux ordres (étape 2).")


if __name__ == "__main__":
    main()
