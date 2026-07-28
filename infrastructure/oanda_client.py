"""
OandaClient - Connexion au broker OANDA via l'API REST v20.

OANDA fonctionne sur n'importe quelle machine avec Python (pas besoin de MT5 desktop
ni de VPS). Compte pratique (demo) gratuit, sans carte bancaire.

Variables requises (.env) :
  OANDA_API_TOKEN   -> token API (https://www.oanda.com/account/ -> API Access)
  OANDA_ACCOUNT_ID  -> ex: 001-001-1234567-001
  OANDA_PRACTICE    -> True (compte demo) / False (compte reel)
"""

import requests
import pandas as pd

PRACTICE_BASE = "https://api-fxpractice.oanda.com"
LIVE_BASE = "https://api-fxtrade.oanda.com"


def to_oanda_symbol(symbol: str) -> str:
    """EURUSD -> EUR_USD, XAUUSD -> XAU_USD."""
    s = symbol.upper()
    specials = {"XAUUSD": "XAU_USD", "XAGUSD": "XAG_USD", "BTCUSD": "BTC_USD"}
    if s in specials:
        return specials[s]
    if "_" in s:
        return s
    return s[:3] + "_" + s[3:]


class OandaClient:
    def __init__(self, token: str, account_id: str, practice: bool = True):
        self.token = token
        self.account_id = account_id
        self.base = PRACTICE_BASE if practice else LIVE_BASE
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "RFC3339",
        })

    # --------------------------------------------------------
    # Requetes de base
    # --------------------------------------------------------
    def _get(self, path, params=None):
        r = self.session.get(self.base + path, params=params, timeout=30)
        if not r.ok:
            raise RuntimeError(f"OANDA GET {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def _post(self, path, body):
        r = self.session.post(self.base + path, json=body, timeout=30)
        if not r.ok:
            raise RuntimeError(f"OANDA POST {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def _put(self, path, body):
        r = self.session.put(self.base + path, json=body, timeout=30)
        if not r.ok:
            raise RuntimeError(f"OANDA PUT {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    # --------------------------------------------------------
    # Données & compte
    # --------------------------------------------------------
    def list_accounts(self):
        """Liste tous les comptes accessibles avec ce token (pour trouver son Account ID)."""
        return self._get("/v3/accounts").get("accounts", [])

    def account(self):
        return self._get(f"/v3/accounts/{self.account_id}")["account"]

    def pricing(self, instrument):
        """Retourne le tick {bid, ask} pour un symbole OANDA (ex: EUR_USD)."""
        d = self._get(f"/v3/accounts/{self.account_id}/pricing", {"instruments": instrument})
        p = d["prices"][0]
        return {
            "bid": float(p["bids"][0]["price"]),
            "ask": float(p["asks"][0]["price"]),
        }

    def candles(self, instrument, granularity="H1", count=500):
        """
        Bougies OHLC -> DataFrame indexé par time (UTC).
        granularity: H1, H4, D1, W1, M5, M15, M30...
        """
        d = self._get(f"/v3/instruments/{instrument}/candles",
                      {"granularity": granularity, "count": count, "price": "M"})
        rows = []
        for c in d.get("candles", []):
            m = c["mid"]
            rows.append({
                "time": pd.to_datetime(c["time"]),
                "open": float(m["o"]), "high": float(m["h"]),
                "low": float(m["l"]), "close": float(m["c"]),
                "volume": float(c.get("volume", 0)),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df.set_index("time", inplace=True)
        return df

    # --------------------------------------------------------
    # Execution (Etape 2)
    # --------------------------------------------------------
    def place_market_order(self, instrument, units, sl=None, tp=None):
        """units > 0 = achat, units < 0 = vente."""
        order = {"type": "MARKET", "instrument": instrument, "units": str(units)}
        if sl is not None:
            order["stopLossOnFill"] = {"price": f"{sl:.5f}"}
        if tp is not None:
            order["takeProfitOnFill"] = {"price": f"{tp:.5f}"}
        return self._post(f"/v3/accounts/{self.account_id}/orders", {"order": order})

    def positions(self):
        return self._get(f"/v3/accounts/{self.account_id}/openPositions").get("positions", [])

    def close_position(self, instrument, side="long"):
        body = {"longUnits": "ALL"} if side == "long" else {"shortUnits": "ALL"}
        return self._put(f"/v3/accounts/{self.account_id}/positions/{instrument}/close", body)

    def transactions(self, frm=None):
        params = {}
        if frm:
            params["from"] = frm
        return self._get(f"/v3/accounts/{self.account_id}/transactions", params)
