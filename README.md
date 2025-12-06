#  GEMINI GOLD EYE — VERSION 13

### Prop Firm Algorithmic Trading System

**Auteur :** Ouattara Laurent (St Lrt)
**Version :** 13.0 (Stable & Prop-Firm Ready)
**Technologies :** Python 3.12, MetaTrader 5, Google Gemini 1.5 Flash Vision

---

##  Présentation Générale

GEMINI GOLD EYE est un système de trading algorithmique hybride conçu pour réussir les challenges de Prop Firm. Il combine l’analyse mathématique de précision et l’intelligence artificielle visuelle multimodale pour prendre des décisions basées sur la structure institutionnelle du marché.

Le système fonctionne en mode **Day-to-Swing**, avec un raisonnement multi-timeframe (W1, D1, H4, H1) et une gestion du risque calibrée pour les comptes financés.

---

##  Architecture Bi‑Céphale

### Côté Mathématique (Prix réels)

* RSI14
* ATR14
* EMA50 / EMA200
* Volatilité réelle (ATR)
* Spread réel (tick bid/ask)
* Analyse CLEAN des données sans repaint

### Côté IA Vision (Google Gemini)

L’IA reçoit des graphiques enrichis avec :

* ZigZag structurel (HH/HL – LH/LL)
* OB (Order Blocks)
* FVG (Fair Value Gaps)
* EMA 50 & 200
* Supports / Résistances
* Prix LIVE (ligne rouge)

L’objectif : détecter les patterns SMC avec précision institutionnelle.

---

##  Fonctionnalités Clé

###  Analyse Multi-Timeframe (W1 / D1 / H4 / H1)

* W1/D1 : Biais macro
* H4 : Structure institutionnelle
* H1 : Sniper Entry

###  Gestion du Risque Prop-Firm

* Horaires filtrés (08h → 20h GMT+0)
* Stop Loss ATR
* Lot dynamique basé sur la volatilité
* Break Even intelligent
* Mode Gold spécial (XAUUSD)

###  Modes de Trading

**Forex Standard**

* Sécurisation rapide à +1 ATR
* Trailing clair 300 points

**Gold Sniper 1:3 (XAUUSD)**

* Aucune sécurisation avant 1:3
* Refus des spikes

---

##  Arborescence du Projet

```
GEMINI_GOLD_EYE/
│
├── config/
│   ├── settings.py          # Paramètres généraux et clés API
│   └── symbols.py           # Timeframes, actifs autorisés
│
├── infrastructure/
│   ├── mt5_connector.py     # Pont MetaTrader 5
│   └── gemini_client.py     # Client Google Gemini + Retry Logic
│
├── data_processor/
│   ├── indicators.py        # Calcul des indicateurs mathématiques
│   └── vision.py            # Générateur de graphiques IA
│
├── core/
│   ├── strategy.py          # Génération du prompt (Version 13)
│   ├── risk_manager.py      # Gestion du risque
│   └── trade_manager.py     # Break Even & Trailing
│
└── main.py                  # Boucle principale H4
```

---

##  Installation

### 1. Prérequis

* Python 3.10 minimum
* MetaTrader 5 installé & connecté
* Clé API Google Gemini

### 2. Installer les dépendances

```
pip install -r requirements.txt
```

**requirements.txt contient :**

* MetaTrader5
* pandas
* pandas_ta
* mplfinance
* google-generativeai
* python-dotenv
* matplotlib

### 3. Configuration

Crée un fichier `.env` :

```
GEMINI_API_KEY=VOTRE_CLE
MT5_LOGIN=XXXXXX
MT5_PASSWORD=YYYYYY
MT5_SERVER=ZZZZZ

SYMBOLS_LIST=AUDCAD,USDJPY,USDCHF,XAUUSD

RISK_PER_TRADE=1.0
MODE_SNIPER=True
BE_TRIGGER=300
TRAILING_DIST=300
```

### 4. Lancer le bot

```
python main.py
```

---

##  Actifs Optimisés

Le système donne ses meilleurs résultats sur :

* AUDCAD (stabilité)
* USDJPY (tendances propres)
* USDCHF (mouvements propres USD)
* XAUUSD (stratégie sniper 1:3)

---

##  Légendes & Explications Visuelles

###  EMAs

* **EMA200 (Bleu)** : Trend institutionnel
* **EMA50 (Orange)** : Dynamique court terme

###  ZigZag

Visualisation structurelle :

* HH/HL = haussier
* LH/LL = baissier

###  Support / Résistance

* Lignes vertes : zones institutionnelles

###  Prix actuel

* Ligne rouge = prix en temps réel

###  Order Block

Zones de prise de liquidité utilisées par les banques.

###  Fair Value Gap (FVG)

Imbalance utilisée comme zone de réaction.

---

##  Avertissement

Ce logiciel assiste le trader. Les marchés financiers comportent des risques importants.
Toujours tester sur compte démo avant d'utiliser en réel.

---

##  .gitignore

```
.env
__pycache__/
*.pyc
charts_buffer/
logs/
venv/
.venv/
```

---

## 🌐 Déploiement Github

```
git init
git add .
git commit -m "V13: Initial Commit"
git branch -M main
git remote add origin https://github.com/VOTRE_USER/GEMINI-GOLD-EYE.git
git push -u origin main
```
