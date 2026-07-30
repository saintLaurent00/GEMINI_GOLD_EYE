"""
tools/test_binance.py - Smoke test du connecteur Binance Futures.

Valide sans risque :
  - ping / serverTime
  - prix live + klines + exchange info
  - solde USDT + positions ouvertes
  - (optionnel) set_leverage + set_margin_type

Usage:
    python tools/test_binance.py                # testnet par defaut (env vars)
    python tools/test_binance.py --symbol BTCUSDT
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from infrastructure.binance_client import BinanceFuturesClient, BinanceApiError


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--mainnet", action="store_true", help="forcer mainnet (DANGER)")
    p.add_argument("--set-leverage", type=int, default=0, help="si >0, applique le levier")
    args = p.parse_args()

    testnet = (not args.mainnet) and settings.BINANCE_TESTNET
    sym = args.symbol.upper()

    if not settings.BINANCE_API_KEY or not settings.BINANCE_SECRET:
        print("❌ BINANCE_API_KEY / BINANCE_SECRET manquantes dans le .env")
        return 1

    mode = "TESTNET" if testnet else "MAINNET ⚠️"
    print(f"🔌 Connexion Binance USD-M Futures ({mode})...")
    bc = BinanceFuturesClient(settings.BINANCE_API_KEY, settings.BINANCE_SECRET, testnet=testnet)

    print(f"   serverTime : {bc.server_time()}")
    print(f"   prix {sym}: {bc.price(sym):.4f}")

    kl = bc.klines(sym, interval="1h", limit=3)
    print(f"   klines H1 (3): open={float(kl[-1][1]):.4f} close={float(kl[-1][4]):.4f}")

    info = bc.symbol_info(sym)
    print(f"   symbol info : step={info['stepSize']} tick={info['tickSize']} "
          f"minQty={info['minQty']} minNotional={info['minNotional']} "
          f"qP={info['quantityPrecision']} pP={info['pricePrecision']}")

    print()
    print(f"💰 Solde USDT disponible : {bc.balance_usdt():.2f}")
    pos = bc.positions()
    if not pos:
        print("📭 Aucune position ouverte.")
    else:
        print(f"📈 Positions ouvertes ({len(pos)}) :")
        for x in pos:
            print(f"   {x['symbol']:<12} amt={x['positionAmt']} entry={x['entryPrice']} "
                  f"upnl={x['unRealizedProfit']}")

    if args.set_leverage > 0:
        try:
            r = bc.set_leverage(sym, args.set_leverage)
            print(f"🔧 Leverage {args.set_leverage}x appliqué sur {sym} : {r}")
        except BinanceApiError as e:
            print(f"⚠️ set_leverage: {e}")

    print("✅ connecteur OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
