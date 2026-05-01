"""PositionManager lifecycle: open -> evaluate -> apply_fill -> close
with weekly-budget accounting kept in sync.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.positions.exits import ExitAction, ExitKind, ExitReason
from src.positions.manager import PositionManager
from src.positions.position import Position, PositionStatus
from src.risk.weekly_budget import WeeklyBudget
from src.strategies.base import SignalAction

ET = ZoneInfo("America/New_York")


def _pos(trade_id="t1", contracts=2, entry_premium=4.0):
    return Position(
        trade_id=trade_id,
        strategy_name="ewo",
        strategy_family="mean_reversion",
        underlying="SPY",
        option_etf="UPRO",
        option_contract_id="OPT1",
        direction=SignalAction.LONG,
        entry_time=datetime(2026, 4, 1, 9, 31, tzinfo=ET),
        entry_premium=entry_premium,
        entry_underlying=400.0,
        entry_atr20=2.0,
        expiry=date(2026, 4, 30),
        initial_contracts=contracts,
        contracts_remaining=contracts,
    )


def test_open_syncs_budget():
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    pm.open(_pos(contracts=2, entry_premium=4.0))
    # 2 * $4 * 100 * 0.5 = $400 risk
    assert budget.open_risk() == 400.0
    assert pm.open_count() == 1


def test_full_close_records_realized_pnl():
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    pos = _pos(contracts=2)
    pm.open(pos)
    action = ExitAction(
        kind=ExitKind.CLOSE_ALL,
        contracts_to_close=2,
        reason=ExitReason.SIGNAL_EXIT,
    )
    now = datetime(2026, 4, 5, 10, 0, tzinfo=ET)
    pnl = pm.apply_fill(pos, action, fill_price=5.0, now_et=now)
    # (5-4) * 2 * 100 = $200
    assert pnl == 200.0
    assert pos.status is PositionStatus.CLOSED
    assert pos.contracts_remaining == 0
    assert budget.open_risk() == 0.0
    # Realized win is positive PnL -> realized_loss should remain zero.
    assert budget.realized_loss(now) == 0.0


def test_partial_close_updates_budget():
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    pos = _pos(contracts=4, entry_premium=4.0)
    pm.open(pos)
    # Scale out 2 at +50% premium
    action = ExitAction(
        kind=ExitKind.SCALE_OUT,
        contracts_to_close=2,
        reason=ExitReason.SCALE_OUT_50,
    )
    now = datetime(2026, 4, 5, 10, 0, tzinfo=ET)
    pm.apply_fill(pos, action, fill_price=6.0, now_et=now)
    assert pos.contracts_remaining == 2
    assert pos.scaled_50pct is True
    # Open risk = 2 * $4 * 100 * 0.5 = $400 (down from $800 pre-scale)
    assert budget.open_risk() == 400.0
    assert pos.status is PositionStatus.OPEN


def test_loss_increments_weekly_realized_loss():
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    pos = _pos(contracts=2, entry_premium=4.0)
    pm.open(pos)
    action = ExitAction(
        kind=ExitKind.CLOSE_ALL,
        contracts_to_close=2,
        reason=ExitReason.PREMIUM_STOP,
        use_stop_loss_path=True,
    )
    now = datetime(2026, 4, 5, 10, 0, tzinfo=ET)
    pm.apply_fill(pos, action, fill_price=2.0, now_et=now)
    # (-2) * 2 * 100 = -$400 PnL
    assert budget.realized_loss(now) == 400.0


def test_advance_trading_day_skips_entry_day():
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    pos = _pos()
    pm.open(pos)
    pm.advance_trading_day(date(2026, 4, 1))  # entry day -> no bump
    assert pos.trading_days_held == 0
    pm.advance_trading_day(date(2026, 4, 2))
    assert pos.trading_days_held == 1
    pm.advance_trading_day(date(2026, 4, 3))
    assert pos.trading_days_held == 2


def test_mark_overnight_propagates_to_budget():
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    pos = _pos(contracts=2, entry_premium=4.0)
    pm.open(pos)
    # Pre-overnight: $400 risk
    assert budget.open_risk() == 400.0
    pm.mark_overnight("t1")
    assert pos.held_overnight is True
    # 1.5x haircut: $600
    assert budget.open_risk() == 600.0


def test_open_in_family_count():
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    pm.open(_pos(trade_id="t1"))
    p2 = _pos(trade_id="t2")
    pm.open(p2)
    assert pm.open_count() == 2
    assert pm.open_in_family("mean_reversion") == 2
    assert pm.open_in_family("afternoon") == 0
