"""
colab_run.py - Lancement rapide pour Google Colab (premier trade testnet).

Usage dans une cellule Colab :
    !git clone -b arena/019fb2fe-gemini-gold-eye https://github.com/saintLaurent00/GEMINI_GOLD_EYE.git
    %cd GEMINI_GOLD_EYE
    !pip install -q -r requirements.txt
    # ------ Remplis tes clés ci-dessous ------
    %env BINANCE_API_KEY=ta_cle
    %env BINANCE_SECRET=ton_secret
    %env BINANCE_TESTNET=True
    %env BINANCE_LEVERAGE=10
    %env GEMINI_API_KEYS=cle_gemini_1,cle_gemini_2,...
    # ------ Premier trade (1 seule boucle, dry-run d'abord) ------
    !python colab_run.py --symbol BTCUSDT --dry-run     # <- vérifie le sizing
    !python colab_run.py --symbol BTCUSDT               # <- PREMIER TRADE REEL testnet
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mode "one-shot" = 1 round, interval court
from main_gemini_binance import run


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT",
                   help="Symbole Binance. Sur testnet : BTCUSDT, ETHUSDT, XAUUSDT selon disponibilité.")
    p.add_argument("--risk", type=float, default=1.0)
    p.add_argument("--rr", type=float, default=2.0)
    p.add_argument("--leverage", type=int, default=0)
    p.add_argument("--confidence", type=int, default=75)
    p.add_argument("--sl-atr", type=float, default=2.0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--mainnet", action="store_true")
    p.add_argument("--interval", type=int, default=30, help="secondes entre boucles (defaut 30s)")
    p.add_argument("--rounds", type=int, default=0, help="0 = boucle infinie")
    p.add_argument("--gemini-every", type=int, default=1, help="appel Gemini tous les N cycles")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
