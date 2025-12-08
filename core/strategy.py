# import json
# from infrastructure.gemini_client import GeminiClient
# from data_processor.indicators import TacticalCalculator
# from data_processor.vision import ChartPainter

# class GeminiStrategy:
#     def __init__(self):
#         self.ai = GeminiClient()

#     def analyze_symbol(self, symbol):
#         print(f"\n🧠 GEMINI GOLD EYE analyse : {symbol}...")

#         # 1. DONNÉES
#         calculator = TacticalCalculator(symbol)
#         bulletin = calculator.get_bulletin()
#         if not bulletin: return None

#         painter = ChartPainter(symbol)
#         image_paths = painter.generate_charts()
#         if not image_paths: return None

#         # 2. PROMPT "PATTERN RECOGNITION & DAY-TO-SWING"
#         prompt = f"""
#         RÔLE: Expert Hedge Fund Trader (Specialité: Price Action & SMC).
        
#         OBJECTIF: Identifier une entrée "Day Trading" (H4) qui a le potentiel de devenir un "Swing" (D1/W1).
        
#         DONNÉES:
#         {json.dumps(bulletin, indent=2)}
        
#         TACHE D'ANALYSE VISUELLE (Images):
#         1. W1/D1 (Fond) : Quelle est la tendance lourde ? (Regarde EMA200 et ZigZag).
#         2. H4 (Signal) : Cherche un PATTERN D'ENTRÉE précis sur la structure actuelle.
#            - Patterns Haussiers : Double Bottom, Bullish Flag, Cassure + Retest (BOS), Avalement Haussier sur support.
#            - Patterns Baissiers : Double Top, Bearish Flag, Rejet sous résistance, Avalement Baissier.
        
#         RÈGLES D'OR :
#         - Ne trade JAMAIS contre la tendance W1/D1 sauf si divergence RSI confirmée.
#         - Regarde le PRIX EXACT (Ligne Rouge). Est-il sur un Support (Ligne Verte) ou une EMA ?
#         - Volatilité : Utilise l'ATR fourni pour valider que le marché n'est pas mort.

#         SORTIE (JSON STRICT):
#         {{
#             "decision": "BUY" | "SELL" | "WAIT",
#             "confidence": 0-100,
#             "reason": "Cite le Pattern visuel H4 détecté et la validation D1",
#             "sl_atr_multiplier": 2.0,
#             "risk_reward_ratio": 3.0
#         }}
#         """

#         # 3. ENVOI
#         print("🤖 Analyse des Patterns & Structure en cours...")
#         response_text = self.ai.send_multimodal_prompt(prompt, image_paths)
#         if not response_text: return None

#         # 4. RETOUR
#         try:
#             cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
#             decision_json = json.loads(cleaned_text)
            
#             # On ajoute les chemins d'images à la réponse pour que le Logger puisse les archiver
#             decision_json["image_paths"] = image_paths
#             decision_json["atr_value"] = bulletin['TECHNICAL_INDICATORS']['ATR_14']
            
#             verdict = decision_json.get("decision", "WAIT")
#             conf = decision_json.get("confidence", 0)
#             print(f"👉 VERDICT : {verdict} ({conf}%) | {decision_json.get('reason')}")
            
#             return decision_json

#         except Exception as e:
#             print(f"❌ Erreur IA: {e}")
#             return None






# import json
# import time
# from infrastructure.gemini_client import GeminiClient
# from data_processor.indicators import TacticalCalculator
# from data_processor.vision import ChartPainter
# from config import settings

# class GeminiStrategy:
#     def __init__(self):
#         self.ai = GeminiClient()

#     def analyze_symbol(self, symbol):
#         print(f"\n🧠 GEMINI GOLD EYE analyzing : {symbol}...")

#         # 1. ACQUISITION DES DONNÉES (MATHS & VISION)
#         calculator = TacticalCalculator(symbol)
#         bulletin = calculator.get_bulletin()
        
#         if not bulletin:
#             print("❌ Live Data Failed.")
#             return None

#         painter = ChartPainter(symbol)
#         image_paths = painter.generate_charts()
        
#         if not image_paths:
#             print("❌ Charts Failed.")
#             return None

#         # 2. LE PROMPT "INSTITUTIONNEL" (EN ANGLAIS)
#         # On donne le pouvoir total à l'IA, mais on lui donne toutes les armes (JSON + Images)
#         # prompt = f"""
#         # reponds en français stp
#         # ROLE: Senior Hedge Fund Trader (Specialty: Price Action, SMC & Multi-Timeframe Analysis).
        
#         # OBJECTIVE: Identify a high-probability "Day Trading" entry (H4) that has the potential to evolve into a "Swing Trade" (D1/W1).
        
#         # --- PART 1: THE MATHEMATICAL TRUTH (LIVE DATA) ---
#         # {json.dumps(bulletin, indent=2)}
        
#         # --- PART 2: THE VISUAL ANALYSIS (CHARTS) ---
#         # You have 3 charts (W1, D1, H4).
#         # - Magenta Line = ZigZag Structure (Highs/Lows).
#         # - Blue Line = EMA 200 (Major Trend).
#         # - Orange Line = EMA 50 (Short Trend).
#         # - Red Line = EXACT Current Price.

#         # --- YOUR MISSION ---
#         # 1. SYNTHESIZE: Cross-reference the Visuals with the Mathematical Data. 
#         #    (Example: If the JSON says 'PRICE_VS_EMA200: BELOW', do NOT look for Buys unless it's a confirmed reversal pattern).
        
#         # 2. FIND THE PATTERN (H4): Look for specific SMC patterns:
#         #    - BULLISH: Break of Structure (BOS) + Retest, Bullish Flag, Double Bottom on Support.
#         #    - BEARISH: Rejection Block, Bearish Flag, Double Top, Breakdown + Retest.
        
#         # 3. VALIDATE VOLATILITY: Check the 'ATR_14' in the JSON. Is the market moving enough?

#         # --- OUTPUT FORMAT (STRICT JSON) ---
#         # {{
#         #     "decision": "BUY" | "SELL" | "WAIT",
#         #     "confidence": 0-100,
#         #     "reason": "Explain your reasoning combining the Visual Pattern AND the Math Data.",
#         #     "sl_atr_multiplier": 2.0,
#         #     "risk_reward_ratio": 3.0
#         # }}
#         # """

        
#         # 3. LE PROMPT "INSTITUTIONNEL" (SMC + SNIPER H1)
#         # On donne le pouvoir total à l'IA, avec des règles d'engagement strictes.
#         prompt = f"""
#         ROLE: Senior Hedge Fund Trader (Specialty: Price Action, SMC & Multi-Timeframe Analysis).
#         LANGUAGE: Please provide the 'reason' in FRENCH.
        
#         OBJECTIVE: -Identify a high-probability "Sniper Entry" on H1 that aligns with the "Structural Trend" of H4/D1.
#                    -Identify a high-probability "Day Trading" entry (H4,H1) that has the potential to evolve into a "Swing Trade" (D1/W1). 
#                    -Prioritize DAY TRADING setups that can transition into SWING TRADES.
                 

#         --- PART 1: THE MATHEMATICAL TRUTH (LIVE DATA) ---
#         {json.dumps(bulletin, indent=2)}
        
#         --- PART 2: THE VISUAL ANALYSIS (4 CHARTS: W1, D1, H4, H1) ---
#         You have 4 charts. Use them hierarchically:
#         1. W1/D1 (Macro): Directional Bias only.
#         2. H4 (Structure): Identify the Order Blocks / Key Zones.
#         3. H1 (Entry): The Trigger execution.

#         LEGEND:
#         - Magenta Line = ZigZag Structure (Highs/Lows). Follow the Flow.
#         - Blue Line = EMA 200 (Major Trend).
#         - Orange Line = EMA 50 (Dynamic Support).
#         - Green Dashed = Support/Resistance Levels.
#         - Red Line = EXACT LIVE PRICE.

#         --- YOUR MISSION (RULES OF ENGAGEMENT) ---
#         1. SYNTHESIZE: Check for CONFLUENCE. 
#            (Example: If Price is ABOVE EMA 200 on H4 AND ZigZag shows Higher Highs on H1 => STRONG BUY).
#            (Conflict Rule: If D1 is Bearish but H1 is Bullish => WAIT).
        
#         2. FIND THE SMC PATTERN (Focus on H1/H4):
#            - BULLISH: Break of Structure (BOS) upwards, Retest of an Order Block, Liquidity Sweep of a previous Low then reversal.
#            - BEARISH: Breakdown of Structure (BOS) downwards, Rejection of a Fair Value Gap (FVG), Double Top.
#            - For every pattern, identified the exact Price Level (from the Red Line) and the relevant Key Level (from Green Dashed Lines).
#            - For BOS patterns, ensure the retest is confirmed with a Pin Bar or Engulfing Candle.
#            - For Order Blocks, ensure the entry is near the edge of the block, not the center.
#            - Validate if it necessarily the timeframe with retest.
        
#         3. VALIDATE WITH MATHS: 
#            - Is RSI divergent? 
#            - Is the Live Price near a Key Level?

#         --- OUTPUT FORMAT (STRICT JSON) ---
#         {{
#             "decision": "BUY" | "SELL" | "WAIT",
#             "confidence": 0-100,
#             "reason": "Explique ton analyse en FRANÇAIS (Structure H4 + Confirmation H1).",
#             "sl_atr_multiplier": 2.0,
#             "risk_reward_ratio": 3.0
#         }}"""

#         # 3. ENVOI À L'IA
#         print("🤖 Analyzing Patterns & Structure (AI)...")
#         response_text = self.ai.send_multimodal_prompt(prompt, image_paths)
        
#         if not response_text: return None

#         # 4. PARSING DE LA RÉPONSE
#         try:
#             cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
#             decision_json = json.loads(cleaned_text)
            
#             # On injecte l'ATR dans la réponse pour que le Risk Manager puisse calculer le SL
#             decision_json["atr_value"] = bulletin['TECHNICAL_INDICATORS']['ATR_14']
            
#             verdict = decision_json.get("decision", "WAIT")
#             conf = decision_json.get("confidence", 0)
#             reason = decision_json.get("reason", "...")
            
#             print(f"👉 VERDICT : {verdict} ({conf}%) | {reason}")
            
#             return decision_json

#         except Exception as e:
#             print(f"❌ AI Error: {e}")
#             return None






# import json
# import time
# from infrastructure.gemini_client import GeminiClient
# from data_processor.indicators import TacticalCalculator
# from data_processor.vision import ChartPainter

# class GeminiStrategy:
#     def __init__(self):
#         self.ai = GeminiClient()

#     def analyze_symbol(self, symbol):
#         print(f"\n🧠 GEMINI GOLD EYE analyzing : {symbol}...")

#         # -------------------------
#         # 1. ACQUISITION DES DONNÉES
#         # -------------------------
#         # On récupère les mathématiques précises (Live Tick)
#         calculator = TacticalCalculator(symbol)
#         bulletin = calculator.get_bulletin()
        
#         if not bulletin:
#             print("❌ Live Data Failed.")
#             return None

#         # On récupère les images (Vision Augmentée)
#         painter = ChartPainter(symbol)
#         image_paths = painter.generate_charts()
        
#         if not image_paths:
#             print("❌ Charts Failed.")
#             return None

#         # -------------------------
#         # 2. PREPARATION DU PROMPT V13
#         # -------------------------
#         bulletin_json = json.dumps(bulletin, indent=2)

#         prompt = f"""
# ROLE: Senior Hedge Fund Trader (Specialty: Price Action, SMC & Multi-Timeframe Analysis).
# LANGUAGE: Provide the reason in FRENCH.

# OBJECTIVE:
# - Identify a Sniper entry on H1 aligned with H4 structure and D1/W1 bias.
# - Identify a Day Trading entry (H4/H1) with potential to evolve into a Swing.
# - Prioritize setups that can evolve into a Swing.

# --- PART 1: MATHEMATICAL TRUTH (LIVE DATA) ---
# {bulletin_json}

# --- PART 2: VISUAL ANALYSIS (W1, D1, H4, H1) ---
# Use timeframes hierarchically:
# • W1/D1 = Macro bias
# • H4 = Structure (OB, FVG, BOS, Zones)
# • H1 = Entry Trigger (Sniper)

# Legend:
# • Magenta = Structure (ZigZag)
# • EMA200 blue / EMA50 orange
# • Support/Resistance green
# • Real-time price red line

# ------------------------------------------------------
# RULES OF ENGAGEMENT V13
# ------------------------------------------------------

# 1. CONFLUENCE CHECK:
# - BUY = Price above EMA200 H4 + HH/HL on H1 + Bullish D1
# - SELL = Price below EMA200 H4 + LH/LL on H1 + Bearish D1
# - Conflict D1 vs H1 => WAIT

# 2. SMC PATTERN VALIDATION:
# - Bullish: BOS up + OB retest + sweep of previous low
# - Bearish: BOS down + FVG rejection + double top
# - Retest must show Pin Bar or Engulfing
# - Entry at OB edge only

# 3. MATHEMATICS CONFIRMATION:
# - Check RSI divergence
# - Check proximity to Key Levels
# - Check sensitive zones

# ------------------------------------------------------
# INTEGRATED MODULES (SAFETY FIRST)
# ------------------------------------------------------

# 4. RANGE BLOCKER:
# - Horizontal/confused H4 => WAIT
# - Flat highs/lows => WAIT
# - ATR < 20 avg => WAIT
# - No impulse in 3 moves => WAIT

# 5. MOMENTUM FILTER:
# - Never enter direct breakout
# - Large impulse? wait confirmation
# - H1 contradicts H4 => WAIT

# 6. GOLD SPECIAL MODE (XAUUSD):
# - Analyze W1/D1/H4/H1 always
# - Long wicks => WAIT
# - No spike trades
# - Clean H1 retest required

# 7. PAIR BLACKLIST:
# - If symbol in [AUDCAD, CADJPY, NZDUSD, EURCHF, EURNZD, AUDNZD] => return "WAIT"

# 8. STRUCTURAL ALIGNMENT:
# - Buy only if D1 bullish + H4 bullish + H1 bullish trigger
# - Sell only if D1 bearish + H4 bearish + H1 bearish trigger
# - Otherwise WAIT

# 9. VOLATILITY & SPIKE FILTER:
# - Extreme wicks => WAIT
# - Abnormal volatility => WAIT
# - Compression => WAIT

# 10. MEMORY CONSISTENCY:
# - If bias changes justify clearly
# - Otherwise maintain direction

# ------------------------------------------------------
# OUTPUT FORMAT (STRICT JSON)
# ------------------------------------------------------
# {{
#     "decision": "BUY" | "SELL" | "WAIT",
#     "confidence": 0-100,
#     "reason": "Analyse complète en FRANÇAIS (Structure H4 + Confirmation H1).",
#     "sl_atr_multiplier": 2.0,
#     "risk_reward_ratio": 3.0
# }}
#         """.strip()

#         # -------------------------
#         # 3. ENVOI À L'IA
#         # -------------------------
#         print("🤖 Analyzing Patterns & Structure (AI)...")
#         # Envoi multimodal : Texte + Images
#         response_text = self.ai.send_multimodal_prompt(prompt, image_paths)
        
#         if not response_text:
#             return None

#         # -------------------------
#         # 4. PARSING JSON
#         # -------------------------
#         try:
#             # Nettoyage des balises Markdown potentielles
#             cleaned = (
#                 response_text.replace("```json", "")
#                 .replace("```", "")
#                 .strip()
#             )

#             decision = json.loads(cleaned)

#             # --- INJECTION CRUCIALE POUR LE RISK MANAGER ---
#             # On ajoute l'ATR précis calculé par les maths dans la décision
#             # pour que le Risk Manager n'ait pas à le recalculer.
#             if "TECHNICAL_INDICATORS" in bulletin:
#                 decision["atr_value"] = bulletin["TECHNICAL_INDICATORS"]["ATR_14"]
#             else:
#                 # Fallback de sécurité si le bulletin est incomplet
#                 decision["atr_value"] = 0.0010 

#             verdict = decision.get("decision", "WAIT")
#             conf = decision.get("confidence", 0)
#             reason = decision.get("reason", "...")

#             print(f"👉 VERDICT : {verdict} ({conf}%) | {reason}")

#             return decision

#         except Exception as e:
#             print(f"❌ AI Error: {e}")
#             print("Raw AI output:", response_text)
#             return None






























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
- Look at the JSON field "H4_METRICS" -> "Alignment_H1_H4".
- IF "CONFLICT" => IMMEDIATE WAIT. Do not trade against the H4 trend.
- BUY only if H1 Bullish AND H4 Bullish.
- SELL only if H1 Bearish AND H4 Bearish.

2. SMC ENTRY PATTERN (ON H1):
- We do NOT enter on random candles.
- BUY Pattern: H1 Break of Structure (BOS) upwards + Retest of an Order Block (OB) or FVG.
- SELL Pattern: H1 BOS downwards + Retest of OB/FVG.
- Confirmation: Look for a Pin Bar or Engulfing candle on H1 during the retest.

3. RANGE & MOMENTUM FILTER:
- Check "H1_METRICS" -> "RSI". If > 70 or < 30, be careful of reversal (WAIT).
- If H4 candles are flat/overlapping (Range) => WAIT.
- Never enter a direct breakout (Parabolic move). Always wait for the pullback.

4. GOLD SPECIAL MODE (XAUUSD):
- Strict Rule: Only trade if the potential Reward is > 3x Risk.
- If H1 shows long wicks (indecision) => WAIT.
- If spread is high (> 40 points in JSON) => WAIT.

5. VOLATILITY PROTECTION:
- Use the "ATR" from H1 Metrics to gauge current volatility.
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
            if "H1_METRICS (TRIGGER)" in bulletin:
                decision["atr_value"] = bulletin["H1_METRICS (TRIGGER)"]["ATR"]
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