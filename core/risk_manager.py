# import MetaTrader5 as mt5
# from config import settings

# class RiskManager:
#     def __init__(self):
#         # On récupère le risque défini dans .env (ex: 2.0)
#         self.risk_percent = settings.RISK_PER_TRADE

#     def check_execution_criteria(self, symbol):
#         """
#         Vérifie les conditions de base avant de calculer.
#         """
#         info = mt5.symbol_info(symbol)
#         if not info:
#             print(f"⛔ Erreur info symbole {symbol}")
#             return False
        
#         # Vérification si le marché est ouvert
#         if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
#             print(f"⛔ Marché fermé ou limité pour {symbol}")
#             return False

#         # Vérification Marge Libre (Sécurité)
#         account = mt5.account_info()
#         if account.margin_free < 50: 
#             print("⛔ Marge libre insuffisante.")
#             return False

#         return True

#     def calculate_lot_size(self, symbol, sl_distance_points):
#         """
#         Calcule la taille du lot.
#         Entrée : Distance du SL en POINTS (ex: 0.00450 pour 45 pips).
#         Sortie : Lot (ex: 0.12).
#         """
#         if sl_distance_points <= 0: return 0.01

#         account = mt5.account_info()
#         symbol_info = mt5.symbol_info(symbol)
        
#         if not account or not symbol_info: return 0.01

#         # 1. Calcul du montant en $ à risquer
#         # Ex: 10 000$ * 2% = 200$
#         risk_amount = account.balance * (self.risk_percent / 100)

#         # 2. Valeur d'un point pour 1 lot standard
#         # Formule universelle MT5
#         tick_value = symbol_info.trade_tick_value
#         tick_size = symbol_info.trade_tick_size
#         point = symbol_info.point
        
#         if tick_size == 0 or point == 0: return 0.01
        
#         # Combien vaut 1 point de mouvement pour 1 lot ?
#         value_per_point = tick_value * (point / tick_size)

#         # 3. Calcul du Lot brut
#         # Lot = Montant_Risque / (Distance_Points * Valeur_1_Point)
#         raw_lot = risk_amount / (sl_distance_points * value_per_point)

#         # # 4. Normalisation (Respect des règles du courtier)
#         # step = symbol_info.volume_step      # Ex: 0.01
#         # min_vol = symbol_info.volume_min    # Ex: 0.01
#         # max_vol = symbol_info.volume_max    # Ex: 100.0

#         # # Arrondi au "step" le plus proche
#         # lot = round(raw_lot / step) * step
        
#         # # Bornes Min/Max
#         # lot = max(lot, min_vol)
#         # lot = min(lot, max_vol)

#         # return float(f"{lot:.2f}")



#         # ... (début du fichier identique)

#         # 4. Arrondi
#         step = symbol_info.volume_step
#         lot = round(raw_lot / step) * step
        
#         # Bornes Courtier
#         lot = max(lot, symbol_info.volume_min)
#         lot = min(lot, symbol_info.volume_max)

#         # --- SÉCURITÉ GEMINI GOLD EYE ---
#         # On force un max de 1.0 lot pour les tests, pour éviter les 500 lots
#         MAX_SAFE_LOT = 1.0 
#         if lot > MAX_SAFE_LOT:
#             print(f"⚠️ Alerte: Lot calculé ({lot}) > Max Sécurité ({MAX_SAFE_LOT}). On plafonne.")
#             lot = MAX_SAFE_LOT
#         # -------------------------------

#         return float(f"{lot:.2f}")




# import MetaTrader5 as mt5
# from config import settings

# class RiskManager:
#     def __init__(self):
#         self.risk_percent = settings.RISK_PER_TRADE
#         # Sécurité Absolue : On ne dépassera jamais 50 lots standards, même si le calcul devient fou
#         self.MAX_LOT_CAP = 50.0 

#     def check_execution_criteria(self, symbol):
#         """Vérifie si le marché est ouvert."""
#         info = mt5.symbol_info(symbol)
#         if not info: return False
        
#         # Vérification si le marché est ouvert (Dimanche = Fermé)
#         # Note : En démo, parfois trade_mode est FULL même le weekend, donc on se fie à l'erreur d'ordre
#         if info.time == 0: 
#             return False # Pas de données récentes = marché fermé

#         account = mt5.account_info()
#         if account.margin_free < 50: return False
#         return True

#     def calculate_lot_size(self, symbol, sl_distance_price):
#         """
#         Calcule la taille du lot.
#         sl_distance_price : La distance en PRIX (ex: 0.00450 pour 45 pips)
#         """
#         if sl_distance_price <= 0: return 0.01

#         account = mt5.account_info()
#         symbol_info = mt5.symbol_info(symbol)
#         if not account or not symbol_info: return 0.01

#         balance = account.balance
#         risk_amount = balance * (self.risk_percent / 100)

#         # --- DEBUG VALUES (Pour comprendre le calcul) ---
#         tick_size = symbol_info.trade_tick_size   # ex: 0.00001
#         tick_value = symbol_info.trade_tick_value # Valeur d'un tick en devise du compte
#         contract_size = symbol_info.trade_contract_size # ex: 100 000 unités
        
#         # Protection Division Zéro
#         if tick_size == 0 or tick_value == 0: 
#             print(f"⚠️ Erreur données courtier (TickSize=0). Lot par défaut 0.01")
#             return 0.01

#         # Formule Universelle Forex :
#         # Perte par Lot = (Distance_SL / Tick_Size) * Tick_Value
#         loss_per_1_lot = (sl_distance_price / tick_size) * tick_value
        
#         if loss_per_1_lot == 0: return 0.01

#         raw_lot = risk_amount / loss_per_1_lot

#         # --- VERIFICATION VISUELLE ---
#         # print(f"   [DEBUG] Capital: {balance} | Risque $: {risk_amount:.2f}")
#         # print(f"   [DEBUG] SL Dist: {sl_distance_price:.5f} | Perte/1Lot: {loss_per_1_lot:.2f}")
#         # print(f"   [DEBUG] Lot Brut: {raw_lot:.2f}")

#         # Arrondis et Bornes
#         step = symbol_info.volume_step
#         lot = round(raw_lot / step) * step
#         lot = max(lot, symbol_info.volume_min)
#         lot = min(lot, symbol_info.volume_max)
        
#         # Cap de sécurité ultime
#         if lot > self.MAX_LOT_CAP:
#             print(f"⚠️ Alerte: Lot calculé ({lot}) énorme. Plafonné à {self.MAX_LOT_CAP}")
#             lot = self.MAX_LOT_CAP

#         return float(f"{lot:.2f}")







    


# import MetaTrader5 as mt5
# from config import settings

# class RiskManager:
#     def __init__(self):
#         self.risk_percent = settings.RISK_PER_TRADE

#     def check_existing_positions(self, symbol):
#         """
#         Vérifie si on a déjà une position ouverte sur ce symbole.
#         Renvoie True si on peut trader (aucune position), False sinon.
#         """
#         positions = mt5.positions_get(symbol=symbol)
        
#         if positions is None:
#             return True # Par sécurité, si erreur MT5, on suppose qu'on peut (ou on gère l'erreur)
            
#         if len(positions) > 0:
#             print(f"✋ Position déjà ouverte sur {symbol}. On passe.")
#             return False # INTERDICTION DE TRADER
            
#         return True # FEU VERT

#     def check_execution_criteria(self, symbol):
#         """Vérifie si le marché est ouvert et sain."""
#         info = mt5.symbol_info(symbol)
#         if not info: return False
        
#         if not info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
#             print(f"⛔ Marché fermé pour {symbol}")
#             return False

#         account = mt5.account_info()
#         if account.margin_free < 50: 
#             print("⛔ Marge insuffisante.")
#             return False

#         return True

#     def calculate_lot_size(self, symbol, sl_distance_points):
#         """Calcule le lot pour risquer X% du capital."""
#         if sl_distance_points <= 0: return 0.01

#         account = mt5.account_info()
#         symbol_info = mt5.symbol_info(symbol)
#         if not account or not symbol_info: return 0.01

#         risk_amount = account.balance * (self.risk_percent / 100)

#         tick_value = symbol_info.trade_tick_value
#         tick_size = symbol_info.trade_tick_size
#         point = symbol_info.point
        
#         if tick_size == 0 or point == 0: return 0.01
        
#         value_per_point = tick_value * (point / tick_size)

#         raw_lot = risk_amount / (sl_distance_points * value_per_point)

#         step = symbol_info.volume_step
#         lot = round(raw_lot / step) * step
        
#         lot = max(lot, symbol_info.volume_min)
#         lot = min(lot, symbol_info.volume_max)

#         return float(f"{lot:.2f}")






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