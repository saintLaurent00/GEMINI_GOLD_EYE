from infrastructure.mt5_connector import MT5Connector
from core.strategy import GeminiStrategy
from core.risk_manager import RiskManager
from config import settings

print("--- 🧠 TEST DU CERVEAU (FINAL) ---")

mt5_app = MT5Connector()
if mt5_app.start():
    
    # On teste sur le premier symbole valide
    symbol = settings.SYMBOLS[0]
    
    # 1. Lancement de la Stratégie
    brain = GeminiStrategy()
    decision = brain.analyze_symbol(symbol)
    
    # 2. Si l'IA donne un ordre, on simule le calcul de risque
    if decision and decision['decision'] in ["BUY", "SELL"]:
        print("\n💰 CALCUL DU RISQUE (Simulation)...")
        risk = RiskManager()
        
        # On récupère l'ATR que l'IA a validé
        atr = decision.get("atr_value", 0.0020)
        
        # SL = 2 x ATR (Standard Day-Swing)
        sl_points = atr * 2.0
        
        lot = risk.calculate_lot_size(symbol, sl_points)
        
        print(f"   - Capital : {mt5.account_info().balance} USD")
        print(f"   - Risque : {settings.RISK_PER_TRADE}%")
        print(f"   - Stop Loss : {sl_points:.5f} points (2xATR)")
        print(f"   - TAILLE DE LOT : {lot} lots")
        
    elif decision:
        print("\n😴 L'IA a décidé d'attendre (WAIT). C'est une décision valide.")

    mt5_app.shutdown()