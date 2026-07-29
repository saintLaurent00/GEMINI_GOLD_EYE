"""core/trade_manager.py - TradeManager.

Place les ordres (place_trade) et gere les positions ouvertes : Break-Even +
Trailing Stop unidirectionnels, avec un seuil minimum anti-spam broker.
"""
import MetaTrader5 as mt5
from config import settings

class TradeManager:
    def __init__(self):
        # Conversion des points config en valeur réelle (ex: 300 points = 300 * Point)
        # Mais ici on garde les int pour la comparaison
        self.be_trigger_points = settings.BE_TRIGGER     
        self.trailing_dist_points = settings.TRAILING_DIST 

    def place_trade(self, symbol, decision, lot, sl_dist_price):
        """
        Exécute l'ordre. 
        Note : sl_dist_price est une distance en PRIX (ex: 0.00200), pas en points.
        """
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        
        # Détection Ask/Bid
        action = decision['decision']
        price = tick.ask if action == "BUY" else tick.bid
        
        # Calcul SL / TP (Basé sur le prix)
        if action == "BUY":
            sl_price = price - sl_dist_price
            tp_price = price + (sl_dist_price * 3) # Ratio 1:3
            order_type = mt5.ORDER_TYPE_BUY
        else:
            sl_price = price + sl_dist_price
            tp_price = price - (sl_dist_price * 3)
            order_type = mt5.ORDER_TYPE_SELL

        # Détection Filling Mode
        symbol_info = mt5.symbol_info(symbol)
        filling = mt5.ORDER_FILLING_FOK
        if symbol_info.filling_mode & 2: filling = mt5.ORDER_FILLING_IOC
        elif symbol_info.filling_mode & 1: filling = mt5.ORDER_FILLING_FOK

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": price,
            "sl": float(f"{sl_price:.5f}"),
            "tp": float(f"{tp_price:.5f}"),
            "magic": 777888,
            "comment": "Gemini V13",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Erreur Ordre {symbol}: {result.comment}")
            return False
        else:
            print(f"✅ EXÉCUTION RÉUSSIE ! Ticket: {result.order}")
            return True


    #     for pos in positions:
    #         # Sécurité : On ne touche qu'aux positions de notre bot
    #         if pos.symbol not in settings.SYMBOLS: continue
            
    #         symbol = pos.symbol
    #         symbol_info = mt5.symbol_info(symbol)
    #         if not symbol_info: continue
            
    #         point = symbol_info.point
    #         tick = mt5.symbol_info_tick(symbol)
    #         if not tick: continue

    #         # Prix actuel
    #         current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    #         open_price = pos.price_open
    #         current_sl = pos.sl

    #         # Calcul du Profit en POINTS (entiers)
    #         if pos.type == mt5.ORDER_TYPE_BUY:
    #             diff = current_price - open_price
    #         else:
    #             diff = open_price - current_price
            
    #         profit_points = int(diff / point)


    #         # --- LOGIQUE 1 : BREAK EVEN (Sécurisation) ---
    #         # Si on gagne +300 points (30 pips), on met le SL à +10 points
    #         if profit_points >= self.be_trigger_points:
    #             be_price = 0.0
                
    #             if pos.type == mt5.ORDER_TYPE_BUY:
    #                 be_target = open_price + (10 * point)
    #                 # On update SEULEMENT si le SL actuel est inférieur à la cible
    #                 if current_sl < be_target: 
    #                     request["sl"] = float(f"{be_target:.5f}")
    #                     should_update = True
    #                     print(f"🔒 {symbol}: BREAK EVEN ACTIVÉ (Sécurisé à {be_target:.5f})")
                
    #             else: # SELL
    #                 be_target = open_price - (10 * point)
    #                 # On update SEULEMENT si le SL est au dessus (ou à 0)
    #                 if current_sl > be_target or current_sl == 0:
    #                     request["sl"] = float(f"{be_target:.5f}")
    #                     should_update = True
    #                     print(f"🔒 {symbol}: BREAK EVEN ACTIVÉ (Sécurisé à {be_target:.5f})")

    #         # --- LOGIQUE 2 : TRAILING STOP (Suivi dynamique) ---
    #         # Si on est très haut, le SL suit le prix
    #         # Ex: Si prix monte, SL monte aussi en gardant 300 points d'écart
    #         if profit_points > (self.be_trigger_points + 200): 
                
                
    #         # Envoi à MT5
    #         if should_update:
    #             res = mt5.order_send(request)
    #             if res.retcode != mt5.TRADE_RETCODE_DONE:
    #                 print(f"⚠️ Echec Update SL {symbol}: {res.comment}")


    def manage_existing_positions(self):
        positions = mt5.positions_get()
        if not positions: return

        for pos in positions:
            if pos.symbol not in settings.SYMBOLS: continue
            
            symbol = pos.symbol
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info: continue
            
            point = symbol_info.point
            tick = mt5.symbol_info_tick(symbol)
            if not tick: continue

            current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            open_price = pos.price_open
            current_sl = pos.sl

            # Calcul Profit
            if pos.type == mt5.ORDER_TYPE_BUY:
                diff = current_price - open_price
            else:
                diff = open_price - current_price
            
            profit_points = int(diff / point)

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": symbol,
                "sl": current_sl,
                "tp": pos.tp
            }
            should_update = False
            
            # Seuil minimum de modification (Anti-Spam Broker)
            # On ne bouge le SL que si l'écart est > 10 points (1 pip)
            min_step = 10 * point

            # 1. BREAK EVEN
            if profit_points >= self.be_trigger_points:
                be_price = 0.0
                if pos.type == mt5.ORDER_TYPE_BUY:
                    be_target = open_price + (10 * point)
                    # On vérifie si on est déjà à BE (à un chouïa près)
                    if current_sl < (be_target - min_step): 
                        request["sl"] = float(f"{be_target:.5f}")
                        should_update = True
                        print(f"🔒 {symbol}: BREAK EVEN ACTIVÉ")
                else: # SELL
                    be_target = open_price - (10 * point)
                    if current_sl > (be_target + min_step) or current_sl == 0:
                        request["sl"] = float(f"{be_target:.5f}")
                        should_update = True
                        print(f"🔒 {symbol}: BREAK EVEN ACTIVÉ")

            # 2. TRAILING STOP
            if profit_points > (self.be_trigger_points + 200):
                if pos.type == mt5.ORDER_TYPE_BUY:
                    new_sl = current_price - (self.trailing_dist_points * point)
                    # On ne bouge que si le gain est significatif (> min_step)
                    if new_sl > (current_sl + min_step):
                        request["sl"] = float(f"{new_sl:.5f}")
                        should_update = True
                        print(f"🚀 {symbol}: Trailing Stop monté à {new_sl:.5f}")
                else: # SELL
                    new_sl = current_price + (self.trailing_dist_points * point)
                    # On ne bouge que si le gain est significatif (> min_step)
                    if new_sl < (current_sl - min_step) or current_sl == 0:
                        request["sl"] = float(f"{new_sl:.5f}")
                        should_update = True
                        print(f"🚀 {symbol}: Trailing Stop descendu à {new_sl:.5f}")

            if should_update:
                res = mt5.order_send(request)
                if res.retcode != mt5.TRADE_RETCODE_DONE:
                    # On n'affiche l'erreur que si ce n'est pas une erreur "No changes"
                    if res.retcode != 10025: 
                        print(f"⚠️ Erreur SL {symbol}: {res.comment}")