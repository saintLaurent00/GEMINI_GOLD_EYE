"""
main_gemini_paper.py - LE VRAI BOT (vision Gemini) en paper trading sur donnees Yahoo.

Le cerveau Gemini analyse les VRAIS graphiques (W1/D1/H4/H1) et decide (BUY/SELL/WAIT).
Execution simulee (paper) via PaperPosition -> aucun broker/API requis (hors cle Gemini).

Besoin:
    - GEMINI_API_KEY (gratuite: https://aistudio.google.com/ -> Get API key)
    - pip install google-generativeai Pillow mplfinance pandas pandas_ta

Usage (Colab):
    import os; os.environ["GEMINI_API_KEY"]="ta_cle"
    !python main_gemini_paper.py --symbol XAUUSD --rounds 12 --interval 300
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import pandas_ta as ta

from main_paper import PaperPosition          # execution paper reutilisee
from backtest import BacktestConfig
from infrastructure.gemini_client import GeminiClient

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TICKERS = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "XAUUSD": "GC=F", "BTCUSD": "BTC-USD"}
TF_FETCH = [("W1", "1wk", "10y"), ("D1", "1d", "5y"), ("H4", "1h", "6mo"), ("H1", "1h", "6mo")]


# ============================================================
# Donnees Yahoo -> DataFrame
# ============================================================
def _fetch_raw(ticker, interval, rng):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={rng}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    res = data["chart"]["result"][0]
    ts = res["timestamp"]; q = res["indicators"]["quote"][0]
    rows = []
    for t, o, h, l, c, v in zip(ts, q["open"], q["high"], q["low"], q["close"], q.get("volume", [0] * len(ts))):
        if None in (o, h, l, c):
            continue
        rows.append({"time": pd.to_datetime(t, unit="s", utc=True).tz_localize(None),
                     "open": o, "high": h, "low": l, "close": c, "volume": v or 0})
    df = pd.DataFrame(rows).set_index("time")
    return df


def fetch_df(ticker, tf_name):
    """Retourne un DataFrame OHLCV (+ indicateurs) pour un timeframe."""
    src = next(s for n, s, r in TF_FETCH if n == tf_name)
    rng = next(r for n, s, r in TF_FETCH if n == tf_name)
    df = _fetch_raw(ticker, src, rng)
    if tf_name == "H4":   # H4 = resample H1 par 4h
        df = df.resample("4h", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return add_indicators(df)


def add_indicators(df):
    try:
        df["EMA50"] = ta.ema(df["close"], length=50)
        df["EMA200"] = ta.ema(df["close"], length=200)
        df["RSI"] = ta.rsi(df["close"], length=14)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        df["VWAP"] = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd is not None:
            df["MACD_HIST"] = macd.iloc[:, 2]
    except Exception as e:
        print(f"⚠️ indicateurs: {e}")
    return df


# ============================================================
# Graphiques pour Gemini (candles + EMA + VWAP + S/R + ZigZag + prix live)
# ============================================================
def _zigzag(df, window=5):
    d = df.copy()
    d["ih"] = d["high"].rolling(window, center=True).max() == d["high"]
    d["il"] = d["low"].rolling(window, center=True).min() == d["low"]
    piv = [(t, r["high"], "H") for t, r in d[d["ih"]].iterrows()]
    piv += [(t, r["low"], "L") for t, r in d[d["il"]].iterrows()]
    piv.sort(key=lambda x: x[0])
    clean, last = [], None
    for p in piv:
        if last != p[2]:
            clean.append((p[0], p[1])); last = p[2]
        elif last == "H" and p[1] > clean[-1][1]:
            clean[-1] = (p[0], p[1])
        elif last == "L" and p[1] < clean[-1][1]:
            clean[-1] = (p[0], p[1])
    return clean


def _sr(df, window=12, n=8):
    lv = []
    for i in range(window, len(df) - window):
        if df["low"].iloc[i] == df["low"].iloc[i - window:i + window].min():
            lv.append(round(float(df["low"].iloc[i]), 5))
        if df["high"].iloc[i] == df["high"].iloc[i - window:i + window].max():
            lv.append(round(float(df["high"].iloc[i]), 5))
    return list(dict.fromkeys(lv))[:n]


def _to_x(pdf, d):
    """Map une date vers sa position entiere dans le graphique (robuste)."""
    try:
        loc = pdf.index.get_loc(d)
        return loc if isinstance(loc, int) else 0
    except Exception:
        idx = pdf.index.get_indexer([d], method="nearest")
        return int(idx[0]) if idx[0] >= 0 else 0


def paint_chart(df, symbol, tf_name, outdir="charts_buffer"):
    os.makedirs(outdir, exist_ok=True)
    pdf = df.tail(120).copy()
    # Addplots : on n'ajoute QUE les colonnes ayant au moins une valeur valide (anti-NaN fatal)
    adds = []
    for col, c in [("EMA50", "orange"), ("EMA200", "blue"), ("VWAP", "purple")]:
        if col in pdf and pdf[col].dropna().shape[0] > 0:
            try:
                adds.append(mpf.make_addplot(pdf[col].fillna(method="ffill").fillna(0), color=c, width=0.9))
            except Exception:
                pass
    zz = _zigzag(pdf)
    sr = _sr(pdf)
    args = {"type": "candle", "style": "yahoo", "addplot": adds or None,
            "returnfig": True, "tight_layout": True, "title": f"{symbol} {tf_name}"}

    def _finalize(fig, ax):
        # ZigZag (magenta) dessine en matplotlib direct (plus fiable que mplfinance alines)
        if len(zz) > 1:
            xs = [_to_x(pdf, d) for d, _ in zz]
            ys = [p for _, p in zz]
            ax.plot(xs, ys, color="magenta", linewidth=1.4, alpha=0.8)
        for lv in sr:                                   # S/R en pointilles vert
            ax.axhline(lv, color="green", linestyle="--", alpha=0.4, linewidth=0.8)
        ax.axhline(float(pdf["close"].iloc[-1]), color="red", linewidth=0.8)  # prix live
        path = os.path.join(outdir, f"{symbol}_{tf_name}.png")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return path

    try:
        fig, axes = mpf.plot(pdf, **args)
        return _finalize(fig, axes[0])
    except Exception as e:
        # Repli: graphique chandeliers minimal sans addplots (garantit un PNG)
        try:
            plt.close("all")
            fig, axes = mpf.plot(pdf, type="candle", style="yahoo", returnfig=True, tight_layout=True,
                                 title=f"{symbol} {tf_name}")
            return _finalize(fig, axes[0])
        except Exception as e2:
            print(f"   ⚠️ paint_chart {tf_name} irreparable: {e2}")
            return None


# ============================================================
# Bulletin (maths) pour Gemini
# ============================================================
def last_valid(s):
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else 0.0


def build_bulletin(symbol, h1, h4, price, spread_pts):
    def trend(df):
        return "BULLISH" if price > last_valid(df["EMA200"]) else "BEARISH"
    return {
        "META": {"Symbol": symbol, "Live_Price": round(price, 5)},
        "INSTITUTIONAL_BIAS": {"Price_vs_VWAP_H1": "BULLISH" if price > last_valid(h1["VWAP"]) else "BEARISH"},
        "H1_INDICATORS": {
            "RSI": round(last_valid(h1["RSI"]), 2),
            "MACD_Histogram": round(last_valid(h1.get("MACD_HIST", pd.Series([0]))), 5),
            "ATR": round(last_valid(h1["ATR"]), 5),
            "Trend": "BULLISH" if price > last_valid(h1["EMA200"]) else "BEARISH",
        },
        "H4_STRUCTURE": {
            "Trend_EMA200": trend(h4),
            "MACD_Status": "UP" if last_valid(h4.get("MACD_HIST", pd.Series([0]))) > 0 else "DOWN",
        },
        "SAFETY": {"SPREAD": spread_pts, "GOLD_MODE": "XAU" in symbol.upper()},
    }


# ============================================================
# Prompt + appel Gemini
# ============================================================
PROMPT = """ROLE: Senior Hedge Fund Trader (Price Action, SMC, Multi-Timeframe).
LANGUAGE: reponds avec 'reason' en FRANCAIS.

OBJECTIVE: Identifier une entree Sniper H1 alignee avec la structure H4 et le biais D1/W1.

--- PART 1: MATHEMATICAL TRUTH (LIVE DATA) ---
{bulletin}

--- PART 2: VISUAL ANALYSIS (W1, D1, H4, H1) ---
Hierarchie : W1/D1 = tendance macro ; H4 = structure ; H1 = declencheur.
Legende : Magenta = structure ZigZag (HH/HL ou LH/LL) ; Bleu = EMA200 ; Orange = EMA50 ;
Violet = VWAP ; Vert pointille = Support/Resistance ; Ligne rouge = prix LIVE.

REGLES :
1. Alignement multi-TF : BUY seulement si H1 ET H4 haussiers ; SELL seulement si H1 ET H4 baissiers.
2. Cherche un cassure de structure (BOS) + retest, ou une figure de consolidation (drapeau/triangle).
3. Ignore les doji/fortes meches (indecision). Entre sur une bougie decisive.
4. R:R minimum 2.

OUTPUT (JSON STRICT, rien d'autre) :
{{"decision": "BUY" | "SELL" | "WAIT", "confidence": 0-100, "reason": "analyse courte en FRANCAIS", "sl_atr_multiplier": 2.0}}
"""


def extract_json(text):
    text = text.replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def ask_gemini(client, bulletin, image_paths):
    prompt = PROMPT.format(bulletin=json.dumps(bulletin, indent=2, ensure_ascii=False))
    raw = client.send_multimodal_prompt(prompt, image_paths)
    if not raw:
        return None
    return extract_json(raw)


# ============================================================
# BACKTEST Gemini (rejoue l'historique, aussi vite que Gemini repond)
# ============================================================
def _load_df(path):
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"].astype(str).str.replace("Z", ""))
    df = df.set_index("time").sort_index()
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    if "volume" not in df.columns:
        df["volume"] = 1000.0
    return df[["open", "high", "low", "close", "volume"]]


def _resample(df, rule):
    r = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return add_indicators(r)


def run_backtest(symbol, csv_path, config, n_bars, max_gemini=60):
    from backtest import load_csv, apply_indicators, decide_deleuse
    if not os.getenv("GEMINI_API_KEY", ""):
        print("❌ GEMINI_API_KEY manquante. Gratuite sur https://aistudio.google.com/")
        return
    client = GeminiClient()
    candles = apply_indicators(load_csv(csv_path))
    h1_df = add_indicators(_load_df(csv_path))
    h4_df = _resample(h1_df, "4h")
    d1_df = _resample(h1_df, "1d")
    w1_df = _resample(h1_df, "1W")
    start = max(220, len(candles) - n_bars)
    state = {"pos": None, "balance": config.initial_balance, "trades": [], "last_price": float(candles[-2].close)}
    gemini_calls = 0
    print(f"🤖 BACKTEST GEMINI sur {symbol} | {len(candles) - start} bougies H1 | "
          f"Deleuse pré-sélectionne, Gemini confirme | max {max_gemini} appels\n")

    i = start
    n = len(candles)
    while i < n - 1:
        row = candles[i]
        state["last_price"] = float(row.close)
        manage(state, row, config)
        if state["pos"] is None and gemini_calls < max_gemini:
            in_session = config.mode != "day" or (config.session_start_hour <= row.time.hour < config.session_end_hour)
            cand = decide_deleuse(candles, i, config)
            if in_session and cand.decision in ("BUY", "SELL"):
                t = row.time
                price = float(row.close)
                try:
                    h1s = h1_df[h1_df.index <= t]; h4s = h4_df[h4_df.index <= t]
                    d1s = d1_df[d1_df.index <= t]; w1s = w1_df[w1_df.index <= t]
                    bulletin = build_bulletin(symbol, h1s, h4s, price, config.spread_points)
                    paths = [paint_chart(w1s, symbol, "W1"), paint_chart(d1s, symbol, "D1"),
                             paint_chart(h4s, symbol, "H4"), paint_chart(h1s, symbol, "H1")]
                    paths = [p for p in paths if p]   # on garde uniquement les graphiques valides
                    if len(paths) < 2:
                        raise RuntimeError("graphiques insuffisants")
                    g = ask_gemini(client, bulletin, paths)
                    gemini_calls += 1
                except Exception as e:
                    print(f"  ⚠️ cycle {t}: {e}"); g = None
                verdict = (g or {}).get("decision", "WAIT")
                conf = (g or {}).get("confidence", 0)
                reason = (g or {}).get("reason", "")[:60]
                if g and verdict in ("BUY", "SELL") and conf >= 75:
                    atr = float(row.atr) if row.atr else 0.001
                    sl_mult = float((g or {}).get("sl_atr_multiplier", cand.sl_atr_multiplier))
                    state["pos"] = PaperPosition(verdict, price, atr, config, row.time)
                    state["pos"].sl = price - atr * sl_mult if verdict == "BUY" else price + atr * sl_mult
                    state["pos"].risk = atr * sl_mult
                    print(f"🟢 {t} {verdict} @ {price:.5f} (règle+IA {conf}%) | {reason}")
                else:
                    print(f"⏸️ {t} candidat {cand.decision} rejeté par l'IA ({verdict} {conf}%)")
                i += config.cooldown_bars
                continue
        i += 1

    # Cloture mark-to-market fin de backtest
    if state["pos"] and not state["pos"].closed:
        pos = state["pos"]
        rfun = (lambda p: (p - pos.entry) / pos.risk) if pos.side == "BUY" else (lambda p: (pos.entry - p) / pos.risk)
        half = config.partial_ratio
        pnl = (half * config.tp1_r + (1 - half) * rfun(state["last_price"])) if pos.partial else rfun(state["last_price"])
        state["balance"] += state["balance"] * config.risk_percent / 100 * pnl
        state["trades"].append(pnl)
        print(f"  ↪ Clôture fin de backtest: {pnl:+.2f}R | solde {state['balance']:.2f}")

    t = state["trades"]
    wins = sum(1 for x in t if x > 0)
    print("\n" + "=" * 60)
    print(f"📊 BILAN GEMINI (backtest) | Trades: {len(t)} | Wins: {wins} | "
          f"Expectancy: {(sum(t)/len(t)) if t else 0:+.2f}R | Solde: {state['balance']:.2f}")
    print(f"   Appels Gemini: {gemini_calls}")
    print("=" * 60)


# ============================================================
# Boucle principale
# ============================================================
def manage(state, candle, config):
    """Gere la position ouverte sur une bougie fermee."""
    pos = state["pos"]
    if pos and not pos.closed:
        if pos.update(candle):
            risk_amt = state["balance"] * config.risk_percent / 100
            state["balance"] += risk_amt * pos.pnl_r
            state["trades"].append(pos.pnl_r)
            print(f"  {'✅' if pos.pnl_r > 0 else '🛑'} FERMETURE {pos.side} {pos.exit_reason} | "
                  f"{pos.pnl_r:+.2f}R | solde {state['balance']:.2f}")
            state["pos"] = None


def run(symbol, ticker, config, rounds, interval, gemini_every):
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        print("❌ GEMINI_API_KEY manquante. Obtiens-en une gratuite sur https://aistudio.google.com/")
        return
    client = GeminiClient()
    state = {"pos": None, "balance": config.initial_balance, "trades": []}
    print(f"🤖 BOT GEMINI (paper) sur {symbol} | {rounds} cycles | interval {interval}s | "
          f"Gemini tous les {gemini_every} cycles\n")

    for r in range(1, rounds + 1):
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")
        try:
            h1 = fetch_df(ticker, "H1")
        except Exception as e:
            print(f"[{now}] ⚠️ fetch: {e}"); time.sleep(interval); continue

        last_closed_idx = len(h1) - 2          # la derniere est en cours
        if last_closed_idx < 1:
            time.sleep(interval); continue
        row = h1.iloc[last_closed_idx]
        price = float(row["close"])
        state["last_price"] = price
        atr = float(row["ATR"]) if pd.notna(row.get("ATR")) else 0.0

        # 1) gestion position ouverte
        from backtest import Candle
        candle = Candle(time=h1.index[last_closed_idx].to_pydatetime(), open=float(row["open"]),
                        high=float(row["high"]), low=float(row["low"]), close=price)
        manage(state, candle, config)

        # 2) decision Gemini si a plat + tour de Gemini
        call_gemini = (state["pos"] is None) and (r % gemini_every == 0 or r == 1)
        if call_gemini and atr > 0:
            try:
                h4 = fetch_df(ticker, "H4")
                d1 = fetch_df(ticker, "D1")
                w1 = fetch_df(ticker, "W1")
                bulletin = build_bulletin(symbol, h1, h4, price, config.spread_points)
                paths = [paint_chart(w1, symbol, "W1"), paint_chart(d1, symbol, "D1"),
                         paint_chart(h4, symbol, "H4"), paint_chart(h1, symbol, "H1")]
                print(f"[{now}] 🔎 Gemini analyse {symbol} ({len(paths)} graphiques)...")
                decision = ask_gemini(client, bulletin, paths)
            except Exception as e:
                print(f"[{now}] ⚠️ Gemini: {e}"); decision = None

            if not decision:
                print(f"[{now}] ⏸️ pas de decision (Gemini indecis ou erreur)")
            else:
                verdict = decision.get("decision", "WAIT")
                conf = decision.get("confidence", 0)
                reason = decision.get("reason", "")[:70]
                print(f"[{now}] 🧠 VERDICT: {verdict} ({conf}%) | {reason}")
                if verdict in ("BUY", "SELL") and conf >= 75:
                    sl_mult = float(decision.get("sl_atr_multiplier", 2.0))
                    state["pos"] = PaperPosition(verdict, price, atr, config, candle.time)
                    state["pos"].sl = price - atr * sl_mult if verdict == "BUY" else price + atr * sl_mult
                    state["pos"].risk = atr * sl_mult
                    print(f"  🟢 OUVERTURE {verdict} @ {price:.5f} | SL {state['pos'].sl:.5f}")
                else:
                    print(f"  ⏸️ {verdict} (conf {conf}% < 75 ou WAIT)")
        time.sleep(interval)

    # Cloture mark-to-market de la position encore ouverte (pour le bilan)
    if state["pos"] and not state["pos"].closed and "last_price" in state:
        pos = state["pos"]
        rfun = (lambda p: (p - pos.entry) / pos.risk) if pos.side == "BUY" else (lambda p: (pos.entry - p) / pos.risk)
        half = config.partial_ratio
        pnl = (half * config.tp1_r + (1 - half) * rfun(state["last_price"])) if pos.partial else rfun(state["last_price"])
        state["balance"] += state["balance"] * config.risk_percent / 100 * pnl
        state["trades"].append(pnl)
        print(f"  ↪ Cloture fin de session @ {state['last_price']:.5f}: {pnl:+.2f}R | solde {state['balance']:.2f}")

    # bilan
    t = state["trades"]
    wins = sum(1 for x in t if x > 0)
    print("\n" + "=" * 56)
    print(f"📊 BILAN GEMINI | Trades fermés: {len(t)} | Wins: {wins} | "
          f"Expectancy: {(sum(t)/len(t)) if t else 0:+.2f}R | Solde: {state['balance']:.2f}")
    print("=" * 56)


def main():
    p = argparse.ArgumentParser(description="Vrai bot Gemini (paper live OU backtest)")
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--risk", type=float, default=1.0)
    p.add_argument("--strategy", choices=["deleuse", "trend"], default="deleuse")
    # mode backtest
    p.add_argument("--backtest", action="store_true", help="rejoue l'historique (sans attendre)")
    p.add_argument("--csv", help="CSV H1 (defaut: data/{SYMBOL}_H1.csv)")
    p.add_argument("--bars", type=int, default=1500, help="fenetre de backtest (bougies H1)")
    p.add_argument("--max-gemini", type=int, default=60, help="limite d'appels Gemini (quota)")
    # mode live
    p.add_argument("--rounds", type=int, default=12)
    p.add_argument("--interval", type=int, default=300, help="secondes entre cycles (live)")
    p.add_argument("--gemini-every", type=int, default=6, help="appel Gemini tous les N cycles (live)")
    args = p.parse_args()
    config = BacktestConfig(symbol=args.symbol, risk_percent=args.risk, mode="day", strategy=args.strategy)
    if args.backtest:
        csv = args.csv or f"data/{args.symbol.upper()}_H1.csv"
        if not os.path.exists(csv):
            print(f"❌ CSV introuvable: {csv}")
            print("   Lance: python tools/fetch_data.py --source yahoo --range 2y")
            return
        run_backtest(args.symbol, csv, config, args.bars, args.max_gemini)
    else:
        ticker = TICKERS.get(args.symbol.upper(), args.symbol)
        run(args.symbol, ticker, config, args.rounds, args.interval, args.gemini_every)


if __name__ == "__main__":
    main()
