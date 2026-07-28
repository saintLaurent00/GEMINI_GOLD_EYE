"""
fetch_data.py - Recuperation GRATUITE de vraies bougies H1 (pas de MT5, pas de cle API).

Deux sources :
  - yahoo   : EUR/USD + Or, ~2 ans max (limite Yahoo sur l'intraday H1)
  - histdata: ~15 ans d'historique H1 (majors FX + metaux). Idéal pour tests longs.

Aucune dependance externe : uniquement la bibliotheque standard.

Exemples :
    python tools/fetch_data.py --source yahoo --range 2y
    python tools/fetch_data.py --source histdata --instrument eurusd --years 5 --out data/EURUSD_H1.csv
    python tools/fetch_data.py --source histdata --instrument eurusd --diagnose   # debug rapide
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
_CJ = CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_CJ))


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


# ============================================================
# SOURCE 1 : YAHOO FINANCE (~2 ans max sur l'H1)
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
# SOURCE 2 : HISTDATA (long historique, ~15 ans, gratuit)
# ============================================================
def _hist_request(url, data=None, referer=None, timeout=60):
    headers = {"User-Agent": _UA, "Referer": referer or url,
               "Accept": "text/html,application/xhtml+xml,*/*"}
    req = urllib.request.Request(url, data=data, headers=headers)
    return _OPENER.open(req, timeout=timeout).read()


def _extract_form_fields(html):
    fields = {}
    for tag in re.findall(r"<input\b[^>]*>", html, flags=re.IGNORECASE):
        nm = re.search(r"""name\s*=\s*["']([^"']+)["']""", tag, re.IGNORECASE)
        vl = re.search(r"""value\s*=\s*["']([^"']*)["']""", tag, re.IGNORECASE)
        if nm:
            fields[nm.group(1)] = vl.group(1) if vl else ""
    return fields


def _parse_hist_line(line):
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


def _download_hist_month(instrument, year, month, verbose=False):
    page = (f"https://www.histdata.com/download-free-forex-data/"
            f"?/ascii/1-hour-bar-quotes/{instrument}/{year}/{month}")
    try:
        raw = _hist_request(page)
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"  [{year}-{month}] HTTP {e.code} sur la page")
        return None
    except Exception as e:
        if verbose:
            print(f"  [{year}-{month}] Erreur reseau page: {e}")
        return None
    html = raw.decode("utf-8", errors="ignore")
    if verbose and year == _utcnow().year - 1 and month == 1:
        has_get = "get.php" in html
        has_tk = "tk" in html
        has_id = '"id"' in html
        print(f"  [{year}-{month}] Page: {len(html)} octets | get.php={has_get} | tk={has_tk} | id={has_id}")
    fields = _extract_form_fields(html)
    if "tk" not in fields or "id" not in fields:
        if verbose:
            print(f"  [{year}-{month}] Formulaire/token introuvable (mois indisponible ou blocage)")
        return None
    fields["platform"] = "HS"
    fields["timeframe"] = "H1"
    fields["fxpair"] = instrument.upper()
    data = urllib.parse.urlencode(fields).encode()
    try:
        blob = _hist_request("https://www.histdata.com/get.php", data=data, referer=page)
    except Exception as e:
        if verbose:
            print(f"  [{year}-{month}] Erreur POST get.php: {e}")
        return None
    if blob[:2] != b"PK":
        if verbose:
            print(f"  [{year}-{month}] get.php n'a pas renvoye de zip ({len(blob)} octets)")
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


def histdata_to_csv(instrument, years, outfile):
    now = _utcnow()
    start_year = now.year - years + 1
    all_rows, ok, miss = [], 0, 0
    for year in range(start_year, now.year + 1):
        last_month = now.month if year == now.year else 12
        for month in range(1, last_month + 1):
            try:
                rows = _download_hist_month(instrument, year, month)
            except Exception as e:
                rows = None
                print(f"  ⚠️ {instrument} {year}-{month}: {e}")
            if rows:
                all_rows.extend(rows)
                ok += 1
            else:
                miss += 1
            time.sleep(0.4)
    all_rows.sort(key=lambda r: r[0])
    _write_csv(outfile, all_rows)
    msg = f"✅ HistData {instrument} ({years} ans) -> {outfile}  ({len(all_rows)} bougies, {ok} mois OK"
    msg += f", {miss} indisponibles)" if miss else f", {ok} mois OK)"
    print(msg)


def diagnose_histdata(instrument):
    """Teste UN seul mois en mode bavard pour identifier la cause d'un echec."""
    year = _utcnow().year - 1
    print(f"=== DIAGNOSTIC HistData : {instrument} mois {year}-1 ===")
    rows = _download_hist_month(instrument, year, 1, verbose=True)
    print("-" * 50)
    if rows:
        print(f"✅ SUCCES : {len(rows)} lignes récupérées. Exemple : {rows[0]}")
        print("=> HistData fonctionne depuis Colab. Lance le téléchargement complet.")
    else:
        print("❌ ECHEC : 0 ligne.")
        print("Causes probables : HistData bloque l'IP de Google Colab, ou la page a changé.")
        print("=> On basculera sur Dukascopy (autre source gratuite).")


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
    p.add_argument("--source", choices=["yahoo", "histdata"], default="yahoo")
    p.add_argument("--range", default="2y")
    p.add_argument("--instrument", default="eurusd")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--out")
    p.add_argument("--diagnose", action="store_true", help="test rapide d'un mois (debug)")
    args = p.parse_args()

    if args.source == "histdata":
        if args.diagnose:
            diagnose_histdata(args.instrument.lower())
            return
        out = args.out or f"data/{args.instrument.upper()}_H1.csv"
        histdata_to_csv(args.instrument.lower(), args.years, out)
        return

    if args.instrument and args.out:
        yahoo_to_csv(args.instrument, args.out, args.range)
        return
    yahoo_to_csv("EURUSD=X", "data/EURUSD_H1.csv", args.range)
    yahoo_to_csv("GC=F", "data/XAUUSD_H1.csv", args.range)
    print("\nDonnées prêtes. Lance maintenant :")
    print("  python backtest.py --csv data/EURUSD_H1.csv --symbol EURUSD")


if __name__ == "__main__":
    main()
