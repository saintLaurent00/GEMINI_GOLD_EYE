"""infrastructure/mt5_connector.py - MT5Connector.

Pont vers le terminal MetaTrader 5 : connexion, envoi d ordres avec detection
automatique du filling mode (FOK/IOC), modification SL/TP.
"""
import MetaTrader5 as mt5
import time
import os
from config import settings

class MT5Connector:
    def __init__(self):
        self.connected = False

    def start(self):
        """Initialise la connexion avec gestion d'erreur précise"""
        # Tentative standard
        if not mt5.initialize():
            # Tentative avec chemin explicite si défini dans .env
            mt5_path = os.getenv("MT5_PATH")
            if mt5_path and os.path.exists(mt5_path):
                if not mt5.initialize(path=mt5_path):
                    return False
            else:
                return False

        # Login
        authorized = mt5.login(
            login=settings.MT5_LOGIN, 
            password=settings.MT5_PASSWORD, 
            server=settings.MT5_SERVER
        )

        if authorized:
            print(f"✅ Connecté : {settings.MT5_LOGIN}")
            if not mt5.terminal_info().trade_allowed:
                print("⚠️ ATTENTION : Algo Trading désactivé dans MT5 !")
            self.connected = True
            return True
        else:
            print(f"❌ Échec Login : {mt5.last_error()}")
            return False

    def check_connection(self):
        if not mt5.terminal_info():
            print("🔄 Reconnexion...")
            return self.start()
        return True

    def execute_order(self, symbol, order_type, lot, sl, tp, comment="Gemini AI"):
        """Envoie un ordre avec détection automatique du Filling Mode (Version Robuste)"""
        
        # 1. Vérifications de base
        tick = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        
        if tick is None or symbol_info is None:
            print(f"❌ Erreur Tick/Info pour {symbol}")
            return None
            
        # 2. Détection du Filling Mode (Version compatible Universelle)
        # On utilise les entiers bruts pour éviter l'erreur d'attribut
        # 2 = IOC, 1 = FOK
        filling_mode = mt5.ORDER_FILLING_FOK # Par défaut
        
        if (symbol_info.filling_mode & 2): # Si IOC est supporté (Bit 2)
            filling_mode = mt5.ORDER_FILLING_IOC
        elif (symbol_info.filling_mode & 1): # Si FOK est supporté (Bit 1)
            filling_mode = mt5.ORDER_FILLING_FOK
        
        # 3. Préparation du prix
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": 234000,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode, 
        }
        
        # 4. Envoi
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Erreur Ordre : {result.comment} (Code: {result.retcode})")
            return None
        
        print(f"✅ ORDRE EXÉCUTÉ : {symbol} | Lot: {lot} | Ticket: {result.order}")
        return result

    def modify_position(self, ticket, sl, tp):
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": float(sl),
            "tp": float(tp)
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def shutdown(self):
        mt5.shutdown()