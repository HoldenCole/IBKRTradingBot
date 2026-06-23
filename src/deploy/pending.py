"""Pending-order persistence + startup drain (closes KL-5).

The orchestrator places MOO orders that fill at the NEXT session's opening
auction — hours after the run that placed them returns. Between runs those
orders are "submitted but not yet known to be filled". Without persistence,
a restart forgets them and the overnight fill shows up as an
ORPHAN_POSITION at the next reconcile (broker has the shares, ledger
doesn't), halting trading.

This module fixes that:

  1. `PendingOrderStore` — atomic JSON persistence of submitted-but-
     unresolved orders, mirroring the StateStore / Ledger pattern. Carries
     enough to re-poll the broker and attribute the fill to a sleeve
     (`strategy_id`, which the broker itself doesn't know).

  2. `drain_pending` — runs at the START of every orchestrator run, BEFORE
     reconcile. For each persisted pending order it polls the broker:
       - FILLED      -> record into the ledger (as of the current trading
                        date — the fill settled at this session's open) and
                        drop from the pending set.
       - REJECTED /
         CANCELLED   -> drop from the pending set; surfaced for alerting.
       - SUBMITTED   -> still working; keep pending.
       - unknown to
         the broker  -> keep pending and surface (a possible lost order the
                        operator must investigate); never silently dropped.

Draining before reconcile is essential: it makes the ledger reflect the
overnight fills so reconcile compares a consistent picture instead of
halting on the expected MOO settlement.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from src.deploy.broker import OrderState, OrderTicket, OrderType, StockBroker
from src.deploy.portfolio import Ledger

_log = logging.getLogger(__name__)

_PENDING_SCHEMA_VERSION = 1


@dataclass
class PendingOrder:
    """A submitted order awaiting resolution. Persisted across runs.

    `strategy_id` is the sleeve attribution the broker doesn't track; it is
    what lets the drain record the fill into the right ledger sleeve.
    `placed_trading_date` is the run that placed the order (for audit); the
    drain records the fill as of the *current* run's trading date.
    """
    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    strategy_id: str
    placed_trading_date: date
    placed_utc: datetime

    @classmethod
    def from_ticket(cls, t: OrderTicket, trading_date: date,
                    now_utc: datetime | None = None) -> "PendingOrder":
        return cls(
            order_id=t.order_id, symbol=t.symbol, side=t.side,
            quantity=t.quantity, order_type=t.order_type.value,
            strategy_id=t.strategy_id, placed_trading_date=trading_date,
            placed_utc=now_utc or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id, "symbol": self.symbol,
            "side": self.side, "quantity": self.quantity,
            "order_type": self.order_type, "strategy_id": self.strategy_id,
            "placed_trading_date": self.placed_trading_date.isoformat(),
            "placed_utc": self.placed_utc.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PendingOrder":
        return cls(
            order_id=d["order_id"], symbol=d["symbol"], side=d["side"],
            quantity=float(d["quantity"]), order_type=d["order_type"],
            strategy_id=d.get("strategy_id", ""),
            placed_trading_date=date.fromisoformat(d["placed_trading_date"]),
            placed_utc=datetime.fromisoformat(d["placed_utc"]),
        )


class PendingOrderStore:
    """Atomically-persisted set of pending orders."""

    def __init__(self, path: Path):
        self.path = path
        self._pending: list[PendingOrder] = []

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text())
        if raw.get("schema_version") != _PENDING_SCHEMA_VERSION:
            raise RuntimeError(
                f"Pending-order store schema v{raw.get('schema_version')} != "
                f"expected v{_PENDING_SCHEMA_VERSION}: {self.path}")
        self._pending = [PendingOrder.from_dict(d)
                         for d in raw.get("pending", [])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _PENDING_SCHEMA_VERSION,
            "pending": [po.to_dict() for po in self._pending],
        }
        fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def all(self) -> list[PendingOrder]:
        return list(self._pending)

    def add(self, po: PendingOrder) -> None:
        self._pending.append(po)

    def replace(self, pending: list[PendingOrder]) -> None:
        self._pending = list(pending)

    @property
    def is_empty(self) -> bool:
        return not self._pending


@dataclass
class DrainResult:
    """What the drain did. The orchestrator turns this into ledger saves
    and alerts."""
    recorded: list[OrderTicket] = field(default_factory=list)   # filled -> ledger
    terminal: list[OrderTicket] = field(default_factory=list)   # rejected/cancelled
    still_pending: list[PendingOrder] = field(default_factory=list)
    unknown: list[PendingOrder] = field(default_factory=list)   # broker has no record
    errors: list[str] = field(default_factory=list)

    @property
    def had_activity(self) -> bool:
        return bool(self.recorded or self.terminal or self.unknown)


async def drain_pending(
    store: PendingOrderStore, broker: StockBroker, ledger: Ledger,
    trading_date: date,
) -> DrainResult:
    """Resolve every persisted pending order against the broker. Records
    fills into `ledger` (as of `trading_date`), updates `store` in place
    (caller saves both), and returns a DrainResult for alerting.

    Pure of alerting/printing: the orchestrator decides how to surface the
    result. Does NOT save the store or ledger — the caller does that once,
    after reconcile decisions, to keep the persistence ordering explicit.
    """
    result = DrainResult()
    keep: list[PendingOrder] = []

    for po in store.all():
        try:
            ticket = await broker.order_status(po.order_id)
        except KeyError:
            _log.warning("pending order %s unknown to broker; keeping pending "
                         "for operator review", po.order_id)
            result.unknown.append(po)
            keep.append(po)
            continue
        except Exception as exc:  # transient broker error: keep, surface
            result.errors.append(f"order_status({po.order_id}): {exc!r}")
            keep.append(po)
            continue

        if ticket.state == OrderState.FILLED:
            if ticket.avg_fill_price is None:
                result.errors.append(
                    f"{po.order_id} FILLED but no avg_fill_price; keeping pending")
                keep.append(po)
                continue
            qty = ticket.filled_quantity or po.quantity
            try:
                if po.side == "BUY":
                    ledger.record_buy(
                        strategy_id=po.strategy_id, symbol=po.symbol,
                        quantity=qty, price=ticket.avg_fill_price,
                        trade_date=trading_date)
                else:
                    ledger.record_sell(
                        strategy_id=po.strategy_id, symbol=po.symbol,
                        quantity=qty, price=ticket.avg_fill_price,
                        trade_date=trading_date)
            except Exception as exc:
                # e.g. SELL with no open lots — a real inconsistency. Keep
                # pending and surface; do NOT silently lose the fill.
                result.errors.append(
                    f"record fill {po.order_id} ({po.side} {qty} {po.symbol}): "
                    f"{exc!r}")
                keep.append(po)
                continue
            ticket.strategy_id = po.strategy_id
            result.recorded.append(ticket)
            _log.info("drained fill: %s %s %g %s @ %.2f -> ledger",
                      po.strategy_id, po.side, qty, po.symbol,
                      ticket.avg_fill_price)
        elif ticket.state in (OrderState.REJECTED, OrderState.CANCELLED):
            ticket.strategy_id = po.strategy_id
            result.terminal.append(ticket)
            _log.info("drained terminal: %s %s -> %s",
                      po.order_id, po.symbol, ticket.state.value)
        else:  # still SUBMITTED
            result.still_pending.append(po)
            keep.append(po)

    store.replace(keep)
    return result
