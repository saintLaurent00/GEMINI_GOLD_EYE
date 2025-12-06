import MetaTrader5 as mt5

class TradeExecutor:
    def execute_order(self, symbol, order_type, lot, sl, tp, comment="Gemini AI"):
        """Exécute l'ordre en s'adaptant au courtier (Filling Mode)"""
        
        # 1. Détection automatique du mode supporté
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"❌ Erreur: Symbole {symbol} non trouvé.")
            return False

        # --- CORRECTION HEURTIQUE ---
        # En Python, les constantes SYMBOL_FILLING_XXX n'existent parfois pas.
        # On utilise les valeurs brutes :
        # 1 = FOK (Fill or Kill)
        # 2 = IOC (Immediate or Cancel)
        
        filling_mode = mt5.ORDER_FILLING_FOK # Par défaut
        
        # On vérifie les flags avec les entiers
        if symbol_info.filling_mode & 2: # Si le bit 2 est activé (IOC)
            filling_mode = mt5.ORDER_FILLING_IOC
        elif symbol_info.filling_mode & 1: # Si le bit 1 est activé (FOK)
            filling_mode = mt5.ORDER_FILLING_FOK
        
        # 2. Préparation
        # On récupère le prix actuel pour l'ordre au marché
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print(f"❌ Erreur: Pas de tick pour {symbol}")
            return False
            
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20, # On tolère un glissement de 20 points
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode, # Mode dynamique corrigé
        }

        # 3. Envoi
        result = mt5.order_send(request)
        
        # 4. Vérification
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Erreur Ordre: {result.comment} (Code: {result.retcode})")
            # Debug pour comprendre si ça plante encore
            print(f"   Mode tenté: {filling_mode} (IOC=1, FOK=2)")
            return False
        else:
            print(f"✅ EXÉCUTION RÉUSSIE ! Ticket: {result.order}")
            return True