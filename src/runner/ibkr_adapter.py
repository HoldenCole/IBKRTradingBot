"""IBKR-backed implementations of `Broker` and `DataFeed`.

This module is a translation layer: each method maps directly to ib_insync
calls. It cannot be unit-tested without a live Gateway connection — the
runner orchestration tests use `SimBroker` / `SimFeed`. Validation against
your paper account happens via `python -m src.main --check-connection`
plus exercising the strategy in paper.

ib_insync is imported lazily so this module can be imported on machines
without the package installed (e.g., in CI for static checks).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

from src.broker.orders import OrderResult, OrderStatus, Quote
from src.runner.broker import OptionContract

ET = ZoneInfo("America/New_York")


@dataclass
class IBKRBroker:
    """Implements `Broker` against ib_insync.IB."""
    ib: object  # ib_insync.IB

    async def quote(self, contract_id: str) -> Quote:
        # Re-resolve the contract by conId. ib_insync caches qualifications.
        from ib_insync import Contract
        c = Contract(conId=int(contract_id))
        self.ib.qualifyContracts(c)
        ticker = self.ib.reqMktData(c, "", False, False)
        # Wait for a tick. In production, callers should use streaming
        # subscriptions; this synchronous form is for one-off lookups.
        for _ in range(20):
            self.ib.sleep(0.1)
            if ticker.bid is not None and ticker.ask is not None and ticker.bid > 0:
                break
        bid = float(ticker.bid or 0.0)
        ask = float(ticker.ask or 0.0)
        return Quote(bid=bid, ask=ask)

    async def underlying_price(self, symbol: str) -> float:
        from ib_insync import Stock
        c = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(c)
        ticker = self.ib.reqMktData(c, "", False, False)
        for _ in range(20):
            self.ib.sleep(0.1)
            if ticker.last is not None and ticker.last > 0:
                return float(ticker.last)
            if ticker.marketPrice() and ticker.marketPrice() > 0:
                return float(ticker.marketPrice())
        raise RuntimeError(f"no underlying price for {symbol}")

    async def select_option(
        self, underlying_etf, right, strike_offset, target_dte_min, target_dte_max,
    ) -> OptionContract:
        """Pick the most-liquid contract in the requested DTE window with
        strike = round(spot) + strike_offset (ATM=0, 1-strike-ITM=-1 for calls).
        """
        from ib_insync import Option, Stock
        spot = await self.underlying_price(underlying_etf)
        target_strike = round(spot) + strike_offset
        chain = self.ib.reqSecDefOptParams(
            underlyingSymbol=underlying_etf,
            futFopExchange="",
            underlyingSecType="STK",
            underlyingConId=Stock(underlying_etf, "SMART", "USD").conId or 0,
        )
        # Pick one chain row (SMART exchange)
        chain_row = next((c for c in chain if c.exchange == "SMART"), chain[0])
        today = datetime.now(tz=ET).date()
        valid_expiries = [
            e for e in sorted(chain_row.expirations)
            if target_dte_min <= (datetime.strptime(e, "%Y%m%d").date() - today).days <= target_dte_max
        ]
        if not valid_expiries:
            raise RuntimeError(
                f"no expiries in DTE window [{target_dte_min},{target_dte_max}] "
                f"for {underlying_etf}"
            )
        expiry_str = valid_expiries[0]  # closest in window

        # Snap target_strike to the nearest available strike
        avail = sorted(chain_row.strikes)
        strike = min(avail, key=lambda s: abs(s - target_strike))

        opt = Option(
            symbol=underlying_etf,
            lastTradeDateOrContractMonth=expiry_str,
            strike=strike,
            right=right,
            exchange="SMART",
            currency="USD",
        )
        self.ib.qualifyContracts(opt)
        return OptionContract(
            id=str(opt.conId),
            underlying_etf=underlying_etf,
            right=right,
            strike=float(strike),
            expiry=datetime.strptime(expiry_str, "%Y%m%d").date(),
        )

    async def place_limit(self, contract_id, side, contracts, limit_price) -> str:
        from ib_insync import Contract, LimitOrder
        c = Contract(conId=int(contract_id))
        self.ib.qualifyContracts(c)
        action = "BUY" if side == "buy" else "SELL"
        order = LimitOrder(action, contracts, limit_price)
        trade = self.ib.placeOrder(c, order)
        return str(trade.order.permId or trade.order.orderId)

    async def cancel(self, order_id):
        # Match by orderId. In practice you'd track the Trade object directly.
        for trade in self.ib.openTrades():
            if str(trade.order.permId) == order_id or str(trade.order.orderId) == order_id:
                self.ib.cancelOrder(trade.order)
                return
        logger.warning(f"cancel: no open trade matching order_id={order_id}")

    async def order_status(self, order_id) -> OrderResult:
        for trade in self.ib.trades():
            oid = str(trade.order.permId or trade.order.orderId)
            if oid != order_id:
                continue
            status = trade.orderStatus.status
            if status in ("Filled",):
                return OrderResult(
                    OrderStatus.FILLED,
                    float(trade.orderStatus.avgFillPrice),
                    int(trade.orderStatus.filled),
                    "filled",
                )
            if status in ("Cancelled", "ApiCancelled"):
                return OrderResult(OrderStatus.CANCELLED, None, 0, status)
            if status in ("Inactive", "Rejected"):
                return OrderResult(OrderStatus.REJECTED, None, 0, status)
            return OrderResult(OrderStatus.PENDING, None, 0, status)
        return OrderResult(OrderStatus.PENDING, None, 0, "unknown")

    async def nav(self) -> float:
        for row in self.ib.accountSummary():
            if row.tag == "NetLiquidation":
                return float(row.value)
        raise RuntimeError("NetLiquidation not in accountSummary")


@dataclass
class IBKRDataFeed:
    """Implements `DataFeed` against ib_insync.IB."""
    ib: object

    async def daily_bars(self, symbol: str, lookback_days: int = 400) -> pd.DataFrame:
        from ib_insync import Stock
        c = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(c)
        bars = self.ib.reqHistoricalData(
            c, endDateTime="", durationStr=f"{lookback_days} D",
            barSizeSetting="1 day", whatToShow="TRADES", useRTH=True, formatDate=1,
        )
        return _bars_to_df(bars, set_tz=False)

    async def session_bars(self, symbol: str, bar_size: str = "5 mins") -> pd.DataFrame:
        from ib_insync import Stock
        c = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(c)
        bars = self.ib.reqHistoricalData(
            c, endDateTime="", durationStr="1 D",
            barSizeSetting=bar_size, whatToShow="TRADES", useRTH=True, formatDate=1,
        )
        return _bars_to_df(bars, set_tz=True)


def _bars_to_df(bars, set_tz: bool) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    rows = []
    for b in bars:
        ts = b.date
        if isinstance(ts, datetime):
            if set_tz and ts.tzinfo is None:
                ts = ts.replace(tzinfo=ET)
        else:
            ts = datetime.combine(ts, datetime.min.time())
        rows.append({"ts": ts, "open": b.open, "high": b.high, "low": b.low,
                     "close": b.close, "volume": b.volume})
    df = pd.DataFrame(rows).set_index("ts").sort_index()
    return df
