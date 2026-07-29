import MetaTrader5 as mt5

# ============================================================
#  SOURCE DE VERITE UNIQUE POUR LES TIMEFRAMES
#  (settings.TIMEFRAME_TRIGGER = bougie qui "réveille" le bot)
# ============================================================

# Les Timeframes pour la VISION (images envoyées à Gemini)
# Tuple : (Constante MT5, Nom du fichier, Nombre de bougies affichées)
VISION_TIMEFRAMES = [
    (mt5.TIMEFRAME_W1, "W1_Weekly",   150),  # Tendance Macro
    (mt5.TIMEFRAME_D1, "D1_Daily",    120),  # Momentum
    (mt5.TIMEFRAME_H4, "H4_Tactical", 100),  # Structure
    (mt5.TIMEFRAME_H1, "H1_Precision", 80),  # Sniper Entry
]