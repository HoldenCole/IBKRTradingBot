"""Tests for target-driven initial positioning.

Unlike plan_orders (which reacts to flips), plan_positioning produces the
trades needed to bring the portfolio to its target weights GIVEN the
current signal state of each sleeve. Used on first startup and after
reconciliation-resolved discrepancies.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.deploy.baskets import BasketConfig
from src.deploy.broker import OrderState, OrderType, SimStockBroker
from src.deploy.orders import OFF_VEHICLE_SYMBOL
from src.deploy.portfolio import Ledger
from src.deploy.positioning import (
    execute_positioning, plan_positioning,
)
from src.deploy.signal_state import SignalState


def _quotes(qqq: float = 540.0, ibit: float = 60.0, sgov: float = 100.0):
    return {"QQQ": qqq, "IBIT": ibit, OFF_VEHICLE_SYMBOL: sgov}


def _all_states(qqq: SignalState, btc: SignalState) -> dict[str, SignalState]:
    return {"qqq_trend_50_200": qqq, "btc_trend_50_200": btc}


# ===== plan_positioning =====

def test_empty_account_both_off_buys_sgov_each_sleeve():
    """Fresh $8k account, both signals OFF. Each sleeve targets 50% in SGOV."""
    cfg = BasketConfig.load()
    L = Ledger()
    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.OFF, SignalState.OFF))
    # Two SGOV BUYs, 40 shares each (4000 / 100).
    sgov_buys = [t for t in plan.trades if t.symbol == OFF_VEHICLE_SYMBOL]
    assert len(sgov_buys) == 2
    assert all(t.side == "BUY" and t.quantity == 40 for t in sgov_buys)
    assert all(t.symbol != "QQQ" and t.symbol != "IBIT" for t in plan.trades)


def test_empty_account_both_on_buys_risk_each_sleeve():
    """Fresh $8k account, both signals ON. Each sleeve buys its risk asset."""
    cfg = BasketConfig.load()
    L = Ledger()
    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.ON, SignalState.ON))
    by_sym = {t.symbol: t for t in plan.trades}
    # QQQ: 4000 / 540 = 7 shares; IBIT: 4000 / 60 = 66 shares.
    assert by_sym["QQQ"].quantity == 7
    assert by_sym["QQQ"].side == "BUY"
    assert by_sym["IBIT"].quantity == 66
    assert by_sym["IBIT"].side == "BUY"
    assert OFF_VEHICLE_SYMBOL not in by_sym       # no SGOV needed


def test_split_states_buys_one_risk_one_sgov():
    """QQQ ON + BTC OFF -> buy QQQ for the QQQ sleeve, SGOV for the BTC sleeve."""
    cfg = BasketConfig.load()
    L = Ledger()
    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.ON, SignalState.OFF))
    by_strat = {(t.strategy_id, t.symbol): t for t in plan.trades}
    assert by_strat[("qqq_trend_50_200", "QQQ")].quantity == 7
    assert by_strat[("btc_trend_50_200", OFF_VEHICLE_SYMBOL)].quantity == 40


def test_already_at_target_produces_empty_plan():
    """Idempotent: re-running positioning when already at target is a no-op."""
    cfg = BasketConfig.load()
    L = Ledger()
    # Pre-seed: QQQ sleeve already holds 7 QQQ; BTC sleeve already holds 40 SGOV.
    L.record_buy(strategy_id="qqq_trend_50_200", symbol="QQQ", quantity=7,
                 price=540.0, trade_date=date(2026, 6, 19))
    L.record_buy(strategy_id="btc_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=date(2026, 6, 19))
    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.ON, SignalState.OFF))
    assert plan.is_empty


def test_transition_from_sgov_to_risk_emits_sell_and_buy():
    """Sleeve currently parked in SGOV but signal is ON -> sell SGOV, buy risk."""
    cfg = BasketConfig.load()
    L = Ledger()
    L.record_buy(strategy_id="qqq_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=date(2026, 6, 19))
    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.ON, SignalState.OFF))
    qqq_trades = [t for t in plan.trades if t.strategy_id == "qqq_trend_50_200"]
    # SELL 40 SGOV + BUY 7 QQQ
    sides = {(t.symbol, t.side) for t in qqq_trades}
    assert (OFF_VEHICLE_SYMBOL, "SELL") in sides
    assert ("QQQ", "BUY") in sides


def test_unknown_signal_parks_in_sgov_with_note():
    """Pre-warmup (UNKNOWN) sleeves default to OFF (SGOV) — matches the
    validated backtest convention."""
    cfg = BasketConfig.load()
    L = Ledger()
    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.UNKNOWN, SignalState.UNKNOWN))
    assert all(t.symbol == OFF_VEHICLE_SYMBOL and t.side == "BUY"
               for t in plan.trades)
    assert any("warmup" in n.lower() for n in plan.notes)


def test_per_sleeve_sgov_is_independent():
    """Two sleeves' SGOV holdings are tracked separately in the ledger;
    one sleeve's positioning doesn't touch the other's SGOV."""
    cfg = BasketConfig.load()
    L = Ledger()
    # Both sleeves parked in SGOV (40 each).
    L.record_buy(strategy_id="qqq_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=date(2026, 6, 19))
    L.record_buy(strategy_id="btc_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=date(2026, 6, 19))
    # Only QQQ flips ON.
    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.ON, SignalState.OFF))
    # QQQ sleeve sells its 40 SGOV; BTC sleeve does nothing.
    by_strat: dict[tuple[str, str], int] = {}
    for t in plan.trades:
        by_strat[(t.strategy_id, t.side)] = t.quantity
    assert by_strat[("qqq_trend_50_200", "SELL")] == 40
    assert ("btc_trend_50_200", "SELL") not in by_strat
    assert ("btc_trend_50_200", "BUY") not in by_strat


def test_missing_quote_raises():
    cfg = BasketConfig.load()
    L = Ledger()
    with pytest.raises(RuntimeError, match="missing quote"):
        plan_positioning(cfg, L, nav=8000.0, quotes={"QQQ": 540.0, "IBIT": 60.0},
                         signal_states=_all_states(SignalState.OFF, SignalState.OFF))


# ===== execute_positioning =====

@pytest.mark.asyncio
async def test_execute_runs_sells_before_buys():
    """A plan with both sells and buys must submit sells first so cash is
    available before the buy hits the broker's cash check."""
    cfg = BasketConfig.load()
    L = Ledger()
    L.record_buy(strategy_id="qqq_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=date(2026, 6, 19))

    b = SimStockBroker(starting_cash=0.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    # Seed broker to match the ledger so MKT fills work.
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0)
    b._cash = 4000.0   # bypass the buy that would normally create the position
    await b.place_order(OFF_VEHICLE_SYMBOL, "BUY", 40, OrderType.MKT)

    plan = plan_positioning(
        cfg, L, nav=4000.0, quotes=_quotes(),
        signal_states={"qqq_trend_50_200": SignalState.ON,
                       "btc_trend_50_200": SignalState.OFF})
    # plan should have a SELL SGOV and a BUY QQQ
    result = await execute_positioning(plan, b, order_type=OrderType.MKT)
    # First submitted ticket must be the SELL.
    assert result.submitted[0].side == "SELL"
    # No errors despite starting with 0 cash — sell freed it.
    assert result.errors == []


@pytest.mark.asyncio
async def test_execute_empty_plan_is_noop():
    cfg = BasketConfig.load()
    L = Ledger()
    L.record_buy(strategy_id="qqq_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=date(2026, 6, 19))
    L.record_buy(strategy_id="btc_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=date(2026, 6, 19))
    b = SimStockBroker(starting_cash=8000.0)
    b.set_quote(OFF_VEHICLE_SYMBOL, 100.0); b.set_quote("QQQ", 540.0)
    b.set_quote("IBIT", 60.0)

    plan = plan_positioning(
        cfg, L, nav=8000.0, quotes=_quotes(),
        signal_states=_all_states(SignalState.OFF, SignalState.OFF))
    result = await execute_positioning(plan, b)
    assert result.submitted == []
    assert result.errors == []
