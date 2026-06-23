"""Tests for startup reconciliation — broker reality vs ledger state."""
from __future__ import annotations

from datetime import date

import pytest

from src.deploy.broker import OrderType, SimStockBroker
from src.deploy.portfolio import Ledger
from src.deploy.reconcile import (
    FindingType, Reconciliation, reconcile_startup,
)


def _seeded_broker() -> SimStockBroker:
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote("QQQ", 540.0); b.set_quote("IBIT", 60.0)
    b.set_quote("SGOV", 100.0)
    return b


@pytest.mark.asyncio
async def test_matching_state_is_safe_to_trade():
    b = _seeded_broker()
    await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10,
                 price=540.0, trade_date=date(2024, 6, 20))
    rec = await reconcile_startup(b, L)
    assert rec.safe_to_trade is True
    assert rec.findings == []
    assert "safe" in rec.summary.lower()


@pytest.mark.asyncio
async def test_phantom_lot_detected():
    """Ledger says we own QQQ, broker says we don't."""
    b = _seeded_broker()
    # broker has NO QQQ
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=7,
                 price=540.0, trade_date=date(2024, 6, 20))
    rec = await reconcile_startup(b, L)
    assert rec.safe_to_trade is False
    assert len(rec.findings) == 1
    assert rec.findings[0].type == FindingType.PHANTOM_LOT
    assert rec.findings[0].ledger_quantity == 7
    assert rec.findings[0].broker_quantity == 0


@pytest.mark.asyncio
async def test_orphan_position_detected():
    """Broker holds shares the ledger doesn't know about."""
    b = _seeded_broker()
    await b.place_order("QQQ", "BUY", 5, OrderType.MKT)
    L = Ledger()   # ledger empty
    rec = await reconcile_startup(b, L)
    assert rec.safe_to_trade is False
    assert len(rec.findings) == 1
    assert rec.findings[0].type == FindingType.ORPHAN_POSITION
    assert rec.findings[0].broker_quantity == 5


@pytest.mark.asyncio
async def test_quantity_mismatch_detected():
    b = _seeded_broker()
    await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=7,
                 price=540.0, trade_date=date(2024, 6, 20))
    rec = await reconcile_startup(b, L)
    assert rec.safe_to_trade is False
    assert rec.findings[0].type == FindingType.QUANTITY_MISMATCH
    assert rec.findings[0].ledger_quantity == 7
    assert rec.findings[0].broker_quantity == 10


@pytest.mark.asyncio
async def test_multiple_findings_all_reported():
    b = _seeded_broker()
    await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    await b.place_order("IBIT", "BUY", 50, OrderType.MKT)  # orphan
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=7,
                 price=540.0, trade_date=date(2024, 6, 20))  # mismatch
    L.record_buy(strategy_id="qqq", symbol="SGOV", quantity=20,
                 price=100.0, trade_date=date(2024, 6, 20))  # phantom (broker has 0 SGOV)
    rec = await reconcile_startup(b, L)
    assert len(rec.findings) == 3
    types = {f.type for f in rec.findings}
    assert types == {FindingType.PHANTOM_LOT, FindingType.ORPHAN_POSITION,
                     FindingType.QUANTITY_MISMATCH}


@pytest.mark.asyncio
async def test_ledger_aggregated_across_strategies():
    """Two strategies each hold 5 QQQ -> broker has 10 -> no finding."""
    b = _seeded_broker()
    await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    L = Ledger()
    L.record_buy(strategy_id="qqq_A", symbol="QQQ", quantity=5,
                 price=540.0, trade_date=date(2024, 6, 20))
    L.record_buy(strategy_id="qqq_B", symbol="QQQ", quantity=5,
                 price=540.0, trade_date=date(2024, 6, 20))
    rec = await reconcile_startup(b, L)
    assert rec.safe_to_trade is True
