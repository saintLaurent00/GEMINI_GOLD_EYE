"""
PropGuard - Bouclier de compte niveau JOURNALIER.
==================================================
C'est ICI que se joue la vraie protection "Prop-Firm".
Un SL mobile protège UN trade ; PropGuard protège la JOURNEE entiere
(la ou les comptes prop meurent reellement : -5%/jour).

3 regles de coupure (parametrables via .env) :
  1. MAX_DAILY_LOSS_PCT   : perte journaliere max  -> ARRET TOTAL
  2. MAX_DAILY_TRADES     : nb max de trades / jour -> ARRET TOTAL
  3. MAX_CONSEC_LOSSES    : pertes consecutives max -> ARRET TOTAL

Fonctionnement : interroge l'historique MT5 (deals fermes du JOUR,
filtres par magic number du bot). Aucune API externe, aucun cout.

Usage (dans main.py, avant toute prise de position) :
    from core.prop_guard import PropGuard
    guard = PropGuard()
    ok, reason = guard.status()
    if not ok:
        print(f"🛑 Protection: {reason}")
        continue   # on n'ouvre RIEN
"""

import datetime
import MetaTrader5 as mt5
from config import settings


class PropGuard:
    def __init__(self):
        self.magic = settings.MAGIC_NUMBER                       # 777888 par defaut
        self.max_daily_loss_pct = settings.MAX_DAILY_LOSS_PCT    # 4.0 % par defaut
        self.max_daily_trades = settings.MAX_DAILY_TRADES        # 5 par defaut
        self.max_consec_losses = settings.MAX_CONSEC_LOSSES      # 3 par defaut

    # ----------------------------------------------------------
    # OUTILS INTERNES
    # ----------------------------------------------------------
    def _today_start_utc(self):
        """Debut de la journee (00:00 UTC)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        return datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)

    def _bot_deals_today(self):
        """
        Recupere les deals FERMES (DEAL_ENTRY_OUT) de NOTRE bot,
        realises aujourd'hui. Retourne [] en cas d'erreur MT5 (defensif).
        """
        try:
            start = self._today_start_utc()
            now = datetime.datetime.now(datetime.timezone.utc)
            deals = mt5.history_deals_get(start, now)
            if deals is None:
                return []
            return [d for d in deals
                    if d.magic == self.magic and d.entry == mt5.DEAL_ENTRY_OUT]
        except Exception as e:
            print(f"⚠️ PropGuard: lecture historique impossible ({e})")
            return []

    # ----------------------------------------------------------
    # METRIQUES
    # ----------------------------------------------------------
    def daily_pnl(self):
        """P&L realise du jour (en devise du compte)."""
        return sum(d.profit for d in self._bot_deals_today())

    def daily_trade_count(self):
        """Nombre de trades fermes aujourd'hui."""
        return len(self._bot_deals_today())

    def consecutive_losses(self):
        """Nombre de pertes consecutives jusqu'a maintenant."""
        deals = sorted(self._bot_deals_today(), key=lambda d: d.time)
        streak = 0
        for d in reversed(deals):
            if d.profit < 0:
                streak += 1
            else:
                break
        return streak

    # ----------------------------------------------------------
    # DECISION
    # ----------------------------------------------------------
    def status(self):
        """
        Retourne (can_trade: bool, reason: str).
        Toute regle traversee -> can_trade = False.
        On lève le pied AVANT que le compte ne saigne.
        """
        deals = self._bot_deals_today()

        # --- Regle 1 : Perte journaliere ---
        pnl = sum(d.profit for d in deals)
        account = mt5.account_info()
        if account and account.balance > 0:
            loss_pct = (pnl / account.balance) * 100.0
            if loss_pct <= -self.max_daily_loss_pct:
                return False, f"STOP PERTE JOURNALIERE: {loss_pct:.2f}% <= -{self.max_daily_loss_pct}%"

        # --- Regle 2 : Trop de trades ---
        if len(deals) >= self.max_daily_trades:
            return False, f"MAX TRADES/JOUR atteint ({len(deals)}/{self.max_daily_trades})"

        # --- Regle 3 : Serie de pertes ---
        streak = self.consecutive_losses()
        if streak >= self.max_consec_losses:
            return False, f"{streak} pertes consecutives (max {self.max_consec_losses}) -> pause 24h"

        return True, "OK"

    def report(self):
        """Petit tableau de bord pour les logs."""
        return (f"P&L jour: {self.daily_pnl():+.2f} | "
                f"Trades: {self.daily_trade_count()} | "
                f"Series pertes: {self.consecutive_losses()}")
