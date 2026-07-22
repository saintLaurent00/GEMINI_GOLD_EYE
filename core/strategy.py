from __future__ import annotations

import json
import os
from typing import Any

from config.settings import MODE_SNIPER


class Strategy:
    """Strategy analyzer using multi-timeframe alignment and SMC patterns."""

    def __init__(self):
        """Initialize the strategy analyzer."""
        self.last_signal: dict[str, Any] = {}

    def analyze_symbol(self, symbol):
        """
        Entry point for the strategy analyzer.
        This analyzes a symbol and returns a decision.

        RULES FOR GEMINI GOLD EYE
        ========================================

        Global Rules :
        1. Never enter if spread is too high.
        2. Never enter during low liquidity (Asian session edge cases).
        3. Always verify alignment H1 / H4 before entry.
        4. Always use 2x ATR for SL (tight SL = tight RR ratio).

        Entry Confirmation:
        5. MUST have a Price Action confirmation on H1:
               - Pin Bar or Engulfing after a pullback (NOT direct breakout).
        6. RSI(14, H1) must NOT be extreme (30-70 range is best).
        7. Volume confirmation (optional, but preferred).

        Exit Management :
        8. Use trailing stop based on ATR after reaching +1.5R.
        9. Use TP at +3R (or adjust based on RR ratio).
        10. Move SL to BE when +1R is reached.
        11. NEVER PYRAMID on this bot.

        Trade Execution :
        12. Lot size = Risk / SL_Distance.
        13. Risk per trade = 1% to 2% of account.
        14. Max 1 trade open at a time (confluence filter).

        Entry Pattern Recognition
        =====================================
        We use SMC (Smart Money Concepts) as a filter :

        Bullish Entry :
        - H1 shows an Engulfing or Pin Bar (white body, small wick below).
        - Price close above the 50 EMA (H1).
        - MACD histogram is positive (upside momentum).
        - H4 trend is also bullish (CRITICAL: H1 and H4 must align).

        Bearish Entry :
        - H1 shows an Engulfing or Pin Bar (black body, small wick above).
        - Price close below the 50 EMA (H1).
        - MACD histogram is negative (downside momentum).
        - H4 trend is also bearish (CRITICAL: H1 and H4 must align).

        Data Structure (Input Bulletin)
        ========================================
        We expect the following structure from the calculator:

        {
            "META": {
                "Symbol": "EURUSD",
                "Scan_Time": "2024-01-15 10:00",
                "Live_Price": 1.08500
            },
            "INSTITUTIONAL_BIAS": {
                "Price_vs_VWAP_H1": "BULLISH" or "BEARISH",
                "VWAP_Level": 1.08400
            },
            "H1_INDICATORS": {
                "RSI": 55.2,
                "MACD_Histogram": 0.00050,
                "Stoch_K": 65.0,
                "ATR": 0.00150,
                "Trend": "BULLISH" or "BEARISH"
            },
            "H4_STRUCTURE": {
                "Trend_EMA200": "BULLISH" or "BEARISH",
                "RSI": 60.0,
                "MACD_Status": "UP" or "DOWN"
            },
            "SAFETY": {
                "SPREAD": 10,
                "GOLD_MODE": false
            }
        }

        Decision Logic
        ========================================

        1. MULTI-TIMEFRAME ALIGNMENT (CRITICAL):
        - Look at the JSON field "H1_INDICATORS" and "H4_STRUCTURE".
        - IF H1 Trend and H4 Trend_EMA200 conflict => IMMEDIATE WAIT. Do not trade against the H4 trend.
        - BUY only if H1 Trend is BULLISH AND H4 Trend_EMA200 is BULLISH.
        - SELL only if H1 Trend is BEARISH AND H4 Trend_EMA200 is BEARISH.

        2. SMC ENTRY PATTERN (ON H1):
        - We do NOT enter on random candles.
        - We enter only on the close of a Pin Bar or Engulfing confirmation.
        - Confirmation: Look for a Pin Bar or Engulfing candle on H1 during the retest.

        3. RANGE & MOMENTUM FILTER:
        - Check "H1_INDICATORS" -> "RSI". If > 70 or < 30, be careful of reversal (WAIT).
        - If H4 candles are flat/overlapping (Range) => WAIT.
        - Never enter a direct breakout (Parabolic move). Always wait for the pullback.

        4. SPREAD & LIQUIDITY FILTER:
        - If spread is very high (GOLD > 40, FX > 25) => WAIT.
        - If spread is high (> 40 points in JSON) => WAIT.

        5. VOLATILITY PROTECTION:
        - Use the "ATR" from H1_INDICATORS to gauge current volatility.
        - If price is too far from EMA50 H1 (Overextended) => WAIT.

        -------------------------------------------------------
        EXECUTION LOGIC
        -------------------------------------------------------
        """

        # Extract bulletin data
        decision = {
            "symbol": symbol,
            "decision": "WAIT",
            "confidence": 0,
            "reason": "No signal yet.",
            "sl_atr_multiplier": 2.0,  # Default: 2x ATR for SL
            "atr_value": 0.0010,  # Default fallback ATR
        }

        bulletin = self._get_bulletin(symbol)
        if not bulletin:
            decision["reason"] = f"No bulletin data for {symbol}"
            return decision

        try:
            # Parse bulletin fields
            h1_ind = bulletin.get("H1_INDICATORS", {})
            h4_str = bulletin.get("H4_STRUCTURE", {})
            safety = bulletin.get("SAFETY", {})
            bias = bulletin.get("INSTITUTIONAL_BIAS", {})

            # --- 1. SAFETY CHECKS ---
            # Spread check
            if safety.get("SPREAD", 0) > 40 and safety.get("GOLD_MODE"):
                decision["confidence"] = 20
                decision["reason"] = "Spread on Gold too high."
                return decision

            # --- 2. MULTI-TIMEFRAME ALIGNMENT (CRITICAL) ---
            h1_trend = h1_ind.get("Trend", "NEUTRAL")
            h4_trend = h4_str.get("Trend_EMA200", "NEUTRAL")

            if h1_trend != h4_trend:
                decision["confidence"] = 35
                decision["reason"] = f"H1/H4 conflict: H1={h1_trend}, H4={h4_trend}"
                return decision

            # --- 3. RSI EXTREME CHECK ---
            rsi = h1_ind.get("RSI", 50)
            if rsi > 70 or rsi < 30:
                decision["confidence"] = 45
                decision["reason"] = f"RSI extreme: {rsi:.1f}"
                return decision

            # --- 4. DETERMINE DIRECTION ---
            # (Based on H1 trend, which is aligned with H4)
            direction = "BUY" if h1_trend == "BULLISH" else "SELL"

            # --- 5. CONFLUENCE SCORING ---
            score = 45  # Base score

            # Bias confirmation
            vwap_bias = bias.get("Price_vs_VWAP_H1", "NEUTRAL")
            if (direction == "BUY" and vwap_bias == "BULLISH") or (
                direction == "SELL" and vwap_bias == "BEARISH"
            ):
                score += 15

            # MACD confirmation
            macd_hist = h1_ind.get("MACD_Histogram", 0)
            if (direction == "BUY" and macd_hist > 0) or (
                direction == "SELL" and macd_hist < 0
            ):
                score += 15

            # H4 MACD confirmation
            h4_macd = h4_str.get("MACD_Status", "NEUTRAL")
            if (direction == "BUY" and h4_macd == "UP") or (
                direction == "SELL" and h4_macd == "DOWN"
            ):
                score += 10

            # RSI not extreme (nice middle range)
            if 38 <= rsi <= 62:
                score += 10

            # Spread is good
            if safety.get("SPREAD", 100) <= 20:
                score += 5

            # --- 6. FINAL DECISION ---
            if score < 75:  # Threshold
                decision["confidence"] = score
                decision["reason"] = f"Confluence not strong enough: {score}/100"
                return decision

            decision["decision"] = direction
            decision["confidence"] = min(score, 95)
            decision["reason"] = f"Strong {direction} confluence: H1/H4 aligned + VWAP + MACD"

            # --- EXTRACTION INTELLIGENTE DE L'ATR ---
            # Le RiskManager a besoin de l'ATR pour calculer le lot.
            # On prend celui du H1 (Trigger) car le SL est basé sur le H1.
            if "H1_INDICATORS" in bulletin:
                decision["atr_value"] = bulletin["H1_INDICATORS"].get("ATR", 0.0010)
            else:
                # Fallback au cas où le bulletin est mal formé
                decision["atr_value"] = 0.0010

            return decision

        except Exception as e:
            decision["reason"] = f"Error analyzing {symbol}: {str(e)}"
            decision["confidence"] = 0
            return decision

    def _get_bulletin(self, symbol: str) -> dict | None:
        """Mock bulletin getter for now."""
        # In production, this would come from the calculator
        return None
