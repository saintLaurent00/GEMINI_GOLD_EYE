"""
main_paper.py - PAPER TRADING en live sur donnees Yahoo (GRATUIT, SANS API, SANS broker).

Le bot prend ses decisions sur les vraies bougies H1 et SIMULE les trades
(entree, SL, prise partielle "free trade", trailing, sortie fin de jour).
Reutilise EXACTEMENT la meme logique que le backtest (backtest.py).

Modes :
    REPLAY (defaut) : rejoue les dernieres bougies H1 fermees -> tu vois le bot trader immediatement.
    LIVE            : sonde Yahoo en continu et trade au fil de l'eau (nouvelles bougies H1).

Exemples :
    python main_paper.py --symbol EURUSD            # replay recent (EUR/USD)
    python main_paper.py --symbol XAUUSD --bars 400  # replay plus long (Or)
    python main_paper.py --symbol EURUSD --live      # vrai live (sondage continu)
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.request

# Racine du projet sur le path (pour importer backtest)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import (apply_indicators, build_bulletin, decide, resample_h4,
                      h4_at, BacktestConfig, Candle)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

TICKERS = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F",     "BTCUSD": "BTC-USD",
}


def fetch_h1(ticker, rng="3mo"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1h&range={rng}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    result = data["chart"]["result"][0]
    ts = result["timestamp"]
    q = result["indicators"]["quote"][0]
    out = []
    for t, o, h, l, c in zip(ts, q["open"], q["high"], q["low"], q["close"]):
        if None in (o, h, l, c):
            continue
        out.append(Candle(time=datetime.datetime.utcfromtimestamp(int(t)).replace(tzinfo=None),
                          open=float(o), high=float(h), low=float(l), close=float(c)))
    return out


# ============================================================
# Position papier : gestion incrementale (free trade + trailing + EOD)
# ============================================================
class PaperPosition:
    def __init__(self, side, entry, atr, config, entry_time):
        self.side, self.entry, self.atr = side, entry, atr
        self.cfg, self.entry_time = config, entry_time
        risk = atr * config.sl_atr_multiplier
        self.risk = risk
        buy = side == "BUY"
        self.sl = entry - risk if buy else entry + risk
        self.tp1 = entry + risk * config.tp1_r if buy else entry - risk * config.tp1_r
        self.tp2 = entry + risk * config.rr_ratio if buy else entry - risk * config.rr_ratio
        self.partial = False
        self.partial_event = False
        self.closed = False
        self.exit_price = self.pnl_r = 0.0
        self.exit_reason = ""

    def _runner(self, p):
        return (p - self.entry) / self.risk if self.side == "BUY" else (self.entry - p) / self.risk

    def _close(self, price, reason):
        half = self.cfg.partial_ratio
        self.pnl_r = (half * self.cfg.tp1_r + (1 - half) * self._runner(price)) if self.partial else self._runner(price)
        self.exit_price, self.exit_reason, self.closed = price, reason, True

    def update(self, c):
        """Met a jour avec une bougie fermee. Retourne True si la position est fermee."""
        if self.closed:
            return True
        self.partial_event = False
        buy = self.side == "BUY"
        if self.cfg.mode == "day" and c.time.date() != self.entry_time.date():
            self._close(c.open, "EOD fin de jour")
            return True
        if buy:
            if c.low <= self.sl:
                self._close(self.sl, "SL")
                return True
            if not self.partial and c.high >= self.tp1:
                self.partial = True
                self.sl = self.entry            # free trade
                self.partial_event = True
            if self.partial and c.high >= self.tp2:
                self._close(self.tp2, "TP final 2.5R")
                return True
            if self.partial:
                self.sl = max(self.sl, c.close - self.atr * self.cfg.trailing_atr_multiplier)
        else:
            if c.high >= self.sl:
                self._close(self.sl, "SL")
                return True
            if not self.partial and c.low <= self.tp1:
                self.partial = True
                self.sl = self.entry
                self.partial_event = True
            if self.partial and c.low <= self.tp2:
                self._close(self.tp2, "TP final 2.5R")
                return True
            if self.partial:
                self.sl = min(self.sl, c.close + self.atr * self.cfg.trailing_atr_multiplier)
        return False


# ============================================================
# Logique commune : gerer position + decision sur une bougie fermee
# ============================================================
def step(state, row, h4, symbol, config):
    """state = {'pos': PaperPosition|None, 'balance', 'trades': []}."""
    pos = state["pos"]
    if pos and not pos.closed:
        if pos.partial_event:
            print(f"     🔒 Prise partielle +1.5R -> SL ramené à l'entrée (free trade)")
        if pos.update(row):
            risk_amt = state["balance"] * config.risk_percent / 100
            pnl = risk_amt * pos.pnl_r
            state["balance"] += pnl
            state["trades"].append(pos.pnl_r)
            emoji = "✅" if pos.pnl_r > 0 else "🛑"
            print(f"  {emoji} FERMETURE {pos.side} {pos.exit_reason} | "
                  f"{pos.pnl_r:+.2f}R ({pnl:+.1f}€) | solde {state['balance']:.2f}")
            state["pos"] = None
            return
        state["pos"] = pos
    if state["pos"] is None:
        h4_row = h4_at(h4, row.time)
        if not h4_row:
            return
        in_session = config.mode != "day" or (config.session_start_hour <= row.time.hour < config.session_end_hour)
        if not in_session:
            return
        d = decide(build_bulletin(symbol, row, h4_row, config.spread_points), config)
        if d.decision in ("BUY", "SELL"):
            state["pos"] = PaperPosition(d.decision, row.close, row.atr, config, row.time)
            print(f"🟢 {row.time} OUVERTURE {d.decision} @ {row.close:.5f} | "
                  f"SL={state['pos'].sl:.5f} TP={state['pos'].tp2:.5f} | {d.reason[:55]}")


def summary(state, config):
    t = state["trades"]
    wins = [r for r in t if r > 0]
    losses = [r for r in t if r < 0]
    wr = len(wins) / max(len(wins) + len(losses), 1) * 100
    exp = sum(t) / len(t) if t else 0
    print("\n" + "=" * 60)
    print(f"📊 BILAN | Trades fermés: {len(t)} | Wins: {len(wins)} | Win rate: {wr:.0f}%")
    print(f"         Expectancy: {exp:+.2f}R/trade")
    print(f"         Solde: {state['balance']:.2f}  ({state['balance'] - config.initial_balance:+.2f})")
    print("=" * 60)


# ============================================================
# Mode REPLAY : rejoue les dernieres bougies fermees
# ============================================================
def run_replay(symbol, ticker, config, n_bars, delay):
    candles = fetch_h1(ticker, "3mo")
    h1 = apply_indicators(candles)
    h4 = resample_h4(h1)
    start = max(220, len(h1) - n_bars)
    state = {"pos": None, "balance": config.initial_balance, "trades": []}
    print(f"\n🎬 PAPER TRADING (REPLAY) {symbol} | mode {config.mode.upper()} | "
          f"{len(h1) - start} bougies H1 | solde départ {config.initial_balance}\n")
    for i in range(start, len(h1) - 1):  # on exclut la derniere (en cours)
        step(state, h1[i], h4, symbol, config)
        if delay:
            time.sleep(delay)
    if state["pos"] and not state["pos"].closed:  # cloture finale
        state["pos"]._close(h1[len(h1) - 2].close, "Fin replay")
        risk_amt = state["balance"] * config.risk_percent / 100
        state["balance"] += risk_amt * state["pos"].pnl_r
        state["trades"].append(state["pos"].pnl_r)
        print(f"  ↪ Clôture fin de replay: {state['pos'].pnl_r:+.2f}R | solde {state['balance']:.2f}")
    summary(state, config)


# ============================================================
# Mode LIVE : sondage continu des nouvelles bougies H1
# ============================================================
def run_live(symbol, ticker, config, duration_min, poll_sec):
    state = {"pos": None, "balance": config.initial_balance, "trades": []}
    last_bar_time = None
    end = time.time() + duration_min * 60
    print(f"\n🔴 PAPER TRADING (LIVE) {symbol} | mode {config.mode.upper()} | "
          f"{duration_min} min (poll {poll_sec}s)\n")
    while time.time() < end:
        try:
            h1 = apply_indicators(fetch_h1(ticker, "3mo"))
        except Exception as e:
            print(f"⚠️ fetch: {e}")
            time.sleep(poll_sec)
            continue
        h4 = resample_h4(h1)
        last_closed = h1[len(h1) - 2]
        step(state, last_closed, h4, symbol, config)
        px = last_closed.close
        pos_str = f"en position {state['pos'].side} (SL {state['pos'].sl:.5f})" if state["pos"] else "à plat"
        if last_closed.time != last_bar_time:
            print(f"⏱️ {last_closed.time} | prix {px:.5f} | {pos_str}")
            last_bar_time = last_closed.time
        time.sleep(poll_sec)
    summary(state, config)


def main():
    p = argparse.ArgumentParser(description="Paper trading GEMINI GOLD EYE (sans broker/API)")
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--risk", type=float, default=1.0)
    p.add_argument("--mode", choices=["day", "swing"], default="day")
    p.add_argument("--bars", type=int, default=250, help="nb de bougies rejouees (replay)")
    p.add_argument("--delay", type=float, default=0.03, help="pause entre bougies (replay)")
    p.add_argument("--live", action="store_true", help="mode live (sondage continu)")
    p.add_argument("--minutes", type=int, default=60, help="duree du mode live (min)")
    p.add_argument("--poll", type=int, default=60, help="intervalle de sondage live (s)")
    args = p.parse_args()

    ticker = TICKERS.get(args.symbol.upper(), args.symbol)
    config = BacktestConfig(symbol=args.symbol, risk_percent=args.risk, mode=args.mode)

    if args.live:
        run_live(args.symbol, ticker, config, args.minutes, args.poll)
    else:
        run_replay(args.symbol, ticker, config, args.bars, args.delay)


if __name__ == "__main__":
    main()
