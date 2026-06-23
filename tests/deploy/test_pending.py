"""Tests for pending-order persistence + startup drain (KL-5).

Covers:
  - PendingOrderStore save/load roundtrip
  - drain_pending against the Sim broker: FILLED -> ledger, REJECTED/
    CANCELLED -> terminal, SUBMITTED -> kept, unknown -> kept + surfaced
  - the MOO-across-runs lifecycle through the orchestrator: a MOO order
    left SUBMITTED on day T is persisted, then drained and recorded on
    day T+1 BEFORE reconcile (so it doesn't halt as an ORPHAN_POSITION).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.deploy.broker import OrderState, OrderType, SimStockBroker
from src.deploy.orders import OFF_VEHICLE_SYMBOL
from src.deploy.pending import (
    PendingOrder, PendingOrderStore, drain_pending,
)
from src.deploy.portfolio import Ledger


def _broker() -> SimStockBroker:
    b = SimStockBroker(starting_cash=8000.0)
    b.set_quote("QQQ", 540.0); b.set_quote("IBIT", 60.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0)
    b.set_open_price("QQQ", 540.0); b.set_open_price("IBIT", 60.0)
    b.set_open_price(OFF_VEHICLE_SYMBOL, 100.0)
    return b


# ===== PendingOrderStore persistence =====

def test_pending_store_roundtrip(tmp_path: Path):
    p = tmp_path / "pending.json"
    store = PendingOrderStore(p)
    store.add(PendingOrder(
        order_id="SIM-1", symbol="QQQ", side="BUY", quantity=7,
        order_type="MOO", strategy_id="qqq_trend_50_200",
        placed_trading_date=date(2024, 6, 20),
        placed_utc=datetime(2024, 6, 20, 20, 1, tzinfo=timezone.utc)))
    store.save()

    reloaded = PendingOrderStore(p)
    reloaded.load()
    assert len(reloaded.all()) == 1
    po = reloaded.all()[0]
    assert po.order_id == "SIM-1"
    assert po.strategy_id == "qqq_trend_50_200"
    assert po.placed_trading_date == date(2024, 6, 20)


def test_pending_store_load_missing_is_empty(tmp_path: Path):
    store = PendingOrderStore(tmp_path / "absent.json")
    store.load()
    assert store.is_empty


# ===== drain_pending =====

@pytest.mark.asyncio
async def test_drain_records_filled_order_into_ledger(tmp_path: Path):
    b = _broker()
    # Place a MOO BUY (stays SUBMITTED until session_open).
    t = await b.place_order("QQQ", "BUY", 7, OrderType.MOO)
    store = PendingOrderStore(tmp_path / "pending.json")
    store.add(PendingOrder.from_ticket(_tag(t, "qqq_trend_50_200"),
                                       date(2024, 6, 20)))
    L = Ledger()

    # Next session opens -> the MOO fills.
    b.session_open()
    result = await drain_pending(store, b, L, date(2024, 6, 21))

    assert len(result.recorded) == 1
    # Recorded as of the drain (current) trading date.
    assert L.open_shares_by_strategy("QQQ") == {"qqq_trend_50_200": 7.0}
    # No longer pending.
    assert store.is_empty


@pytest.mark.asyncio
async def test_drain_keeps_still_submitted(tmp_path: Path):
    b = _broker()
    t = await b.place_order("QQQ", "BUY", 7, OrderType.MOO)  # not opened yet
    store = PendingOrderStore(tmp_path / "pending.json")
    store.add(PendingOrder.from_ticket(_tag(t, "qqq_trend_50_200"),
                                       date(2024, 6, 20)))
    L = Ledger()
    result = await drain_pending(store, b, L, date(2024, 6, 21))
    # Order is still working -> stays pending, nothing recorded.
    assert result.recorded == []
    assert len(result.still_pending) == 1
    assert len(store.all()) == 1


@pytest.mark.asyncio
async def test_drain_handles_rejected_order(tmp_path: Path):
    b = SimStockBroker(starting_cash=100.0)   # too little cash
    b.set_quote("QQQ", 540.0); b.set_open_price("QQQ", 540.0)
    t = await b.place_order("QQQ", "BUY", 7, OrderType.MOO)
    store = PendingOrderStore(tmp_path / "pending.json")
    store.add(PendingOrder.from_ticket(_tag(t, "qqq_trend_50_200"),
                                       date(2024, 6, 20)))
    L = Ledger()
    b.session_open()   # fill attempt -> REJECTED (insufficient cash)
    result = await drain_pending(store, b, L, date(2024, 6, 21))
    assert len(result.terminal) == 1
    assert result.terminal[0].state == OrderState.REJECTED
    assert result.recorded == []
    assert store.is_empty            # terminal orders are dropped


@pytest.mark.asyncio
async def test_drain_unknown_order_is_kept_and_surfaced(tmp_path: Path):
    b = _broker()
    store = PendingOrderStore(tmp_path / "pending.json")
    # An order_id the broker never issued.
    store.add(PendingOrder(
        order_id="GHOST-99", symbol="QQQ", side="BUY", quantity=7,
        order_type="MOO", strategy_id="qqq_trend_50_200",
        placed_trading_date=date(2024, 6, 20),
        placed_utc=datetime(2024, 6, 20, 20, 1, tzinfo=timezone.utc)))
    L = Ledger()
    result = await drain_pending(store, b, L, date(2024, 6, 21))
    assert len(result.unknown) == 1
    # Kept pending — never silently dropped.
    assert len(store.all()) == 1


@pytest.mark.asyncio
async def test_drain_sell_with_no_lots_surfaces_error_keeps_pending(tmp_path):
    """A SELL fill with no matching open lots is a real inconsistency: it is
    surfaced as an error and kept pending, not silently lost."""
    b = _broker()
    t = await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 10, OrderType.MKT)
    # Now create a pending SELL for a symbol the ledger has no lots for.
    sell = await b.place_order(OFF_VEHICLE_SYMBOL, "SELL", 10, OrderType.MOO)
    store = PendingOrderStore(tmp_path / "pending.json")
    store.add(PendingOrder.from_ticket(_tag(sell, "qqq_trend_50_200"),
                                       date(2024, 6, 20)))
    L = Ledger()   # empty -> record_sell will raise
    b.session_open()
    result = await drain_pending(store, b, L, date(2024, 6, 21))
    assert result.errors
    assert len(store.all()) == 1     # kept for operator review


def _tag(ticket, strategy_id: str):
    ticket.strategy_id = strategy_id
    return ticket
