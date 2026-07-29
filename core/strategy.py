"""core/strategy.py - GeminiStrategy.

Construit le bulletin technique + les graphiques (W1/D1/H4/H1), envoie le prompt
multimodal a Gemini et parse la decision JSON (BUY/SELL/WAIT + confiance).
"""
import json
import time
from infrastructure.gemini_client import GeminiClient
from data_processor.indicators import TacticalCalculator
from data_processor.vision import ChartPainter

class GeminiStrategy:
    def __init__(self):
        self.ai = GeminiClient()

    def analyze_symbol(self, symbol):
        print(f"\n🧠 GEMINI GOLD EYE analyzing : {symbol}...")

        # 1. ACQUISITION DES DONNÉES (H1 + H4)
        calculator = TacticalCalculator(symbol)
        bulletin = calculator.get_bulletin()
        
        if not bulletin:
            print("❌ Echec des données Live.")
            return None

        # 2. VISION (W1, D1, H4, H1)
        painter = ChartPainter(symbol)
        image_paths = painter.generate_charts()
        
        if not image_paths:
            print("❌ Echec des graphiques.")
            return None

        # 3. LE PROMPT ULTIME (H1 SNIPER + V13 SECURITY)
        bulletin_json = json.dumps(bulletin, indent=2)

        prompt = f"""
ROLE: Senior Hedge Fund Trader (Specialty: Price Action, SMC & Multi-Timeframe Analysis).
LANGUAGE: Provide the reason in FRENCH.

OBJECTIVE:
- Identify a **Sniper entry on H1** that aligns perfectly with the **H4 Structure** and **D1 Bias**.
- We are looking for "Day Trading to Swing" opportunities.

--- PART 1: MATHEMATICAL TRUTH (LIVE H1 & H4 DATA) ---
{bulletin_json}

--- PART 2: VISUAL ANALYSIS (W1, D1, H4, H1) ---
Hierarchy:
• W1/D1 = Macro Trend (Direction).
• H4 = Key Structure (Order Blocks, FVG, Major S/R).
• H1 = The Trigger (Entry Pattern).

Legend:
• Magenta Line = ZigZag Structure (Look for HH/HL or LH/LL).
• Blue Line = EMA 200 (Trend Filter).
• Orange Line = EMA 50 (Momentum).
• Green Dotted = Support/Resistance.

------------------------------------------------------
RULES OF ENGAGEMENT V13 (H1 SNIPER EDITION)
------------------------------------------------------

1. MULTI-TIMEFRAME ALIGNMENT (CRITICAL):
- Look at the JSON field "H1_INDICATORS" and "H4_STRUCTURE".
- IF H1 Trend and H4 Trend_EMA200 conflict => IMMEDIATE WAIT. Do not trade against the H4 trend.
- BUY only if H1 Trend is BULLISH AND H4 Trend_EMA200 is BULLISH.
- SELL only if H1 Trend is BEARISH AND H4 Trend_EMA200 is BEARISH.

2. SMC ENTRY PATTERN (ON H1):
- We do NOT enter on random candles.
- BUY Pattern: H1 Break of Structure (BOS) upwards + Retest of an Order Block (OB) or FVG.
- SELL Pattern: H1 BOS downwards + Retest of OB/FVG.
- Confirmation: Look for a Pin Bar or Engulfing candle on H1 during the retest.

3. RANGE & MOMENTUM FILTER:
- Check "H1_INDICATORS" -> "RSI". If > 70 or < 30, be careful of reversal (WAIT).
- If H4 candles are flat/overlapping (Range) => WAIT.
- Never enter a direct breakout (Parabolic move). Always wait for the pullback.

4. GOLD SPECIAL MODE (XAUUSD):
- Strict Rule: Only trade if the potential Reward is > 3x Risk.
- If H1 shows long wicks (indecision) => WAIT.
- If spread is high (> 40 points in JSON) => WAIT.

5. VOLATILITY PROTECTION:
- Use the "ATR" from H1_INDICATORS to gauge current volatility.
- If price is too far from EMA50 H1 (Overextended) => WAIT.

------------------------------------------------------
DECISION OUTPUT (STRICT JSON)
------------------------------------------------------
Analyze the confluence of Images + Maths.
If Setup Quality > 80%:
    "decision": "BUY" or "SELL"
    "sl_atr_multiplier": 2.0 (Standard) or 3.0 (Gold)

If any doubt or conflict:
    "decision": "WAIT"

Response Format:
{{
    "decision": "BUY" | "SELL" | "WAIT",
    "confidence": 0-100,
    "reason": "Analyse détaillée en FRANÇAIS (Alignement H1/H4 + Setup SMC).",
    "sl_atr_multiplier": 2.0
}}
        """.strip()

        # 4. ENVOI À L'IA
        print("🤖 Analyzing Patterns & Structure (AI)...")
        response_text = self.ai.send_multimodal_prompt(prompt, image_paths)
        
        if not response_text: return None

        # 5. PARSING
        try:
            cleaned = response_text.replace("```json", "").replace("```", "").strip()
            decision = json.loads(cleaned)

            # --- EXTRACTION INTELLIGENTE DE L'ATR ---
            # Le RiskManager a besoin de l'ATR pour calculer le lot.
            # On prend celui du H1 (Trigger) car le SL est basé sur le H1.
            if "H1_INDICATORS" in bulletin:
                decision["atr_value"] = bulletin["H1_INDICATORS"].get("ATR", 0.0010)
            else:
                # Fallback au cas où le bulletin est mal formé
                decision["atr_value"] = 0.0010 

            verdict = decision.get("decision", "WAIT")
            conf = decision.get("confidence", 0)
            reason = decision.get("reason", "...")

            print(f"👉 VERDICT : {verdict} ({conf}%) | {reason}")
            return decision

        except Exception as e:
            print(f"❌ AI Error: {e}")
            return None