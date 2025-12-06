# import MetaTrader5 as mt5
# from config import settings

# class TradeManager:
#     def __init__(self, connector):
#         self.mt5 = connector

#     def manage_positions(self):
#         """
#         Boucle sur toutes les positions ouvertes pour gérer SL/TP.
#         """
#         positions = mt5.positions_get()
#         if not positions: return

#         for pos in positions:
#             # On ne touche qu'aux symboles de notre liste
#             if pos.symbol not in settings.SYMBOLS: continue

#             symbol = pos.symbol
#             tick = mt5.symbol_info_tick(symbol)
#             point = mt5.symbol_info(symbol).point
            
#             current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            
#             # Conversion des paramètres (Points -> Prix)
#             be_trigger_points = settings.BE_TRIGGER * point
#             trailing_step_points = settings.TRAILING_DIST * point
            
#             # --- LOGIQUE BUY ---
#             if pos.type == mt5.ORDER_TYPE_BUY:
#                 profit_dist = current_price - pos.price_open
                
#                 # 1. Break Even (Sécurisation)
#                 # Si on gagne X points et que le SL est encore en dessous du prix d'entrée
#                 if profit_dist > be_trigger_points and pos.sl < pos.price_open:
#                     new_sl = pos.price_open + (10 * point) # On sécurise un tout petit profit
#                     self.mt5.modify_position(pos.ticket, new_sl, pos.tp)
#                     print(f"🛡️ BREAK-EVEN activé sur {symbol} (Ticket {pos.ticket})")

#                 # 2. Trailing Stop (Suivi)
#                 # Si le prix monte, on remonte le SL
#                 proposed_sl = current_price - trailing_step_points
#                 if proposed_sl > pos.sl and proposed_sl > pos.price_open:
#                     self.mt5.modify_position(pos.ticket, proposed_sl, pos.tp)
#                     print(f"🚀 TRAILING STOP remonté sur {symbol} -> {proposed_sl:.5f}")

#             # --- LOGIQUE SELL ---
#             elif pos.type == mt5.ORDER_TYPE_SELL:
#                 profit_dist = pos.price_open - current_price
                
#                 # 1. Break Even
#                 if profit_dist > be_trigger_points and (pos.sl > pos.price_open or pos.sl == 0):
#                     new_sl = pos.price_open - (10 * point)
#                     self.mt5.modify_position(pos.ticket, new_sl, pos.tp)
#                     print(f"🛡️ BREAK-EVEN activé sur {symbol} (Ticket {pos.ticket})")

#                 # 2. Trailing Stop
#                 proposed_sl = current_price + trailing_step_points
#                 if (pos.sl == 0 or proposed_sl < pos.sl) and proposed_sl < pos.price_open:
#                     self.mt5.modify_position(pos.ticket, proposed_sl, pos.tp)
#                     print(f"🚀 TRAILING STOP descendu sur {symbol} -> {proposed_sl:.5f}")





# import MetaTrader5 as mt5
# from config import settings

# class TradeManager:
#     def __init__(self):
#         self.be_trigger = settings.BE_TRIGGER     # Ex: 300 points (30 pips)
#         self.trailing_dist = settings.TRAILING_DIST # Ex: 300 points

#     def place_trade(self, symbol, action, lot, sl_points):
#         """Exécute l'ordre initial calculé par le Stratège"""
        
#         # Récupération prix actuel
#         tick = mt5.symbol_info_tick(symbol)
#         if not tick: return
        
#         price = tick.ask if action == "BUY" else tick.bid
#         point = mt5.symbol_info(symbol).point
        
#         # Calcul SL / TP Physique
#         # TP par défaut assez loin (Ratio 1:3), le trailing fera le reste
#         if action == "BUY":
#             sl_price = price - (sl_points * point)
#             tp_price = price + (sl_points * 3 * point)
#             order_type = mt5.ORDER_TYPE_BUY
#         else:
#             sl_price = price + (sl_points * point)
#             tp_price = price - (sl_points * 3 * point)
#             order_type = mt5.ORDER_TYPE_SELL

#         request = {
#             "action": mt5.TRADE_ACTION_DEAL,
#             "symbol": symbol,
#             "volume": lot,
#             "type": order_type,
#             "price": price,
#             "sl": float(f"{sl_price:.5f}"),
#             "tp": float(f"{tp_price:.5f}"),
#             "deviation": 20,
#             "magic": 123456,
#             "comment": "GEMINI GOLD EYE",
#             "type_time": mt5.ORDER_TIME_GTC,
#             "type_filling": mt5.ORDER_FILLING_IOC,
#         }

#         result = mt5.order_send(request)
#         if result.retcode != mt5.TRADE_RETCODE_DONE:
#             print(f"❌ Erreur Ordre {symbol}: {result.comment}")
#         else:
#             print(f"✅ EXÉCUTION RÉUSSIE ! Ticket: {result.order}")

#     def manage_existing_positions(self):
#         """
#         Tourne en boucle pour gérer : Break Even & Trailing Stop.
#         """
#         positions = mt5.positions_get()
#         if not positions: return

#         for pos in positions:
#             # On ne gère que les positions de notre bot (Magic Number ou Symbole)
#             if pos.symbol not in settings.SYMBOLS: continue
            
#             symbol = pos.symbol
#             point = mt5.symbol_info(symbol).point
#             tick = mt5.symbol_info_tick(symbol)
#             if not tick: continue

#             # Données variables
#             current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
#             open_price = pos.price_open
#             current_sl = pos.sl

#             # --- CALCUL DU PROFIT EN POINTS ---
#             if pos.type == mt5.ORDER_TYPE_BUY:
#                 profit_points = (current_price - open_price) / point
#             else:
#                 profit_points = (open_price - current_price) / point

#             request = {
#                 "action": mt5.TRADE_ACTION_SLTP,
#                 "position": pos.ticket,
#                 "symbol": symbol,
#                 "sl": current_sl,
#                 "tp": pos.tp
#             }
#             should_update = False

#             # 1. BREAK EVEN (Sécurisation)
#             # Si le profit dépasse le seuil (ex: 300 pts) et qu'on n'est pas encore sécurisé
#             if profit_points >= self.be_trigger:
#                 be_price = 0.0
#                 if pos.type == mt5.ORDER_TYPE_BUY:
#                     # On met le SL à l'entrée + 10 points (pour couvrir les frais)
#                     be_price = open_price + (10 * point)
#                     if current_sl < be_price: # Si le SL est encore en perte
#                         request["sl"] = float(f"{be_price:.5f}")
#                         should_update = True
#                         print(f"🔒 {symbol}: BREAK EVEN ACTIVÉ (Sécurisé à {be_price})")
#                 else: # SELL
#                     be_price = open_price - (10 * point)
#                     if current_sl > be_price or current_sl == 0:
#                         request["sl"] = float(f"{be_price:.5f}")
#                         should_update = True
#                         print(f"🔒 {symbol}: BREAK EVEN ACTIVÉ (Sécurisé à {be_price})")

#             # 2. TRAILING STOP (Mode Swing)
#             # Si le profit explose, on suit le prix
#             if profit_points > (self.be_trigger + 200): # Ex: Profit > 500 points
#                 if pos.type == mt5.ORDER_TYPE_BUY:
#                     new_sl = current_price - (self.trailing_dist * point)
#                     if new_sl > current_sl: # On ne fait que monter le SL
#                         request["sl"] = float(f"{new_sl:.5f}")
#                         should_update = True
#                         print(f"🚀 {symbol}: Trailing Stop monté à {new_sl}")
#                 else: # SELL
#                     new_sl = current_price + (self.trailing_dist * point)
#                     if new_sl < current_sl or current_sl == 0: # On ne fait que descendre
#                         request["sl"] = float(f"{new_sl:.5f}")
#                         should_update = True
#                         print(f"🚀 {symbol}: Trailing Stop descendu à {new_sl}")

#             # Envoi de la modification
#             if should_update:
#                 res = mt5.order_send(request)
#                 if res.retcode != mt5.TRADE_RETCODE_DONE:
#                     print(f"❌ Erreur Update SL {symbol}: {res.comment}")











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

    # def manage_existing_positions(self):
    #     """
    #     SECURISEUR DE GAINS : 
    #     Cette fonction doit être appelée très souvent (toutes les secondes).
    #     Elle ne coûte rien (pas d'API IA) car elle interroge juste MT5 localement.
    #     """
    #     positions = mt5.positions_get()
    #     if not positions: return

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

    #         # Préparation Requête
    #         request = {
    #             "action": mt5.TRADE_ACTION_SLTP,
    #             "position": pos.ticket,
    #             "symbol": symbol,
    #             "sl": current_sl,
    #             "tp": pos.tp
    #         }
    #         should_update = False

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
                
    #             if pos.type == mt5.ORDER_TYPE_BUY:
    #                 # SL cible = Prix actuel - Distance Trailing
    #                 new_sl = current_price - (self.trailing_dist_points * point)
    #                 # On ne déplace le SL que vers le HAUT (jamais redescendre)
    #                 if new_sl > current_sl:
    #                     request["sl"] = float(f"{new_sl:.5f}")
    #                     should_update = True
    #                     print(f"🚀 {symbol}: Trailing Stop remonté à {new_sl:.5f}")
                
    #             else: # SELL
    #                 # SL cible = Prix actuel + Distance Trailing
    #                 new_sl = current_price + (self.trailing_dist_points * point)
    #                 # On ne déplace le SL que vers le BAS
    #                 if new_sl < current_sl or current_sl == 0:
    #                     request["sl"] = float(f"{new_sl:.5f}")
    #                     should_update = True
    #                     print(f"🚀 {symbol}: Trailing Stop descendu à {new_sl:.5f}")

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