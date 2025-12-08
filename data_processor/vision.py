# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import mplfinance as mpf
# import numpy as np
# import os
# import matplotlib.pyplot as plt
# from matplotlib.ticker import FormatStrFormatter, FixedLocator
# from config import symbols

# class ChartPainter:
#     def __init__(self, symbol):
#         self.symbol = symbol
#         self.output_dir = "charts_buffer"
#         if not os.path.exists(self.output_dir):
#             os.makedirs(self.output_dir)

#     def _get_data(self, timeframe, count=400):
#         if not mt5.symbol_select(self.symbol, True): return None
#         rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
#         if rates is None or len(rates) == 0: return None
#         df = pd.DataFrame(rates)
#         df['time'] = pd.to_datetime(df['time'], unit='s')
#         df.set_index('time', inplace=True)
#         return df

#     def _add_technical_layers(self, df):
#         # EMAs
#         df['EMA50'] = df.ta.ema(length=50)
#         df['EMA200'] = df.ta.ema(length=200)
        
#         # Bollinger Bands Dynamique (Correction Robustesse)
#         try:
#             bb = df.ta.bbands(length=20, std=2)
#             if bb is not None:
#                 cols = bb.columns.tolist()
#                 # On cherche n'importe quelle colonne qui contient BBU/BBL
#                 bbu = next((c for c in cols if "BBU" in c), None)
#                 bbl = next((c for c in cols if "BBL" in c), None)
                
#                 if bbu and bbl:
#                     df['BBU'] = bb[bbu]
#                     df['BBL'] = bb[bbl]
#         except: pass
#         return df

#     def _calculate_zigzag_smc(self, df, window=5):
#         try:
#             df['is_high'] = df['high'].rolling(window=window, center=True).max() == df['high']
#             df['is_low'] = df['low'].rolling(window=window, center=True).min() == df['low']
            
#             pivots = []
#             for t, r in df[df['is_high']].iterrows(): pivots.append((t, r['high'], 'H'))
#             for t, r in df[df['is_low']].iterrows(): pivots.append((t, r['low'], 'L'))
#             pivots.sort(key=lambda x: x[0])
            
#             clean = []
#             last_type = None
#             for p in pivots:
#                 if last_type != p[2]:
#                     clean.append((p[0], p[1]))
#                     last_type = p[2]
#                 else:
#                     if last_type == 'H' and p[1] > clean[-1][1]: clean[-1] = (p[0], p[1])
#                     if last_type == 'L' and p[1] < clean[-1][1]: clean[-1] = (p[0], p[1])
#             return clean
#         except: return []

#     def _calculate_sr(self, df):
#         try:
#             levels = []
#             window = 20
#             for i in range(window, len(df)-window):
#                 if df['low'].iloc[i] == df['low'].iloc[i-window:i+window].min():
#                     levels.append(df['low'].iloc[i])
#                 if df['high'].iloc[i] == df['high'].iloc[i-window:i+window].max():
#                     levels.append(df['high'].iloc[i])
#             return list(set([l for l in levels]))
#         except: return []

#     def generate_charts(self):
#         paths = []
#         for tf, name, view_count in symbols.VISION_TIMEFRAMES:
#             df = self._get_data(tf, count=400)
#             if df is None: continue
            
#             df = self._add_technical_layers(df)
#             zigzag = self._calculate_zigzag_smc(df)
#             sr = self._calculate_sr(df)
            
#             # ZOOM
#             plot_df = df.tail(view_count).copy()
#             start_dt = plot_df.index[0]
#             visible_zigzag = [p for p in zigzag if p[0] >= start_dt]
            
#             adds = []
#             if 'EMA50' in plot_df: adds.append(mpf.make_addplot(plot_df['EMA50'], color='orange', width=1.5))
#             if 'EMA200' in plot_df: adds.append(mpf.make_addplot(plot_df['EMA200'], color='blue', width=2))
#             if 'BBU' in plot_df:
#                 adds.append(mpf.make_addplot(plot_df['BBU'], color='gray', alpha=0.3))
#                 adds.append(mpf.make_addplot(plot_df['BBL'], color='gray', alpha=0.3))
                
#             fname = f"{self.output_dir}/{self.symbol}_{name}.png"
#             s = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle=':', facecolor='#FAFAFA')
            
#             plot_args = {
#                 'type': 'candle',
#                 'style': s,
#                 'addplot': adds,
#                 'volume': False,
#                 'title': f"{self.symbol} - {name} (RAW PRECISION)",
#                 'returnfig': True,
#                 'tight_layout': True
#             }
            
#             if sr: plot_args['hlines'] = dict(hlines=sr, colors='green', alpha=0.5, linestyle='-.', linewidths=0.8)
#             if len(visible_zigzag) > 1: plot_args['alines'] = dict(alines=visible_zigzag, colors='magenta', linewidths=2, alpha=0.8)

#             try:
#                 fig, axlist = mpf.plot(plot_df, **plot_args)
#                 ax = axlist[0]
                
#                 # --- FORCAGE DES AXES BRUTS (RAW) ---
                
#                 # 1. On récupère le min et max EXACT visible sur l'écran
#                 y_min = plot_df['low'].min()
#                 y_max = plot_df['high'].max()
                
#                 # 2. On divise cet espace en 12 parts égales mathématiques
#                 # Cela crée des tics comme 1.16021, 1.16045... (pas d'arrondi)
#                 custom_ticks = np.linspace(y_min, y_max, 12)
                
#                 # 3. On applique ces tics forcés
#                 ax.yaxis.set_major_locator(FixedLocator(custom_ticks))
#                 ax.yaxis.set_major_formatter(FormatStrFormatter('%.5f'))
                
#                 # 4. Affichage du PRIX LIVE EN ROUGE
#                 current_price = plot_df['close'].iloc[-1]
#                 ax.axhline(current_price, color='red', linestyle='-', linewidth=0.8)
#                 ax.text(len(plot_df)+1, current_price, f" {current_price:.5f}", color='white', backgroundcolor='red', fontsize=8, fontweight='bold', va='center')

#                 # ------------------------------------

#                 fig.savefig(fname, dpi=120, bbox_inches='tight')
#                 plt.close(fig)
#                 paths.append(fname)
                
#             except Exception as e:
#                 print(f"❌ Erreur Graphique {name}: {e}")
        
#         return paths



import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, MaxNLocator
from config import symbols

class ChartPainter:
    def __init__(self, symbol):
        self.symbol = symbol
        self.output_dir = "charts_buffer"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _get_data(self, timeframe, count=400):
        if not mt5.symbol_select(self.symbol, True): return None
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0: return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df

    def _add_indicators(self, df):
        try:
            df['EMA50'] = df.ta.ema(length=50)
            df['EMA200'] = df.ta.ema(length=200)
            # VWAP (Ligne Violette)
            df['VWAP'] = df.ta.vwap()
            
            bb = df.ta.bbands(length=20, std=2)
            if bb is not None:
                cols = bb.columns.tolist()
                bbu = next((c for c in cols if "BBU" in c), None)
                bbl = next((c for c in cols if "BBL" in c), None)
                if bbu and bbl:
                    df['BBU'] = bb[bbu]
                    df['BBL'] = bb[bbl]
        except: pass
        return df

    def _get_levels(self, timeframe):
        """Récupère les S/R pour un TF donné."""
        df = self._get_data(timeframe, count=300)
        if df is None: return []
        levels = []
        window = 15
        for i in range(window, len(df)-window):
            if df['low'].iloc[i] == df['low'].iloc[i-window:i+window].min():
                levels.append(df['low'].iloc[i])
            if df['high'].iloc[i] == df['high'].iloc[i-window:i+window].max():
                levels.append(df['high'].iloc[i])
        return list(set(levels))

    def _calculate_smart_structure(self, df, window=5):
        """
        LE VRAI ZIGZAG ROBUSTE (SMC).
        Détecte les Highs/Lows et force l'alternance.
        """
        try:
            # 1. Fractales
            df['is_high'] = df['high'].rolling(window=window, center=True).max() == df['high']
            df['is_low'] = df['low'].rolling(window=window, center=True).min() == df['low']
            
            pivots = []
            for t, r in df[df['is_high']].iterrows(): pivots.append((t, r['high'], 'H'))
            for t, r in df[df['is_low']].iterrows(): pivots.append((t, r['low'], 'L'))
            pivots.sort(key=lambda x: x[0])
            
            # 2. Nettoyage (Alternance H -> L -> H)
            clean = []
            last_type = None
            for p in pivots:
                if last_type != p[2]:
                    clean.append((p[0], p[1]))
                    last_type = p[2]
                else:
                    # Garder le meilleur extremum si doublon
                    if last_type == 'H' and p[1] > clean[-1][1]: clean[-1] = (p[0], p[1])
                    if last_type == 'L' and p[1] < clean[-1][1]: clean[-1] = (p[0], p[1])
            return clean
        except: return []

    def generate_charts(self):
        paths = []
        
        # 1. PRÉ-CALCUL DES NIVEAUX SUPÉRIEURS
        levels_w1 = self._get_levels(mt5.TIMEFRAME_W1)
        levels_d1 = self._get_levels(mt5.TIMEFRAME_D1)
        levels_h4 = self._get_levels(mt5.TIMEFRAME_H4)

        for tf, name, view_count in symbols.VISION_TIMEFRAMES:
            df = self._get_data(tf, count=400)
            if df is None: continue
            
            df = self._add_indicators(df)
            
            # --- ZIGZAG IS BACK ---
            zigzag = self._calculate_smart_structure(df)
            
            plot_df = df.tail(view_count).copy()
            start_dt = plot_df.index[0]
            
            # Filtrage pour l'affichage (points visibles uniquement)
            visible_zigzag = [p for p in zigzag if p[0] >= start_dt]

            # --- SUPERPOSITION S/R ---
            hlines_list = []
            colors_list = []
            linewidths_list = []
            alphas_list = []
            linestyles_list = []

            visible_min = plot_df['low'].min() * 0.995
            visible_max = plot_df['high'].max() * 1.005
            
            def add_line(level, color, width, alpha, style):
                if visible_min < level < visible_max:
                    if not any(abs(level - l) < (level*0.0005) for l in hlines_list):
                        hlines_list.append(level)
                        colors_list.append(color)
                        linewidths_list.append(width)
                        alphas_list.append(alpha)
                        linestyles_list.append(style)

            # A. W1 (ROUGE)
            for l in levels_w1: add_line(l, 'red', 1.8, 0.9, '-')
            # B. D1 (BLEU)
            if tf != mt5.TIMEFRAME_W1:
                for l in levels_d1: add_line(l, 'blue', 1.2, 0.7, '-')
            # C. H4 (ORANGE)
            if tf in [mt5.TIMEFRAME_H4, mt5.TIMEFRAME_H1]:
                for l in levels_h4: add_line(l, 'orange', 1.0, 0.6, '--')
            # D. H1 (VERT)
            if tf == mt5.TIMEFRAME_H1:
                local = self._get_levels(mt5.TIMEFRAME_H1)
                for l in local: add_line(l, 'green', 0.8, 0.5, ':')

            # --- PLOTTING ---
            adds = []
            if 'EMA50' in plot_df: adds.append(mpf.make_addplot(plot_df['EMA50'], color='orange', width=1))
            if 'EMA200' in plot_df: adds.append(mpf.make_addplot(plot_df['EMA200'], color='blue', width=1.5))
            if 'VWAP' in plot_df: adds.append(mpf.make_addplot(plot_df['VWAP'], color='purple', width=1.2, linestyle='-.'))
            if 'BBU' in plot_df:
                adds.append(mpf.make_addplot(plot_df['BBU'], color='gray', width=0.5, alpha=0.3))
                adds.append(mpf.make_addplot(plot_df['BBL'], color='gray', width=0.5, alpha=0.3))

            fname = f"{self.output_dir}/{self.symbol}_{name}.png"
            s = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle=':', facecolor='#FAFAFA')
            
            plot_args = {
                'type': 'candle', 'style': s, 'addplot': adds, 'volume': False,
                'title': f"{self.symbol} - {name}",
                'returnfig': True, 'tight_layout': True
            }
            
            if hlines_list:
                plot_args['hlines'] = dict(hlines=hlines_list, colors=colors_list, linewidths=linewidths_list, alpha=alphas_list, linestyles=linestyles_list)

            # --- DESSIN DU ZIGZAG ---
            if len(visible_zigzag) > 1:
                plot_args['alines'] = dict(alines=visible_zigzag, colors='magenta', linewidths=2.0, alpha=0.9)

            try:
                fig, axlist = mpf.plot(plot_df, **plot_args)
                ax = axlist[0]
                ax.yaxis.set_major_formatter(FormatStrFormatter('%.5f'))
                ax.yaxis.set_major_locator(MaxNLocator(nbins=12, prune='both'))
                
                # Prix Actuel
                current_price = plot_df['close'].iloc[-1]
                ax.axhline(current_price, color='red', linestyle='--', linewidth=0.8)
                
                fig.savefig(fname, dpi=120, bbox_inches='tight')
                plt.close(fig)
                paths.append(fname)
            except Exception as e:
                print(f"❌ Erreur Graphique {name}: {e}")
        
        return paths