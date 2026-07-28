"""Backtest local sans dépendances lourdes pour GEMINI GOLD EYE.

Usage rapide :
    python backtest.py --demo --bars 700
    python backtest.py --csv data/EURUSD_H1.csv --symbol EURUSD
    python backtest.py --mt5 --symbol XAUUSD --bars 2000

Le CSV doit contenir au minimum: time, open, high, low, close.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import math
import os
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

Direction = Literal["BUY", "SELL", "WAIT"]
Outcome = Literal["WIN", "LOSS", "BE", "OPEN", "WAIT"]


@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: float = 1_000.0
    ema50: float = 0.0
    ema200: float = 0.0
    atr: float = 0.0
    rsi: float = 50.0
    macd_hist: float = 0.0
    stoch_k: float = 50.0
    vwap: float = 0.0
    adx: float = 0.0


@dataclass
class BacktestConfig:
    symbol: str = "EURUSD"
    bars: int = 1200
    initial_balance: float = 10_000.0
    risk_percent: float = 1.0
    min_confidence: int = 75
    sl_atr_multiplier: float = 2.0
    rr_ratio: float = 2.5            # objectif R:R 1:2.5
    max_holding_bars: int = 120      # ~5 jours : laisser courir les gagnants
    spread_points: int = 10
    cooldown_bars: int = 6           # pause apres chaque trade (anti-overtrading)
    mode: str = "day"                # "day" (intraday) ou "swing"
    session_start_hour: int = 6      # entrees uniquement en session liquide (heure UTC)
    session_end_hour: int = 15       # fin des entrees (avant cloture NY)
    point: float = 0.00001
    be_at_r: float = 1.0
    be_offset_points: int = 10
    trailing_start_r: float = 1.7
    trailing_atr_multiplier: float = 1.5
    tp1_r: float = 1.5              # cible de prise partielle (en multiple de R)
    partial_ratio: float = 0.5      # fraction de la position fermee a tp1 (free trade)
    adx_min: int = 0                # force tendance min (0 = filtre ADX desactive ; calibre a 22 nuit a l'edge 2 ans)
    output: str = "backtest_results/gemini_gold_eye_backtest.csv"


@dataclass
class Decision:
    decision: Direction
    confidence: int
    reason: str
    sl_atr_multiplier: float
    risk_reward_ratio: float


@dataclass
class TradeResult:
    time: str
    symbol: str
    decision: Direction
    confidence: int
    entry: float
    sl: float
    tp: float
    atr: float
    risk_amount: float
    lot_units: float
    outcome: Outcome
    pnl_r: float
    pnl_money: float
    balance: float
    reason: str


def rolling_sma(values: list[float], i: int, length: int) -> float:
    if i + 1 < length:
        return float("nan")
    window = values[i + 1 - length : i + 1]
    return sum(window) / length


def compute_adx(candles: list[Candle], period: int = 14):
    """ADX (Wilder) : force de la tendance. >25 = tendance, <20 = range/chop."""
    n = len(candles)
    if n < period * 2:
        return
    trs: list[float] = []
    pdms: list[float] = []
    mdms: list[float] = []
    for i, c in enumerate(candles):
        if i == 0:
            trs.append(c.high - c.low); pdms.append(0.0); mdms.append(0.0)
            continue
        prev = candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
        up = c.high - prev.high
        down = prev.low - c.low
        pdms.append(up if (up > down and up > 0) else 0.0)
        mdms.append(down if (down > up and down > 0) else 0.0)
        trs.append(tr)
    tr_s = sum(trs[:period])
    pdm_s = sum(pdms[:period])
    mdm_s = sum(mdms[:period])
    dxs: list[float] = []
    adx = 0.0
    for i in range(period, n):
        tr_s = tr_s - tr_s / period + trs[i]
        pdm_s = pdm_s - pdm_s / period + pdms[i]
        mdm_s = mdm_s - mdm_s / period + mdms[i]
        di_p = 100 * pdm_s / tr_s if tr_s else 0.0
        di_m = 100 * mdm_s / tr_s if tr_s else 0.0
        denom = di_p + di_m
        dx = 100 * abs(di_p - di_m) / denom if denom else 0.0
        dxs.append(dx)
        if len(dxs) <= period:
            adx = sum(dxs) / len(dxs)
        else:
            adx = (adx * (period - 1) + dx) / period
        candles[i].adx = adx


def apply_indicators(candles: list[Candle]) -> list[Candle]:
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [max(c.tick_volume, 1.0) for c in candles]

    ema12 = ema26 = signal = closes[0]
    ema50 = ema200 = closes[0]
    gains: list[float] = []
    losses: list[float] = []
    trs: list[float] = []

    for i, candle in enumerate(candles):
        close = candle.close
        ema50 = close * (2 / 51) + ema50 * (1 - 2 / 51)
        ema200 = close * (2 / 201) + ema200 * (1 - 2 / 201)
        ema12 = close * (2 / 13) + ema12 * (1 - 2 / 13)
        ema26 = close * (2 / 27) + ema26 * (1 - 2 / 27)
        macd_line = ema12 - ema26
        signal = macd_line * (2 / 10) + signal * (1 - 2 / 10)

        prev_close = closes[i - 1] if i else close
        tr = max(candle.high - candle.low, abs(candle.high - prev_close), abs(candle.low - prev_close))
        trs.append(tr)

        delta = close - prev_close
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

        candle.ema50 = ema50
        candle.ema200 = ema200
        candle.macd_hist = macd_line - signal
        candle.atr = rolling_sma(trs, i, 14)
        avg_gain = rolling_sma(gains, i, 14)
        avg_loss = rolling_sma(losses, i, 14)
        if math.isfinite(avg_gain) and math.isfinite(avg_loss) and avg_loss != 0:
            rs = avg_gain / avg_loss
            candle.rsi = 100 - (100 / (1 + rs))
        elif math.isfinite(avg_gain) and avg_loss == 0:
            candle.rsi = 100.0

        low14 = rolling_sma(lows, i, 1) if i < 13 else min(lows[i - 13 : i + 1])
        high14 = rolling_sma(highs, i, 1) if i < 13 else max(highs[i - 13 : i + 1])
        candle.stoch_k = 50.0 if high14 == low14 else 100 * (close - low14) / (high14 - low14)

        start = max(0, i - 23)
        typical_volume = 0.0
        total_volume = 0.0
        for j in range(start, i + 1):
            typical = (candles[j].high + candles[j].low + candles[j].close) / 3
            typical_volume += typical * volumes[j]
            total_volume += volumes[j]
        candle.vwap = typical_volume / total_volume if total_volume else close

    compute_adx(candles)
    return [c for c in candles if math.isfinite(c.atr)]


def load_csv(path: str) -> list[Candle]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        candles = []
        for row in reader:
            lower = {k.lower(): v for k, v in row.items()}
            candles.append(
                Candle(
                    time=datetime.fromisoformat(lower["time"].replace("Z", "+00:00")).replace(tzinfo=None),
                    open=float(lower["open"]),
                    high=float(lower["high"]),
                    low=float(lower["low"]),
                    close=float(lower["close"]),
                    tick_volume=float(lower.get("tick_volume") or lower.get("volume") or 1000),
                )
            )
    return candles


def load_mt5(symbol: str, bars: int) -> list[Candle]:
    mt5 = importlib.import_module("MetaTrader5")
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize impossible: {mt5.last_error()}")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, bars)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Aucune donnée MT5 pour {symbol}")
    return [
        Candle(
            time=datetime.fromtimestamp(int(r["time"])),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            tick_volume=float(r["tick_volume"]),
        )
        for r in rates
    ]


def make_demo_data(bars: int) -> list[Candle]:
    rng = random.Random(42)
    candles: list[Candle] = []
    close = 1.08
    now = datetime(2024, 1, 1)
    for i in range(bars):
        wave = math.sin(i / 35) * 0.00015
        drift = 0.000015 if i % 240 < 140 else -0.00001
        noise = rng.gauss(0, 0.00065)
        open_ = close
        close = close + wave + drift + noise
        wick = rng.uniform(0.00025, 0.0012)
        high = max(open_, close) + wick
        low = min(open_, close) - wick
        candles.append(Candle(now + timedelta(hours=i), open_, high, low, close, rng.randint(500, 2500)))
    return candles


def resample_h4(candles: list[Candle]) -> list[Candle]:
    grouped: dict[datetime, list[Candle]] = {}
    for c in candles:
        slot = c.time.replace(hour=(c.time.hour // 4) * 4, minute=0, second=0, microsecond=0)
        grouped.setdefault(slot, []).append(c)
    h4 = []
    for slot in sorted(grouped):
        group = grouped[slot]
        h4.append(
            Candle(
                time=slot,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                tick_volume=sum(c.tick_volume for c in group),
            )
        )
    return apply_indicators(h4)


def h4_at(h4: list[Candle], time_value: datetime) -> Candle | None:
    eligible = [c for c in h4 if c.time <= time_value]
    return eligible[-1] if eligible else None


def build_bulletin(symbol: str, h1: Candle, h4: Candle, spread_points: int) -> dict:
    return {
        "META": {"Symbol": symbol, "Scan_Time": str(h1.time), "Live_Price": round(h1.close, 5)},
        "INSTITUTIONAL_BIAS": {
            "Price_vs_VWAP_H1": "BULLISH" if h1.close > h1.vwap else "BEARISH",
            "VWAP_Level": round(h1.vwap, 5),
        },
        "H1_INDICATORS": {
            "RSI": round(h1.rsi, 2),
            "MACD_Histogram": round(h1.macd_hist, 5),
            "Stoch_K": round(h1.stoch_k, 2),
            "ATR": round(h1.atr, 5),
            "ADX": round(h1.adx, 1),
            "Trend": "BULLISH" if h1.close > h1.ema200 else "BEARISH",
        },
        "H4_STRUCTURE": {
            "Trend_EMA200": "BULLISH" if h4.close > h4.ema200 else "BEARISH",
            "RSI": round(h4.rsi, 2),
            "MACD_Status": "UP" if h4.macd_hist > 0 else "DOWN",
        },
        "SAFETY": {"SPREAD": spread_points, "GOLD_MODE": "XAU" in symbol.upper()},
    }


def decide(bulletin: dict, config: BacktestConfig) -> Decision:
    h1 = bulletin["H1_INDICATORS"]
    h4 = bulletin["H4_STRUCTURE"]
    safety = bulletin["SAFETY"]
    bias = bulletin["INSTITUTIONAL_BIAS"]["Price_vs_VWAP_H1"]

    if safety["GOLD_MODE"] and safety["SPREAD"] > 40:
        return Decision("WAIT", 20, "Spread Gold trop élevé", config.sl_atr_multiplier, config.rr_ratio)
    if h1["Trend"] != h4["Trend_EMA200"]:
        return Decision("WAIT", 35, "Conflit H1/H4", config.sl_atr_multiplier, config.rr_ratio)
    # Filtre de régime : on ne trade que s'il y a une vraie tendance (sinon chop = pertes)
    if h1.get("ADX", 0) < config.adx_min:
        return Decision("WAIT", 30, "Marché en range (ADX faible)", config.sl_atr_multiplier, config.rr_ratio)
    if h1["RSI"] > 68 or h1["RSI"] < 32:
        return Decision("WAIT", 45, "RSI extrême", config.sl_atr_multiplier, config.rr_ratio)

    direction: Direction = "BUY" if h1["Trend"] == "BULLISH" else "SELL"

    # Confluence VWAP : le biais VWAP doit suivre la tendance H1 (sinon pas d'entrée)
    if bias != h1["Trend"]:
        return Decision("WAIT", 40, "VWAP désaligné de la tendance", config.sl_atr_multiplier, config.rr_ratio)
    score = 45
    if (direction == "BUY" and bias == "BULLISH") or (direction == "SELL" and bias == "BEARISH"):
        score += 15
    if (direction == "BUY" and h1["MACD_Histogram"] > 0) or (direction == "SELL" and h1["MACD_Histogram"] < 0):
        score += 15
    if (direction == "BUY" and h4["MACD_Status"] == "UP") or (direction == "SELL" and h4["MACD_Status"] == "DOWN"):
        score += 10
    if 38 <= h1["RSI"] <= 62:
        score += 10
    if safety["SPREAD"] <= 20:
        score += 5

    if score < config.min_confidence:
        return Decision("WAIT", score, "Confluence insuffisante", config.sl_atr_multiplier, config.rr_ratio)
    return Decision(direction, min(score, 95), f"Alignement {direction} H1/H4 + VWAP/MACD", config.sl_atr_multiplier, config.rr_ratio)


def simulate_trade(future: list[Candle], entry: float, entry_time: datetime, atr_value: float, decision: Decision, config: BacktestConfig) -> tuple[Outcome, float, int]:
    risk_dist = atr_value * decision.sl_atr_multiplier
    if risk_dist <= 0:
        return "WAIT", 0.0, 0
    is_buy = decision.decision == "BUY"
    sl = entry - risk_dist if is_buy else entry + risk_dist
    tp1 = entry + risk_dist * config.tp1_r if is_buy else entry - risk_dist * config.tp1_r        # prise partielle
    tp2 = entry + risk_dist * decision.risk_reward_ratio if is_buy else entry - risk_dist * decision.risk_reward_ratio  # cible finale
    half = config.partial_ratio
    partial_done = False
    sl_current = sl
    exit_price = entry
    trailing_dist = atr_value * config.trailing_atr_multiplier
    horizon = future[: config.max_holding_bars]

    def runner(price: float) -> float:
        return (price - entry) / risk_dist if is_buy else (entry - price) / risk_dist

    for idx, candle in enumerate(horizon):
        held = idx + 1
        # DAY TRADING : sortie fin de jour (zéro position la nuit)
        if config.mode == "day" and candle.time.date() != entry_time.date():
            rpnl = runner(candle.open)
            pnl = (half * config.tp1_r + (1 - half) * rpnl) if partial_done else rpnl
            return "OPEN", pnl, held
        exit_price = candle.close
        if is_buy:
            if candle.low <= sl_current:                                   # stop (conservateur d'abord)
                if partial_done:
                    pnl = half * config.tp1_r + (1 - half) * runner(sl_current)
                    return ("WIN" if pnl > 0 else "LOSS"), pnl, held
                return "LOSS", -1.0, held
            if not partial_done and candle.high >= tp1:                     # FREE TRADE : on sécurise 50% + SL à l'entrée
                partial_done = True
                sl_current = entry
            if partial_done and candle.high >= tp2:                        # cible finale sur le reste
                pnl = half * config.tp1_r + (1 - half) * decision.risk_reward_ratio
                return "WIN", pnl, held
            if partial_done:                                               # trailing sur le runner
                sl_current = max(sl_current, candle.close - trailing_dist)
        else:
            if candle.high >= sl_current:
                if partial_done:
                    pnl = half * config.tp1_r + (1 - half) * runner(sl_current)
                    return ("WIN" if pnl > 0 else "LOSS"), pnl, held
                return "LOSS", -1.0, held
            if not partial_done and candle.low <= tp1:
                partial_done = True
                sl_current = entry
            if partial_done and candle.low <= tp2:
                pnl = half * config.tp1_r + (1 - half) * decision.risk_reward_ratio
                return "WIN", pnl, held
            if partial_done:
                sl_current = min(sl_current, candle.close + trailing_dist)

    rpnl = runner(exit_price)
    pnl = (half * config.tp1_r + (1 - half) * rpnl) if partial_done else rpnl
    return "OPEN", pnl, len(horizon)


def run_backtest(candles: list[Candle], config: BacktestConfig) -> list[TradeResult]:
    h1 = apply_indicators(candles)
    h4 = resample_h4(h1)
    balance = config.initial_balance
    results: list[TradeResult] = []

    # UNE seule position à la fois + cooldown : on avance dans le temps après
    # chaque trade (réaliste, évite l'overtrading de 4000+ trades).
    i = 220
    n = len(h1)
    while i < n - config.max_holding_bars:
        row = h1[i]
        h4_row = h4_at(h4, row.time)
        if h4_row is None:
            i += 1
            continue
        # DAY TRADING : on n'entre qu'en session liquide (Londres/NY)
        if config.mode == "day":
            h = row.time.hour
            if not (config.session_start_hour <= h < config.session_end_hour):
                i += 1
                continue
        bulletin = build_bulletin(config.symbol, row, h4_row, config.spread_points)
        decision = decide(bulletin, config)
        if decision.decision == "WAIT":
            i += 1
            continue

        entry = row.close
        risk_dist = row.atr * decision.sl_atr_multiplier
        risk_amount = balance * (config.risk_percent / 100)
        lot_units = risk_amount / risk_dist if risk_dist else 0.0
        outcome, pnl_r, held = simulate_trade(h1[i + 1 :], entry, row.time, row.atr, decision, config)
        pnl_money = risk_amount * pnl_r
        balance += pnl_money
        results.append(
            TradeResult(
                time=str(row.time),
                symbol=config.symbol,
                decision=decision.decision,
                confidence=decision.confidence,
                entry=round(entry, 5),
                sl=round(entry - risk_dist if decision.decision == "BUY" else entry + risk_dist, 5),
                tp=round(entry + risk_dist * decision.risk_reward_ratio if decision.decision == "BUY" else entry - risk_dist * decision.risk_reward_ratio, 5),
                atr=round(row.atr, 5),
                risk_amount=round(risk_amount, 2),
                lot_units=round(lot_units, 2),
                outcome=outcome,
                pnl_r=round(pnl_r, 2),
                pnl_money=round(pnl_money, 2),
                balance=round(balance, 2),
                reason=decision.reason,
            )
        )
        # On saute la durée du trade + cooldown : pas de chevauchement.
        i += max(held, 1) + config.cooldown_bars
    return results


def write_results(results: list[TradeResult], output: str) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(TradeResult.__dataclass_fields__)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow(asdict(row))


def print_report(results: list[TradeResult], config: BacktestConfig) -> None:
    print("\n📊 BACKTEST GEMINI GOLD EYE")
    print(f"Symbole: {config.symbol} | Mode: {config.mode.upper()} | Risk: {config.risk_percent}% | RR: {config.rr_ratio}")
    if config.mode == "day":
        print(f"Session: {config.session_start_hour}h-{config.session_end_hour}h UTC | Sortie fin de jour (zéro nuit)")
    if not results:
        print("Aucun trade déclenché par les règles de confluence.")
        print(f"Export CSV: {config.output}")
        return
    wins = sum(r.outcome == "WIN" for r in results)
    losses = sum(r.outcome == "LOSS" for r in results)
    be = sum(r.outcome == "BE" for r in results)
    open_trades = sum(r.outcome == "OPEN" for r in results)
    win_rate = wins / max(wins + losses, 1) * 100
    expectancy = sum(r.pnl_r for r in results) / len(results)
    final_balance = results[-1].balance
    gross_win = sum(r.pnl_money for r in results if r.pnl_money > 0)
    gross_loss = abs(sum(r.pnl_money for r in results if r.pnl_money < 0))
    profit_factor = gross_win / gross_loss if gross_loss else float("inf")
    peak = config.initial_balance
    max_dd = 0.0
    for r in results:
        peak = max(peak, r.balance)
        max_dd = min(max_dd, r.balance - peak)
    print(f"Trades: {len(results)} | WIN: {wins} | LOSS: {losses} | BE: {be} | OPEN: {open_trades}")
    print(f"Win rate hors BE/OPEN: {win_rate:.1f}%")
    print(f"Expectancy: {expectancy:.2f} R/trade | Profit factor: {profit_factor:.2f}")
    print(f"Capital final: {final_balance:.2f} ({final_balance - config.initial_balance:+.2f})")
    print(f"Drawdown max: {max_dd:.2f} ({max_dd / config.initial_balance * 100:.1f}%)")
    print(f"Export CSV: {config.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest local GEMINI GOLD EYE")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="utilise une série synthétique reproductible")
    source.add_argument("--csv", help="chemin CSV H1 avec time/open/high/low/close")
    source.add_argument("--mt5", action="store_true", help="charge les bougies H1 depuis MT5")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--bars", type=int, default=1200)
    parser.add_argument("--risk", type=float, default=float(os.getenv("RISK_PER_TRADE", "1.0")))
    parser.add_argument("--confidence", type=int, default=75)
    parser.add_argument("--rr", type=float, default=2.5)
    parser.add_argument("--sl-atr", type=float, default=2.0)
    parser.add_argument("--max-holding", type=int, default=120)
    parser.add_argument("--spread-points", type=int, default=10)
    parser.add_argument("--mode", choices=["day", "swing"], default="day", help="day (intraday) ou swing")
    parser.add_argument("--session-start", type=int, default=6, help="heure UTC debut session (day)")
    parser.add_argument("--session-end", type=int, default=15, help="heure UTC fin entrees (day)")
    parser.add_argument("--adx-min", type=int, default=0, help="force tendance min (0=off ; >0 filtre ADX)")
    parser.add_argument("--output", default="backtest_results/gemini_gold_eye_backtest.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    point = 0.01 if "XAU" in args.symbol.upper() else 0.00001
    # Day trading : tenue intraday courte + cooldown court ; swing : longue tenue
    max_hold = 8 if args.mode == "day" else args.max_holding
    cooldown = 3 if args.mode == "day" else 6
    config = BacktestConfig(
        symbol=args.symbol,
        bars=args.bars,
        risk_percent=args.risk,
        min_confidence=args.confidence,
        sl_atr_multiplier=args.sl_atr,
        rr_ratio=args.rr,
        max_holding_bars=max_hold,
        spread_points=args.spread_points,
        cooldown_bars=cooldown,
        mode=args.mode,
        session_start_hour=args.session_start,
        session_end_hour=args.session_end,
        adx_min=args.adx_min,
        point=point,
        output=args.output,
    )
    if args.demo:
        candles = make_demo_data(config.bars)
    elif args.csv:
        candles = load_csv(args.csv)
    else:
        candles = load_mt5(config.symbol, config.bars)
    if not candles:
        print("❌ Aucune bougie chargée (fichier vide, introuvable ou téléchargement échoué).")
        return
    results = run_backtest(candles, config)
    write_results(results, config.output)
    print_report(results, config)


if __name__ == "__main__":
    main()
