"""
fetch_data.py - Recuperation GRATUITE de vraies bougies H1 (pas de MT5, pas de cle API).

Sources : Yahoo Finance (public, sans cle, sans inscription).
  - EURUSD=X  -> EUR/USD
  - GC=F      -> Or (futures, tres proche du XAUUSD spot)

Aucune dependance externe : utilise uniquement la bibliotheque standard (urllib).
Fonctionne sur ton PC, sur Google Colab, sur n'importe quelle machine avec Python + internet.

Usage :
    python tools/fetch_data.py                 # telecharge EURUSD + Or (2 ans H1)
    python tools/fetch_data.py --range 1y      # 1 an
    python tools/fetch_data.py --symbol GC=F --out data/XAUUSD_H1.csv

Puis lancer le backtest :
    python backtest.py --csv data/EURUSD_H1.csv --symbol EURUSD
    python backtest.py --csv data/XAUUSD_H1.csv --symbol XAUUSD
"""

import argparse
import csv
import datetime
import json
import os
import urllib.request


def fetch_yahoo(ticker: str, interval: str = "1h", rng: str = "2y", retries: int = 3):
    """Recupere les donnees OHLC depuis l'API publique Yahoo Finance."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval={interval}&range={rng}")
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            result = data["chart"]["result"][0]
            ts = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            return ts, quote
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Echec recuperation {ticker} apres {retries} essais : {last_err}")


def to_csv(ticker: str, outfile: str, rng: str):
    ts, quote = fetch_yahoo(ticker, rng=rng)
    rows = []
    for t, o, h, l, c in zip(ts, quote["open"], quote["high"], quote["low"], quote["close"]):
        if None in (o, h, l, c):
            continue
        iso = datetime.datetime.utcfromtimestamp(int(t)).isoformat()
        rows.append([iso, round(o, 5), round(h, 5), round(l, 5), round(c, 5)])

    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close"])
        w.writerows(rows)
    print(f"✅ {ticker} -> {outfile}  ({len(rows)} bougies H1)")


def main():
    p = argparse.ArgumentParser(description="Telecharge des bougies H1 gratuites (Yahoo Finance)")
    p.add_argument("--range", default="2y", help="periode : 1mo, 3mo, 6mo, 1y, 2y (defaut 2y)")
    p.add_argument("--symbol", help="ticker Yahoo specifique (ex: EURUSD=X, GC=F)")
    p.add_argument("--out", help="fichier de sortie CSV")
    args = p.parse_args()

    if args.symbol:
        out = args.out or f"data/{args.symbol.replace('=','_').replace('=','')}.csv"
        to_csv(args.symbol, out, args.range)
        return

    # Defaut : EUR/USD + Or
    to_csv("EURUSD=X", "data/EURUSD_H1.csv", args.range)
    to_csv("GC=F", "data/XAUUSD_H1.csv", args.range)   # Or (proxy du XAUUSD)
    print("\nDonnées prêtes. Lance maintenant :")
    print("  python backtest.py --csv data/EURUSD_H1.csv --symbol EURUSD")
    print("  python backtest.py --csv data/XAUUSD_H1.csv --symbol XAUUSD")


if __name__ == "__main__":
    main()
