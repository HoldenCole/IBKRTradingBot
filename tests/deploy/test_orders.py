"""Tests for the order workflow (src/deploy/orders.py).

End-to-end coverage of: state-change → plan → execute → broker fills →
final positions. All against SimStockBroker; no live IBKR.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.deploy.baskets import BasketConfig
from src.deploy.broker import OrderState, OrderType, SimStockBroker
from src.deploy.orders import (
    OFF_VEHICLE_SYMBOL, execute_plans, plan_orders,
)
from src.deploy.portfolio import Ledger
from src.deploy.signal_state import SignalState, StateChange


# ---------- Helpers ----------

def _quotes(qqq: float = 540.0, ibit: float = 60.0, sgov: float = 100.0):
    return {"QQQ": qqq, "IBIT": ibit, OFF_VEHICLE_SYMBOL: sgov}


def _broker_with_sgov_only(nav: float = 8000.0,
                           sgov: float = 100.0) -> SimStockBroker:
    """Account fully in SGOV — the "both sleeves OFF" starting state."""
    b = SimStockBroker(starting_cash=nav)
    b.set_quote("QQQ", 540.0); b.set_quote("IBIT", 60.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, sgov); b.set_open_price("QQQ", 540.0)
    b.set_open_price("IBIT", 60.0); b.set_open_price(OFF_VEHICLE_SYMBOL, sgov)
    return b


def _enter_qqq() -> StateChange:
    return StateChange(strategy_id="qqq_trend_50_200",
                       prev_state=SignalState.OFF, new_state=SignalState.ON,
                       prev_date=date(2024, 6, 19), new_date=date(2024, 6, 20))


def _exit_qqq() -> StateChange:
    return StateChange(strategy_id="qqq_trend_50_200",
                       prev_state=SignalState.ON, new_state=SignalState.OFF,
                       prev_date=date(2024, 6, 19), new_date=date(2024, 6, 20))


def _enter_btc() -> StateChange:
    return StateChange(strategy_id="btc_trend_50_200",
                       prev_state=SignalState.OFF, new_state=SignalState.ON,
                       prev_date=date(2024, 6, 19), new_date=date(2024, 6, 20))


# ---------- Planning ----------

@pytest.mark.asyncio
async def test_no_flip_no_plan():
    cfg = BasketConfig.load()
    b = _broker_with_sgov_only()
    noop = StateChange("qqq_trend_50_200", SignalState.ON, SignalState.ON,
                       date(2024, 6, 19), date(2024, 6, 20))
    plans = await plan_orders([noop], cfg, b, _quotes())
    assert plans == []


@pytest.mark.asyncio
async def test_enter_qqq_plan_sizes_to_basket_weight():
    cfg = BasketConfig.load()   # B2 (BTC) 50% + B3 (QQQ) 50%
    b = SimStockBroker(starting_cash=8000.0)
    # Account starts with 80 shares of SGOV @ 100 = $8000
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0)
    b.set_quote("QQQ", 540.0)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 80, OrderType.MKT)
    # cash now 0, 80 SGOV held; NAV = 8000

    plans = await plan_orders([_enter_qqq()], cfg, b, _quotes(qqq=540.0))
    assert len(plans) == 1
    p = plans[0]
    assert p.direction == "enter"
    assert p.risk_symbol == "QQQ"
    assert p.risk_side == "BUY"
    # target = 50% * 8000 = 4000; 4000 / 540 = 7.4 -> 7 shares
    assert p.risk_quantity == 7
    # SGOV to sell: target_dollars / sgov_quote = 4000 / 100 = 40 shares
    assert p.off_quantity == 40
    assert p.off_side == "SELL"


@pytest.mark.asyncio
async def test_exit_qqq_plan_sells_all_held():
    cfg = BasketConfig.load()
    b = SimStockBroker(starting_cash=8000.0)
    b.set_quote("QQQ", 540.0); b.set_quote(OFF_VEHICLE_SYMBOL, 100.0)
    # Already long 7 QQQ + 32 SGOV (sliver)
    await b.place_order("QQQ", "BUY", 7, OrderType.MKT)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 32, OrderType.MKT)

    plans = await plan_orders([_exit_qqq()], cfg, b, _quotes())
    assert len(plans) == 1
    p = plans[0]
    assert p.direction == "exit"
    assert p.risk_side == "SELL"
    assert p.risk_quantity == 7              # sell ALL held QQQ
    # proceeds = 7 * 540 = 3780; 3780 / 100 = 37 shares SGOV
    assert p.off_quantity == 37
    assert p.off_side == "BUY"


@pytest.mark.asyncio
async def test_exit_when_position_is_empty_skips_with_note():
    """Edge case: state says we should exit but broker shows no position.
    Could indicate state-store/broker mismatch. We skip with a note, NOT
    a crash — the restart-resilience layer (item #10) will reconcile."""
    cfg = BasketConfig.load()
    b = _broker_with_sgov_only()   # no QQQ held
    plans = await plan_orders([_exit_qqq()], cfg, b, _quotes())
    assert len(plans) == 1
    assert plans[0].risk_quantity == 0
    assert "nothing to sell" in plans[0].note.lower()


@pytest.mark.asyncio
async def test_enter_with_insufficient_funds_for_one_share_skips():
    """If basket-weight * NAV < 1 share of the risk asset, skip the buy."""
    cfg = BasketConfig.load()
    # Tiny account: 50% of $200 = $100, less than 1 share of QQQ @ $540
    b = SimStockBroker(starting_cash=200.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 2, OrderType.MKT)
    plans = await plan_orders([_enter_qqq()], cfg, b, _quotes())
    assert plans[0].risk_quantity == 0
    assert "< 1 share" in plans[0].note


@pytest.mark.asyncio
async def test_missing_quote_raises():
    cfg = BasketConfig.load()
    b = _broker_with_sgov_only()
    with pytest.raises(RuntimeError, match="missing quote"):
        await plan_orders([_enter_qqq()], cfg, b, {})   # no quotes at all


# ---------- Execution ----------

@pytest.mark.asyncio
async def test_execute_enter_qqq_end_to_end():
    """Full path: start all-SGOV, enter QQQ, MOO orders fill at session open."""
    cfg = BasketConfig.load()
    b = SimStockBroker(starting_cash=8000.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    b.set_open_price(OFF_VEHICLE_SYMBOL, 100.0); b.set_open_price("QQQ", 540.0)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 80, OrderType.MKT)

    plans = await plan_orders([_enter_qqq()], cfg, b, _quotes())
    result = await execute_plans(plans, b, order_type=OrderType.MOO)

    # Two MOO tickets submitted (SELL SGOV, BUY QQQ); not yet filled
    assert len(result.submitted) == 2
    assert all(t.state == OrderState.SUBMITTED for t in result.submitted)
    assert "QQQ" not in await b.positions()       # MOO hasn't filled yet

    # Open the session
    b.session_open()
    positions = await b.positions()
    assert positions["QQQ"].quantity == 7
    # SGOV reduced from 80 to 40
    assert positions[OFF_VEHICLE_SYMBOL].quantity == 40


@pytest.mark.asyncio
async def test_execute_exit_orders_sell_risk_first_then_buy_off():
    """Locked decision: on exit, sell risk asset first (frees cash), then
    buy off-vehicle. Verifies the order of submission for cash sufficiency."""
    cfg = BasketConfig.load()
    b = SimStockBroker(starting_cash=8000.0)
    b.set_quote("QQQ", 540.0); b.set_quote(OFF_VEHICLE_SYMBOL, 100.0)
    b.set_open_price("QQQ", 540.0); b.set_open_price(OFF_VEHICLE_SYMBOL, 100.0)
    await b.place_order("QQQ", "BUY", 7, OrderType.MKT)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 32, OrderType.MKT)

    plans = await plan_orders([_exit_qqq()], cfg, b, _quotes())
    result = await execute_plans(plans, b, order_type=OrderType.MOO)
    # First ticket should be the SELL QQQ
    assert result.submitted[0].symbol == "QQQ"
    assert result.submitted[0].side == "SELL"
    assert result.submitted[1].symbol == OFF_VEHICLE_SYMBOL
    assert result.submitted[1].side == "BUY"


@pytest.mark.asyncio
async def test_enter_sells_off_first_then_buys_risk():
    """On enter, sell off-vehicle FIRST so cash is available for the risk buy."""
    cfg = BasketConfig.load()
    b = SimStockBroker(starting_cash=8000.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    b.set_open_price(OFF_VEHICLE_SYMBOL, 100.0); b.set_open_price("QQQ", 540.0)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 80, OrderType.MKT)

    plans = await plan_orders([_enter_qqq()], cfg, b, _quotes())
    result = await execute_plans(plans, b, order_type=OrderType.MOO)
    assert result.submitted[0].symbol == OFF_VEHICLE_SYMBOL
    assert result.submitted[0].side == "SELL"
    assert result.submitted[1].symbol == "QQQ"
    assert result.submitted[1].side == "BUY"


@pytest.mark.asyncio
async def test_two_simultaneous_flips_planned_independently():
    """If QQQ and BTC both flip on the same day, plan independently per
    sleeve. This is the test that confirms baskets are independent."""
    cfg = BasketConfig.load()
    b = SimStockBroker(starting_cash=8000.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    b.set_quote("IBIT", 60.0)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 80, OrderType.MKT)

    plans = await plan_orders([_enter_qqq(), _enter_btc()], cfg, b, _quotes())
    assert len(plans) == 2
    by_strat = {p.strategy_id: p for p in plans}
    assert by_strat["qqq_trend_50_200"].risk_symbol == "QQQ"
    assert by_strat["btc_trend_50_200"].risk_symbol == "IBIT"
    # Each sizes to its own basket weight (both 50% in Stage 1)
    # QQQ: floor(4000 / 540) = 7
    # IBIT: floor(4000 / 60) = 66
    assert by_strat["qqq_trend_50_200"].risk_quantity == 7
    assert by_strat["btc_trend_50_200"].risk_quantity == 66


@pytest.mark.asyncio
async def test_enter_sizes_sgov_per_sleeve_from_ledger():
    """CRITICAL-1 regression: when two sleeves enter on the same day, each
    must sell only the SGOV *it* parked (tracked in the ledger), never the
    pooled broker balance. Otherwise the planner over-orders SGOV sells and
    the second order is rejected at the broker."""
    cfg = BasketConfig.load()
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    b.set_quote("IBIT", 60.0)
    # Pooled broker SGOV = 60 shares; the $4000 cash sliver inflates NAV to
    # $10000 so each sleeve's target ($5000) exceeds its parked SGOV.
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 60, OrderType.MKT)

    # Ledger: each sleeve parked 30 SGOV (total 60 == broker pool).
    L = Ledger()
    L.record_buy(strategy_id="qqq_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=30, price=100.0, trade_date=date(2024, 6, 19))
    L.record_buy(strategy_id="btc_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=30, price=100.0, trade_date=date(2024, 6, 19))

    plans = await plan_orders([_enter_qqq(), _enter_btc()], cfg, b,
                              _quotes(), ledger=L)
    by_strat = {p.strategy_id: p for p in plans}
    # Each sleeve sells exactly its own 30 SGOV...
    assert by_strat["qqq_trend_50_200"].off_quantity == 30
    assert by_strat["btc_trend_50_200"].off_quantity == 30
    # ...so combined SGOV sells never exceed the 60 actually held.
    assert sum(p.off_quantity for p in plans) == 60


@pytest.mark.asyncio
async def test_enter_without_ledger_can_oversize_pooled_sgov():
    """Documents the CRITICAL-1 hazard the ledger fix addresses: without a
    ledger the planner sizes each sleeve's SGOV sell against the *pooled*
    broker balance, so two same-day flips each request the full target and
    the combined sells exceed what is actually held. The orchestrator MUST
    pass a ledger in production."""
    cfg = BasketConfig.load()
    b = SimStockBroker(starting_cash=10000.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    b.set_quote("IBIT", 60.0)
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 60, OrderType.MKT)
    plans = await plan_orders([_enter_qqq(), _enter_btc()], cfg, b, _quotes())
    # 50% * 10000 / 100 = 50 SGOV each -> 100 total > 60 held (the bug).
    assert sum(p.off_quantity for p in plans) > 60


@pytest.mark.asyncio
async def test_skipped_plans_do_not_submit_orders():
    """A plan with both risk_quantity=0 and off_quantity=0 must not produce
    broker orders, only a skipped-reason entry."""
    cfg = BasketConfig.load()
    b = _broker_with_sgov_only()       # account in SGOV, no QQQ held
    plans = await plan_orders([_exit_qqq()], cfg, b, _quotes())
    assert plans[0].risk_quantity == 0
    result = await execute_plans(plans, b)
    assert result.submitted == []
    assert len(result.skipped) == 1
    assert "qqq_trend_50_200" in result.skipped[0]


@pytest.mark.asyncio
async def test_execute_errors_captured_not_raised():
    """If the broker raises mid-execution, the workflow records the error
    and continues — partial failures shouldn't stop other sleeves."""
    cfg = BasketConfig.load()
    b = _broker_with_sgov_only()
    # Buy enough SGOV for the workflow to plan a real trade
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 80, OrderType.MKT)

    plans = await plan_orders([_enter_qqq()], cfg, b, _quotes())

    # Monkey-patch the broker to fail on the second place_order call
    original = b.place_order
    call_count = {"n": 0}
    async def flaky(symbol, side, quantity, order_type):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated broker glitch")
        return await original(symbol, side, quantity, order_type)
    b.place_order = flaky  # type: ignore[assignment]

    result = await execute_plans(plans, b)
    # First order went through; second failed; workflow returns normally
    assert len(result.submitted) == 1
    assert len(result.errors) == 1
    assert "simulated broker glitch" in result.errors[0]
