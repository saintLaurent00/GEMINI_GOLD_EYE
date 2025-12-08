# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# from config import symbols

# class TacticalCalculator:
#     def __init__(self, symbol):
#         self.symbol = symbol

#     def _get_live_tick(self):
#         """Récupère le prix actuel à la milliseconde près."""
#         if not mt5.symbol_select(self.symbol, True): return None
#         tick = mt5.symbol_info_tick(self.symbol)
#         return tick

#     def _get_historical_data(self, timeframe, candles=500):
#         """Récupère l'historique pour calculer les indicateurs (RSI, EMA)."""
#         rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, candles)
#         if rates is None or len(rates) == 0: return None
        
#         df = pd.DataFrame(rates)
#         df['time'] = pd.to_datetime(df['time'], unit='s')
#         df.set_index('time', inplace=True)
#         return df

#     def get_bulletin(self):
#         """
#         Génère le BULLETIN TACTIQUE.
#         Combine : Historique (Tendance) + Live Tick (Exécution).
#         """
#         # 1. Données Live (La Vérité)
#         tick = self._get_live_tick()
#         if tick is None: 
#             print(f"❌ Erreur Tick pour {self.symbol}")
#             return None

#         # 2. Données Historiques (Le Contexte)
#         df = self._get_historical_data(symbols.MATH_TIMEFRAME)
#         if df is None: return None

#         # 3. Calculs Techniques
#         try:
#             df['EMA50'] = df.ta.ema(length=50)
#             df['EMA200'] = df.ta.ema(length=200)
#             df['RSI'] = df.ta.rsi(length=14)
#             df['ATR'] = df.ta.atr(length=14)
            
#             # --- CORRECTION BOLLINGER BANDS ---
#             bb = df.ta.bbands(length=20, std=2)
#             if bb is not None:
#                 # On cherche dynamiquement la colonne qui commence par BBU et BBL
#                 # Peu importe si c'est BBU_20_2.0 ou autre chose
#                 bbu_col = [c for c in bb.columns if c.startswith('BBU')][0]
#                 bbl_col = [c for c in bb.columns if c.startswith('BBL')][0]
                
#                 df['BBU'] = bb[bbu_col]
#                 df['BBL'] = bb[bbl_col]
#             # ----------------------------------

#         except Exception as e:
#             print(f"Erreur calculs indicateurs: {e}")
#             return None

#         # On prend la dernière bougie CLÔTURÉE pour les indicateurs stables
#         last_closed = df.iloc[-2]

#         # 4. Formatage de Précision (5 décimales)
#         bulletin = {
#             "META": {
#                 "Symbol": self.symbol,
#                 "Timeframe": "H4",
#                 "Tick_Time": str(tick.time)
#             },
#             "LIVE_PRICE_ACTION": {
#                 "REAL_BID": float(f"{tick.bid:.5f}"),  # LE VRAI PRIX
#                 "REAL_ASK": float(f"{tick.ask:.5f}"),
#                 "SPREAD_POINTS": int((tick.ask - tick.bid) * 100000)
#             },
#             "TECHNICAL_INDICATORS": {
#                 "RSI_14": round(last_closed['RSI'], 2),
#                 "ATR_14": float(f"{last_closed['ATR']:.5f}"),
#                 "EMA_200": float(f"{last_closed['EMA200']:.5f}"),
#                 "EMA_50": float(f"{last_closed['EMA50']:.5f}"),
#                 "BB_UPPER": float(f"{last_closed.get('BBU', 0):.5f}"),
#                 "BB_LOWER": float(f"{last_closed.get('BBL', 0):.5f}")
#             },
#             "TREND_CHECK": {
#                 "PRICE_VS_EMA200": "ABOVE" if tick.bid > last_closed['EMA200'] else "BELOW",
#                 "VOLATILITY_ATR": "HIGH" if last_closed['ATR'] > 0.0020 else "NORMAL"
#             }
#         }
        
#         return bulletin


# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# from config import symbols

# class TacticalCalculator:
#     def __init__(self, symbol):
#         self.symbol = symbol

#     def _get_live_tick(self):
#         """
#         Récupère le prix actuel avec INSISTANCE.
#         Si MT5 dort, on le réveille.
#         """
#         # 1. On force la sélection (plusieurs fois si nécessaire)
#         selected = False
#         for _ in range(5):
#             if mt5.symbol_select(self.symbol, True):
#                 selected = True
#                 break
#             time.sleep(0.5)
            
#         if not selected:
#             print(f"⚠️ Impossible de sélectionner {self.symbol} (Check Market Watch)")
#             return None

#         # 2. On attend que le Tick soit disponible (Warmup instantané)
#         # Parfois MT5 a besoin de quelques secondes après la sélection
#         for i in range(10): # On essaie pendant 5 secondes max
#             tick = mt5.symbol_info_tick(self.symbol)
#             if tick is not None:
#                 return tick
#             time.sleep(0.5)
            
#         return None

#     def _get_historical_data(self, timeframe, candles=500):
#         """Récupère l'historique avec Retry Logic."""
#         # On essaie 3 fois de récupérer les bougies
#         for _ in range(3):
#             rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, candles)
#             if rates is not None and len(rates) > 0:
#                 df = pd.DataFrame(rates)
#                 df['time'] = pd.to_datetime(df['time'], unit='s')
#                 df.set_index('time', inplace=True)
#                 return df
#             time.sleep(1)
#         return None

#     def get_bulletin(self):
#         """Génère le BULLETIN TACTIQUE."""
#         # 1. Données Live
#         tick = self._get_live_tick()
#         if tick is None: 
#             print(f"❌ Erreur Tick pour {self.symbol} (MT5 ne renvoie pas de prix)")
#             return None

#         # 2. Données Historiques
#         df = self._get_historical_data(symbols.MATH_TIMEFRAME)
#         if df is None: 
#             print(f"❌ Erreur Historique pour {self.symbol} (Pas de bougies)")
#             return None

#         # 3. Calculs Techniques
#         try:
#             df['EMA50'] = df.ta.ema(length=50)
#             df['EMA200'] = df.ta.ema(length=200)
#             df['RSI'] = df.ta.rsi(length=14)
#             df['ATR'] = df.ta.atr(length=14)
            
#             # Correction Bollinger robuste
#             bb = df.ta.bbands(length=20, std=2)
#             if bb is not None:
#                 cols = bb.columns.tolist()
#                 bbu = next((c for c in cols if "BBU" in c), None)
#                 bbl = next((c for c in cols if "BBL" in c), None)
#                 if bbu and bbl:
#                     df['BBU'] = bb[bbu]
#                     df['BBL'] = bb[bbl]
#         except Exception as e:
#             print(f"Erreur calculs: {e}")
#             return None

#         last_closed = df.iloc[-2]

#         # 4. Formatage
#         bulletin = {
#             "META": {
#                 "Symbol": self.symbol,
#                 "Timeframe": "H4",
#                 "Tick_Time": str(tick.time)
#             },
#             "LIVE_PRICE_ACTION": {
#                 "REAL_BID": float(f"{tick.bid:.5f}"),
#                 "REAL_ASK": float(f"{tick.ask:.5f}"),
#                 "SPREAD_POINTS": int((tick.ask - tick.bid) * 100000)
#             },
#             "TECHNICAL_INDICATORS": {
#                 "RSI_14": round(last_closed['RSI'], 2),
#                 "ATR_14": float(f"{last_closed['ATR']:.5f}"),
#                 "EMA_200": float(f"{last_closed['EMA200']:.5f}"),
#                 "BB_UPPER": float(f"{last_closed.get('BBU', 0):.5f}")
#             },
#             "TREND_CHECK": {
#                 "PRICE_VS_EMA200": "ABOVE" if tick.bid > last_closed['EMA200'] else "BELOW",
#                 "VOLATILITY_ATR": "HIGH" if last_closed['ATR'] > 0.0020 else "NORMAL"
#             }
#         }
        
#         return bulletin





# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# from config import symbols

# class TacticalCalculator:
#     def __init__(self, symbol):
#         self.symbol = symbol

#     # ------------------------------------
#     # 1. GET TICK (LIVE EXECUTION)
#     # ------------------------------------
#     def _get_live_tick(self):
#         # On insiste un peu pour avoir le tick
#         for _ in range(5):
#             if mt5.symbol_select(self.symbol, True): break
#             time.sleep(0.2)
        
#         tick = mt5.symbol_info_tick(self.symbol)
#         return tick

#     # ------------------------------------
#     # 2. GET HISTO DATA (H4 context)
#     # ------------------------------------
#     def _get_historical_data(self, tf, candles=500):
#         for _ in range(3):
#             rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, candles)
#             if rates is not None and len(rates) > 0:
#                 df = pd.DataFrame(rates)
#                 df['time'] = pd.to_datetime(df['time'], unit='s')
#                 df.set_index('time', inplace=True)
#                 return df
#             time.sleep(1)
#         return None

#     # ------------------------------------
#     # 3. MAIN BULLETIN V13
#     # ------------------------------------
#     def get_bulletin(self):
#         # A. LIVE DATA
#         tick = self._get_live_tick()
#         if tick is None:
#             print(f"❌ Erreur Tick pour {self.symbol}")
#             return None

#         # B. HISTORICAL DATA (H4)
#         df = self._get_historical_data(symbols.MATH_TIMEFRAME)
#         if df is None: return None

#         # C. INDICATORS CALCULATION
#         try:
#             df["EMA50"] = df.ta.ema(length=50)
#             df["EMA200"] = df.ta.ema(length=200)
#             df["RSI"] = df.ta.rsi(length=14)
#             df["ATR"] = df.ta.atr(length=14)

#             bb = df.ta.bbands(length=20, std=2)
#             if bb is not None:
#                 # Recherche dynamique des colonnes BBU/BBL
#                 cols = bb.columns.tolist()
#                 bbu_col = next((c for c in cols if "BBU" in c), None)
#                 bbl_col = next((c for c in cols if "BBL" in c), None)
#                 if bbu_col and bbl_col:
#                     df["BBU"] = bb[bbu_col]
#                     df["BBL"] = bb[bbl_col]

#         except Exception as e:
#             print(f"⚠️ Erreur Maths: {e}")
#             return None

#         last = df.iloc[-2] # Dernière bougie CLÔTURÉE

#         # ------------------------------------
#         # 🛡️ MODULES V13 (FILTRES DE DÉFENSE)
#         # ------------------------------------

#         # 1. SPREAD CHECK (Protection Coûts)
#         spread_pts = int((tick.ask - tick.bid) * 100000)
#         spread_bad = spread_pts > 40  # Seuil d'alerte (4 pips)

#         # 2. RANGE BLOCKER (Pente des Moyennes Mobiles)
#         # Si la pente est proche de 0, le marché est plat (Range)
#         ema50_slope = df["EMA50"].diff().tail(5).mean()
#         ema200_slope = df["EMA200"].diff().tail(5).mean()
#         # Seuil très fin pour détecter le plat
#         range_block = abs(ema50_slope) < 0.00005 and abs(ema200_slope) < 0.00005

#         # 3. VOLATILITY / WICKS FILTER (Chasse aux stops)
#         # Si les mèches sont plus grandes que 1.5x l'ATR, c'est dangereux
#         wick_top = last["high"] - max(last["open"], last["close"])
#         wick_bot = min(last["open"], last["close"]) - last["low"]
#         long_wicks = wick_top > (last["ATR"] * 1.5) or wick_bot > (last["ATR"] * 1.5)

#         # 4. GOLD SPECIAL MODE
#         gold_mode = "XAU" in self.symbol # Détection auto OR

#         # 5. PAIR BLACKLIST (Paires exotiques ou corrélées négativement)
#         blacklist = ["AUDCAD", "CADJPY", "NZDUSD", "EURCHF", "EURNZD", "AUDNZD"]
#         blacklisted = self.symbol in blacklist

#         # 6. MOMENTUM FILTER (Bougie Impulsive)
#         # Si la bougie précédente est énorme (> 2.5 ATR), risque d'épuisement
#         impulse_threshold = last["ATR"] * 2.5
#         big_impulse = (last["high"] - last["low"]) > impulse_threshold

#         # 7. Pré-Check Structurel
#         price_vs_ema200 = "ABOVE" if tick.bid > last["EMA200"] else "BELOW"

#         # ------------------------------------
#         # CONSTRUCTION DU BULLETIN FINAL
#         # ------------------------------------
#         bulletin = {
#             "META": {
#                 "Symbol": self.symbol,
#                 "Timeframe": "H4",
#                 "Tick_Time": str(tick.time)
#             },

#             "LIVE_PRICE_ACTION": {
#                 "REAL_BID": float(f"{tick.bid:.5f}"), # PRÉCISION 5 DÉCIMALES
#                 "REAL_ASK": float(f"{tick.ask:.5f}"),
#                 "SPREAD_POINTS": spread_pts
#             },

#             "TECHNICAL_INDICATORS": {
#                 "RSI_14": round(last["RSI"], 2),
#                 "ATR_14": float(f"{last['ATR']:.5f}"),
#                 "EMA_200": float(f"{last['EMA200']:.5f}"),
#                 "EMA_50": float(f"{last['EMA50']:.5f}")
#             },

#             "TREND_CHECK": {
#                 "PRICE_VS_EMA200": price_vs_ema200,
#                 "VOLATILITY_ATR": "HIGH" if last["ATR"] > 0.0020 else "NORMAL"
#             },

#             # LE CŒUR DE LA V13
#             "MODULES_V13": {
#                 "ALERTE_SPREAD": spread_bad,      # True = Danger
#                 "ALERTE_RANGE": range_block,      # True = Marché plat (Danger)
#                 "ALERTE_MECHES": long_wicks,      # True = Volatilité dangereuse
#                 "ALERTE_IMPULSE": big_impulse,    # True = Mouvement violent fini ?
#                 "MODE_OR": gold_mode,
#                 "BLACKLIST": blacklisted
#             }
#         }

#         return bulletin




# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# from config import symbols

# class TacticalCalculator:
#     def __init__(self, symbol):
#         self.symbol = symbol

#     # ------------------------------------
#     # 1. GET TICK
#     # ------------------------------------
#     def _get_live_tick(self):
#         for _ in range(5):
#             if mt5.symbol_select(self.symbol, True): break
#             time.sleep(0.2)
        
#         tick = mt5.symbol_info_tick(self.symbol)
#         return tick

#     # ------------------------------------
#     # 2. GET HISTO DATA
#     # ------------------------------------
#     def _get_historical_data(self, tf, candles=500):
#         for _ in range(3):
#             rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, candles)
#             if rates is not None and len(rates) > 0:
#                 df = pd.DataFrame(rates)
#                 df['time'] = pd.to_datetime(df['time'], unit='s')
#                 df.set_index('time', inplace=True)
#                 return df
#             time.sleep(1)
#         return None

#     # ------------------------------------
#     # 3. MAIN BULLETIN
#     # ------------------------------------
#     def get_bulletin(self):
#         # A. LIVE
#         tick = self._get_live_tick()
#         if tick is None: return None

#         # B. HISTO
#         df = self._get_historical_data(symbols.MATH_TIMEFRAME)
#         if df is None: return None

#         # C. INDICATORS
#         try:
#             df["EMA50"] = df.ta.ema(length=50)
#             df["EMA200"] = df.ta.ema(length=200)
#             df["RSI"] = df.ta.rsi(length=14)
#             df["ATR"] = df.ta.atr(length=14)

#             bb = df.ta.bbands(length=20, std=2)
#             if bb is not None:
#                 cols = bb.columns.tolist()
#                 bbu_col = next((c for c in cols if "BBU" in c), None)
#                 bbl_col = next((c for c in cols if "BBL" in c), None)
#                 if bbu_col and bbl_col:
#                     df["BBU"] = bb[bbu_col]
#                     df["BBL"] = bb[bbl_col]

#         except Exception as e:
#             print(f"⚠️ Erreur Maths: {e}")
#             return None

#         last = df.iloc[-2]

#         # ------------------------------------
#         # 🛡️ MODULES V13 (CORRECTION JSON)
#         # ------------------------------------
        
#         # On utilise bool(...) pour forcer le type Python standard
#         # et éviter l'erreur "Object of type bool is not JSON serializable" (qui vient de NumPy)

#         # 1. SPREAD CHECK
#         spread_pts = int((tick.ask - tick.bid) * 100000)
#         spread_bad = bool(spread_pts > 40)

#         # 2. RANGE BLOCKER
#         ema50_slope = df["EMA50"].diff().tail(5).mean()
#         ema200_slope = df["EMA200"].diff().tail(5).mean()
#         range_block = bool(abs(ema50_slope) < 0.00005 and abs(ema200_slope) < 0.00005)

#         # 3. VOLATILITY / WICKS
#         wick_top = last["high"] - max(last["open"], last["close"])
#         wick_bot = min(last["open"], last["close"]) - last["low"]
#         long_wicks = bool(wick_top > (last["ATR"] * 1.5) or wick_bot > (last["ATR"] * 1.5))

#         # 4. GOLD SPECIAL
#         gold_mode = bool("XAU" in self.symbol)

#         # 5. BLACKLIST
#         blacklist = ["AUDCAD", "CADJPY", "NZDUSD", "EURCHF", "EURNZD", "AUDNZD"]
#         blacklisted = bool(self.symbol in blacklist)

#         # 6. MOMENTUM
#         impulse_threshold = last["ATR"] * 2.5
#         big_impulse = bool((last["high"] - last["low"]) > impulse_threshold)

#         # 7. STRUCTURE
#         price_vs_ema200 = "ABOVE" if tick.bid > last["EMA200"] else "BELOW"

#         # ------------------------------------
#         # BULLETIN
#         # ------------------------------------
#         bulletin = {
#             "META": {
#                 "Symbol": self.symbol,
#                 "Timeframe": "H4",
#                 "Tick_Time": str(tick.time)
#             },

#             "LIVE_PRICE_ACTION": {
#                 "REAL_BID": float(f"{tick.bid:.5f}"),
#                 "REAL_ASK": float(f"{tick.ask:.5f}"),
#                 "SPREAD_POINTS": spread_pts
#             },

#             "TECHNICAL_INDICATORS": {
#                 "RSI_14": round(last["RSI"], 2),
#                 "ATR_14": float(f"{last['ATR']:.5f}"),
#                 "EMA_200": float(f"{last['EMA200']:.5f}"),
#                 "EMA_50": float(f"{last['EMA50']:.5f}")
#             },

#             "TREND_CHECK": {
#                 "PRICE_VS_EMA200": price_vs_ema200,
#                 "VOLATILITY_ATR": "HIGH" if last["ATR"] > 0.0020 else "NORMAL"
#             },

#             "MODULES_V13": {
#                 "ALERTE_SPREAD": spread_bad,
#                 "ALERTE_RANGE": range_block,
#                 "ALERTE_MECHES": long_wicks,
#                 "ALERTE_IMPULSE": big_impulse,
#                 "MODE_OR": gold_mode,
#                 "BLACKLIST": blacklisted
#             }
#         }

#         return bulletin



import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
from config import symbols

class TacticalCalculator:
    def __init__(self, symbol):
        self.symbol = symbol

    def _get_live_tick(self):
        for _ in range(5):
            if mt5.symbol_select(self.symbol, True): break
            time.sleep(0.2)
        return mt5.symbol_info_tick(self.symbol)

    def _get_historical_data(self, tf, candles=500):
        rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, candles)
        if rates is None or len(rates) == 0: return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df

    def _calculate_indicators(self, df):
        try:
            # 1. Trend & Volatility
            df["EMA50"] = df.ta.ema(length=50)
            df["EMA200"] = df.ta.ema(length=200)
            df["ATR"] = df.ta.atr(length=14)
            
            # 2. Institutional (VWAP) - Rolling Calculation approximation
            # Note: Le vrai VWAP se reset chaque jour, ici on utilise un rolling pour l'analyse continue
            df["VWAP"] = df.ta.vwap() 

            # 3. Oscillators
            df["RSI"] = df.ta.rsi(length=14)
            
            # MACD (12, 26, 9)
            macd = df.ta.macd(fast=12, slow=26, signal=9)
            if macd is not None:
                df["MACD_LINE"] = macd["MACD_12_26_9"]
                df["MACD_SIGNAL"] = macd["MACDs_12_26_9"]
                df["MACD_HIST"] = macd["MACDh_12_26_9"]

            # Stochastique (14, 3, 3)
            stoch = df.ta.stoch(k=14, d=3, smooth_k=3)
            if stoch is not None:
                df["STOCH_K"] = stoch["STOCHk_14_3_3"]
                df["STOCH_D"] = stoch["STOCHd_14_3_3"]

        except: pass
        return df

    def get_bulletin(self):
        # A. LIVE
        tick = self._get_live_tick()
        if tick is None: return None
        current_price = tick.bid

        # B. DATA H1 (Trigger)
        df_h1 = self._get_historical_data(mt5.TIMEFRAME_H1)
        if df_h1 is None: return None
        df_h1 = self._calculate_indicators(df_h1)
        last_h1 = df_h1.iloc[-2]

        # C. DATA H4 (Structure)
        df_h4 = self._get_historical_data(mt5.TIMEFRAME_H4)
        if df_h4 is None: return None
        df_h4 = self._calculate_indicators(df_h4)
        last_h4 = df_h4.iloc[-2]

        # D. ANALYSE VWAP (Bullish/Bearish Bias)
        vwap_status = "BULLISH" if current_price > last_h1.get("VWAP", 0) else "BEARISH"

        # E. CONSTRUCTION DU BULLETIN ENRICHI
        bulletin = {
            "META": {
                "Symbol": self.symbol,
                "Scan_Time": str(tick.time),
                "Live_Price": float(f"{current_price:.5f}")
            },
            "INSTITUTIONAL_BIAS": {
                "Price_vs_VWAP_H1": vwap_status,
                "VWAP_Level": float(f"{last_h1.get('VWAP', 0):.5f}")
            },
            "H1_INDICATORS": {
                "RSI": round(last_h1["RSI"], 2),
                "MACD_Histogram": float(f"{last_h1.get('MACD_HIST', 0):.5f}"),
                "Stoch_K": round(last_h1.get('STOCH_K', 50), 2),
                "ATR": float(f"{last_h1['ATR']:.5f}"),
                "Trend": "BULLISH" if last_h1["close"] > last_h1["EMA200"] else "BEARISH"
            },
            "H4_STRUCTURE": {
                "Trend_EMA200": "BULLISH" if last_h4["close"] > last_h4["EMA200"] else "BEARISH",
                "RSI": round(last_h4["RSI"], 2),
                "MACD_Status": "UP" if last_h4.get('MACD_HIST', 0) > 0 else "DOWN"
            },
            "SAFETY": {
                "SPREAD": int((tick.ask - tick.bid) * 100000),
                "GOLD_MODE": "XAU" in self.symbol
            }
        }
        return bulletin