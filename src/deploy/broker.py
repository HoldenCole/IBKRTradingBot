"""Broker abstraction for the Stage-1 deployment.

Two responsibilities:
  1. Define a narrow Protocol (`StockBroker`) covering exactly what the
     order-workflow needs: NAV, positions, place MOO/MKT orders, poll
     fills. No options, no Greeks, no FillChase.
  2. Provide an in-memory `SimStockBroker` for unit tests and a thin
     `IBKRStockBroker` adapter for live (paper or production) trading.

The Protocol design lets the order workflow be 100% testable without a
live IBKR Gateway. The IBKR adapter is intentionally tiny: each method
maps directly to ib_insync calls and is validated against a paper
account during the integration dry-run.

Inherits TWO patterns from the legacy ibkr_adapter that ARE correct:
  - lazy import of ib_insync (so this module imports on machines
    without the package installed — important for CI)
  - SMART routing + USD for US equity symbols (QQQ, IBIT, SGOV)

What this module does NOT do:
  - select_option / option chains (options strategy is abandoned)
  - intraday limit-order ladders (FillChase)
  - quote streaming (the daily-bar SMA strategy doesn't need it)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

_log = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Stage-1 supports two order types — that's all the strategy needs."""
    MOO = "MOO"        # Market-on-open, fills at next session's opening auction
    MKT = "MKT"        # Plain market order, fills immediately during RTH


class OrderState(str, Enum):
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Position:
    """A held position. Stage 1: long-only equity-class instruments
    (QQQ, IBIT, SGOV)."""
    symbol: str
    quantity: float          # shares; integer-valued in Stage 1
    avg_cost: float          # average cost basis per share
    market_value: float      # current MV (informational; nav() is authoritative)


@dataclass
class OrderTicket:
    """The result of placing an order. order_id is broker-assigned;
    everything else is the strategy's record of what we asked for.
    """
    order_id: str
    symbol: str
    side: str                # "BUY" | "SELL"
    quantity: float
    order_type: OrderType
    state: OrderState
    avg_fill_price: float | None = None
    filled_quantity: float = 0.0
    note: str = ""


class StockBroker(Protocol):
    """The minimal broker interface the order workflow needs.

    All methods are async. Implementations should be idempotent on
    repeated reads (`nav`, `positions`, `order_status`) and report errors
    by raising exceptions (no None-returns for failures).
    """

    async def nav(self) -> float:
        """Net liquidation value (account equity in USD)."""
        ...

    async def positions(self) -> dict[str, Position]:
        """All currently held positions, keyed by symbol."""
        ...

    async def place_order(
        self, symbol: str, side: str, quantity: float, order_type: OrderType,
    ) -> OrderTicket:
        """Submit an order. Returns a ticket with broker-assigned order_id.
        Does NOT block waiting for fill; use order_status to poll."""
        ...

    async def order_status(self, order_id: str) -> OrderTicket:
        """Look up a previously-submitted order's current state."""
        ...

    async def cancel(self, order_id: str) -> None:
        """Best-effort cancel. Idempotent if order is already filled/cancelled."""
        ...


# =====================================================================
# In-memory SimStockBroker — used by tests and by the integration dry-run
# =====================================================================
@dataclass
class _SimOrderState:
    """Internal state of a sim order; mirrors OrderTicket but mutable."""
    ticket: OrderTicket
    next_session_fill_price: float | None = None


@dataclass
class SimStockBroker:
    """Deterministic broker simulator.

    Tracks NAV, positions, and orders in memory. Order fills are
    triggered by explicit calls (`fill_pending_orders` for MKT; advance
    the clock and call `open_session` for MOO). This makes tests
    fully deterministic — no flakiness from polling or timing.
    """
    starting_cash: float = 8000.0
    _cash: float = field(init=False)
    _positions: dict[str, Position] = field(default_factory=dict)
    _orders: dict[str, _SimOrderState] = field(default_factory=dict)
    _next_order_id: int = field(default=1, init=False)
    # Set by tests via set_quote() — gives the broker a current price for
    # NAV calculation and immediate-fill MKT orders.
    _quotes: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._cash = self.starting_cash

    # ----- test helpers -----
    def set_quote(self, symbol: str, price: float) -> None:
        self._quotes[symbol] = float(price)

    def set_open_price(self, symbol: str, price: float) -> None:
        """The price MOO orders for this symbol will fill at on next session_open()."""
        self._quotes[symbol] = float(price)

    def session_open(self) -> list[OrderTicket]:
        """Fill all SUBMITTED MOO orders at their symbol's opening price."""
        filled = []
        for st in self._orders.values():
            if st.ticket.state != OrderState.SUBMITTED:
                continue
            if st.ticket.order_type != OrderType.MOO:
                continue
            price = self._quotes.get(st.ticket.symbol)
            if price is None:
                raise RuntimeError(
                    f"no open price set for {st.ticket.symbol}; "
                    f"call set_open_price() before session_open()")
            self._fill(st, price)
            filled.append(st.ticket)
        return filled

    # ----- StockBroker Protocol -----
    async def nav(self) -> float:
        equity = self._cash
        for pos in self._positions.values():
            px = self._quotes.get(pos.symbol, pos.avg_cost)
            equity += pos.quantity * px
        return float(equity)

    async def positions(self) -> dict[str, Position]:
        # Refresh market_value from current quote
        out: dict[str, Position] = {}
        for sym, pos in self._positions.items():
            px = self._quotes.get(sym, pos.avg_cost)
            out[sym] = Position(symbol=sym, quantity=pos.quantity,
                                avg_cost=pos.avg_cost,
                                market_value=pos.quantity * px)
        return out

    async def place_order(
        self, symbol: str, side: str, quantity: float, order_type: OrderType,
    ) -> OrderTicket:
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")
        oid = f"SIM-{self._next_order_id}"
        self._next_order_id += 1
        ticket = OrderTicket(
            order_id=oid, symbol=symbol, side=side, quantity=quantity,
            order_type=order_type, state=OrderState.SUBMITTED,
        )
        st = _SimOrderState(ticket=ticket)
        self._orders[oid] = st
        # MKT fills immediately at current quote
        if order_type == OrderType.MKT:
            price = self._quotes.get(symbol)
            if price is None:
                raise RuntimeError(f"no quote for {symbol}; set_quote() first")
            self._fill(st, price)
        return st.ticket

    async def order_status(self, order_id: str) -> OrderTicket:
        st = self._orders.get(order_id)
        if st is None:
            raise KeyError(f"unknown order_id {order_id}")
        return st.ticket

    async def cancel(self, order_id: str) -> None:
        st = self._orders.get(order_id)
        if st is None:
            return
        if st.ticket.state == OrderState.SUBMITTED:
            st.ticket.state = OrderState.CANCELLED

    # ----- internal -----
    def _fill(self, st: _SimOrderState, price: float) -> None:
        t = st.ticket
        qty = t.quantity
        cost = qty * price
        if t.side == "BUY":
            if cost > self._cash + 1e-9:
                t.state = OrderState.REJECTED
                t.note = "insufficient cash"
                return
            self._cash -= cost
            pos = self._positions.get(t.symbol)
            if pos is None:
                self._positions[t.symbol] = Position(
                    symbol=t.symbol, quantity=qty, avg_cost=price,
                    market_value=qty * price)
            else:
                new_qty = pos.quantity + qty
                new_cost = (pos.quantity * pos.avg_cost + qty * price) / new_qty
                self._positions[t.symbol] = Position(
                    symbol=t.symbol, quantity=new_qty, avg_cost=new_cost,
                    market_value=new_qty * price)
        else:  # SELL
            pos = self._positions.get(t.symbol)
            if pos is None or pos.quantity < qty - 1e-9:
                t.state = OrderState.REJECTED
                t.note = f"insufficient position ({pos.quantity if pos else 0} < {qty})"
                return
            self._cash += cost
            remaining = pos.quantity - qty
            if remaining < 1e-9:
                del self._positions[t.symbol]
            else:
                self._positions[t.symbol] = Position(
                    symbol=t.symbol, quantity=remaining,
                    avg_cost=pos.avg_cost, market_value=remaining * price)
        t.state = OrderState.FILLED
        t.avg_fill_price = price
        t.filled_quantity = qty


# =====================================================================
# IBKR adapter — thin translation to ib_insync
# =====================================================================
@dataclass
class IBKRStockBroker:
    """Live broker adapter. Lazy-imports ib_insync; not unit-tested
    here (the SimStockBroker covers the workflow). Validated against the
    paper account during the integration dry-run.
    """
    ib: object  # ib_insync.IB instance (post-connect)

    async def nav(self) -> float:
        for row in self.ib.accountSummary():
            if row.tag == "NetLiquidation":
                return float(row.value)
        raise RuntimeError("NetLiquidation not in accountSummary")

    async def positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for p in self.ib.positions():
            sym = getattr(p.contract, "symbol", None)
            if not sym:
                continue
            out[sym] = Position(
                symbol=sym, quantity=float(p.position),
                avg_cost=float(p.avgCost),
                market_value=float(p.position) * float(p.avgCost),
            )
        return out

    async def place_order(
        self, symbol: str, side: str, quantity: float, order_type: OrderType,
    ) -> OrderTicket:
        from ib_insync import Stock, MarketOrder
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")
        c = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(c)
        # TIF="OPG" = at-the-open (MOO). Default TIF (DAY) for plain MKT.
        order = MarketOrder(side, quantity)
        if order_type == OrderType.MOO:
            order.tif = "OPG"
        trade = self.ib.placeOrder(c, order)
        order_id = str(trade.order.permId or trade.order.orderId)
        _log.info("placed %s %s %s %s -> order_id=%s",
                  order_type.value, side, quantity, symbol, order_id)
        return OrderTicket(
            order_id=order_id, symbol=symbol, side=side, quantity=quantity,
            order_type=order_type, state=OrderState.SUBMITTED,
        )

    async def order_status(self, order_id: str) -> OrderTicket:
        for trade in self.ib.trades():
            oid = str(trade.order.permId or trade.order.orderId)
            if oid != order_id:
                continue
            ib_status = trade.orderStatus.status
            sym = getattr(trade.contract, "symbol", "?")
            tif = getattr(trade.order, "tif", "DAY")
            ot = OrderType.MOO if tif == "OPG" else OrderType.MKT
            qty = float(trade.order.totalQuantity)
            side = str(trade.order.action)
            state = {
                "Filled": OrderState.FILLED,
                "Cancelled": OrderState.CANCELLED,
                "ApiCancelled": OrderState.CANCELLED,
                "Inactive": OrderState.REJECTED,
                "Rejected": OrderState.REJECTED,
            }.get(ib_status, OrderState.SUBMITTED)
            return OrderTicket(
                order_id=order_id, symbol=sym, side=side, quantity=qty,
                order_type=ot, state=state,
                avg_fill_price=(float(trade.orderStatus.avgFillPrice)
                                if state == OrderState.FILLED else None),
                filled_quantity=float(trade.orderStatus.filled or 0.0),
                note=str(ib_status),
            )
        raise KeyError(f"unknown order_id {order_id}")

    async def cancel(self, order_id: str) -> None:
        for trade in self.ib.openTrades():
            oid = str(trade.order.permId or trade.order.orderId)
            if oid == order_id:
                self.ib.cancelOrder(trade.order)
                return
        _log.warning("cancel: no open trade matching order_id=%s", order_id)
