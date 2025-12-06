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

# Import des modules existants
from infrastructure.gemini_client import GeminiClient
from config import settings

# --- CONFIGURATION DU BACKTEST ---
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_H4
HISTORY_DEPTH = 2000   # Historique chargé
TEST_CANDLES = 10      # Nombre de bougies à tester (Attention Quotas !)
PAUSE_BETWEEN = 20     # Pause en secondes (Google est strict avec les images)

class BacktestPro:
    def __init__(self):
        self.ai = GeminiClient()
        self.bt_dir = "backtest_temp"
        
        # Nettoyage dossier temporaire
        if os.path.exists(self.bt_dir): shutil.rmtree(self.bt_dir)
        os.makedirs(self.bt_dir)
        
        # Stats
        self.wins = 0
        self.losses = 0
        self.be = 0

    def _get_data(self):
        """Charge les données brutes H4, D1, W1"""
        if not mt5.initialize(): return None
        print(f"📥 Téléchargement Données Multi-Timeframe...")
        
        data = {}
        for tf, name in [(mt5.TIMEFRAME_H4, "H4"), (mt5.TIMEFRAME_D1, "D1"), (mt5.TIMEFRAME_W1, "W1")]:
            rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, HISTORY_DEPTH)
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            # Calculs Indicateurs sur tout l'historique
            df['EMA50'] = df.ta.ema(length=50)
            df['EMA200'] = df.ta.ema(length=200)
            df['RSI'] = df.ta.rsi(length=14)
            df['ATR'] = df.ta.atr(length=14)
            
            # Bollinger
            bb = df.ta.bbands(length=20, std=2)
            if bb is not None:
                cols = bb.columns.tolist()
                bbu = next((c for c in cols if "BBU" in c), None)
                bbl = next((c for c in cols if "BBL" in c), None)
                if bbu and bbl:
                    df['BBU'] = bb[bbu]
                    df['BBL'] = bb[bbl]
            
            data[name] = df
            
        return data

    def _create_snapshot(self, data, end_date):
        """
        Crée les 3 IMAGES et le JSON tels qu'ils auraient été à 'end_date'
        """
        image_paths = []
        
        # 1. GÉNÉRATION DES 3 IMAGES (W1, D1, H4)
        for name, full_df in data.items():
            # On coupe les données pour ne pas voir le futur
            # On prend les données jusqu'à end_date inclus
            past_df = full_df[full_df.index <= end_date]
            
            if len(past_df) < 100: continue
            
            # Zoom sur les dernières bougies pour l'image
            plot_df = past_df.tail(100) # Vue tactique
            
            fname = f"{self.bt_dir}/{SYMBOL}_{name}_{end_date.strftime('%H%M')}.png"
            
            # Style et Indicateurs (Identique Vision.py)
            adds = []
            if 'EMA50' in plot_df: adds.append(mpf.make_addplot(plot_df['EMA50'], color='orange', width=1.5))
            if 'EMA200' in plot_df: adds.append(mpf.make_addplot(plot_df['EMA200'], color='blue', width=2))
            if 'BBU' in plot_df:
                adds.append(mpf.make_addplot(plot_df['BBU'], color='gray', alpha=0.3))
                adds.append(mpf.make_addplot(plot_df['BBL'], color='gray', alpha=0.3))

            s = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle=':', facecolor='#FAFAFA')
            
            try:
                fig, axlist = mpf.plot(
                    plot_df, type='candle', style=s, addplot=adds, volume=False,
                    title=f"{SYMBOL} - {name} (Backtest)", returnfig=True, tight_layout=True
                )
                
                # Précision 5 décimales
                axlist[0].yaxis.set_major_formatter(FormatStrFormatter('%.5f'))
                axlist[0].yaxis.set_major_locator(MaxNLocator(nbins=12, prune='both'))
                
                # Prix "Live" (Clôture de la bougie testée)
                current_price = plot_df['close'].iloc[-1]
                axlist[0].axhline(current_price, color='red', linestyle='--', linewidth=1)
                
                fig.savefig(fname, dpi=100, bbox_inches='tight')
                plt.close(fig)
                image_paths.append(fname)
            except: pass

        # 2. GÉNÉRATION DU JSON (Bulletin Tactique Simulé)
        # On utilise les données H4 à l'instant T
        row = data['H4'].loc[end_date]
        
        trend = "NEUTRAL"
        if row['close'] > row['EMA200']: trend = "BULLISH"
        elif row['close'] < row['EMA200']: trend = "BEARISH"

        bulletin = {
            "META": {"Timeframe": "H4", "Simulated_Time": str(end_date)},
            "LIVE_PRICE_ACTION": {
                "REAL_BID": float(f"{row['close']:.5f}"), # Close = Prix actuel en backtest
                "REAL_ASK": float(f"{row['close'] + 0.00010:.5f}"), # Spread simulé 1 pip
            },
            "TECHNICAL_INDICATORS": {
                "RSI_14": round(row['RSI'], 2),
                "ATR_14": float(f"{row['ATR']:.5f}"),
                "EMA_200": float(f"{row['EMA200']:.5f}"),
                "BB_UPPER": float(f"{row.get('BBU', 0):.5f}")
            },
            "TREND_CHECK": {
                "PRICE_VS_EMA200": "ABOVE" if row['close'] > row['EMA200'] else "BELOW"
            }
        }
        
        return image_paths, bulletin

    def _simulate_result(self, entry, sl, tp, direction, future_data):
        """Simule le trade avec BE et TP"""
        outcome = "OPEN"
        pnl = 0
        sl_current = sl
        be_dist = abs(entry - sl) # On met à BE à 1R
        be_active = False
        
        for idx, row in future_data.iterrows():
            if direction == "BUY":
                if row['low'] <= sl_current:
                    outcome = "LOSS" if not be_active else "BE"
                    pnl = -1.0 if not be_active else 0
                    break
                if row['high'] >= tp:
                    outcome = "WIN"
                    pnl = 3.0
                    break
                # Gestion BE
                if not be_active and row['high'] >= entry + be_dist:
                    sl_current = entry + 0.00010
                    be_active = True
            
            else: # SELL
                if row['high'] >= sl_current:
                    outcome = "LOSS" if not be_active else "BE"
                    pnl = -1.0 if not be_active else 0
                    break
                if row['low'] <= tp:
                    outcome = "WIN"
                    pnl = 3.0
                    break
                # Gestion BE
                if not be_active and row['low'] <= entry - be_dist:
                    sl_current = entry - 0.00010
                    be_active = True
                    
        return outcome, pnl

    def run(self):
        data = self._get_data()
        if not data: return
        
        df_h4 = data['H4']
        
        # On définit la plage de test (ex: les 20 dernières bougies sauf les 5 dernières)
        test_indices = df_h4.index[-(TEST_CANDLES + 20) : -20]
        
        print(f"\n🧪 DÉMARRAGE BACKTEST RÉALISTE ({len(test_indices)} Bougies)")
        print("Note: Ce test utilise les 3 images (W1/D1/H4) et le JSON précis.")
        print(f"⏳ Délai sécurité Google : {PAUSE_BETWEEN}s par trade...\n")

        for current_time in test_indices:
            print(f"🕰️ Analyse : {current_time} ... ", end="", flush=True)
            
            # 1. Création de l'environnement passé
            img_paths, bulletin = self._create_snapshot(data, current_time)
            
            if len(img_paths) < 3: 
                print("⚠️ Manque des images contextuelles.")
                continue

            # 2. LE PROMPT EXACT DE TON STRATEGY.PY
            prompt = f"""
            RÔLE: Expert Hedge Fund Trader (Specialité: Price Action & SMC).
            
            OBJECTIF: Identifier une entrée "Day Trading" (H4) qui a le potentiel de devenir un "Swing" (D1/W1).
            
            DONNÉES:
            {json.dumps(bulletin, indent=2)}
            
            TACHE D'ANALYSE VISUELLE (Images):
            1. W1/D1 (Fond) : Quelle est la tendance lourde ? (Regarde EMA200 et ZigZag).
            2. H4 (Signal) : Cherche un PATTERN D'ENTRÉE précis sur la structure actuelle.
               - Patterns Haussiers : Double Bottom, Bullish Flag, Cassure + Retest (BOS), Avalement Haussier sur support.
               - Patterns Baissiers : Double Top, Bearish Flag, Rejet sous résistance, Avalement Baissier.
            
            RÈGLES D'OR :
            - Ne trade JAMAIS contre la tendance W1/D1 sauf si divergence RSI confirmée.
            - Regarde le PRIX EXACT (Ligne Rouge). Est-il sur un Support (Ligne Verte) ou une EMA ?
            - Volatilité : Utilise l'ATR fourni pour valider que le marché n'est pas mort.

            SORTIE (JSON STRICT):
            {{
                "decision": "BUY" | "SELL" | "WAIT",
                "confidence": 0-100,
                "reason": "Cite le Pattern visuel H4 détecté et la validation D1",
                "sl_atr_multiplier": 2.0,
                "risk_reward_ratio": 3.0
            }}
            """

            # 3. Appel IA
            response = self.ai.send_multimodal_prompt(prompt, img_paths)
            
            if response:
                try:
                    clean = response.replace("```json", "").replace("```", "").strip()
                    dec = json.loads(clean)
                    verdict = dec.get('decision')
                    conf = dec.get('confidence', 0)
                    
                    print(f"{verdict} ({conf}%)")
                    
                    if verdict in ["BUY", "SELL"] and conf >= 75:
                        # Simulation Trade
                        row = df_h4.loc[current_time]
                        atr = row['ATR']
                        entry = row['close']
                        sl_mult = dec.get('sl_atr_multiplier', 2.0)
                        rr = dec.get('risk_reward_ratio', 3.0)
                        
                        sl_dist = atr * sl_mult
                        
                        if verdict == "BUY":
                            sl = entry - sl_dist
                            tp = entry + (sl_dist * rr)
                        else:
                            sl = entry + sl_dist
                            tp = entry - (sl_dist * rr)
                            
                        # On regarde le futur à partir de la bougie SUIVANTE
                        future_data = df_h4[df_h4.index > current_time]
                        outcome, r = self._simulate_result(entry, sl, tp, verdict, future_data)
                        
                        print(f"   🎲 Résultat : {outcome} ({r} R) | {dec.get('reason')[:50]}...")
                        
                        if outcome == "WIN": self.wins += 1
                        elif outcome == "LOSS": self.losses += 1
                        elif outcome == "BE": self.be += 1
                
                except Exception as e:
                    print(f"⚠️ Erreur JSON: {e}")
            else:
                print("❌ Pas de réponse.")

            # Pause obligatoire
            time.sleep(PAUSE_BETWEEN)

        print(f"\n📊 BILAN PRO : WIN {self.wins} | LOSS {self.losses} | BE {self.be}")

if __name__ == "__main__":
    bt = BacktestPro()
    bt.run()