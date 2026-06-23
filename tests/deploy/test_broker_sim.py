"""Tests for the SimStockBroker — verifies the test double itself behaves
correctly. Without this, the order-workflow tests are testing against
broken simulator behavior."""
from __future__ import annotations

import pytest

from src.deploy.broker import OrderState, OrderType, SimStockBroker


@pytest.mark.asyncio
async def test_initial_nav_equals_starting_cash():
    b = SimStockBroker(starting_cash=8000.0)
    assert await b.nav() == 8000.0
    assert await b.positions() == {}


@pytest.mark.asyncio
async def test_mkt_buy_fills_immediately():
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote("QQQ", 500.0)
    t = await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    assert t.state == OrderState.FILLED
    assert t.avg_fill_price == 500.0
    assert t.filled_quantity == 10
    positions = await b.positions()
    assert positions["QQQ"].quantity == 10
    # cash drops by 5000; position MV is 5000; total NAV unchanged
    assert await b.nav() == pytest.approx(10000.0)


@pytest.mark.asyncio
async def test_moo_does_not_fill_until_session_open():
    b = SimStockBroker(starting_cash=10000.0)
    b.set_open_price("QQQ", 500.0)
    t = await b.place_order("QQQ", "BUY", 10, OrderType.MOO)
    assert t.state == OrderState.SUBMITTED       # not filled yet!
    assert "QQQ" not in await b.positions()       # no position yet
    # Now open the session
    filled = b.session_open()
    assert len(filled) == 1
    status = await b.order_status(t.order_id)
    assert status.state == OrderState.FILLED
    assert status.avg_fill_price == 500.0


@pytest.mark.asyncio
async def test_sell_more_than_held_is_rejected():
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote("QQQ", 500.0)
    await b.place_order("QQQ", "BUY", 5, OrderType.MKT)
    t = await b.place_order("QQQ", "SELL", 10, OrderType.MKT)
    assert t.state == OrderState.REJECTED
    assert "insufficient" in t.note


@pytest.mark.asyncio
async def test_buy_more_than_cash_is_rejected():
    b = SimStockBroker(starting_cash=1000.0)
    b.set_quote("QQQ", 500.0)
    t = await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    assert t.state == OrderState.REJECTED
    assert "insufficient cash" in t.note


@pytest.mark.asyncio
async def test_partial_sell_leaves_remaining_position():
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote("QQQ", 500.0)
    await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    await b.place_order("QQQ", "SELL", 3, OrderType.MKT)
    positions = await b.positions()
    assert positions["QQQ"].quantity == 7


@pytest.mark.asyncio
async def test_full_sell_removes_position():
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote("QQQ", 500.0)
    await b.place_order("QQQ", "BUY", 10, OrderType.MKT)
    await b.place_order("QQQ", "SELL", 10, OrderType.MKT)
    assert "QQQ" not in await b.positions()


@pytest.mark.asyncio
async def test_avg_cost_blends_on_multiple_buys():
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote("QQQ", 500.0)
    await b.place_order("QQQ", "BUY", 5, OrderType.MKT)
    b.set_quote("QQQ", 600.0)
    await b.place_order("QQQ", "BUY", 5, OrderType.MKT)
    positions = await b.positions()
    # 5 @ 500 + 5 @ 600 = avg 550
    assert positions["QQQ"].avg_cost == pytest.approx(550.0)


@pytest.mark.asyncio
async def test_cancel_pending_moo():
    b = SimStockBroker(starting_cash=10000.0)
    b.set_open_price("QQQ", 500.0)
    t = await b.place_order("QQQ", "BUY", 10, OrderType.MOO)
    await b.cancel(t.order_id)
    status = await b.order_status(t.order_id)
    assert status.state == OrderState.CANCELLED
    # And session_open does not fill it
    filled = b.session_open()
    assert len(filled) == 0


@pytest.mark.asyncio
async def test_session_open_without_quote_raises():
    b = SimStockBroker(starting_cash=10000.0)
    # MOO submitted but no open price set
    await b.place_order("QQQ", "BUY", 10, OrderType.MOO)
    with pytest.raises(RuntimeError, match="no open price"):
        b.session_open()


@pytest.mark.asyncio
async def test_invalid_side_raises():
    b = SimStockBroker()
    with pytest.raises(ValueError, match="BUY or SELL"):
        await b.place_order("QQQ", "HOLD", 1, OrderType.MKT)
