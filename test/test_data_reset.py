from infrastructure.mt5_connector import MT5Connector
from data_processor.indicators import TacticalCalculator
from data_processor.vision import ChartPainter
from config import settings
import json

print("--- 🔬 TEST VALIDATION DATA (RESET) ---")

mt5_app = MT5Connector()
if mt5_app.start():
    symbol = settings.SYMBOLS[0]
    print(f"🎯 Cible : {symbol}")

    # 1. TEST TACTIQUE (JSON)
    print("\n1️⃣ CALCULATEUR TACTIQUE (LIVE PRICE)...")
    calc = TacticalCalculator(symbol)
    bulletin = calc.get_bulletin()
    
    if bulletin:
        print(json.dumps(bulletin, indent=2))
        print(f"✅ VÉRIFIEZ : Le prix 'REAL_BID' doit correspondre exactement à MT5.")
    else:
        print("❌ ECHEC Bulletin.")

    # 2. TEST VISION (IMAGES)
    print("\n2️⃣ GÉNÉRATEUR VISUEL (5 DÉCIMALES)...")
    painter = ChartPainter(symbol)
    paths = painter.generate_charts()
    
    if paths:
        print(f"✅ Images générées dans /charts_buffer :")
        for p in paths: print(f"   - {p}")
        print("👉 VÉRIFIEZ : Ouvrez les images. L'axe de droite doit avoir 5 décimales (ex: 1.08450).")
    else:
        print("❌ ECHEC Vision.")

    mt5_app.shutdown()