"""In-memory simulated Broker + DataFeed for tests and dry runs.

You feed it pre-built daily bars, intraday bars, and a quote-fn. It plays
back deterministically. Order fills happen instantly at the limit price
(adequate for orchestration tests; the FillChase ladder has its own tests).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

import pandas as pd

from src.broker.orders import OrderResult, OrderStatus, Quote
from src.runner.broker import OptionContract


@dataclass
class SimBroker:
    """Implements `Broker`. Deterministic, used by tests and dry runs."""
    quote_fn: Callable[[str], Quote]
    underlying_fn: Callable[[str], float]
    nav_value: float = 8000.0
    next_order_id: int = 1
    orders: dict[str, dict] = field(default_factory=dict)

    async def quote(self, contract_id: str) -> Quote:
        return self.quote_fn(contract_id)

    async def underlying_price(self, symbol: str) -> float:
        return self.underlying_fn(symbol)

    async def select_option(
        self, underlying_etf, right, strike_offset, target_dte_min, target_dte_max,
    ) -> OptionContract:
        # Pick midpoint of the DTE range and a strike == round(price) + offset.
        from datetime import datetime
        mid_dte = (target_dte_min + target_dte_max) // 2
        spot = await self.underlying_price(underlying_etf)
        strike = round(spot) + strike_offset
        expiry = (datetime.utcnow().date() + timedelta(days=mid_dte))
        cid = f"{underlying_etf}_{right}_{strike}_{expiry.isoformat()}"
        return OptionContract(
            id=cid, underlying_etf=underlying_etf, right=right,
            strike=float(strike), expiry=expiry,
        )

    async def place_limit(self, contract_id, side, contracts, limit_price):
        oid = f"o{self.next_order_id}"
        self.next_order_id += 1
        # Instant fill at limit (sim simplification)
        self.orders[oid] = {
            "contract_id": contract_id, "side": side, "contracts": contracts,
            "limit_price": limit_price, "status": OrderStatus.FILLED,
            "fill_price": limit_price,
        }
        return oid

    async def cancel(self, order_id):
        if order_id in self.orders and self.orders[order_id]["status"] is OrderStatus.PENDING:
            self.orders[order_id]["status"] = OrderStatus.CANCELLED

    async def order_status(self, order_id) -> OrderResult:
        o = self.orders[order_id]
        return OrderResult(
            status=o["status"],
            fill_price=o.get("fill_price"),
            contracts=o["contracts"],
            detail="sim",
        )

    async def nav(self) -> float:
        return self.nav_value


@dataclass
class SimFeed:
    """Implements `DataFeed`. Holds DataFrames keyed by symbol."""
    daily: dict[str, pd.DataFrame] = field(default_factory=dict)
    session: dict[str, pd.DataFrame] = field(default_factory=dict)

    async def daily_bars(self, symbol: str, lookback_days: int = 400) -> pd.DataFrame:
        return self.daily.get(symbol, pd.DataFrame()).tail(lookback_days)

    async def session_bars(self, symbol: str, bar_size: str = "5 mins") -> pd.DataFrame:
        return self.session.get(symbol, pd.DataFrame())
