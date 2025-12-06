from infrastructure.mt5_connector import MT5Connector
from data_processor.indicators import TacticalCalculator
from data_processor.vision import ChartPainter
from config import settings
import json

print("--- 🧠 TEST DATA PROCESSOR (MATHS + VISION) ---")

mt5_app = MT5Connector()
if mt5_app.start():
    
    # On teste sur la première paire de ta liste (ex: EURUSD)
    test_symbol = settings.SYMBOLS[0]
    print(f"\n🔬 Analyse de : {test_symbol}")

    # 1. TEST CALCULATEUR TACTIQUE
    print("   🧮 Calcul du Bulletin Tactique...")
    calc = TacticalCalculator(test_symbol)
    bulletin = calc.get_bulletin()
    
    if bulletin:
        print(json.dumps(bulletin, indent=2))
        print("   ✅ Bulletin généré avec succès.")
    else:
        print("   ❌ Erreur Bulletin.")

    # 2. TEST VISION
    print("\n   🎨 Génération des Graphiques Augmentés...")
    painter = ChartPainter(test_symbol)
    paths = painter.generate_charts()
    
    if paths:
        print(f"   ✅ {len(paths)} Images générées :")
        for p in paths:
            print(f"      - {p}")
    else:
        print("   ❌ Erreur Vision.")

    mt5_app.shutdown()
else:
    print("❌ Impossible de connecter MT5 pour le test.")