"""
regime_analyzer.py - Analyse les regimes de marche sur un CSV H1.

Decoupe l'historique en fenetres et classe chaque segment :
  HAUSSIER / BAISSIER / RANGE
selon la pente de l'EMA200 (normalisee par l'ATR) + l'ADX moyen.

Permet de cibler une fenetre precise pour le backtest Gemini (--offset-bars).

Usage :
    python tools/regime_analyzer.py --csv data/XAUUSD_H1.csv --symbol XAUUSD
    python tools/regime_analyzer.py --csv data/XAUUSD_H1.csv --window 500 --step 250
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import load_csv, apply_indicators


def classify_segment(seg):
    """Classe un segment de bougies en HAUSSIER / BAISSIER / RANGE."""
    valid = [c for c in seg if c.ema200 > 0 and c.atr > 0]
    if len(valid) < 50:
        return "INCONNU", 0.0, 0.0, 0.0
    first, last = valid[0], valid[-1]
    n = len(valid)
    # Pente de l'EMA200 normalisee par l'ATR moyen (sans echelle)
    atr_mean = sum(c.atr for c in valid) / n
    slope = (last.ema200 - first.ema200) / n if atr_mean else 0.0
    strength = abs(slope) / atr_mean if atr_mean else 0.0
    # ADX moyen (force de tendance)
    adx_mean = sum(c.adx for c in valid) / n
    # % de variation du prix
    pct = (last.close - first.close) / first.close * 100.0
    # Classification
    if strength > 0.025 and slope > 0:
        regime = "HAUSSIER"
    elif strength > 0.025 and slope < 0:
        regime = "BAISSIER"
    else:
        regime = "RANGE"
    return regime, strength, adx_mean, pct


def main():
    p = argparse.ArgumentParser(description="Analyse des regimes de marche")
    p.add_argument("--csv", required=True)
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--window", type=int, default=500, help="taille de fenetre (bougies H1)")
    p.add_argument("--step", type=int, default=250, help="pas entre fenetres")
    args = p.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ CSV introuvable: {args.csv}")
        return

    candles = apply_indicators(load_csv(args.csv))
    print(f"\n📈 ANALYSE DES REGIMES — {args.symbol} | {len(candles)} bougies H1")
    print(f"   Fenêtre: {args.window} bougies (~{args.window//24} jours) | pas: {args.step}\n")
    print(f"{'#':>3}  {'Début':<17} {'Fin':<17} {'Régime':<11} {'Force':>7} {'ADX':>6} {'Var%':>8}")
    print("-" * 78)

    counts = {"HAUSSIER": 0, "BAISSIER": 0, "RANGE": 0, "INCONNU": 0}
    segments = []
    idx = 0
    pos = 0
    while pos + args.window <= len(candles):
        seg = candles[pos:pos + args.window]
        regime, strength, adx, pct = classify_segment(seg)
        start_dt = seg[0].time.strftime("%Y-%m-%d %Hh")
        end_dt = seg[-1].time.strftime("%Y-%m-%d %Hh")
        emoji = {"HAUSSIER": "🟢", "BAISSIER": "🔴", "RANGE": "🟡", "INCONNU": "⚪"}[regime]
        print(f"{idx:>3}  {start_dt:<17} {end_dt:<17} {emoji} {regime:<9} {strength:>7.3f} {adx:>6.1f} {pct:>+7.2f}%")
        counts[regime] = counts.get(regime, 0) + 1
        # offset = nb de bougies depuis la fin (pour --offset-bars du backtest)
        offset_from_end = len(candles) - (pos + args.window)
        segments.append((idx, start_dt, end_dt, regime, offset_from_end, args.window))
        idx += 1
        pos += args.step

    print("-" * 78)
    print(f"Répartition : 🟢 HAUSSIER={counts['HAUSSIER']} | 🔴 BAISSIER={counts['BAISSIER']} | 🟡 RANGE={counts['RANGE']}\n")

    # Recommandations : un segment de chaque regime
    print("🎯 Fenêtres recommandées pour tester la robustesse (backtest Gemini) :")
    seen = {}
    for s in segments:
        sidx, sd, ed, reg, off, win = s
        if reg in ("HAUSSIER", "BAISSIER", "RANGE") and reg not in seen:
            seen[reg] = s
            print(f"   {reg:10} : segment #{sidx} ({sd} -> {ed})")
            print(f"              -> python main_gemini_paper.py --symbol {args.symbol} --backtest "
                  f"--bars {win} --offset-bars {off} --max-gemini 30")
    print()
    if not seen.get("HAUSSIER"):
        print("   (aucun segment haussier franc trouvé — essaie --window 300 ou --step 150)")


if __name__ == "__main__":
    main()
