"""Portfolio ledger: tax lots, realized P&L, and per-strategy + per-basket
aggregation.

The ledger is the persistent record of every share ever bought or sold,
tracked at the LOT level. From it we can produce:
  - per-strategy realized P&L
  - per-basket realized P&L (aggregating strategies)
  - per-strategy / per-basket open-position market value (with current quotes)
  - per-strategy / per-basket drawdown via the equity curve (item #13)
  - tax-ready realized-gain log with ST/LT classification + wash-sale flag
    for QQQ shares (item #9)

LOCKED DECISIONS this module implements (from the locked Operational Spec):
  - Tax-lot method: HIFO (highest-cost-first) on sells. This MINIMIZES
    realized gains and aligns with the IBKR account-default we're setting.
  - Wash-sale tracking applies ONLY to QQQ shares. Other symbols (SGOV,
    IBIT, futures) are exempt or out-of-scope here.
  - Strategy attribution: every lot carries its origin strategy_id so
    proceeds and gains are unambiguously attributable. SGOV lots are
    attributed to the strategy that bought them (the sleeve that was
    parked in cash).

What this module does NOT do:
  - Fetch quotes (caller provides current-price dict to mark_to_market)
  - Talk to the broker (the order workflow does that; this module
    consumes fill events)
  - Persist itself (a thin StateStore-like wrapper can be added when
    needed; the LedgerSnapshot dataclass is serialization-ready)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Iterable

_log = logging.getLogger(__name__)

# Wash-sale window per IRC §1091: 30 days before AND 30 days after.
_WASH_SALE_DAYS = 30

# Locked: only QQQ shares are wash-sale-tracked.
# (SGOV is held in interest-equivalent role; IBIT could be in theory but
#  Stage-1 short-term holds rarely realize losses there. Adding more
#  later is a 1-line change.)
_WASH_SALE_SYMBOLS = frozenset({"QQQ"})


class LotStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class TaxLot:
    """One purchased batch of shares. Sells consume lots in HIFO order.

    `lot_id` is internally generated (UUID-prefix) for stable references
    across persistence. `parent_lot_id` is set on lots that inherit a
    wash-sale-disallowed loss from a prior closed lot (the basis is
    augmented and the holding period is inherited).
    """
    lot_id: str
    strategy_id: str
    symbol: str
    quantity: float           # remaining open quantity (decreases on sell)
    original_quantity: float
    cost_basis_per_share: float
    open_date: date
    status: LotStatus = LotStatus.OPEN
    parent_lot_id: str | None = None
    disallowed_wash_basis_addon: float = 0.0  # added to cost basis from a prior wash-sale loss

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price


@dataclass
class RealizedSale:
    """One sell event, post-HIFO-matching. Each row in this list is a
    closure of part-or-all of ONE tax lot.

    For tax reporting: a sell that consumes multiple lots produces multiple
    RealizedSale rows (one per lot consumed). This matches the 1099-B row
    structure.
    """
    sale_id: str
    strategy_id: str
    symbol: str
    sell_date: date
    quantity: float
    sale_price: float
    cost_basis_per_share: float        # the closed lot's basis
    open_date: date                    # for ST/LT determination
    realized_pnl: float                # (sale_price - basis) * qty
    is_long_term: bool                 # True if held > 1 year (calendar)
    closed_lot_id: str
    # Wash-sale: if this sale realized a LOSS and a replacement purchase
    # occurred within +/- 30 days, the loss is DISALLOWED for tax purposes
    # and added to the replacement lot's basis.
    wash_sale_disallowed_loss: float = 0.0
    wash_sale_replacement_lot_id: str | None = None


@dataclass
class LedgerSnapshot:
    """A point-in-time view of the ledger for reporting / persistence."""
    open_lots_by_symbol: dict[str, list[TaxLot]]
    realized_sales: list[RealizedSale]
    cash_by_strategy: dict[str, float]   # informational; broker is authoritative

    def open_quantity(self, symbol: str) -> float:
        return sum(lot.quantity for lot in self.open_lots_by_symbol.get(symbol, ()))


class Ledger:
    """The portfolio ledger. Stateful (open lots + realized history)."""

    def __init__(self) -> None:
        # symbol -> list of open lots (FIFO order of insertion; HIFO order
        # of sell-matching is computed on each sell, not maintained here)
        self._open: dict[str, list[TaxLot]] = {}
        self._closed: list[TaxLot] = []
        self._realized: list[RealizedSale] = []
        self._cash_by_strategy: dict[str, float] = {}

    # ----- mutation -----

    def record_buy(
        self, *, strategy_id: str, symbol: str, quantity: float,
        price: float, trade_date: date, lot_id: str | None = None,
    ) -> TaxLot:
        """Record a fill from a BUY order. Optionally attaches to a
        previously-disallowed wash-sale loss (the order workflow doesn't
        know about wash-sales; this is computed here as a post-step on
        record_sell)."""
        lot = TaxLot(
            lot_id=lot_id or f"L-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id, symbol=symbol,
            quantity=quantity, original_quantity=quantity,
            cost_basis_per_share=price, open_date=trade_date,
        )
        self._open.setdefault(symbol, []).append(lot)
        # Cash bookkeeping (informational)
        self._cash_by_strategy[strategy_id] = (
            self._cash_by_strategy.get(strategy_id, 0.0) - quantity * price)
        # Apply wash-sale basis add-on if a prior disallowed loss is waiting
        # for a replacement lot in this symbol/strategy.
        self._apply_pending_wash_sale(lot, trade_date)
        return lot

    def record_sell(
        self, *, strategy_id: str, symbol: str, quantity: float,
        price: float, trade_date: date,
    ) -> list[RealizedSale]:
        """Record fills from a SELL order. Matches against open lots in
        HIFO order. Returns the RealizedSale rows produced (one per lot
        consumed). Wash-sale flagging is applied immediately if a
        replacement lot already exists; otherwise the loss is held
        pending until a future buy.
        """
        open_for_sym = self._open.get(symbol, [])
        if not open_for_sym:
            raise ValueError(f"no open lots to sell for {symbol}")
        # HIFO: sort by cost_basis_per_share descending (highest first)
        # to MINIMIZE realized gains (or maximize realized losses, which
        # is fine — wash-sale handling is downstream).
        ordered = sorted(open_for_sym,
                         key=lambda L: -(L.cost_basis_per_share
                                         + L.disallowed_wash_basis_addon))
        remaining = quantity
        sales: list[RealizedSale] = []
        for lot in ordered:
            if remaining <= 1e-9:
                break
            take = min(lot.quantity, remaining)
            adjusted_basis = (lot.cost_basis_per_share
                              + lot.disallowed_wash_basis_addon)
            pnl = (price - adjusted_basis) * take
            is_lt = (trade_date - lot.open_date).days > 365
            sale = RealizedSale(
                sale_id=f"S-{uuid.uuid4().hex[:8]}",
                strategy_id=strategy_id, symbol=symbol, sell_date=trade_date,
                quantity=take, sale_price=price,
                cost_basis_per_share=adjusted_basis,
                open_date=lot.open_date, realized_pnl=pnl,
                is_long_term=is_lt, closed_lot_id=lot.lot_id,
            )
            sales.append(sale)
            lot.quantity -= take
            remaining -= take
            if lot.quantity <= 1e-9:
                lot.status = LotStatus.CLOSED
                open_for_sym.remove(lot)
                self._closed.append(lot)

        if remaining > 1e-9:
            raise ValueError(
                f"insufficient open quantity for sell: {symbol} "
                f"requested {quantity}, short {remaining}")

        # Cash bookkeeping
        self._cash_by_strategy[strategy_id] = (
            self._cash_by_strategy.get(strategy_id, 0.0) + quantity * price)
        # Apply wash-sale rule if any of these sales were losses
        for sale in sales:
            if sale.realized_pnl < 0 and sale.symbol in _WASH_SALE_SYMBOLS:
                self._maybe_flag_wash_sale(sale)
        self._realized.extend(sales)
        return sales

    # ----- queries -----

    def open_lots(self, symbol: str | None = None) -> list[TaxLot]:
        if symbol is None:
            return [L for lots in self._open.values() for L in lots]
        return list(self._open.get(symbol, ()))

    def realized_sales(self) -> list[RealizedSale]:
        return list(self._realized)

    def mark_to_market(self, prices: dict[str, float]) -> dict[str, float]:
        """Return {symbol: total market value of open lots in that symbol}.
        Missing symbols default to using cost basis (warning logged)."""
        out: dict[str, float] = {}
        for symbol, lots in self._open.items():
            px = prices.get(symbol)
            if px is None:
                _log.warning("no quote for %s during mark_to_market; using basis", symbol)
                out[symbol] = sum(L.quantity * L.cost_basis_per_share for L in lots)
            else:
                out[symbol] = sum(L.quantity * px for L in lots)
        return out

    def market_value_by_strategy(self, prices: dict[str, float]) -> dict[str, float]:
        """{strategy_id: total MV of open lots} attributed by lot.strategy_id."""
        out: dict[str, float] = {}
        for lots in self._open.values():
            for L in lots:
                px = prices.get(L.symbol, L.cost_basis_per_share)
                out[L.strategy_id] = out.get(L.strategy_id, 0.0) + L.quantity * px
        return out

    def open_shares_by_strategy(self, symbol: str) -> dict[str, float]:
        """{strategy_id: total open shares of `symbol`} attributed by
        lot.strategy_id.

        Used to size per-sleeve OFF-vehicle (SGOV) sells: a sleeve entering
        the risk asset should sell only the SGOV *it* parked, not the pooled
        broker balance shared across sleeves."""
        out: dict[str, float] = {}
        for lot in self._open.get(symbol, []):
            out[lot.strategy_id] = out.get(lot.strategy_id, 0.0) + lot.quantity
        return out

    def realized_pnl_by_strategy(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for s in self._realized:
            out[s.strategy_id] = out.get(s.strategy_id, 0.0) + s.realized_pnl
        return out

    def realized_pnl_by_basket(
        self, strategy_to_basket: dict[str, str],
    ) -> dict[str, float]:
        out: dict[str, float] = {}
        for s in self._realized:
            bid = strategy_to_basket.get(s.strategy_id, "?")
            out[bid] = out.get(bid, 0.0) + s.realized_pnl
        return out

    def snapshot(self) -> LedgerSnapshot:
        return LedgerSnapshot(
            open_lots_by_symbol={s: list(ls) for s, ls in self._open.items()},
            realized_sales=list(self._realized),
            cash_by_strategy=dict(self._cash_by_strategy),
        )

    # ----- wash-sale internals -----

    def _maybe_flag_wash_sale(self, sale: RealizedSale) -> None:
        """If a replacement lot in the same symbol/strategy exists within
        the wash-sale window (±30 days of sale_date), flag the loss as
        disallowed and add it to that lot's basis.

        `disallowed_wash_basis_addon` is per-share (matching the cost_basis
        field it's added to). The TOTAL disallowed loss / replacement
        lot's quantity = per-share addon. For Stage-1 symmetric flips
        (sell N, buy N) this fully passes the loss through; for asymmetric
        cases the cap is loss/qty per share."""
        replacements = self._find_wash_replacements(
            sale.symbol, sale.strategy_id, sale.sell_date)
        if not replacements:
            return
        replacement = replacements[0]
        total_loss = -sale.realized_pnl  # positive dollar amount
        # Only the loss on the number of shares actually replaced is
        # disallowed (IRC §1091). Replaced shares = min(sold, repurchased).
        matched_shares = min(sale.quantity, replacement.original_quantity)
        disallowed = total_loss * (matched_shares / sale.quantity)
        # Spread the disallowed dollars over the replacement lot as a
        # per-share basis addon (total addon == disallowed dollars).
        per_share_addon = disallowed / replacement.original_quantity
        replacement.disallowed_wash_basis_addon += per_share_addon
        sale.wash_sale_disallowed_loss = disallowed
        sale.wash_sale_replacement_lot_id = replacement.lot_id
        _log.info("wash-sale: $%.2f disallowed on sale %s; basis +$%.4f/share on lot %s",
                  disallowed, sale.sale_id, per_share_addon, replacement.lot_id)

    def _apply_pending_wash_sale(self, new_lot: TaxLot, buy_date: date) -> None:
        """When a buy occurs, check recent realized sales (within 30 days
        prior) in the SAME symbol/strategy that haven't yet been matched
        to a replacement. If found, retroactively disallow the loss.

        Same per-share semantics as _maybe_flag_wash_sale: divide the
        disallowed dollar amount by the new lot's quantity so the addon
        matches the cost-basis-per-share field it adds to."""
        if new_lot.symbol not in _WASH_SALE_SYMBOLS:
            return
        cutoff = buy_date - timedelta(days=_WASH_SALE_DAYS)
        for sale in self._realized:
            if sale.symbol != new_lot.symbol:
                continue
            if sale.strategy_id != new_lot.strategy_id:
                continue
            if sale.wash_sale_replacement_lot_id is not None:
                continue
            if sale.realized_pnl >= 0:
                continue
            if sale.sell_date < cutoff:
                continue
            total_loss = -sale.realized_pnl
            matched_shares = min(sale.quantity, new_lot.original_quantity)
            disallowed = total_loss * (matched_shares / sale.quantity)
            per_share_addon = disallowed / new_lot.original_quantity
            new_lot.disallowed_wash_basis_addon += per_share_addon
            sale.wash_sale_disallowed_loss = disallowed
            sale.wash_sale_replacement_lot_id = new_lot.lot_id
            _log.info("wash-sale (pending->matched): $%.2f from sale %s "
                      "to lot %s (+$%.4f/share)",
                      disallowed, sale.sale_id, new_lot.lot_id, per_share_addon)

    def _find_wash_replacements(
        self, symbol: str, strategy_id: str, sell_date: date,
    ) -> list[TaxLot]:
        """Open lots in the same symbol/strategy purchased within +/- 30
        days of sell_date that don't already have a disallowed basis
        attached. ('Replacement' here means a lot that triggers wash-sale
        on a prior loss; this function is called immediately after a
        loss sale, so it returns lots bought BEFORE the sale within
        window — buys AFTER the sale go through _apply_pending_wash_sale.)
        """
        cutoff = sell_date - timedelta(days=_WASH_SALE_DAYS)
        return [
            L for L in self._open.get(symbol, [])
            if L.strategy_id == strategy_id
            and L.open_date >= cutoff
            and L.open_date <= sell_date
            and L.disallowed_wash_basis_addon == 0.0
        ]
