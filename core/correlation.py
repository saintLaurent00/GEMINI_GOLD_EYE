import MetaTrader5 as mt5
import pandas as pd
from config import settings

class CorrelationGuard:
    def __init__(self):
        self.threshold = 0.80 # Si corrélation > 80%, on bloque

    def get_correlation(self, symbol_a, symbol_b):
        """Calcule la corrélation mathématique entre deux paires sur H4."""
        # On récupère 50 bougies H4 pour avoir un échantillon statistique
        rates_a = mt5.copy_rates_from_pos(symbol_a, mt5.TIMEFRAME_H4, 0, 50)
        rates_b = mt5.copy_rates_from_pos(symbol_b, mt5.TIMEFRAME_H4, 0, 50)
        
        if rates_a is None or rates_b is None: return 0.0
        
        df_a = pd.DataFrame(rates_a)['close']
        df_b = pd.DataFrame(rates_b)['close']
        
        # Calcul de corrélation de Pearson
        corr = df_a.corr(df_b)
        return corr

    def check_exposure(self, new_symbol, new_signal):
        """
        Vérifie si on a déjà une position ouverte sur une paire corrélée
        dans le même sens.
        Retourne : (Autorisé [True/False], Raison)
        """
        positions = mt5.positions_get()
        if not positions: return True, "No positions"

        for pos in positions:
            open_symbol = pos.symbol
            
            # On ignore le symbole lui-même (géré ailleurs)
            if open_symbol == new_symbol: continue
            
            # Calcul corrélation
            corr_score = self.get_correlation(new_symbol, open_symbol)
            
            # Si forte corrélation positive (> 0.80)
            if corr_score > self.threshold:
                # Vérifier le sens
                open_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                
                # Si on veut faire la même chose (BUY & BUY ou SELL & SELL) sur deux paires identiques
                if open_type == new_signal:
                    return False, f"Trop corrélé avec {open_symbol} ({corr_score:.2f}) qui est déjà en {open_type}"
                    
            # Si forte corrélation négative (< -0.80) (Ex: EURUSD vs USDCHF)
            # Si on veut faire l'inverse (BUY EURUSD alors qu'on a SELL USDCHF) -> C'est le même pari !
            elif corr_score < -self.threshold:
                open_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                if open_type != new_signal:
                     return False, f"Corrélation inverse avec {open_symbol} ({corr_score:.2f}). Risque doublé."

        return True, "Safe"