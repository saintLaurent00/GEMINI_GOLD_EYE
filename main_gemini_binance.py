"""
main_gemini_binance.py - Bot Gemini connecte a BINANCE FUTURES (testnet ou mainnet).

Meme cerveau Gemini que main_gemini_paper.py (analyse multi-TF W1/D1/H4/H1 via
bulletins + images) mais l'execution est REELLE sur Binance USD-M Futures :
  * Entree MARKET sur decision BUY/SELL (conf >= seuil)
  * STOP LOSS = STOP_MARKET  (reduceOnly)
  * TAKE PROFIT = TAKE_PROFIT_MARKET (reduceOnly)
  * Sizing = (balance * risk%) / distance_SL  (respect step/tick/minNotional)
  * Leverage pre-applique au symbol
  * Anti-stacking : pas de nouvel ordre si une position est deja ouverte
                    (verifie via API, donc resiste aux redemarrages)
  * Aucun ordre GRATUIT/trailing sur cette v1 : SL/TP binaires, R:R fixe.

Usage :
  pip install -r requirements.txt
  cp .env.example .env   puis remplir GEMINI_API_KEYS, BINANCE_API_KEY, BINANCE_SECRET
  # testnet recommande pour la mise en route :
  python main_gemini_binance.py --symbol XAUUSD --rounds 60 --interval 300
  # mainnet (ARGENT REEL !) : mettre BINANCE_TESTNET=False dans .env

Arguments :
  --symbol        (defaut XAUUSD)   alias supportes -> symbole Binance
  --risk          (defaut 1.0)      % du solde risque par trade
  --rr            (defaut 2.0)      ratio R:R
  --leverage      (overrides env)   levier applique au symbol
  --rounds        nombre de cycles (0 = boucle infinie)
  --interval      secondes entre 2 cycles (defaut 300 = 5min)
  --confidence    seuil de confiance Gemini (defaut 75)
  --sl-atr        multiplicateur ATR pour SL (defaut: valeur renvoyee par Gemini, fallback 2.0)
  --dry-run       simule les ordres sans les envoyer
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

# pandas_ta est optionnel (cassé par numpy>=2). On fournit un fallback 100% pandas/numpy.
try:
    import pandas_ta as _ta
    _HAS_PANDAS_TA = True
except Exception:
    _ta = None
    _HAS_PANDAS_TA = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from infrastructure.binance_client import (BinanceFuturesClient, BinanceApiError)
from infrastructure.gemini_client import GeminiClient


# ============================================================
# Indicateurs (EMA / RSI / ATR / MACD / VWAP) sans dépendance exotique
# ============================================================
def _ema(s: pd.Series, length: int) -> pd.Series:
    return s.ewm(span=length, adjust=False).mean()


def _rsi(s: pd.Series, length: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _atr(h: pd.Series, l: pd.Series, c: pd.Series, length: int = 14) -> pd.Series:
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def _macd_hist(c: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_f = _ema(c, fast)
    ema_s = _ema(c, slow)
    macd = ema_f - ema_s
    sig = _ema(macd, signal)
    return macd - sig


def _vwap(h: pd.Series, l: pd.Series, c: pd.Series, v: pd.Series) -> pd.Series:
    tp = (h + l + c) / 3.0
    cv = tp * v
    cv_sum = cv.cumsum()
    v_sum = v.cumsum().replace(0, np.nan)
    return cv_sum / v_sum

# Mapping alias metier -> symbole Binance Futures USD-M.
# Sur le testnet, tous les cross/marges ne sont pas actifs ; BTCUSDT et ETHUSDT le sont
# systematiquement ; XAUUSDT l'est aussi sur le testnet public (Gold Perp).
SYMBOL_ALIASES = {
    "XAUUSD": "XAUUSDT",
    "GOLD":   "XAUUSDT",
    "BTCUSD": "BTCUSDT",
    "ETHUSD": "ETHUSDT",
    "EURUSD": "EURUSDT",
    "GBPUSD": "GBPUSDT",
}


# ============================================================
# Donnees de marche Binance -> DataFrame + indicateurs
# ============================================================
def fetch_ohlcv(bc: BinanceFuturesClient, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    """Retourne OHLCV DataFrame avec indicateurs (EMA/RSI/ATR/MACD/VWAP)."""
    raw = bc.klines(symbol, interval=interval, limit=limit)
    rows = []
    for k in raw:
        # k = [ot, O, H, L, C, vol, ct, qvol, trades, ...]
        rows.append({
            "time":   pd.to_datetime(k[0], unit="ms", utc=True).tz_localize(None),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        })
    df = pd.DataFrame(rows).set_index("time").sort_index()
    return _add_indicators(df)


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if _HAS_PANDAS_TA:
            df["EMA50"] = _ta.ema(df["close"], length=50)
            df["EMA200"] = _ta.ema(df["close"], length=200)
            df["RSI"] = _ta.rsi(df["close"], length=14)
            df["ATR"] = _ta.atr(df["high"], df["low"], df["close"], length=14)
            df["VWAP"] = _ta.vwap(df["high"], df["low"], df["close"], df["volume"])
            macd = _ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd is not None:
                df["MACD_HIST"] = macd.iloc[:, 2]
        else:
            # Fallback 100% numpy/pandas
            df["EMA50"] = _ema(df["close"], 50)
            df["EMA200"] = _ema(df["close"], 200)
            df["RSI"] = _rsi(df["close"], 14)
            df["ATR"] = _atr(df["high"], df["low"], df["close"], 14)
            df["VWAP"] = _vwap(df["high"], df["low"], df["close"], df["volume"])
            df["MACD_HIST"] = _macd_hist(df["close"], 12, 26, 9)
    except Exception as e:
        print(f"⚠️ indicateurs: {e}")
    return df


# ============================================================
# Graphiques (mêmes que main_gemini_paper.py)
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
    try:
        loc = pdf.index.get_loc(d)
        return loc if isinstance(loc, int) else 0
    except Exception:
        idx = pdf.index.get_indexer([d], method="nearest")
        return int(idx[0]) if idx[0] >= 0 else 0


def paint_chart(df, symbol, tf_name, outdir="charts_buffer"):
    os.makedirs(outdir, exist_ok=True)
    pdf = df.tail(120).copy()
    adds = []
    for col, c in [("EMA50", "orange"), ("EMA200", "blue"), ("VWAP", "purple")]:
        if col in pdf and pdf[col].dropna().shape[0] > 0:
            try:
                adds.append(mpf.make_addplot(pdf[col].ffill().fillna(0), color=c, width=0.9))
            except Exception:
                pass
    zz = _zigzag(pdf); sr = _sr(pdf)
    args = {"type": "candle", "style": "yahoo", "addplot": adds or None,
            "returnfig": True, "tight_layout": True, "title": f"{symbol} {tf_name}"}

    def _finalize(fig, ax):
        if len(zz) > 1:
            xs = [_to_x(pdf, d) for d, _ in zz]
            ys = [p for _, p in zz]
            ax.plot(xs, ys, color="magenta", linewidth=1.4, alpha=0.8)
        for lv in sr:
            ax.axhline(lv, color="green", linestyle="--", alpha=0.4, linewidth=0.8)
        ax.axhline(float(pdf["close"].iloc[-1]), color="red", linewidth=0.8)
        path = os.path.join(outdir, f"{symbol}_{tf_name}.png")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return path

    try:
        fig, axes = mpf.plot(pdf, **args)
        return _finalize(fig, axes[0])
    except Exception:
        plt.close("all")
        try:
            fig, axes = mpf.plot(pdf, type="candle", style="yahoo", returnfig=True,
                                 tight_layout=True, title=f"{symbol} {tf_name}")
            return _finalize(fig, axes[0])
        except Exception as e2:
            print(f"   ⚠️ paint_chart {tf_name}: {e2}")
            return None


# ============================================================
# Bulletin + Gemini
# ============================================================
def _last(s, col):
    v = s[col].dropna()
    return float(v.iloc[-1]) if len(v) else 0.0


def build_bulletin(symbol, h1, h4, d1, w1, price):
    return {
        "META": {"Symbol": symbol, "Live_Price": round(price, 5),
                 "TimeUTC": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M")},
        "INSTITUTIONAL_BIAS": {
            "W1_Trend": "BULLISH" if price > _last(w1, "EMA200") else "BEARISH",
            "D1_Trend": "BULLISH" if price > _last(d1, "EMA200") else "BEARISH",
            "H4_Trend": "BULLISH" if price > _last(h4, "EMA200") else "BEARISH",
            "H1_vs_VWAP": "BULLISH" if price > _last(h1, "VWAP") else "BEARISH",
        },
        "H1_INDICATORS": {
            "RSI": round(_last(h1, "RSI"), 2),
            "MACD_Histogram": round(_last(h1, "MACD_HIST") if "MACD_HIST" in h1 else 0.0, 5),
            "ATR(14)": round(_last(h1, "ATR"), 5),
        },
        "EXECUTION_PARAMS": {
            "min_RR": 2.0,
            "max_confidence_only": True,
        },
    }


PROMPT = """ROLE: Senior Hedge Fund Trader (Price Action, SMC, Multi-Timeframe).
LANGUAGE: reponds avec 'reason' en FRANCAIS.

OBJECTIVE: Identifier une entree Sniper H1 alignee avec la structure H4 et le biais D1/W1.

--- PART 1: MATHEMATICAL TRUTH (LIVE DATA) ---
{bulletin}

--- PART 2: VISUAL ANALYSIS (W1, D1, H4, H1) ---
Hierarchie : W1/D1 = tendance macro ; H4 = structure ; H1 = declencheur.
Legende : Magenta = structure ZigZag (HH/HL ou LH/LL) ; Bleu = EMA200 ; Orange = EMA50 ;
Violet = VWAP ; Vert pointille = Support/Resistance ; Ligne rouge = prix LIVE.

REGLES STRICTES :
1. Alignement multi-TF : BUY seulement si H1 ET H4 haussiers ; SELL seulement si H1 ET H4 baissiers.
2. Cherche une cassure de structure (BOS) + retest, ou une figure de consolidation (drapeau/triangle).
3. Ignore les doji / fortes meches (indecision). Entre sur une bougie decisive.
4. R:R minimum 2.
5. Ne trade pas si le setup est ambigu -> WAIT.

OUTPUT (JSON STRICT, rien d'autre, sans markdown) :
{{"decision": "BUY" | "SELL" | "WAIT", "confidence": 0-100, "reason": "analyse courte en FRANCAIS", "sl_atr_multiplier": 2.0}}
"""


def extract_json(text: str):
    if not text:
        return None
    t = text.replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def ask_gemini(client, bulletin, image_paths):
    prompt = PROMPT.format(bulletin=json.dumps(bulletin, indent=2, ensure_ascii=False))
    raw = client.send_multimodal_prompt(prompt, image_paths)
    return extract_json(raw)


# ============================================================
# Execution REELLE : sizing + ordres
# ============================================================
def compute_qty(bc: BinanceFuturesClient, symbol: str, side: str, entry: float,
                sl_price: float, risk_pct: float) -> tuple[float, float, float]:
    """
    Calcule la qte a acheter/vendre pour risquer `risk_pct`% du solde USDT.
    Formule : qty = (balance * risk%) / |entry - sl|
    Retourne (qty_normalisee, sl_normalise, notional).
    """
    balance = bc.balance_usdt()
    risk_amt = balance * (risk_pct / 100.0)
    sl_dist = abs(entry - sl_price)
    if sl_dist <= 0:
        raise BinanceApiError(-1, f"SL distance nulle (entry={entry}, sl={sl_price})")
    raw_qty = risk_amt / sl_dist
    qty = bc.normalize_quantity(symbol, raw_qty)
    sl = bc.normalize_price(symbol, sl_price)
    notional = bc.check_notional(symbol, qty, entry)
    # Verif de securite : qty ne doit pas risquer plus de 2x le risque souhaite
    real_risk = qty * abs(entry - sl)
    if real_risk > risk_amt * 1.5:
        # arrondi quantite au palier de step inf -> risque <= risk_amt
        info = bc.symbol_info(symbol)
        step = info.get("marketStepSize") or info.get("stepSize") or 0.001
        # reduire d'un step a la fois jusqu'a passer sous le risque
        while qty > (info.get("marketMinQty") or 0) and qty * abs(entry - sl) > risk_amt:
            qty = max(0.0, round(qty - step, 12))
        qty = bc.normalize_quantity(symbol, qty)
        notional = bc.check_notional(symbol, qty, entry)
    return qty, sl, notional


def execute_trade(bc: BinanceFuturesClient, symbol: str, side: str, entry: float,
                  sl_price: float, tp_price: float, risk_pct: float, dry_run: bool):
    """
    1) Cancel tous les ordres ouverts existants (nettoyage)
    2) Calcule taille de position
    3) MARKET in
    4) Place STOP_MARKET SL
    5) Place TAKE_PROFIT_MARKET TP
    """
    side = side.upper()
    # Nettoyage prealable
    bc.cancel_open_orders(symbol)

    qty, sl_norm, notional = compute_qty(bc, symbol, side, entry, sl_price, risk_pct)
    tp_norm = bc.normalize_price(symbol, tp_price)

    # Le SL doit etre du bon cote par rapport au sens
    if side == "BUY":
        if not (sl_norm < entry < tp_norm):
            raise BinanceApiError(-1, f"SL/TP du mauvais cote pour BUY: sl={sl_norm} < {entry} < {tp_norm} ?")
        sl_side, tp_side = "SELL", "SELL"
    else:
        if not (tp_norm < entry < sl_norm):
            raise BinanceApiError(-1, f"SL/TP du mauvais cote pour SELL: tp={tp_norm} < {entry} < {sl_norm} ?")
        sl_side, tp_side = "BUY", "BUY"

    # Affichage humain
    sl_dist = abs(entry - sl_norm)
    tp_dist = abs(entry - tp_norm)
    rr = tp_dist / sl_dist if sl_dist else 0
    balance = bc.balance_usdt()
    risk_amt = qty * sl_dist
    print(f"   🧮 sizing : qty={qty} notional≈{notional:.2f} USDT (levier applique cote exchange)")
    print(f"   🧮 risque ≈ {risk_amt:.2f} USDT sur solde {balance:.2f} ({risk_pct}% demandé)")
    print(f"   🧮 entry≈{entry:.5f}  SL={sl_norm:.5f}  TP={tp_norm:.5f}  R:R={rr:.2f}")

    if dry_run:
        print("   🧪 DRY-RUN : aucun ordre reel envoye.")
        return {"dry_run": True, "qty": qty, "sl": sl_norm, "tp": tp_norm, "notional": notional}

    # 3) MARKET entry
    print("   📤 Envoi ordre MARKET...")
    m = bc.market_order(symbol, side, qty)
    print(f"   ✅ MARKET {side} rempli : orderId={m.get('orderId')}")

    # 4) SL
    print("   📤 Placement SL (STOP_MARKET)...")
    try:
        s = bc.place_sl(symbol, sl_side, sl_norm)
        print(f"   ✅ SL placé : orderId={s.get('orderId')} @ {sl_norm}")
    except BinanceApiError as e:
        print(f"   ❌ ERREUR SL : {e} -> fermeture d'urgence de la position")
        bc.close_position(symbol)
        raise

    # 5) TP
    print("   📤 Placement TP (TAKE_PROFIT_MARKET)...")
    try:
        tp = bc.place_tp(symbol, tp_side, tp_norm)
        print(f"   ✅ TP placé : orderId={tp.get('orderId')} @ {tp_norm}")
    except BinanceApiError as e:
        print(f"   ❌ ERREUR TP : {e} -> annulation SL + fermeture position")
        bc.cancel_open_orders(symbol)
        bc.close_position(symbol)
        raise

    return {"market": m, "sl": s, "tp": tp, "qty": qty}


# ============================================================
# Boucle principale
# ============================================================
def log(msg: str):
    print(f"[{dt.datetime.utcnow().strftime('%H:%M:%S')}] {msg}", flush=True)


def run(args):
    # Alias -> symbole Binance
    sym_key = args.symbol.upper()
    binance_symbol = SYMBOL_ALIASES.get(sym_key, sym_key)

    if not (settings.GEMINI_API_KEY or settings.GEMINI_API_KEYS):
        log("❌ Clé(s) Gemini manquante(s) (GEMINI_API_KEYS=...)")
        return 1
    if not settings.BINANCE_API_KEY or not settings.BINANCE_SECRET:
        log("❌ BINANCE_API_KEY/SECRET manquants dans .env")
        return 1

    testnet = settings.BINANCE_TESTNET and not args.mainnet
    log(f"🚀 Lancement BOT GEMINI BINANCE ({'TESTNET fictif' if testnet else 'MAINNET ⚠️ ARGENT REEL'})")
    log(f"   symbole metier={sym_key}  ->  binance={binance_symbol}")
    log(f"   risk={args.risk}%  RR={args.rr}  conf>={args.confidence}  "
        f"dry_run={args.dry_run}  interval={args.interval}s  rounds={args.rounds or '∞'}")

    bc = BinanceFuturesClient(settings.BINANCE_API_KEY, settings.BINANCE_SECRET, testnet=testnet)
    gc = GeminiClient()

    # Vérification connexion + info
    servert = bc.server_time()
    log(f"   serverTime(Binance)={pd.to_datetime(servert, unit='ms')}  soldeUSDT={bc.balance_usdt():.2f}")

    # Info symbole
    info = bc.symbol_info(binance_symbol)
    log(f"   {binance_symbol} step={info['stepSize']} tick={info['tickSize']} "
        f"minQty={info['minQty']} minNotional={info['minNotional']}")

    # Application du levier
    leverage = args.leverage or settings.BINANCE_LEVERAGE
    try:
        bc.set_margin_type(binance_symbol, "ISOLATED")
        r = bc.set_leverage(binance_symbol, leverage)
        log(f"   levier {leverage}x ISOLATED appliqué : {r}")
    except BinanceApiError as e:
        log(f"   ⚠️ set_leverage/margin: {e}")

    rnd = 0
    while True:
        rnd += 1
        if args.rounds and rnd > args.rounds:
            log("🏁 Nombre de rounds atteint, arrêt.")
            break

        try:
            # ---- 1. Récupération données ----
            h1 = fetch_ohlcv(bc, binance_symbol, "1h", 300)
            price = float(h1["close"].iloc[-1])
            atr = float(h1["ATR"].dropna().iloc[-1]) if h1["ATR"].dropna().any() else 0.0
            if atr <= 0:
                log(f"⚠️ ATR nul ({atr}), skip ce cycle.")
                time.sleep(args.interval); continue

            # ---- 2. Etat position (anti-stacking) ----
            pos = bc.position(binance_symbol)
            if pos is not None:
                amt = float(pos["positionAmt"])
                upnl = float(pos["unRealizedProfit"])
                entry_pos = float(pos["entryPrice"])
                side_pos = "LONG" if amt > 0 else "SHORT"
                log(f"📂 POSITION OUVERTE {side_pos} {binance_symbol} qty={abs(amt)} "
                    f"entry={entry_pos:.5f} price={price:.5f} upnl={upnl:+.2f} USDT -> pas de nouvel ordre")
                time.sleep(args.interval); continue

            # Aucune position : verifier aussi qu'il n'y a pas d'ordres en vol (nettoyage)
            oo = bc.open_orders(binance_symbol)
            if oo:
                log(f"🧹 {len(oo)} ordre(s) ouvert(s) sans position -> annulation")
                bc.cancel_open_orders(binance_symbol)

            # ---- 3. Récup TF supérieurs + Gemini ----
            # Appel Gemini seulement tous les N cycles (defaut chaque cycle = 1)
            if rnd == 1 or (rnd % args.gemini_every == 0):
                log(f"🔎 #{rnd} Récupération H4/D1/W1 + analyse Gemini...")
                h4 = fetch_ohlcv(bc, binance_symbol, "4h", 300)
                d1 = fetch_ohlcv(bc, binance_symbol, "1d", 300)
                w1 = fetch_ohlcv(bc, binance_symbol, "1w", 200)
                bulletin = build_bulletin(binance_symbol, h1, h4, d1, w1, price)
                paths = [paint_chart(w1, binance_symbol, "W1"),
                         paint_chart(d1, binance_symbol, "D1"),
                         paint_chart(h4, binance_symbol, "H4"),
                         paint_chart(h1, binance_symbol, "H1")]
                paths = [p for p in paths if p]
                decision = ask_gemini(gc, bulletin, paths)
            else:
                decision = None

            if not decision:
                log(f"⏸️ #{rnd} pas de décision (Gemini skip/indécis/erreur). Prix={price:.5f} ATR(H1)={atr:.5f}")
                time.sleep(args.interval); continue

            verdict = decision.get("decision", "WAIT")
            conf = int(decision.get("confidence", 0))
            reason = (decision.get("reason", "") or "")[:90]
            sl_mult = float(decision.get("sl_atr_multiplier", args.sl_atr))
            log(f"🧠 VERDICT: {verdict} ({conf}%) | sl_mult={sl_mult:.2f} | {reason}")

            if verdict not in ("BUY", "SELL") or conf < args.confidence:
                log(f"⏸️ pas d'action ({verdict} conf<{args.confidence})")
                time.sleep(args.interval); continue

            # ---- 4. Préparation du trade ----
            sl_dist = atr * sl_mult
            if verdict == "BUY":
                sl_price = price - sl_dist
                tp_price = price + sl_dist * args.rr
            else:
                sl_price = price + sl_dist
                tp_price = price - sl_dist * args.rr

            # Rafraichir le prix juste avant l'ordre pour limiter le slippage
            price = bc.price(binance_symbol)
            log(f"🎯 {verdict} préparé : prix_frais={price:.5f} ATR={atr:.5f}")

            try:
                res = execute_trade(bc, binance_symbol, verdict, price, sl_price, tp_price,
                                    risk_pct=args.risk, dry_run=args.dry_run)
                log(f"🟢 TRADE EXECUTÉ : {verdict} {binance_symbol} -> {res}")
            except BinanceApiError as e:
                log(f"❌ Échec exécution : {e}")

        except KeyboardInterrupt:
            log("🛑 Interruption clavier, arrêt propre.")
            break
        except BinanceApiError as e:
            log(f"❌ Erreur Binance (cycle #{rnd}) : {e}")
        except Exception as e:
            log(f"❌ Erreur inattendue (cycle #{rnd}) : {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()

        time.sleep(args.interval)

    # Fin : affichage de l'état
    try:
        log(f"💰 Solde USDT final : {bc.balance_usdt():.2f}")
        ps = bc.positions()
        if ps:
            for p in ps:
                log(f"📂 {p['symbol']} amt={p['positionAmt']} upnl={p['unRealizedProfit']}")
    except Exception:
        pass
    return 0


def main():
    p = argparse.ArgumentParser(description="Bot Gemini -> Binance Futures (réel)")
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--risk", type=float, default=1.0, help="% solde risqué/trade")
    p.add_argument("--rr", type=float, default=2.0, help="R:R")
    p.add_argument("--leverage", type=int, default=0, help="surcharge levier")
    p.add_argument("--rounds", type=int, default=0, help="0=infini")
    p.add_argument("--interval", type=int, default=300, help="secondes entre cycles")
    p.add_argument("--gemini-every", type=int, default=6, help="appel Gemini tous les N cycles")
    p.add_argument("--confidence", type=int, default=75, help="seuil de confiance 0-100")
    p.add_argument("--sl-atr", type=float, default=2.0, help="multiplicateur ATR fallback SL")
    p.add_argument("--dry-run", action="store_true", help="simule, n'envoie aucun ordre")
    p.add_argument("--mainnet", action="store_true", help="forcer mainnet (DANGER)")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
