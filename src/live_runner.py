"""Paper/live runner for the CL1/USO spread strategy.

Polls quotes once per minute during RTH, feeds synchronized PairBars to
the strategy, and routes its signals through the OrderRouter. CL is data
only — orders go to USO exclusively.
"""

from __future__ import annotations

from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from loguru import logger

from src.broker.connection import IBConnection
from src.broker.orders import OrderRejected, OrderRouter, check_entry_spread
from src.config import Settings
from src.data.market_data import front_month_cl, qualify_uso
from src.risk.guardrails import Guardrails
from src.strategies.base import Action
from src.strategies.cl1_uso_spread import Cl1UsoSpreadStrategy, PairBar

ET = ZoneInfo("America/New_York")
RTH_START = dtime(9, 30)
RTH_END = dtime(16, 0)
FILL_WAIT_SECONDS = 30


def _now_et() -> datetime:
    return datetime.now(tz=ET)


def _in_rth(now: datetime) -> bool:
    return now.weekday() < 5 and RTH_START <= now.time() < RTH_END


class LiveRunner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.conn = IBConnection(settings)
        self.guardrails = Guardrails(settings.max_position_usd, settings.max_daily_loss_usd)
        self.strategy = Cl1UsoSpreadStrategy()
        self.router: OrderRouter | None = None
        self.uso = None
        self.cl = None
        self.uso_ticker = None
        self.cl_ticker = None
        self.open_shares = 0  # signed: + long, - short
        self.entry_price = 0.0

    # -- setup -----------------------------------------------------------

    def setup(self) -> None:
        self.conn.connect()
        ib = self.conn.ib
        self.router = OrderRouter(ib, self.settings, self.guardrails)
        self.uso = qualify_uso(ib)
        self.cl = front_month_cl(ib)
        self.uso_ticker = ib.reqMktData(self.uso)
        self.cl_ticker = ib.reqMktData(self.cl)
        ib.sleep(3)  # let first ticks arrive
        logger.info("Runner ready — mode={}", self.settings.mode)

    def _refresh_front_month(self) -> None:
        """Re-check the CL roll once per day; re-subscribe if it changed."""
        ib = self.conn.ib
        fresh = front_month_cl(ib)
        if self.cl is None or fresh.conId != self.cl.conId:
            logger.info(f"Rolling CL1 subscription to {fresh.localSymbol}")
            if self.cl is not None:
                ib.cancelMktData(self.cl)
            self.cl = fresh
            self.cl_ticker = ib.reqMktData(self.cl)
            ib.sleep(3)

    # -- quotes ----------------------------------------------------------

    @staticmethod
    def _price_of(ticker) -> float | None:
        bid, ask = ticker.bid, ticker.ask
        if bid and ask and bid > 0 and ask >= bid:
            return (bid + ask) / 2
        last = ticker.last or ticker.close
        return float(last) if last and last > 0 else None

    # -- order handling --------------------------------------------------

    def _await_fill(self, trade) -> float | None:
        """Wait for a fill; returns avg fill price or None after cancel."""
        ib = self.conn.ib
        waited = 0.0
        while waited < FILL_WAIT_SECONDS:
            ib.sleep(1)
            waited += 1
            if trade.orderStatus.status == "Filled":
                return float(trade.orderStatus.avgFillPrice)
            if trade.orderStatus.status in ("Cancelled", "Inactive"):
                return None
        ib.cancelOrder(trade.order)
        ib.sleep(2)
        if trade.orderStatus.status == "Filled":
            return float(trade.orderStatus.avgFillPrice)
        return None

    def _handle_entry(self, signal, now: datetime) -> None:
        ticker = self.uso_ticker
        try:
            check_entry_spread(ticker.bid or 0.0, ticker.ask or 0.0)
        except OrderRejected as exc:
            logger.warning(f"Entry skipped ({signal.reason}): {exc}")
            self.strategy.position = None
            return

        mid = (ticker.bid + ticker.ask) / 2
        shares = self.guardrails.size_shares(mid)
        if shares < 1:
            logger.warning("Entry skipped: cap too small for one share")
            self.strategy.position = None
            return

        action = "BUY" if signal.action is Action.BUY else "SELL"
        try:
            trade = self.router.place_limit(
                self.uso, action, shares, mid,
                is_entry=True, today=now.date(), reason=signal.reason,
            )
        except OrderRejected as exc:
            logger.warning(f"Entry rejected ({signal.reason}): {exc}")
            self.strategy.position = None
            return

        fill = self._await_fill(trade)
        if fill is None:
            logger.warning("Entry unfilled after chase window — standing down")
            self.strategy.position = None
            return
        self.open_shares = shares if action == "BUY" else -shares
        self.entry_price = fill
        logger.info(f"FILLED entry {action} {shares} USO @ {fill:.2f} ({signal.reason})")

    def _handle_close(self, signal, now: datetime) -> None:
        if self.open_shares == 0:
            return
        ticker = self.uso_ticker
        shares = abs(self.open_shares)
        closing_long = self.open_shares > 0
        action = "SELL" if closing_long else "BUY"
        # Marketable limit through the spread — exits must fill.
        if closing_long:
            price = (ticker.bid or self.entry_price) - 0.02
        else:
            price = (ticker.ask or self.entry_price) + 0.02

        trade = self.router.place_limit(
            self.uso, action, shares, price,
            is_entry=False, today=now.date(), reason=signal.reason,
        )
        fill = self._await_fill(trade)
        if fill is None:
            logger.error("Exit unfilled — retrying next bar")
            # Keep strategy flat-side state consistent: it already cleared
            # its position, so force another close attempt next minute.
            self.strategy.position = None
            return
        side = 1 if closing_long else -1
        pnl = side * (fill - self.entry_price) * shares
        self.guardrails.record_realized_pnl(pnl, now.date())
        logger.info(
            f"FILLED exit {action} {shares} USO @ {fill:.2f} pnl=${pnl:.2f} "
            f"({signal.reason}) | daily realized ${self.guardrails.realized_pnl(now.date()):.2f}"
        )
        self.open_shares = 0
        self.entry_price = 0.0

    # -- main loop -------------------------------------------------------

    def run(self) -> None:
        self.setup()
        ib = self.conn.ib
        last_roll_check: object = None
        logger.info("Entering main loop (1-min cadence, RTH only)")
        try:
            while True:
                self.conn.ensure_connected()
                now = _now_et()

                if not _in_rth(now):
                    if self.open_shares != 0:
                        logger.error("Position open outside RTH — flattening")
                        from src.strategies.base import Signal

                        self._handle_close(Signal(Action.CLOSE, "outside_rth"), now)
                    ib.sleep(60)
                    continue

                if last_roll_check != now.date():
                    self._refresh_front_month()
                    last_roll_check = now.date()

                cl_price = self._price_of(self.cl_ticker)
                uso_price = self._price_of(self.uso_ticker)
                if cl_price is None or uso_price is None:
                    logger.warning("Missing quote (cl={}, uso={}) — skipping bar", cl_price, uso_price)
                    ib.sleep(60)
                    continue

                bar = PairBar(ts=now, cl_close=cl_price, uso_close=uso_price)
                signal = self.strategy.on_bar(bar)
                state = self.strategy.last_state
                if state is not None:
                    logger.debug(f"z={state.z:+.2f} beta={state.beta:.3f} cl={cl_price:.2f} uso={uso_price:.2f}")

                if signal is not None:
                    logger.info(f"SIGNAL {signal.action.name}: {signal.reason}")
                    if signal.action is Action.CLOSE:
                        self._handle_close(signal, now)
                    else:
                        self._handle_entry(signal, now)

                ib.sleep(60)
        finally:
            if self.open_shares != 0:
                logger.error("Shutting down with an open position — flatten manually!")
            self.conn.disconnect()
