import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import json
import os
import time
import shutil
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, MaxNLocator

from config import settings
from infrastructure.gemini_client import GeminiClient

# --- CONFIGURATION ---
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_H4
HISTORY_DEPTH = 1500
TEST_RANGE = 15        # On réduit un peu pour tester la stabilité
PAUSE_SECONDS = 15     # On augmente la pause pour éviter le blocage API

class BacktestEngine:
    def __init__(self):
        self.ai = GeminiClient()
        self.wins = 0
        self.losses = 0
        self.be = 0 
        self.bt_charts_dir = "backtest_charts"
        if os.path.exists(self.bt_charts_dir): shutil.rmtree(self.bt_charts_dir)
        os.makedirs(self.bt_charts_dir)

    def _prepare_data(self):
        if not mt5.initialize(): return None
        print(f"📥 Téléchargement Données...")
        
        rates_h4 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H4, 0, HISTORY_DEPTH)
        df_h4 = pd.DataFrame(rates_h4)
        df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
        df_h4.set_index('time', inplace=True)
        
        rates_d1 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_D1, 0, 300)
        df_d1 = pd.DataFrame(rates_d1)
        df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
        df_d1.set_index('time', inplace=True)
        
        df_h4['EMA50'] = df_h4.ta.ema(length=50)
        df_h4['EMA200'] = df_h4.ta.ema(length=200)
        df_h4['RSI'] = df_h4.ta.rsi(length=14)
        df_h4['ATR'] = df_h4.ta.atr(length=14)
        
        df_d1['EMA200'] = df_d1.ta.ema(length=200)
        
        return df_h4, df_d1

    def _get_d1_trend(self, df_d1, current_date):
        target_date = current_date.normalize() - pd.Timedelta(days=1)
        try:
            idx = df_d1.index.get_indexer([target_date], method='nearest')[0]
            row = df_d1.iloc[idx]
            if row['close'] > row['EMA200']: return "HAUSSIER"
            else: return "BAISSIER"
        except: return "NEUTRE"

    def _generate_chart(self, slice_df, index_name):
        fname = f"{self.bt_charts_dir}/{SYMBOL}_{index_name}.png"
        plot_df = slice_df.tail(60)
        
        s = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle=':', facecolor='#FAFAFA')
        adds = [
            mpf.make_addplot(plot_df['EMA50'], color='orange', width=1.5),
            mpf.make_addplot(plot_df['EMA200'], color='blue', width=2)
        ]

        try:
            fig, axlist = mpf.plot(
                plot_df, type='candle', style=s, addplot=adds, volume=False,
                title=f"BT {SYMBOL} {index_name}", returnfig=True, tight_layout=True
            )
            axlist[0].yaxis.set_major_formatter(FormatStrFormatter('%.5f'))
            fig.savefig(fname, dpi=80, bbox_inches='tight')
            plt.close(fig)
            return fname
        except: return None

    def _simulate_trade_smart(self, entry, sl, tp, direction, future_df):
        outcome = "OPEN"
        pnl = 0
        sl_current = sl
        be_triggered = False
        risk_dist = abs(entry - sl)
        be_trigger_dist = risk_dist * 1.0 

        # Prix final par défaut (si trade reste ouvert)
        exit_price = future_df.iloc[-1]['close'] if len(future_df) > 0 else entry

        for i, row in future_df.iterrows():
            high = row['high']
            low = row['low']
            exit_price = row['close'] # On met à jour le prix de sortie potentiel
            
            if direction == "BUY":
                if low <= sl_current:
                    outcome = "LOSS" if not be_triggered else "BE"
                    pnl = -1.0 if not be_triggered else 0
                    break
                if high >= tp:
                    outcome = "WIN"
                    pnl = 2.0 
                    break
                if not be_triggered and high >= (entry + be_trigger_dist):
                    sl_current = entry + (0.00010)
                    be_triggered = True
                    
            else: # SELL
                if high >= sl_current:
                    outcome = "LOSS" if not be_triggered else "BE"
                    pnl = -1.0 if not be_triggered else 0
                    break
                if low <= tp:
                    outcome = "WIN"
                    pnl = 2.0
                    break
                if not be_triggered and low <= (entry - be_trigger_dist):
                    sl_current = entry - (0.00010)
                    be_triggered = True
        
        # Si trade encore OPEN, on calcule le PnL latent
        if outcome == "OPEN":
            if direction == "BUY":
                dist = exit_price - entry
            else:
                dist = entry - exit_price
            
            # PnL en ratio R (approx)
            pnl = dist / risk_dist
            
        return outcome, pnl

    def run(self):
        print(f"\n🧪 DÉMARRAGE BACKTEST v3 (Lent & Robuste)")
        print(f"⏳ Délai entre requêtes : {PAUSE_SECONDS} secondes\n")
        
        df_h4, df_d1 = self._prepare_data()
        
        start_idx = len(df_h4) - TEST_RANGE - 20
        end_idx = len(df_h4) - 10
        
        for i in range(start_idx, end_idx):
            current_slice = df_h4.iloc[:i+1]
            current_candle = current_slice.iloc[-1]
            future_slice = df_h4.iloc[i+1:]
            
            trend_d1 = self._get_d1_trend(df_d1, current_candle.name)
            img_path = self._generate_chart(current_slice, str(i))
            
            if not img_path: continue
            
            bulletin = {
                "Price": current_candle['close'],
                "ATR": float(f"{current_candle['ATR']:.5f}"),
                "Trend_H4": "HAUSSIER" if current_candle['close'] > current_candle['EMA200'] else "BAISSIER",
                "Trend_D1": trend_d1
            }
            
            prompt = f"""
            BACKTEST. Tendance D1: {bulletin['Trend_D1']}.
            Données H4: {json.dumps(bulletin)}.
            
            REGLE: Ne trade PAS contre D1.
            Si D1 HAUSSIER -> Cherche BUY (Repli sur support).
            Si D1 BAISSIER -> Cherche SELL (Rejet sous résistance).
            
            Analyse l'image. Décision ?
            JSON: {{ "decision": "BUY/SELL/WAIT", "confidence": int }}
            """
            
            print(f"🔍 {current_candle.name} | D1: {trend_d1} ... ", end="", flush=True)
            response = self.ai.send_multimodal_prompt(prompt, [img_path])
            
            if response:
                try:
                    clean = response.replace("```json", "").replace("```", "").strip()
                    dec = json.loads(clean)
                    verdict = dec.get('decision')
                    conf = dec.get('confidence', 0)
                    
                    print(f"IA: {verdict} ({conf}%)")

                    if verdict in ["BUY", "SELL"] and conf >= 75:
                        # --- FILTRE D1 ---
                        is_safe = True
                        if "HAUSSIER" in trend_d1 and verdict == "SELL": is_safe = False
                        if "BAISSIER" in trend_d1 and verdict == "BUY": is_safe = False
                        
                        if not is_safe:
                            print(f"      🛡️ FILTRE: Trade {verdict} refusé (Contre D1)")
                        else:
                            # SIMULATION
                            atr = current_candle['ATR']
                            entry = current_candle['close']
                            sl_dist = atr * 2.0
                            
                            if verdict == "BUY":
                                sl = entry - sl_dist
                                tp = entry + (sl_dist * 2.5)
                            else:
                                sl = entry + sl_dist
                                tp = entry - (sl_dist * 2.5)
                                
                            outcome, r = self._simulate_trade_smart(entry, sl, tp, verdict, future_slice)
                            print(f"      🎲 Résultat : {outcome} ({r:.2f} R)")
                            
                            if outcome == "WIN": self.wins += 1
                            elif outcome == "LOSS": self.losses += 1
                            elif outcome == "BE": self.be += 1
                            
                except Exception as e: 
                    # --- DEBUG DES ERREURS ---
                    print(f"\n      ⚠️ ERREUR JSON: {e}")
                    print(f"      📝 RÉPONSE BRUTE REÇUE: {response[:100]}...") # On affiche le début
            else:
                print("❌ Pas de réponse API.")
            
            # PAUSE LONGUE
            time.sleep(PAUSE_SECONDS)

        total = self.wins + self.losses + self.be
        print(f"\n📊 BILAN v3 : Trades {total} | WIN {self.wins} | LOSS {self.losses} | BE {self.be}")

if __name__ == "__main__":
    bt = BacktestEngine()
    bt.run()