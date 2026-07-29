"""
fetch_data.py - Recuperation GRATUITE de vraies bougies (pas de MT5, pas de cle API pour Yahoo).

Sources :
  - yahoo      : EUR/USD + Or, ~2 ans max (limite Yahoo sur l'intraday H1). SANS cle.
  - twelvedata : 5 ans+ d'historique H1, API propre (JSON). Cle API GRATUITE requise.
  - histdata   : desactive (le site genere son formulaire en JavaScript -> inaccessible en Python).

Aucune dependance externe : uniquement la bibliotheque standard.

Exemples :
    # 2 ans (Yahoo, sans cle) - EUR/USD + Or
    python tools/fetch_data.py --source yahoo --range 2y

    # 5 ANS d'historique reel H1 (Twelve Data, cle gratuite)
    python tools/fetch_data.py --source twelvedata --td-symbol "EUR/USD" --years 5 --out data/EURUSD_H1.csv
    python tools/fetch_data.py --source twelvedata --td-symbol "XAU/USD" --years 5 --out data/XAUUSD_H1.csv

Cle API gratuite Twelve Data : https://twelvedata.com/  (inscription 1 min, plan free = 800 appels/jour)

Puis backtest :
    python backtest.py --csv data/EURUSD_H1.csv --symbol EURUSD
    python backtest.py --csv data/XAUUSD_H1.csv --symbol XAUUSD
"""

import argparse
import csv
import datetime
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.cookiejar import CookieJar

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


# ============================================================
# SOURCE 1 : YAHOO FINANCE (~2 ans max sur l'H1, sans cle)
# ============================================================
def fetch_yahoo(ticker, interval="1h", rng="2y", retries=3):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={rng}"
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            result = data["chart"]["result"][0]
            return result["timestamp"], result["indicators"]["quote"][0]
        except Exception as e:
            last = e
    raise RuntimeError(f"Echec Yahoo {ticker}: {last}")


def yahoo_to_csv(ticker, outfile, rng):
    ts, quote = fetch_yahoo(ticker, rng=rng)
    rows = []
    for t, o, h, l, c in zip(ts, quote["open"], quote["high"], quote["low"], quote["close"]):
        if None in (o, h, l, c):
            continue
        iso = datetime.datetime.fromtimestamp(int(t), datetime.timezone.utc).replace(tzinfo=None).isoformat()
        rows.append([iso, o, h, l, c])
    _write_csv(outfile, rows)
    print(f"✅ Yahoo {ticker} -> {outfile}  ({len(rows)} bougies H1)")


# ============================================================
# SOURCE 2 : TWELVE DATA (5 ans+ H1, cle gratuite, API propre)
# ============================================================
def twelvedata_to_csv(td_symbol, apikey, years, outfile):
    base = "https://api.twelvedata.com/time_series"
    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(days=365 * years)
    collected = {}
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    page = 0
    while page < 40:
        params = {
            "symbol": td_symbol, "interval": "1h", "outputsize": "5000",
            "apikey": apikey, "format": "JSON", "timezone": "UTC", "end_date": end,
        }
        url = base + "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            print(f"❌ HTTP {e.code}: {body[:300]}")
            if e.code == 401:
                print("   -> Cle API invalide OU email non confirme.")
                print("   -> Verifie : 1) cle bien collee (sans espaces), 2) email confirme sur twelvedata.com")
            break
        except Exception as e:
            print(f"⚠️ Erreur reseau: {e}")
            break
        if data.get("status") == "error":
            print(f"❌ Twelve Data: {data.get('message')}")
            break
        values = data.get("values", [])
        if not values:
            break
        oldest = None
        for v in values:
            try:
                dt = datetime.datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            collected[dt] = (float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]))
            if oldest is None or dt < oldest:
                oldest = dt
        page += 1
        print(f"   page {page}: +{len(values)} bars (total {len(collected)}), jusqu'a {oldest}")
        if len(values) < 5000 or oldest is None or oldest <= start:
            break
        end = (oldest - datetime.timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
        time.sleep(8)  # respecte la limite 8 appels/min du plan gratuit

    rows = sorted(collected.items())
    out_rows = [[dt.isoformat()] + list(ohlc) for dt, ohlc in rows]
    _write_csv(outfile, out_rows)
    if not rows:
        print(f"❌ Echec : 0 bougie recuperee pour {td_symbol}. Verifie ta cle API.")
        return
    print(f"✅ Twelve Data {td_symbol} ({years} ans) -> {outfile}  ({len(rows)} bougies H1)")


# ============================================================
# Commun
# ============================================================
def _write_csv(outfile, rows):
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close"])
        for r in rows:
            w.writerow([r[0], round(r[1], 5), round(r[2], 5), round(r[3], 5), round(r[4], 5)])


def main():
    p = argparse.ArgumentParser(description="Telecharge des bougies H1 gratuites")
    p.add_argument("--source", choices=["yahoo", "twelvedata"], default="yahoo")
    p.add_argument("--range", default="2y")
    # Twelve Data
    p.add_argument("--td-symbol", default="EUR/USD", help='ex: "EUR/USD", "XAU/USD", "GBP/USD"')
    p.add_argument("--apikey", default=os.getenv("TWELVEDATA_API_KEY", ""),
                   help="cle API Twelve Data (ou variable TWELVEDATA_API_KEY)")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--out")
    args = p.parse_args()

    if args.source == "twelvedata":
        if not args.apikey:
            print("❌ Cle API manquante. Obtenez-en une gratuite sur https://twelvedata.com/")
            print("   Puis: --apikey VOTRE_CLE  (ou variable d'env TWELVEDATA_API_KEY)")
            return
        out = args.out or f"data/{args.td_symbol.replace('/', '')}_H1.csv"
        twelvedata_to_csv(args.td_symbol, args.apikey, args.years, out)
        return

    # Yahoo : par defaut EUR/USD + Or
    yahoo_to_csv("EURUSD=X", "data/EURUSD_H1.csv", args.range)
    yahoo_to_csv("GC=F", "data/XAUUSD_H1.csv", args.range)
    print("\nDonnées prêtes. Lance maintenant :")
    print("  python backtest.py --csv data/EURUSD_H1.csv --symbol EURUSD")


if __name__ == "__main__":
    main()
