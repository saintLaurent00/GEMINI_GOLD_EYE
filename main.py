"""main.py - Boucle principale GEMINI GOLD EYE (bot live MT5).

Connexion MT5 -> analyse (GeminiStrategy) -> execution (TradeManager) avec le
bouclier Prop-Firm (PropGuard) en amont de chaque prise de position.
Ce chemin requiert le terminal MT5 (Windows). Pour le backtest/paper sans MT5,
voir main_paper.py et main_gemini_paper.py.
"""
import time
import datetime
import MetaTrader5 as mt5
from config import settings
from infrastructure.mt5_connector import MT5Connector
from data_processor.indicators import TacticalCalculator
from core.strategy import GeminiStrategy
from core.risk_manager import RiskManager
from core.trade_manager import TradeManager
from core.prop_guard import PropGuard

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
    guard = PropGuard()  # Bouclier compte Prop-Firm (circuit-breaker journalier)

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

                                # 0. BOUCLIER PROP-FIRM (circuit-breaker)
                                ok, reason = guard.status()
                                if not ok:
                                    print(f"🛑 PROTECTION: {reason} — pas de nouveau trade.")
                                    continue

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