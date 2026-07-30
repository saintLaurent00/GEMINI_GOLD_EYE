"""
binance_client.py - Client REST Binance USD-M Futures (testnet + mainnet).

* Signature HMAC-SHA256 (timestamp + recvWindow + params).
* Endpoints : klines, ticker/price, exchangeInfo, account, positions,
              set_leverage, set_margin_type, market_order, sl/tp (reduceOnly),
              close_position, cancel_open_orders.
* Utilise `requests` (déjà dans requirements via transitif ; on l'ajoute dans requirements.txt).

Usage:
    from infrastructure.binance_client import BinanceFuturesClient
    bc = BinanceFuturesClient(api_key, secret, testnet=True)
    print(bc.balance_usdt())
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

log = logging.getLogger("binance")

BASE_TESTNET = "https://testnet.binancefuture.com"
BASE_MAINNET = "https://fapi.binance.com"


class BinanceApiError(RuntimeError):
    """Erreur renvoyée par l'API Binance (-10xx / -20xx / -40xx ...)."""
    def __init__(self, code: int, msg: str, http_status: int = None):
        super().__init__(f"[Binance err {code}] {msg}")
        self.code = code
        self.msg = msg
        self.http_status = http_status


class BinanceFuturesClient:
    # RecvWindow large pour tolérer la latence (Binance tolère jusqu'à 60 000 ms).
    RECV_WINDOW = 5000

    def __init__(self, api_key: str, secret: str, testnet: bool = True,
                 timeout: int = 15, max_retries: int = 3):
        if not api_key or not secret:
            raise ValueError("BINANCE_API_KEY et BINANCE_SECRET sont requis.")
        self.api_key = api_key
        self.secret = secret.encode("utf-8")
        self.testnet = testnet
        self.base = BASE_TESTNET if testnet else BASE_MAINNET
        self.timeout = timeout
        self.max_retries = max_retries
        self._sess = requests.Session()
        self._sess.headers.update({"X-MBX-APIKEY": self.api_key,
                                   "Accept": "application/json"})
        # cache exchange info (lot size / tick size)
        self._sym_info: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------
    # HTTP helpers (signé + non signé)
    # ------------------------------------------------------------
    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.RECV_WINDOW
        qs = urlencode(params, doseq=True)
        sig = hmac.new(self.secret, qs.encode("utf-8"), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _request(self, method: str, path: str, params: Dict = None,
                 signed: bool = False) -> Any:
        url = self.base + path
        params = dict(params or {})
        if signed:
            params = self._sign(params)
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if method.upper() == "GET":
                    r = self._sess.get(url, params=params, timeout=self.timeout)
                elif method.upper() == "POST":
                    r = self._sess.post(url, params=params, timeout=self.timeout)
                elif method.upper() == "DELETE":
                    r = self._sess.delete(url, params=params, timeout=self.timeout)
                else:
                    raise ValueError(f"Méthode HTTP non supportée: {method}")
            except requests.RequestException as e:
                last_err = e
                log.warning("réseau tentative %s/%s échouée: %s", attempt, self.max_retries, e)
                time.sleep(0.5 * attempt)
                continue
            if r.status_code == 200:
                return r.json()
            # Erreur Binance
            try:
                j = r.json()
                code = int(j.get("code", -1))
                msg = j.get("msg", r.text)
            except Exception:
                code, msg = -1, r.text
            # Codes "retriables"
            if code in (-1001, -1003, -1007, -1021, -500) and attempt < self.max_retries:
                log.warning("Binance code=%s msg=%s retry %s/%s", code, msg, attempt, self.max_retries)
                time.sleep(0.6 * attempt)
                if code == -1021:  # timestamp hors fenêtre
                    time.sleep(0.5)
                continue
            raise BinanceApiError(code, msg, http_status=r.status_code)
        raise BinanceApiError(-1, f"échec réseau après {self.max_retries} tentatives: {last_err}")

    def _get(self, path, params=None, signed=False):
        return self._request("GET", path, params, signed=signed)

    def _post(self, path, params=None, signed=True):
        return self._request("POST", path, params, signed=signed)

    def _delete(self, path, params=None, signed=True):
        return self._request("DELETE", path, params, signed=signed)

    # ------------------------------------------------------------
    # Données marché (public)
    # ------------------------------------------------------------
    def server_time(self) -> int:
        return int(self._get("/fapi/v1/time")["serverTime"])

    def price(self, symbol: str) -> float:
        data = self._get("/fapi/v1/ticker/price", {"symbol": symbol.upper()})
        return float(data["price"])

    def klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> List[List]:
        """
        Interval: 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M.
        Retour: liste de listes [open_t, O, H, L, C, vol, close_t, ...].
        """
        data = self._get("/fapi/v1/klines",
                         {"symbol": symbol.upper(), "interval": interval, "limit": int(limit)})
        return data

    def exchange_info(self, symbol: str = None) -> Dict:
        """Retourne les filtres d'un (ou tous les) symboles (lot/tick/minNotional)."""
        params = {"symbol": symbol.upper()} if symbol else None
        return self._get("/fapi/v1/exchangeInfo", params=params)

    def symbol_info(self, symbol: str, force: bool = False) -> Dict[str, Any]:
        """Retourne les infos utiles (stepSize, tickSize, minQty, minNotional, pricePrecision, quantityPrecision)."""
        s = symbol.upper()
        if s in self._sym_info and not force:
            return self._sym_info[s]
        info = self.exchange_info(s)
        sym = None
        for item in info.get("symbols", []):
            if item["symbol"] == s:
                sym = item
                break
        if not sym:
            raise BinanceApiError(-1, f"Symbole introuvable sur Binance Futures: {s}")
        out = {
            "symbol": s,
            "status": sym.get("status"),
            "pricePrecision": int(sym.get("pricePrecision", 2)),
            "quantityPrecision": int(sym.get("quantityPrecision", 3)),
            "stepSize": None,
            "tickSize": None,
            "minQty": None,
            "minNotional": None,
        }
        for f in sym.get("filters", []):
            t = f.get("filterType")
            if t == "LOT_SIZE":
                out["stepSize"] = float(f["stepSize"])
                out["minQty"] = float(f["minQty"])
            elif t == "PRICE_FILTER":
                out["tickSize"] = float(f["tickSize"])
            elif t == "MARKET_LOT_SIZE":
                # préfèrer la taille de marché si présente (quelques altcoins)
                out["marketStepSize"] = float(f["stepSize"])
                out["marketMinQty"] = float(f["minQty"])
            elif t == "MIN_NOTIONAL":
                out["minNotional"] = float(f.get("notional", f.get("minNotional", 0)))
        self._sym_info[s] = out
        return out

    # ------------------------------------------------------------
    # Quantité / prix respectant step/tick + minimums
    # ------------------------------------------------------------
    @staticmethod
    def _floor_prec(x: float, step: float) -> float:
        if step <= 0:
            return x
        # arrondi au multiple inférieur de step (évite les "qty < minQty"/"precision" errors)
        return round(int(x / step) * step, 12)

    @staticmethod
    def _round_to_tick(x: float, tick: float) -> float:
        if tick <= 0:
            return x
        return round(round(x / tick) * tick, 12)

    def normalize_quantity(self, symbol: str, qty: float) -> float:
        info = self.symbol_info(symbol)
        step = info.get("marketStepSize") or info.get("stepSize") or 0.001
        min_qty = info.get("marketMinQty") or info.get("minQty") or 0.0
        q = self._floor_prec(qty, step)
        if q < min_qty:
            # essayer d'augmenter au minimum négociable (sera re-checké par appelant via notional)
            q = min_qty
        return q

    def normalize_price(self, symbol: str, price: float) -> float:
        info = self.symbol_info(symbol)
        tick = info.get("tickSize") or 0.01
        return self._round_to_tick(price, tick)

    def check_notional(self, symbol: str, qty: float, price: float) -> float:
        """Retourne le notional et lève si en dessous du minimum."""
        info = self.symbol_info(symbol)
        notional = qty * price
        mn = info.get("minNotional") or 0.0
        if mn and notional < mn:
            raise BinanceApiError(-1, f"Notional {notional:.2f} < minNotional {mn} pour {symbol}")
        return notional

    # ------------------------------------------------------------
    # Compte & positions (signés)
    # ------------------------------------------------------------
    def account(self) -> Dict:
        return self._get("/fapi/v2/account", signed=True)

    def balance_usdt(self) -> float:
        """Solde USDT disponible (free) du portefeuille Futures."""
        acc = self.account()
        for a in acc.get("assets", []):
            if a.get("asset") == "USDT":
                return float(a.get("availableBalance", a.get("walletBalance", "0")))
        return 0.0

    def positions(self, symbol: str = None) -> List[Dict]:
        """Retourne les positions ouvertes (positionAmt != 0)."""
        data = self._get("/fapi/v2/positionRisk",
                         {"symbol": symbol.upper()} if symbol else None,
                         signed=True)
        return [p for p in data if float(p.get("positionAmt", 0)) != 0.0]

    def position(self, symbol: str) -> Optional[Dict]:
        ps = self.positions(symbol)
        return ps[0] if ps else None

    # ------------------------------------------------------------
    # Paramètres de trading
    # ------------------------------------------------------------
    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED"):
        try:
            return self._post("/fapi/v1/marginType",
                              {"symbol": symbol.upper(), "marginType": margin_type.upper()})
        except BinanceApiError as e:
            # -4046 = "No need to change margin type" (déjà dans ce mode)
            if e.code == -4046:
                return {"msg": "margin type already set"}
            raise

    def set_leverage(self, symbol: str, leverage: int):
        return self._post("/fapi/v1/leverage",
                          {"symbol": symbol.upper(), "leverage": int(leverage)})

    # ------------------------------------------------------------
    # Ordres
    # ------------------------------------------------------------
    def _new_order(self, symbol: str, side: str, ord_type: str, **params) -> Dict:
        p = {"symbol": symbol.upper(), "side": side.upper(), "type": ord_type.upper()}
        p.update({k: v for k, v in params.items() if v is not None})
        return self._post("/fapi/v1/order", p)

    def market_order(self, symbol: str, side: str, qty: float,
                     reduce_only: bool = False, new_client_order_id: str = None) -> Dict:
        qty = self.normalize_quantity(symbol, qty)
        return self._new_order(
            symbol, side, "MARKET",
            quantity=qty,
            reduceOnly="true" if reduce_only else None,
            newClientOrderId=new_client_order_id,
        )

    def place_sl(self, symbol: str, side: str, stop_price: float,
                 reduce_only: bool = True) -> Dict:
        """STOP_MARKET : déclenche un ordre de marché quand stopPrice est touché."""
        sp = self.normalize_price(symbol, stop_price)
        # Pour SL en one-way mode, on ne met PAS de qty (closePosition=true Binance >=v1).
        # Mais tous les comptes ne l'acceptent pas, donc on passe la qty de la position.
        pos = self.position(symbol)
        qty = abs(float(pos["positionAmt"])) if pos else None
        return self._new_order(
            symbol, side, "STOP_MARKET",
            stopPrice=sp,
            closePosition="true" if qty is None else None,
            quantity=qty if qty is not None else None,
            reduceOnly="true" if reduce_only and qty is not None else None,
        )

    def place_tp(self, symbol: str, side: str, tp_price: float,
                 reduce_only: bool = True) -> Dict:
        """TAKE_PROFIT_MARKET : idem SL mais sur TP."""
        tp = self.normalize_price(symbol, tp_price)
        pos = self.position(symbol)
        qty = abs(float(pos["positionAmt"])) if pos else None
        return self._new_order(
            symbol, side, "TAKE_PROFIT_MARKET",
            stopPrice=tp,
            closePosition="true" if qty is None else None,
            quantity=qty if qty is not None else None,
            reduceOnly="true" if reduce_only and qty is not None else None,
        )

    def close_position(self, symbol: str) -> Optional[Dict]:
        pos = self.position(symbol)
        if not pos:
            return None
        amt = abs(float(pos["positionAmt"]))
        side = "SELL" if float(pos["positionAmt"]) > 0 else "BUY"
        return self.market_order(symbol, side, amt, reduce_only=True)

    def cancel_open_orders(self, symbol: str):
        return self._delete("/fapi/v1/allOpenOrders", {"symbol": symbol.upper()})

    def open_orders(self, symbol: str) -> List[Dict]:
        return self._get("/fapi/v1/openOrders", {"symbol": symbol.upper()}, signed=True)
