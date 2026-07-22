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
    supertrend_direction: str = "NEUTRAL"
    ema50: float = 0.0
    ema200: float = 0.0
    atr: float = 0.0
    rsi: float = 50.0
    macd_hist: float = 0.0
    stoch_k: float = 50.0
    vwap: float = 0.0


@dataclass
class BacktestConfig:
    symbol: str = "EURUSD"
    bars: int = 1200
    initial_balance: float = 10_000.0
    risk_percent: float = 1.0
    min_confidence: int = 75
    sl_atr_multiplier: float = 2.0
    rr_ratio: float = 3.0
    max_holding_bars: int = 48
    strategy: str = "confluence"
    spread_points: int = 10
    point: float = 0.00001
    be_at_r: float = 1.0
    be_offset_points: int = 10
    trailing_start_r: float = 1.7
    trailing_atr_multiplier: float = 1.5
    output: str = "backtest_results/gemini_gold_eye_backtest.csv"


@dataclass
class Decision:
    decision: Direction
    confidence: int
    reason: str
    sl_atr_multiplier: float
    risk_reward_ratio: float
    strategy: str = "confluence"


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
    strategy: str = "confluence"


def rolling_sma(values: list[float], i: int, length: int) -> float:
    if i + 1 < length:
        return float("nan")
    window = values[i + 1 - length : i + 1]
    return sum(window) / length


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

    return [c for c in candles if math.isfinite(c.atr)]


def apply_supertrend(candles: list[Candle], period: int = 10, multiplier: float = 3.0) -> list[Candle]:
    prepared = apply_indicators(candles)
    if not prepared:
        return []

    upper_band = 0.0
    lower_band = 0.0
    direction = "BULLISH"
    previous_close = prepared[0].close

    for candle in prepared:
        hl2 = (candle.high + candle.low) / 2
        atr_value = candle.atr if math.isfinite(candle.atr) else 0.0
        basic_upper = hl2 + multiplier * atr_value
        basic_lower = hl2 - multiplier * atr_value

        if upper_band == 0.0 or basic_upper < upper_band or previous_close > upper_band:
            upper_band = basic_upper
        if lower_band == 0.0 or basic_lower > lower_band or previous_close < lower_band:
            lower_band = basic_lower

        if direction == "BULLISH" and candle.close < lower_band:
            direction = "BEARISH"
        elif direction == "BEARISH" and candle.close > upper_band:
            direction = "BULLISH"

        candle.supertrend_direction = direction
        previous_close = candle.close

    return prepared


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
        candles.append(Candle(now + timedelta(minutes=15 * i), open_, high, low, close, rng.randint(500, 2500)))
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


def resample_h1(candles: list[Candle]) -> list[Candle]:
    grouped: dict[datetime, list[Candle]] = {}
    for c in candles:
        slot = c.time.replace(minute=0, second=0, microsecond=0)
        grouped.setdefault(slot, []).append(c)
    h1 = []
    for slot in sorted(grouped):
        group = grouped[slot]
        h1.append(
            Candle(
                time=slot,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                tick_volume=sum(c.tick_volume for c in group),
            )
        )
    return apply_indicators(h1)


def h4_at(h4: list[Candle], time_value: datetime) -> Candle | None:
    eligible = [c for c in h4 if c.time <= time_value]
    return eligible[-1] if eligible else None


def candle_at_or_before(candles: list[Candle], time_value: datetime) -> Candle | None:
    eligible = [c for c in candles if c.time <= time_value]
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
    if h1["RSI"] > 70 or h1["RSI"] < 30:
        return Decision("WAIT", 45, "RSI extrême", config.sl_atr_multiplier, config.rr_ratio)

    direction: Direction = "BUY" if h1["Trend"] == "BULLISH" else "SELL"
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


def asian_breakout_decision(candles: list[Candle], i: int, config: BacktestConfig) -> Decision:
    row = candles[i]
    if not (9 <= row.time.hour < 13):
        return Decision("WAIT", 0, "Hors session Asian Breakout 09h-13h", config.sl_atr_multiplier, config.rr_ratio, "asian_breakout")

    day_candles = [c for c in candles[:i] if c.time.date() == row.time.date() and 0 <= c.time.hour < 9]
    if len(day_candles) < 4:
        return Decision("WAIT", 0, "Range asiatique incomplet", config.sl_atr_multiplier, config.rr_ratio, "asian_breakout")

    asia_high = max(c.high for c in day_candles)
    asia_low = min(c.low for c in day_candles)
    previous = candles[i - 1]

    if previous.close <= asia_high < row.close and row.close > row.ema50:
        return Decision("BUY", 88, f"Cassure range asiatique haut {asia_high:.5f}, SL EMA50", 1.0, config.rr_ratio, "asian_breakout")
    if previous.close >= asia_low > row.close and row.close < row.ema50:
        return Decision("SELL", 88, f"Cassure range asiatique bas {asia_low:.5f}, SL EMA50", 1.0, config.rr_ratio, "asian_breakout")

    return Decision("WAIT", 55, "Pas de cassure confirmée du range asiatique", config.sl_atr_multiplier, config.rr_ratio, "asian_breakout")


def us_opr_decision(candles: list[Candle], h1_supertrend: list[Candle], i: int, config: BacktestConfig) -> Decision:
    row = candles[i]
    is_us_breakout_window = row.time.hour == 15 and row.time.minute >= 45 or row.time.hour == 16 or (row.time.hour == 17 and row.time.minute <= 30)
    if not is_us_breakout_window:
        return Decision("WAIT", 0, "Hors session US OPR 15h45-17h30", config.sl_atr_multiplier, config.rr_ratio, "us_opr")

    open_range = [
        c
        for c in candles[:i]
        if c.time.date() == row.time.date() and c.time.hour == 15 and 30 <= c.time.minute < 45
    ]
    if not open_range:
        return Decision("WAIT", 0, "Bougie OPR 15h30-15h45 absente", config.sl_atr_multiplier, config.rr_ratio, "us_opr")

    opr_high = max(c.high for c in open_range)
    opr_low = min(c.low for c in open_range)
    previous = candles[i - 1]
    trend = candle_at_or_before(h1_supertrend, row.time)
    if trend is None or trend.supertrend_direction == "NEUTRAL":
        return Decision("WAIT", 0, "Supertrend H1 indisponible", config.sl_atr_multiplier, config.rr_ratio, "us_opr")

    if trend.supertrend_direction == "BULLISH" and previous.close <= opr_high < row.close:
        return Decision("BUY", 90, f"US OPR BUY: cassure haut {opr_high:.5f} avec Supertrend H1 haussier", 1.0, config.rr_ratio, "us_opr")
    if trend.supertrend_direction == "BEARISH" and previous.close >= opr_low > row.close:
        return Decision("SELL", 90, f"US OPR SELL: cassure bas {opr_low:.5f} avec Supertrend H1 baissier", 1.0, config.rr_ratio, "us_opr")

    return Decision("WAIT", 55, "Pas de cassure OPR alignée Supertrend H1", config.sl_atr_multiplier, config.rr_ratio, "us_opr")


def simulate_trade(future: list[Candle], entry: float, atr_value: float, decision: Decision, config: BacktestConfig) -> tuple[Outcome, float]:
    risk_dist = atr_value * decision.sl_atr_multiplier
    if risk_dist <= 0:
        return "WAIT", 0.0
    sl = entry - risk_dist if decision.decision == "BUY" else entry + risk_dist
    tp = entry + risk_dist * decision.risk_reward_ratio if decision.decision == "BUY" else entry - risk_dist * decision.risk_reward_ratio
    be_active = False
    sl_current = sl
    exit_price = entry
    trailing_dist = atr_value * config.trailing_atr_multiplier

    for candle in future[: config.max_holding_bars]:
        exit_price = candle.close
        if decision.decision == "BUY":
            if candle.low <= sl_current:
                return ("BE" if be_active else "LOSS", 0.0 if be_active else -1.0)
            if candle.high >= tp:
                return "WIN", decision.risk_reward_ratio
            if not be_active and candle.high >= entry + risk_dist * config.be_at_r:
                sl_current = entry + config.be_offset_points * config.point
                be_active = True
            if be_active and candle.high >= entry + risk_dist * config.trailing_start_r:
                sl_current = max(sl_current, candle.close - trailing_dist)
        else:
            if candle.high >= sl_current:
                return ("BE" if be_active else "LOSS", 0.0 if be_active else -1.0)
            if candle.low <= tp:
                return "WIN", decision.risk_reward_ratio
            if not be_active and candle.low <= entry - risk_dist * config.be_at_r:
                sl_current = entry - config.be_offset_points * config.point
                be_active = True
            if be_active and candle.low <= entry - risk_dist * config.trailing_start_r:
                sl_current = min(sl_current, candle.close + trailing_dist)

    pnl_r = (exit_price - entry) / risk_dist if decision.decision == "BUY" else (entry - exit_price) / risk_dist
    return "OPEN", pnl_r


def simulate_trade_levels(
    future: list[Candle],
    entry: float,
    sl: float,
    tp: float,
    decision: Decision,
    config: BacktestConfig,
) -> tuple[Outcome, float]:
    risk_dist = abs(entry - sl)
    if risk_dist <= 0:
        return "WAIT", 0.0
    be_active = False
    sl_current = sl
    exit_price = entry
    trailing_dist = risk_dist * config.trailing_atr_multiplier

    for candle in future[: config.max_holding_bars]:
        exit_price = candle.close
        if decision.decision == "BUY":
            if candle.low <= sl_current:
                return ("BE" if be_active else "LOSS", 0.0 if be_active else -1.0)
            if candle.high >= tp:
                return "WIN", decision.risk_reward_ratio
            if not be_active and candle.high >= entry + risk_dist * config.be_at_r:
                sl_current = entry + config.be_offset_points * config.point
                be_active = True
            if be_active and candle.high >= entry + risk_dist * config.trailing_start_r:
                sl_current = max(sl_current, candle.close - trailing_dist)
        else:
            if candle.high >= sl_current:
                return ("BE" if be_active else "LOSS", 0.0 if be_active else -1.0)
            if candle.low <= tp:
                return "WIN", decision.risk_reward_ratio
            if not be_active and candle.low <= entry - risk_dist * config.be_at_r:
                sl_current = entry - config.be_offset_points * config.point
                be_active = True
            if be_active and candle.low <= entry - risk_dist * config.trailing_start_r:
                sl_current = min(sl_current, candle.close + trailing_dist)

    pnl_r = (exit_price - entry) / risk_dist if decision.decision == "BUY" else (entry - exit_price) / risk_dist
    return "OPEN", pnl_r


def session_trade_levels(candles: list[Candle], i: int, decision: Decision, config: BacktestConfig) -> tuple[float, float, float]:
    entry = candles[i].close
    if decision.strategy == "asian_breakout":
        sl = candles[i].ema50
        if decision.decision == "BUY" and sl >= entry:
            sl = entry - candles[i].atr * config.sl_atr_multiplier
        if decision.decision == "SELL" and sl <= entry:
            sl = entry + candles[i].atr * config.sl_atr_multiplier
    elif decision.strategy == "us_opr":
        open_range = [
            c
            for c in candles[:i]
            if c.time.date() == candles[i].time.date() and c.time.hour == 15 and 30 <= c.time.minute < 45
        ]
        opr_high = max(c.high for c in open_range)
        opr_low = min(c.low for c in open_range)
        sl = (opr_high + opr_low) / 2
        if decision.decision == "BUY" and sl >= entry:
            sl = entry - candles[i].atr * config.sl_atr_multiplier
        if decision.decision == "SELL" and sl <= entry:
            sl = entry + candles[i].atr * config.sl_atr_multiplier
    else:
        risk_dist = candles[i].atr * decision.sl_atr_multiplier
        sl = entry - risk_dist if decision.decision == "BUY" else entry + risk_dist

    risk_dist = abs(entry - sl)
    tp = entry + risk_dist * decision.risk_reward_ratio if decision.decision == "BUY" else entry - risk_dist * decision.risk_reward_ratio
    return entry, sl, tp


def run_backtest(candles: list[Candle], config: BacktestConfig) -> list[TradeResult]:
    h1 = apply_indicators(candles)
    h4 = resample_h4(h1)
    h1_supertrend = apply_supertrend(resample_h1(candles))
    balance = config.initial_balance
    results: list[TradeResult] = []

    for i in range(220, len(h1) - config.max_holding_bars):
        row = h1[i]
        h4_row = h4_at(h4, row.time)
        if h4_row is None:
            continue
        bulletin = build_bulletin(config.symbol, row, h4_row, config.spread_points)
        if config.strategy == "asian_breakout":
            decision = asian_breakout_decision(h1, i, config)
        elif config.strategy == "us_opr":
            decision = us_opr_decision(h1, h1_supertrend, i, config)
        else:
            decision = decide(bulletin, config)
        if decision.decision == "WAIT":
            continue

        entry, sl, tp = session_trade_levels(h1, i, decision, config)
        risk_dist = abs(entry - sl)
        risk_amount = balance * (config.risk_percent / 100)
        lot_units = risk_amount / risk_dist if risk_dist else 0.0
        outcome, pnl_r = simulate_trade_levels(h1[i + 1 :], entry, sl, tp, decision, config)
        pnl_money = risk_amount * pnl_r
        balance += pnl_money
        results.append(
            TradeResult(
                time=str(row.time),
                symbol=config.symbol,
                decision=decision.decision,
                confidence=decision.confidence,
                entry=round(entry, 5),
                sl=round(sl, 5),
                tp=round(tp, 5),
                atr=round(row.atr, 5),
                risk_amount=round(risk_amount, 2),
                lot_units=round(lot_units, 2),
                outcome=outcome,
                pnl_r=round(pnl_r, 2),
                pnl_money=round(pnl_money, 2),
                balance=round(balance, 2),
                reason=decision.reason,
                strategy=decision.strategy,
            )
        )
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
    print(f"Stratégie: {config.strategy} | Symbole: {config.symbol} | Risk: {config.risk_percent}% | RR: {config.rr_ratio}")
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
    print(f"Trades: {len(results)} | WIN: {wins} | LOSS: {losses} | BE: {be} | OPEN: {open_trades}")
    print(f"Win rate hors BE/OPEN: {win_rate:.1f}%")
    print(f"Expectancy: {expectancy:.2f} R/trade")
    print(f"Capital final: {final_balance:.2f} ({final_balance - config.initial_balance:+.2f})")
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
    parser.add_argument(
        "--strategy",
        choices=["confluence", "asian_breakout", "us_opr"],
        default="confluence",
        help="logique à backtester: confluence existante, breakout asiatique 09h-13h ou US OPR 15h45-17h30",
    )
    parser.add_argument("--rr", type=float, default=3.0)
    parser.add_argument("--sl-atr", type=float, default=2.0)
    parser.add_argument("--max-holding", type=int, default=48)
    parser.add_argument("--spread-points", type=int, default=10)
    parser.add_argument("--output", default="backtest_results/gemini_gold_eye_backtest.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    point = 0.01 if "XAU" in args.symbol.upper() else 0.00001
    config = BacktestConfig(
        symbol=args.symbol,
        bars=args.bars,
        risk_percent=args.risk,
        min_confidence=args.confidence,
        sl_atr_multiplier=args.sl_atr,
        rr_ratio=args.rr,
        max_holding_bars=args.max_holding,
        strategy=args.strategy,
        spread_points=args.spread_points,
        point=point,
        output=args.output,
    )
    if args.demo:
        candles = make_demo_data(config.bars)
    elif args.csv:
        candles = load_csv(args.csv)
    else:
        candles = load_mt5(config.symbol, config.bars)
    results = run_backtest(candles, config)
    write_results(results, config.output)
    print_report(results, config)


if __name__ == "__main__":
    main()
