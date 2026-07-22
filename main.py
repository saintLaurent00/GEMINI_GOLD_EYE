# import time
# import MetaTrader5 as mt5
# from datetime import datetime

# from infrastructure.mt5_connector import MT5Connector
# from core.strategy import GeminiStrategy
# from core.risk_manager import RiskManager
# from core.executor import TradeExecutor
# from core.logger import TradeLogger # <--- NOUVEAU LOGGER

# def run_bot():
#     print("\n💎 --- GEMINI GOLD EYE : DÉMARRAGE --- 💎")
    
#     mt5_app = MT5Connector()
#     if not mt5_app.start(): return

#     brain = GeminiStrategy()
#     risk = RiskManager()
#     executor = TradeExecutor()
#     logger = TradeLogger() # <--- Initialisation Excel

#     try:
#         while True:
#             print(f"\n⏳ --- CYCLE DE SCAN ({datetime.now().strftime('%H:%M')}) ---")
            
#             from config import settings
#             for symbol in settings.SYMBOLS:
                
#                 # 1. Check Santé Marché
#                 if not risk.check_execution_criteria(symbol): continue

#                 # 2. Analyse Cerveau
#                 decision = brain.analyze_symbol(symbol)
                
#                 # 3. Décision
#                 if decision and decision.get('decision') in ["BUY", "SELL"]:
#                     verdict = decision['decision']
#                     conf = int(decision.get('confidence', 0))
                    
#                     if conf >= 75:
#                         # --- MONEY MANAGEMENT ---
#                         atr = decision.get('atr_value', 0.0020)
#                         sl_mult = decision.get('sl_atr_multiplier', 2.0)
#                         rr_ratio = decision.get('risk_reward_ratio', 3.0)
                        
#                         sl_points = atr * sl_mult
#                         tp_points = sl_points * rr_ratio # TP dynamique basé sur l'IA
                        
#                         lot = risk.calculate_lot_size(symbol, sl_points)
                        
#                         # --- PRIX ---
#                         tick = mt5.symbol_info_tick(symbol)
#                         price = tick.ask if verdict == "BUY" else tick.bid
                        
#                         if verdict == "BUY":
#                             sl = price - sl_points
#                             tp = price + tp_points
#                             otype = mt5.ORDER_TYPE_BUY
#                         else:
#                             sl = price + sl_points
#                             tp = price - tp_points
#                             otype = mt5.ORDER_TYPE_SELL

#                         print(f"💰 ORDRE : {verdict} {symbol} | Lot {lot} | SL {sl:.5f}")
                        
#                         # --- EXÉCUTION ---
#                         success = executor.execute_order(symbol, otype, lot, sl, tp, f"Gemini {conf}%")
                        
#                         # --- LOGGING EXCEL & ARCHIVAGE ---
#                         status = {"executed": success, "confidence": conf}
#                         logger.log_trade(
#                             symbol=symbol,
#                             decision=verdict,
#                             entry=price,
#                             sl=sl,
#                             tp=tp,
#                             lot=lot,
#                             status=status,
#                             reason=decision.get('reason'),
#                             image_sources=decision.get('image_paths', []) # On passe les images pour archivage
#                         )
                        
#                     else:
#                         print(f"⏸️ Confiance faible ({conf}%)")
                
#                 time.sleep(2)

#             print("💤 Pause du cycle...")
#             time.sleep(60)

#     except KeyboardInterrupt:
#         print("\n🛑 Arrêt manuel.")
#     finally:
#         mt5_app.shutdown()

# if __name__ == "__main__":
#     run_bot()





















# import time
# import MetaTrader5 as mt5
# from config import settings
# from infrastructure.mt5_connector import MT5Connector
# from core.strategy import GeminiStrategy
# from core.risk_manager import RiskManager
# import datetime

# def main():
#     print("💎 --- GEMINI GOLD EYE : DÉMARRAGE --- 💎")
    
#     # 1. Connexion MT5
#     connector = MT5Connector()
#     if not connector.start():
#         return

#     # 2. Initialisation des Modules
#     brain = GeminiStrategy()
#     risk_manager = RiskManager()

#     while True:
#         try:
#             print(f"\n⏳ --- CYCLE DE SCAN ({datetime.datetime.now().strftime('%H:%M')}) ---")
            
#             # --- SCAN DES NOUVELLES OPPORTUNITÉS ---
#             for symbol in settings.SYMBOLS:
                
#                 # 1. FILTRE DE POSITION (Anti-Mitraillette)
#                 if not risk_manager.check_existing_positions(symbol):
#                     continue

#                 # 2. FILTRE DE MARCHÉ
#                 if not risk_manager.check_execution_criteria(symbol):
#                     continue

#                 # 3. ANALYSE IA
#                 decision = brain.analyze_symbol(symbol)
                
#                 # 4. EXÉCUTION
#                 if decision and decision['decision'] in ["BUY", "SELL"]:
#                     if decision.get('confidence', 0) >= 75:
                        
#                         # --- CORRECTION 1 : FILLING MODE (Valeurs Numériques) ---
#                         symbol_info = mt5.symbol_info(symbol)
#                         if symbol_info is None: continue

#                         # Par défaut, on tente FOK (Fill or Kill) -> Valeur 0
#                         filling_type = mt5.ORDER_FILLING_FOK 
                        
#                         # On vérifie les "Capabilities" du symbole via les bits
#                         # Bit 1 (valeur 2) = IOC supporté
#                         # Bit 0 (valeur 1) = FOK supporté
                        
#                         if (symbol_info.filling_mode & 2): 
#                             filling_type = mt5.ORDER_FILLING_IOC
#                         elif (symbol_info.filling_mode & 1):
#                             filling_type = mt5.ORDER_FILLING_FOK
                        
#                         # --- CALCULS ---
#                         atr = decision.get("atr_value", 0.0020)
#                         multiplier = decision.get("sl_atr_multiplier", 2.0)
#                         sl_points = atr * multiplier
                        
#                         lot = risk_manager.calculate_lot_size(symbol, sl_points)
                        
#                         # --- CORRECTION 2 : SÉCURITÉ LOT MAX ---
#                         if lot > 10.0:
#                             print(f"⚠️ SÉCURITÉ : Lot {lot} réduit à 10.0 max.")
#                             lot = 10.0
                        
#                         # Prix
#                         tick = mt5.symbol_info_tick(symbol)
#                         price = tick.ask if decision['decision'] == "BUY" else tick.bid
                        
#                         if decision['decision'] == "BUY":
#                             sl_price = price - sl_points
#                             tp_price = price + (sl_points * 3)
#                             order_type = mt5.ORDER_TYPE_BUY
#                         else:
#                             sl_price = price + sl_points
#                             tp_price = price - (sl_points * 3)
#                             order_type = mt5.ORDER_TYPE_SELL

#                         print(f"💰 ORDRE : {decision['decision']} {symbol} | Lot {lot} | SL {sl_price:.5f}")
                        
#                         # Envoi Ordre
#                         request = {
#                             "action": mt5.TRADE_ACTION_DEAL,
#                             "symbol": symbol,
#                             "volume": lot,
#                             "type": order_type,
#                             "price": price,
#                             "sl": sl_price,
#                             "tp": tp_price,
#                             "magic": 123456,
#                             "comment": "Gemini Gold Eye",
#                             "type_time": mt5.ORDER_TIME_GTC,
#                             "type_filling": filling_type, # Utilisation du mode détecté
#                         }
                        
#                         res = mt5.order_send(request)
                        
#                         if res.retcode == mt5.TRADE_RETCODE_DONE:
#                             print(f"✅ EXÉCUTION RÉUSSIE ! Ticket: {res.order}")
#                         else:
#                             print(f"❌ Erreur Ordre: {res.comment} (Code: {res.retcode})")
#                     else:
#                         print(f"✋ Confiance trop faible ({decision.get('confidence')}%)")
            
#             print("💤 Pause du cycle (5 min)...")
#             time.sleep(300)

#         except KeyboardInterrupt:
#             print("\n🛑 Arrêt manuel du bot.")
#             break
#         except Exception as e:
#             print(f"❌ Erreur boucle principale : {e}")
#             time.sleep(10)

#     connector.shutdown()

# if __name__ == "__main__":
#     main()





# import time
# import datetime
# import MetaTrader5 as mt5
# from config import settings
# from infrastructure.mt5_connector import MT5Connector
# from core.strategy import GeminiStrategy
# from core.risk_manager import RiskManager

# # --- FONCTION UTILITAIRE ---
# def has_open_position(symbol):
#     """Vérifie si une position est déjà ouverte sur ce symbole."""
#     positions = mt5.positions_get(symbol=symbol)
#     if positions is None: return False
#     return len(positions) > 0

# def main():
#     print("💎 --- GEMINI GOLD EYE V13 : DÉMARRAGE --- 💎")
#     print(f"🌍 Serveur: {settings.MT5_SERVER} | Risque: {settings.RISK_PER_TRADE}%")
    
#     # 1. CONNEXION INFRASTRUCTURE
#     connector = MT5Connector()
#     if not connector.start():
#         print("❌ Impossible de démarrer. Vérifiez MT5.")
#         return

#     # 2. CHARGEMENT DES CERVEAUX
#     brain = GeminiStrategy()
#     risk_manager = RiskManager()

#     print("🤖 Le système est en ligne. En attente du cycle...")

#     # BOUCLE INFINIE
#     while True:
#         try:
#             now = datetime.datetime.now().strftime('%H:%M:%S')
#             print(f"\n⏳ --- CYCLE DE SCAN ({now}) ---")
            
#             for symbol in settings.SYMBOLS:
                
#                 # A. FILTRE ANTI-MITRAILETTE (Une seule position par paire)
#                 if has_open_position(symbol):
#                     print(f"🔒 Position existante sur {symbol}. On passe.")
#                     continue

#                 # B. FILTRE TECHNIQUE (Marché ouvert, Spread...)
#                 if not risk_manager.check_execution_criteria(symbol):
#                     continue

#                 # C. ANALYSE IA (Cœur V13)
#                 # C'est ici que l'IA checke le Spread, le Range, la Structure, etc.
#                 decision = brain.analyze_symbol(symbol)
                
#                 # Si l'IA renvoie None (Erreur technique), on passe
#                 if not decision: continue

#                 # D. EXÉCUTION
#                 if decision['decision'] in ["BUY", "SELL"]:
                    
#                     # Filtre de Confiance
#                     confidence = decision.get('confidence', 0)
#                     if confidence >= 75:
                        
#                         print(f"🚀 SIGNAL VALIDÉ sur {symbol} ({confidence}%)")

#                         # --- PRÉPARATION DE L'ORDRE (MODE PRÉCISION) ---
                        
#                         # 1. Récupération Tick Frais (Milliseconde près)
#                         tick = mt5.symbol_info_tick(symbol)
#                         if tick is None: continue
                        
#                         entry_price = tick.ask if decision['decision'] == "BUY" else tick.bid
                        
#                         # 2. Calcul du Stop Loss via ATR (Fourni par le Bulletin Tactique)
#                         # L'IA nous renvoie l'ATR qu'elle a vu, ou on prend une sécurité
#                         atr = decision.get("atr_value", 0.0020) 
#                         multiplier = decision.get("sl_atr_multiplier", 2.0)
                        
#                         sl_dist = atr * multiplier
                        
#                         # 3. Calcul du Lot (Money Management Rigoureux)
#                         lot = risk_manager.calculate_lot_size(symbol, sl_dist)
                        
#                         # Sécurité Lot Max (Anti-Gros Doigt)
#                         if lot > 5.0: lot = 5.0 

#                         # 4. Calcul SL / TP
#                         if decision['decision'] == "BUY":
#                             sl_price = entry_price - sl_dist
#                             # Ratio 1:3 par défaut pour viser le Swing
#                             tp_price = entry_price + (sl_dist * 3) 
#                             order_type = mt5.ORDER_TYPE_BUY
#                         else:
#                             sl_price = entry_price + sl_dist
#                             tp_price = entry_price - (sl_dist * 3)
#                             order_type = mt5.ORDER_TYPE_SELL

#                         print(f"📐 CALIBRAGE : Lot {lot} | SL {sl_price:.5f} | ATR {atr:.5f}")

#                         # 5. Détection du Filling Mode (Compatibilité Courtier)
#                         symbol_info = mt5.symbol_info(symbol)
#                         filling = mt5.ORDER_FILLING_FOK # Par défaut
#                         if symbol_info.filling_mode & 2: filling = mt5.ORDER_FILLING_IOC
#                         elif symbol_info.filling_mode & 1: filling = mt5.ORDER_FILLING_FOK

#                         # 6. ENVOI DE L'ORDRE
#                         request = {
#                             "action": mt5.TRADE_ACTION_DEAL,
#                             "symbol": symbol,
#                             "volume": lot,
#                             "type": order_type,
#                             "price": entry_price,
#                             "sl": sl_price,
#                             "tp": tp_price,
#                             "magic": 777888, # Magic Number "Gold Eye"
#                             "comment": "Gemini V13",
#                             "type_time": mt5.ORDER_TIME_GTC,
#                             "type_filling": filling,
#                         }
                        
#                         result = mt5.order_send(request)
                        
#                         if result.retcode == mt5.TRADE_RETCODE_DONE:
#                             print(f"✅ EXÉCUTION CONFIRMÉE ! Ticket: {result.order}")
#                             # Petit son de victoire (Windows seulement)
#                             print("\a") 
#                         else:
#                             print(f"❌ ECHEC ORDRE: {result.comment} (Code: {result.retcode})")
                    
#                     else:
#                         print(f"✋ Ignoré : Confiance trop faible ({confidence}% < 75%)")
                
#                 else:
#                     # Si WAIT
#                     print(f"⏸️ Standby : {decision.get('reason', 'Pas de signal')}")

#             # E. PAUSE DU CYCLE
#             # On attend 5 minutes avant le prochain scan pour laisser respirer l'API
#             print("💤 Mise en veille (5 min)...")
#             time.sleep(300)

#         except KeyboardInterrupt:
#             print("\n🛑 ARRÊT D'URGENCE DEMANDÉ.")
#             break
#         except Exception as e:
#             print(f"❌ ERREUR CRITIQUE DANS LA BOUCLE : {e}")
#             time.sleep(10) # Pause de sécurité en cas de crash

#     connector.shutdown()
#     print("👋 Au revoir.")

# if __name__ == "__main__":
#     main()







# import time
# import datetime
# import MetaTrader5 as mt5
# from config import settings
# from infrastructure.mt5_connector import MT5Connector
# from core.strategy import GeminiStrategy
# from core.risk_manager import RiskManager
# from core.trade_manager import TradeManager # <--- Nouveau Module

# def has_open_position(symbol):
#     """Vérifie si une position est déjà ouverte sur ce symbole."""
#     positions = mt5.positions_get(symbol=symbol)
#     if positions is None: return False
#     return len(positions) > 0

# def main():
#     print("💎 --- GEMINI GOLD EYE V13 : DÉMARRAGE --- 💎")
    
#     # 1. CONNEXION
#     connector = MT5Connector()
#     if not connector.start():
#         return

#     # 2. CHARGEMENT MODULES
#     brain = GeminiStrategy()
#     risk_manager = RiskManager()
#     trade_manager = TradeManager() # Le Sécuriseur

#     # --- CONFIGURATION DU TIMER ---
#     # Fréquence de l'IA (en secondes). 
#     # Pour H4, on peut scanner toutes les 5 min (300s) ou 15 min (900s) pour voir si la bougie est close.
#     AI_SCAN_INTERVAL = 300 
#     last_ai_scan = 0 

#     print("🤖 Le système est en ligne. Boucle de gestion active.")

#     # BOUCLE PRINCIPALE (NON-BLOQUANTE)
#     while True:
#         try:
#             # ==========================================
#             # TÂCHE 1 : GESTION DES POSITIONS (Haute Fréquence)
#             # ==========================================
#             # S'exécute à chaque tour de boucle (quasi temps réel)
#             trade_manager.manage_existing_positions()


#             # ==========================================
#             # TÂCHE 2 : ANALYSE IA (Basse Fréquence)
#             # ==========================================
#             # On vérifie si le temps est écoulé depuis le dernier scan
#             if time.time() - last_ai_scan > AI_SCAN_INTERVAL:
                
#                 now = datetime.datetime.now().strftime('%H:%M')
#                 print(f"\n🔎 --- SCAN IA ({now}) ---")

#                 for symbol in settings.SYMBOLS:
                    
#                     # Filtres préliminaires pour ne pas déranger l'IA pour rien
#                     if has_open_position(symbol):
#                         print(f"🔒 Position en cours sur {symbol}. Sécurisation active.")
#                         continue

#                     if not risk_manager.check_execution_criteria(symbol):
#                         continue

#                     # Appel IA
#                     decision = brain.analyze_symbol(symbol)
                    
#                     if not decision: continue

#                     # Exécution
#                     if decision['decision'] in ["BUY", "SELL"]:
#                         if decision.get('confidence', 0) >= 75:
                            
#                             # Récupération ATR
#                             atr = decision.get("atr_value", 0.0020)
#                             multiplier = decision.get("sl_atr_multiplier", 2.0)
#                             sl_dist = atr * multiplier
                            
#                             # Calcul Lot
#                             lot = risk_manager.calculate_lot_size(symbol, sl_dist)
#                             if lot > 5.0: lot = 5.0
                            
#                             # Appel au Trade Manager pour placer l'ordre
#                             trade_manager.place_trade(symbol, decision, lot, sl_dist)
#                         else:
#                             print(f"✋ Confiance faible ({decision.get('confidence')}%)")
                
#                 # Mise à jour du timer
#                 last_ai_scan = time.time()
#                 print(f"💤 Fin du scan IA. Prochain dans {AI_SCAN_INTERVAL}s. Sécurisation continue...")

            
#             # ==========================================
#             # PAUSE COURTE (CPU SAVER)
#             # ==========================================
#             # On dort juste 1 seconde pour ne pas surchauffer le processeur
#             # Mais c'est assez rapide pour gérer le Trailing Stop
#             time.sleep(1)

#         except KeyboardInterrupt:
#             print("\n🛑 ARRÊT MANUEL.")
#             break
#         except Exception as e:
#             print(f"❌ ERREUR BOUCLE : {e}")
#             time.sleep(5)

#     connector.shutdown()

# if __name__ == "__main__":
#     main()







# import time
# import datetime
# import MetaTrader5 as mt5
# from config import settings
# from infrastructure.mt5_connector import MT5Connector
# from data_processor.indicators import TacticalCalculator # Pour l'ATR frais
# from core.strategy import GeminiStrategy
# from core.risk_manager import RiskManager
# from core.trade_manager import TradeManager

# # --- CONFIGURATION HORAIRE PROP FIRM (GMT/Abidjan) ---
# # Le bot ne prend des NOUVEAUX trades qu'entre ces heures.
# # 08h00 : Ouverture Londres (Liquidité max)
# # 20h00 : Clôture New York (On arrête avant les spreads de nuit)
# TRADING_START_HOUR = 8   
# TRADING_END_HOUR = 20    

# def is_trading_hours():
#     """
#     Vérifie si on est dans la fenêtre de tir (Heure UTC/GMT).
#     Comme la Côte d'Ivoire est GMT+0, cela correspond à ton heure locale.
#     """
#     current_hour = datetime.datetime.now(datetime.timezone.utc).hour
#     is_open = TRADING_START_HOUR <= current_hour < TRADING_END_HOUR
    
#     # Petit log toutes les 5 minutes si le marché est fermé pour rassurer l'utilisateur
#     if not is_open and int(time.time()) % 300 == 0:
#         print(f"💤 Marché OFF (Heure: {current_hour}h). Gestion positions active, mais pas de nouveaux trades.")
            
#     return is_open

# def has_open_position(symbol):
#     """Vérifie si une position est déjà ouverte sur ce symbole pour éviter le stacking."""
#     positions = mt5.positions_get(symbol=symbol)
#     if positions is None: return False
#     return len(positions) > 0

# def get_last_candle_time(symbol, timeframe):
#     """Récupère l'heure d'ouverture de la bougie actuelle pour détecter la clôture."""
#     rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
#     if rates is None or len(rates) == 0: return 0
#     return int(rates[0]['time'])

# def main():
#     print("💎 --- GEMINI GOLD EYE V13 : PROP FIRM KILLER --- 💎")
#     print(f"🌍 Zone : Côte d'Ivoire (GMT+0)")
#     print(f"⏰ Chasse : {TRADING_START_HOUR}h00 - {TRADING_END_HOUR}h00")
    
#     # 1. CONNEXION INFRASTRUCTURE
#     connector = MT5Connector()
#     if not connector.start():
#         return

#     # 2. CHARGEMENT DES CERVEAUX
#     brain = GeminiStrategy()
#     risk_manager = RiskManager()
#     trade_manager = TradeManager() # Le Berger (Trailing/BE)

#     # 3. MÉMOIRE DES BOUGIES (Sync H4)
#     # On stocke l'heure de la dernière bougie connue pour ne pas analyser 2 fois la même
#     last_candle_memory = {}
    
#     # Initialisation
#     print("⏳ Synchronisation des bougies H4...")
#     for sym in settings.SYMBOLS:
#         last_candle_memory[sym] = get_last_candle_time(sym, settings.TIMEFRAME_TRIGGER)

#     print("🤖 SYSTÈME ARMÉ ET PRÊT.")

#     # BOUCLE PRINCIPALE INFINIE
#     while True:
#         try:
#             # ==========================================
#             # TÂCHE 1 : GESTION DES POSITIONS (Priorité Absolue)
#             # ==========================================
#             # S'exécute à chaque seconde. C'est ici que le Trailing Stop et le BE travaillent.
#             # Même la nuit, on gère les trades ouverts.
#             trade_manager.manage_existing_positions()

#             # ==========================================
#             # TÂCHE 2 : ANALYSE IA (Conditionnelle)
#             # ==========================================
            
#             # On ne scanne pour de nouvelles opportunités que si c'est l'heure
#             if is_trading_hours():
                
#                 for symbol in settings.SYMBOLS:
#                     # A. Détection Nouvelle Bougie H4
#                     # On compare l'heure de la bougie actuelle avec celle en mémoire
#                     current_candle_time = get_last_candle_time(symbol, settings.TIMEFRAME_TRIGGER)
                    
#                     if current_candle_time != last_candle_memory.get(symbol, 0):
                        
#                         now_str = datetime.datetime.now().strftime('%H:%M')
#                         print(f"\n🕯️ NOUVELLE BOUGIE H4 sur {symbol} à {now_str}")
                        
#                         # Mise à jour mémoire immédiate
#                         last_candle_memory[symbol] = current_candle_time

#                         # B. Filtres de Sécurité (Prop Firm Rules)
#                         if has_open_position(symbol):
#                             print(f"🔒 Position déjà en cours. On laisse le Trade Manager gérer.")
#                             continue

#                         if not risk_manager.check_execution_criteria(symbol):
#                             print(f"⛔ Critères exécution non remplis (Spread/Marge).")
#                             continue

#                         # C. Appel à l'Intelligence Artificielle
#                         decision = brain.analyze_symbol(symbol)
                        
#                         # D. Exécution de la Décision
#                         if decision and decision['decision'] in ["BUY", "SELL"]:
#                             confidence = decision.get('confidence', 0)
                            
#                             # Seuil de confiance élevé pour Prop Firm
#                             if confidence >= 75:
#                                 print(f"✅ SIGNAL VALIDÉ ({confidence}%) -> PRÉPARATION...")
                                
#                                 # E. Recalcul Mathématique (Double Check)
#                                 # On récupère l'ATR frais pour le SL
#                                 calc = TacticalCalculator(symbol)
#                                 bulletin = calc.get_bulletin()
                                
#                                 if bulletin:
#                                     real_atr = bulletin.get('H1_INDICATORS', {}).get('ATR', decision.get('atr_value', 0.0010))
                                    
#                                     # Récupération du multiplicateur (défaut 2.0 pour laisser respirer)
#                                     sl_multiplier = decision.get("sl_atr_multiplier", 2.0)
                                    
#                                     # Calcul Distance SL en PRIX
#                                     sl_dist_price = real_atr * sl_multiplier
                                    
#                                     # Calcul du Lot (Risque Management Strict 1%)
#                                     lot = risk_manager.calculate_lot_size(symbol, sl_dist_price)
                                    
#                                     print(f"📐 Calibration: ATR={real_atr:.5f} | SL={sl_dist_price:.5f} | LOT={lot}")
                                    
#                                     # Tir final
#                                     trade_manager.place_trade(symbol, decision, lot, sl_dist_price)
#                                 else:
#                                     print("❌ Erreur critique : Impossible de calculer l'ATR.")
#                             else:
#                                 print(f"✋ Confiance trop faible ({confidence}%). On attend mieux.")
            
#             # ==========================================
#             # PAUSE CPU
#             # ==========================================
#             time.sleep(1)

#         except KeyboardInterrupt:
#             print("\n🛑 ARRÊT MANUEL DU BOT.")
#             break
#         except Exception as e:
#             print(f"❌ ERREUR BOUCLE PRINCIPALE : {e}")
#             time.sleep(5) # Petite pause de sécurité en cas de crash

#     connector.shutdown()

# if __name__ == "__main__":
#     main()


















import time
import datetime
import MetaTrader5 as mt5
from config import settings
from infrastructure.mt5_connector import MT5Connector
from data_processor.indicators import TacticalCalculator
from core.strategy import GeminiStrategy
from core.risk_manager import RiskManager
from core.trade_manager import TradeManager

# --- CONFIGURATION HORAIRE PROP FIRM (GMT/Abidjan) ---
TRADING_START_HOUR = 8   
TRADING_END_HOUR = 20    

def is_trading_hours():
    """Vérifie l'heure pour les NOUVEAUX trades (08h-20h)."""
    current_hour = datetime.datetime.now(datetime.timezone.utc).hour
    return TRADING_START_HOUR <= current_hour < TRADING_END_HOUR

def is_market_open_for_management():
    """
    Vérifie si le marché Forex est ouvert pour la GESTION (Trailing Stop).
    Fermé le Samedi toute la journée et le Dimanche jusqu'à 21h GMT.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    day = now.weekday() # 0=Lundi ... 5=Samedi, 6=Dimanche
    hour = now.hour

    # Si Samedi (5) : FERMÉ
    if day == 5: return False
    
    # Si Dimanche (6) et avant 22h00 GMT : FERMÉ (Pré-ouverture Asie)
    if day == 6 and hour < 22: return False
    
    # Le reste du temps (Lundi -> Vendredi soir) : OUVERT
    return True

def has_open_position(symbol):
    positions = mt5.positions_get(symbol=symbol)
    if positions is None: return False
    return len(positions) > 0

def get_last_candle_time(symbol, timeframe):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
    if rates is None or len(rates) == 0: return 0
    return int(rates[0]['time'])

def main():
    print("💎 --- GEMINI GOLD EYE V13 : PROP FIRM KILLER --- 💎")
    print(f"🌍 Zone : Côte d'Ivoire (GMT+0)")
    print(f"⏰ Chasse : {TRADING_START_HOUR}h00 - {TRADING_END_HOUR}h00")
    
    # 1. CONNEXION
    connector = MT5Connector()
    if not connector.start(): return

    # 2. MODULES
    brain = GeminiStrategy()
    risk_manager = RiskManager()
    trade_manager = TradeManager()

    # 3. INIT MÉMOIRE
    last_candle_memory = {}
    print("⏳ Synchronisation des bougies H4...")
    for sym in settings.SYMBOLS:
        last_candle_memory[sym] = get_last_candle_time(sym, settings.TIMEFRAME_TRIGGER)

    print("🤖 SYSTÈME ARMÉ.")

    # BOUCLE PRINCIPALE
    while True:
        try:
            # ==========================================
            # TÂCHE 1 : GESTION DES POSITIONS (Si Marché Ouvert)
            # ==========================================
            # On ne tente de bouger les SL que si le Forex est ouvert
            if is_market_open_for_management():
                trade_manager.manage_existing_positions()
            else:
                # Petit log discret toutes les 5 min pour dire qu'on dort
                if int(time.time()) % 300 == 0:
                    print("💤 Week-end : Marché fermé. Le Bot se repose.")

            # ==========================================
            # TÂCHE 2 : ANALYSE IA (Si Heures de Bureau)
            # ==========================================
            if is_trading_hours() and is_market_open_for_management():
                
                for symbol in settings.SYMBOLS:
                    current_candle_time = get_last_candle_time(symbol, settings.TIMEFRAME_TRIGGER)
                    
                    if current_candle_time != last_candle_memory.get(symbol, 0):
                        now_str = datetime.datetime.now().strftime('%H:%M')
                        print(f"\n🕯️ NOUVELLE BOUGIE H4 sur {symbol} à {now_str}")
                        last_candle_memory[symbol] = current_candle_time

                        if has_open_position(symbol):
                            print(f"🔒 Position en cours. Skip.")
                            continue

                        if not risk_manager.check_execution_criteria(symbol):
                            continue

                        # Appel IA
                        decision = brain.analyze_symbol(symbol)
                        
                        if decision and decision['decision'] in ["BUY", "SELL"]:
                            confidence = decision.get('confidence', 0)
                            if confidence >= 75:
                                print(f"✅ SIGNAL {confidence}% DETECTÉ...")
                                
                                # Recalcul ATR
                                calc = TacticalCalculator(symbol)
                                bulletin = calc.get_bulletin()
                                
                                if bulletin:
                                    real_atr = bulletin.get('H1_INDICATORS', {}).get('ATR', decision.get('atr_value', 0.0010))
                                    sl_multiplier = decision.get("sl_atr_multiplier", 2.0)
                                    sl_dist_price = real_atr * sl_multiplier
                                    lot = risk_manager.calculate_lot_size(symbol, sl_dist_price)
                                    
                                    print(f"📐 ATR={real_atr:.5f} | SL={sl_dist_price:.5f} | LOT={lot}")
                                    trade_manager.place_trade(symbol, decision, lot, sl_dist_price)
            
            time.sleep(1)

        except KeyboardInterrupt:
            print("\n🛑 ARRÊT MANUEL.")
            break
        except Exception as e:
            print(f"❌ ERREUR : {e}")
            time.sleep(5)

    connector.shutdown()

if __name__ == "__main__":
    main()