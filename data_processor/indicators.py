"""data_processor/indicators.py - TacticalCalculator.

Calcule les indicateurs (EMA50/200, RSI, ATR, VWAP, MACD, Stochastique) sur H1
et H4 et construit le BULLETIN TACTIQUE envoye a Gemini.
"""
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