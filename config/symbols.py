import MetaTrader5 as mt5

# Le Timeframe maître (celui qui déclenche l'analyse)
# On a validé H4 pour du Day-to-Swing
TRIGGER_TIMEFRAME = mt5.TIMEFRAME_H1

# Les Timeframes pour la Vision (Les images envoyées à l'IA)
# Tuple : (Constante MT5, Nom pour le fichier, Nombre de bougies à afficher)
VISION_TIMEFRAMES = [
    (mt5.TIMEFRAME_W1, "W1_Weekly", 150),   # Tendance Macro
    (mt5.TIMEFRAME_D1, "D1_Daily", 120),    # Momentum
    (mt5.TIMEFRAME_H4, "H4_Tactical", 100),  # Structure / Entrée
    (mt5.TIMEFRAME_H1, "H1_Precision, H1_Sniper", 80)  # Zoom Entrée

]

# Les Timeframes pour les Maths (Indicateurs)
# On calcule les indicateurs sur le H4 pour la précision tactique
MATH_TIMEFRAME = mt5.TIMEFRAME_H1