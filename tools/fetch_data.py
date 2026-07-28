"""
fetch_data.py - Recuperation GRATUITE de vraies bougies H1 (pas de MT5, pas de cle API).

Deux sources :
  - yahoo   : EUR/USD + Or, ~2 ans max (limite Yahoo sur l'intraday H1)
  - histdata: ~15 ans d'historique H1 (majors FX + metaux). Idéal pour tests longs.

Aucune dependance externe : uniquement la bibliotheque standard.
Fonctionne sur ton PC, sur Google Colab, sur n'importe quelle machine avec Python + internet.

Exemples :
    # 2 ans (Yahoo, rapide) - EUR/USD + Or
    python tools/fetch_data.py --source yahoo --range 2y

    # 5 ANS d'historique reel (HistData) - EUR/USD
    python tools/fetch_data.py --source histdata --instrument eurusd --years 5 --out data/EURUSD_H1.csv

    # 5 ANS - Or (XAU/USD)
    python tools/fetch_data.py --source histdata --instrument xauusd --years 5 --out data/XAUUSD_H1.csv

Puis lancer le backtest :
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

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_CJ = CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_CJ))


# ============================================================
# SOURCE 1 : YAHOO FINANCE (recent, ~2 ans max sur l'H1)
# ============================================================
def fetch_yahoo(ticker: str, interval: str = "1h", rng: str = "2y", retries: int = 3):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval={interval}&range={rng}")
    last_err = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            result = data["chart"]["result"][0]
            return result["timestamp"], result["indicators"]["quote"][0]
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Echec Yahoo {ticker}: {last_err}")


def yahoo_to_csv(ticker: str, outfile: str, rng: str):
    ts, quote = fetch_yahoo(ticker, rng=rng)
    rows = []
    for t, o, h, l, c in zip(ts, quote["open"], quote["high"], quote["low"], quote["close"]):
        if None in (o, h, l, c):
            continue
        iso = datetime.datetime.utcfromtimestamp(int(t)).isoformat()
        rows.append([iso, round(o, 5), round(h, 5), round(l, 5), round(c, 5)])
    _write_csv(outfile, rows)
    print(f"✅ Yahoo {ticker} -> {outfile}  ({len(rows)} bougies H1)")


# ============================================================
# SOURCE 2 : HISTDATA (long historique, ~15 ans, gratuit)
# ============================================================
def _hist_request(url: str, data=None, referer=None, timeout=60):
    headers = {"User-Agent": _UA, "Referer": referer or url, "Accept": "*/*"}
    req = urllib.request.Request(url, data=data, headers=headers)
    return _OPENER.open(req, timeout=timeout).read()


def _parse_hist_line(line: str):
    """Une ligne HistData -> (iso_time, open, high, low, close) ou None."""
    parts = [p.strip() for p in line.replace(",", ";").split(";")]
    if len(parts) < 5:
        return None
    dt_raw, o, h, l, c = parts[0], parts[1], parts[2], parts[3], parts[4]
    dt = None
    for fmt in ("%Y.%m.%d %H:%M", "%Y%m%d %H%M%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(dt_raw, fmt)
            break
        except ValueError:
            continue
    if dt is None:
        return None
    try:
        return dt.isoformat(), float(o), float(h), float(l), float(c)
    except ValueError:
        return None


def _download_hist_month(instrument: str, year: int, month: int):
    """Telecharge un mois H1 depuis HistData -> liste de lignes (ou None si echec)."""
    page = (f"https://www.histdata.com/download-free-forex-data/"
            f"?/ascii/1-hour-bar-quotes/{instrument}/{year}/{month}")
    html = _hist_request(page).decode("utf-8", errors="ignore")
    # On releve tous les champs caches du formulaire qui pointe vers /get.php
    fields = {}
    for tag in re.findall(r"<input\b[^>]*>", html):
        nm = re.search(r'name="([^"]+)"', tag)
        vl = re.search(r'value="([^"]*)"', tag)
        if nm:
            fields[nm.group(1)] = vl.group(1) if vl else ""
    if "id" not in fields or "tk" not in fields:
        return None  # mois indisponible
    fields["platform"] = "HS"
    fields["timeframe"] = "H1"
    data = urllib.parse.urlencode(fields).encode()
    blob = _hist_request("https://www.histdata.com/get.php", data=data, referer=page)
    if not blob[:2] == b"PK":  # pas un zip -> erreur/indisponible
        return None
    rows = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".txt", ".csv")):
                continue
            for line in zf.read(name).decode("utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                parsed = _parse_hist_line(line)
                if parsed:
                    rows.append(parsed)
    return rows


def histdata_to_csv(instrument: str, years: int, outfile: str):
    now = datetime.datetime.utcnow()
    start_year = now.year - years + 1
    all_rows = []
    ok, miss = 0, 0
    for year in range(start_year, now.year + 1):
        last_month = now.month if year == now.year else 12
        for month in range(1, last_month + 1):
            try:
                rows = _download_hist_month(instrument, year, month)
            except Exception as e:
                rows = None
                print(f"   ⚠️ {instrument} {year}-{month}: {e}")
            if rows:
                all_rows.extend(rows)
                ok += 1
            else:
                miss += 1
            time.sleep(0.4)  # polite, evite le blocage
    all_rows.sort(key=lambda r: r[0])
    _write_csv(outfile, all_rows)
    status = f"✅ HistData {instrument} ({years} ans) -> {outfile}  ({len(all_rows)} bougies H1, {ok} mois OK"
    status += f", {miss} indisponibles)" if miss else f", {ok} mois OK)"
    print(status)


# ============================================================
# Commun
# ============================================================
def _write_csv(outfile: str, rows):
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close"])
        for r in rows:
            w.writerow([r[0], round(r[1], 5), round(r[2], 5), round(r[3], 5), round(r[4], 5)])


def main():
    p = argparse.ArgumentParser(description="Telecharge des bougies H1 gratuites")
    p.add_argument("--source", choices=["yahoo", "histdata"], default="yahoo")
    # Yahoo
    p.add_argument("--range", default="2y")
    # HistData
    p.add_argument("--instrument", default="eurusd", help="ex: eurusd, gbpusd, usdjpy, xauusd")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--out", help="fichier de sortie CSV")
    args = p.parse_args()

    if args.source == "histdata":
        out = args.out or f"data/{args.instrument.upper()}_H1.csv"
        histdata_to_csv(args.instrument.lower(), args.years, out)
        return

    # Yahoo : par defaut EUR/USD + Or
    if args.instrument and args.out:
        yahoo_to_csv(args.instrument, args.out, args.range)
        return
    yahoo_to_csv("EURUSD=X", "data/EURUSD_H1.csv", args.range)
    yahoo_to_csv("GC=F", "data/XAUUSD_H1.csv", args.range)
    print("\nDonnées prêtes. Lance maintenant :")
    print("  python backtest.py --csv data/EURUSD_H1.csv --symbol EURUSD")


if __name__ == "__main__":
    main()
