"""core/risk_manager.py - RiskManager.

Verifie les criteres d execution (marche ouvert, marge) et calcule la taille de lot
pour risquer X% du capital selon la distance du SL (formule universelle MT5).
"""
import MetaTrader5 as mt5
from config import settings

class RiskManager:
    def __init__(self):
        self.risk_percent = settings.RISK_PER_TRADE

    def check_existing_positions(self, symbol):
        """
        Vérifie si une position est déjà ouverte sur ce symbole.
        Retourne False si une position existe (pour bloquer le trade).
        Retourne True si la voie est libre.
        """
        positions = mt5.positions_get(symbol=symbol)
        
        if positions is None:
            # Erreur de lecture MT5
            return True 
            
        if len(positions) > 0:
            print(f"✋ Position déjà ouverte sur {symbol}. On passe.")
            return False
            
        return True

    def check_execution_criteria(self, symbol):
        """Vérifie si le marché est ouvert et sain."""
        info = mt5.symbol_info(symbol)
        if not info: return False
        
        if not info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
            print(f"⛔ Marché fermé pour {symbol}")
            return False

        account = mt5.account_info()
        if account.margin_free < 50: 
            print("⛔ Marge insuffisante.")
            return False

        return True

    def calculate_lot_size(self, symbol, sl_distance_price):
        """
        Calcule le lot pour risquer X% du capital.
        Accepte une distance en PRIX (ex: 0.0020) et la convertit en POINTS.
        """
        if sl_distance_price <= 0: return 0.01

        account = mt5.account_info()
        symbol_info = mt5.symbol_info(symbol)
        if not account or not symbol_info: return 0.01

        # 1. Montant du risque
        risk_amount = account.balance * (self.risk_percent / 100)

        # 2. Récupération des infos du point
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        point = symbol_info.point
        
        if tick_size == 0 or point == 0: return 0.01

        # --- CONVERSION PRIX -> POINTS ---
        sl_points = sl_distance_price / point
        # ---------------------------------

        # 3. Valeur d'un point pour 1 lot
        value_per_point = tick_value * (point / tick_size)

        if value_per_point == 0: return 0.01

        # 4. Calcul du Lot
        raw_lot = risk_amount / (sl_points * value_per_point)

        # 5. Normalisation
        step = symbol_info.volume_step
        lot = round(raw_lot / step) * step
        
        # Bornes
        lot = max(lot, symbol_info.volume_min)
        lot = min(lot, symbol_info.volume_max)

        # Sécurité : Cap à 10 lots max pour le test
        lot = min(lot, 10.0)

        return float(f"{lot:.2f}")