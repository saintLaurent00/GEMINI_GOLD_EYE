# GEMINI GOLD EYE

Un bot de trading multi-timeframe pour Forex & Or.

## Configuration

### 5. Backtester le bot

Un moteur de backtest local est disponible sans appel Gemini obligatoire. Il reproduit le bulletin H1/H4 du live, applique une décision de confluence déterministe, simule SL/TP/BE/trailing et exporte un CSV.

```
python backtest.py --demo --bars 700 --strategy confluence
python backtest.py --demo --bars 1200 --strategy asian_breakout --risk 0.5 --rr 3
python backtest.py --csv data/EURUSD_M15.csv --symbol EURUSD --strategy us_opr --risk 0.25 --rr 2
python backtest.py --mt5 --symbol XAUUSD --bars 2000 --strategy confluence
```

Stratégies disponibles :

* `confluence` : logique GEMINI GOLD EYE actuelle, alignement H1/H4 + VWAP/MACD.
* `asian_breakout` : cassure du range asiatique entre 09h00 et 13h00, stop sur EMA50.
* `us_opr` : cassure du range d'ouverture US 15h30-15h45 entre 15h45 et 17h30, filtre Supertrend H1, stop au milieu du range.

Le CSV doit contenir au minimum : `time, open, high, low, close`. Pour `us_opr`, utilisez idéalement des bougies M15.
