# 💎 GEMINI GOLD EYE — VERSION 14

### Bot de trading algorithmique hybride (Day Trading) — IA visuelle Gemini + règles

**Auteur :** Ouattara Laurent (St Lrt)
**Version :** 14.0
**Technologies :** Python 3.10+, Google Gemini (vision multimodale), MetaTrader 5 (optionnel)

---

## 🎯 Présentation

GEMINI GOLD EYE combine **l'analyse mathématique** et **la vision IA de Gemini** pour détecter
des setups de cassure (stratégie day trading inspirée de Benjamin Deleuse) sur l'Or (XAUUSD)
et le Forex. Le bot peut tourner **sans broker ni MT5** (paper trading / backtest sur données
Yahoo gratuites), ce qui le rend testable depuis n'importe quel PC ou Google Colab.

> ⚠️ **Avertissement** : ce logiciel assiste le trader. Les marchés financiers comportent des
> risques importants. Les backtests/paper trading ne garantissent pas les performances futures.
> Toujours tester en démo avant tout usage réel.

---

## 🧠 Architecture

```
GEMINI_GOLD_EYE/
├── main.py                  # Bot live MT5 (requiert terminal MT5 Windows)
├── main_paper.py            # Paper trading (moteur de règles) sur données Yahoo — SANS broker
├── main_gemini_paper.py     # LE VRAI BOT : vision Gemini + paper trading (live OU backtest)
├── backtest.py              # Backtest local (stratégies Deleuse / Trend, day / swing)
├── core/
│   ├── strategy.py          # GeminiStrategy (prompt multimodal + parsing JSON)
│   ├── risk_manager.py      # Taille de lot (risque X% du capital)
│   ├── trade_manager.py     # Break-Even + Trailing Stop
│   └── prop_guard.py        # Bouclier Prop-Firm (circuit-breaker journalier)
├── data_processor/
│   ├── indicators.py        # Indicateurs (EMA, RSI, ATR, VWAP, MACD, Stochastique, ADX)
│   └── vision.py            # Génération des graphiques annotés pour Gemini
├── infrastructure/
│   ├── gemini_client.py     # Client Gemini + ROTATION de clés API (anti-quota)
│   ├── mt5_connector.py     # Pont MetaTrader 5
│   └── oanda_client.py      # Client OANDA (broker cloud, optionnel)
├── config/                  # settings.py + symbols.py
└── tools/
    ├── fetch_data.py        # Téléchargement gratuit de bougies H1 (Yahoo / Twelve Data)
    ├── regime_analyzer.py   # Analyse des régimes (haussier / baissier / range)
    └── test_oanda.py        # Test de connexion OANDA
```

---

## ✨ Fonctionnalités clé (v14)

### Stratégie day trading (Deleuse)
- Filtre de tendance **EMA50**, détection de **consolidation** (contraction de la plage),
  **cassure** dans le sens de la tendance avec **bougie décisive** (anti-doji).
- Classification des figures : RANGE / TRIANGLE ASC / TRIANGLE DESC / DRAPEAU / BISEAU.
- **SL structurel** (bord de la zone cassée), **R:R 1:2.5**.

### Free trade (anti-perte)
À **+1.5R**, on sécurise **50 %** de la position et on ramène le SL à l'entrée.
Le reste court vers 2.5R avec trailing. → transforme de nombreuses pertes en gains sécurisés.

### Vision Gemini (le vrai bot)
Gemini lit les **vrais graphiques** W1/D1/H4/H1 (ZigZag, EMA, VWAP, S/R, prix live) et
décide (BUY/SELL/WAIT + confiance). Les règles Deleuse **pré-sélectionnent** les setups,
Gemini **confirme ou rejette** → l'IA filtre mieux que le code seul.

### Rotation de clés API
Plusieurs clés Gemini → bascule automatique en cas de quota (round-robin, sans attente bloquante).

### Bouclier Prop-Firm (`PropGuard`)
Circuit-breaker journalier : perte max/jour, max trades/jour, pertes consécutives.

### Sans broker ni MT5
Backtest + paper trading sur **données Yahoo gratuites** → testable sur Google Colab, sans VPS.

---

## 🚀 Démarrage rapide (Google Colab, gratuit)

```python
!git clone -b arena/019fa813-gemini-gold-eye https://github.com/saintLaurent00/GEMINI_GOLD_EYE.git
%cd GEMINI_GOLD_EYE
!pip install -q google-generativeai Pillow mplfinance pandas pandas_ta
!python tools/fetch_data.py --source yahoo --range 2y     # données H1 (EUR/USD + Or)

import os
os.environ["GEMINI_API_KEYS"] = "cle1,cle2,cle3"          # clés gratuites (aistudio.google.com)

# 1) Backtest du moteur de règles (rapide, sans Gemini)
!python backtest.py --csv data/XAUUSD_H1.csv --symbol XAUUSD --strategy deleuse

# 2) Paper trading (moteur de règles, sans Gemini)
!python main_paper.py --symbol XAUUSD

# 3) LE VRAI BOT Gemini (backtest sur historique, sans attendre)
!python main_gemini_paper.py --symbol XAUUSD --backtest --bars 1500 --max-gemini 30
```

---

## 📊 Backtest — commandes utiles

```bash
# Stratégies : deleuse (défaut, cassure) ou trend (confluence EMA/VWAP/MACD)
python backtest.py --csv data/XAUUSD_H1.csv --symbol XAUUSD --strategy deleuse
python backtest.py --csv data/XAUUSD_H1.csv --symbol XAUUSD --mode swing --rr 2.5

# Analyser les régimes pour cibler une fenêtre
python tools/regime_analyzer.py --csv data/XAUUSD_H1.csv --symbol XAUUSD

# Backtest Gemini sur un régime ciblé (--offset-bars depuis la fin)
python main_gemini_paper.py --symbol XAUUSD --backtest --bars 500 --offset-bars 8653 --max-gemini 25
```

Métriques produites : win rate, expectancy (R/trade), profit factor, drawdown max.

---

## ⚙️ Configuration (`.env`)

Copiez `.env.example` en `.env` et remplissez vos valeurs (**jamais de secret en clair dans le code**) :

```
GEMINI_API_KEYS=cle1,cle2,cle3        # rotation auto en cas de quota
SYMBOLS_LIST=AUDCAD,USDJPY,USDCHF,XAUUSD
RISK_PER_TRADE=1.0
MAX_DAILY_LOSS_PCT=4.0
MAX_DAILY_TRADES=5
MAX_CONSEC_LOSSES=3
```

---

## 📈 Résultats observés (backtest, données réelles)

| Test | Régime | Win rate | Expectancy |
|---|---|---|---|
| Moteur Deleuse (2 ans, Or) | mixte | 29 % | +0.09 R, PF 1.34, DD -8 % |
| Bot Gemini (3 mois, Or) | baissier/range | 56 % | +0.18 R |
| Bot Gemini (haussier) | haussier | 86 % | +0.51 R |
| Bot Gemini (range plat) | range | 43 % | -0.24 R |

Profil **tendance/cassure** : fort en tendance, légèrement perdant en range (inhérent au type
de stratégie). Edge réel mais modeste — à confirmer sur d'autres périodes. **Pas de garantie.**

---

## 🔒 Sécurité

- Ne jamais committer de mots de passe / clés API. Le `.env` est gitignoré.
- Régénérez toute clé partagée par erreur.

---

## 🗂️ Historique

Le code mort des versions précédentes (~2500 lignes commentées) a été retiré en v14.
Tout l'historique est préservé via Git et le tag `v13-avant-nettoyage` :
```
git show v13-avant-nettoyage:main.py
```
