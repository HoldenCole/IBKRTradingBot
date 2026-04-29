from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.risk.weekly_budget import Gate, OpenPosition, WeeklyBudget

ET = ZoneInfo("America/New_York")


def _now(y, m, d, h=12, mn=0):
    return datetime(y, m, d, h, mn, tzinfo=ET)


def test_normal_gate_when_empty():
    b = WeeklyBudget()
    assert b.gate(_now(2026, 4, 29)) is Gate.NORMAL
    assert b.risk_used(_now(2026, 4, 29)) == 0.0


def test_open_position_consumes_risk_50pct_premium():
    b = WeeklyBudget()
    # 1 contract * $4 premium = $400 notional; 50% stop = $200 risk
    b.record_open(OpenPosition("t1", contracts=1, entry_premium=4.0))
    assert b.open_risk() == 200.0


def test_overnight_haircut_15x():
    b = WeeklyBudget()
    b.record_open(OpenPosition("t1", contracts=1, entry_premium=4.0, held_overnight=True))
    assert b.open_risk() == 300.0


def test_soft_gate_at_70pct():
    b = WeeklyBudget(budget=500.0, soft_gate_pct=0.70)
    # Force realized loss of $360 -> 72% used
    now = _now(2026, 4, 29)
    b.realized_pnl_by_week[b.week_anchor(now)] = -360.0
    assert b.gate(now) is Gate.SOFT
    assert b.sizing_multiplier(now) == 0.5


def test_hard_gate_blocks_entry():
    b = WeeklyBudget(budget=500.0)
    now = _now(2026, 4, 29)
    b.realized_pnl_by_week[b.week_anchor(now)] = -500.0
    assert b.gate(now) is Gate.HARD
    ok, gate, _ = b.can_enter(now, prospective_risk=10.0)
    assert not ok and gate is Gate.HARD


def test_can_enter_respects_remaining():
    b = WeeklyBudget(budget=500.0)
    now = _now(2026, 4, 29)
    b.realized_pnl_by_week[b.week_anchor(now)] = -300.0
    ok, _, _ = b.can_enter(now, prospective_risk=150.0)
    assert ok
    ok, _, reason = b.can_enter(now, prospective_risk=250.0)
    assert not ok and "exceed budget" in reason


def test_week_resets_on_monday():
    b = WeeklyBudget()
    fri = _now(2026, 5, 1, 15, 0)  # Friday
    mon = _now(2026, 5, 4, 10, 0)  # Following Monday after 09:30
    assert b.week_anchor(fri) != b.week_anchor(mon)
    # Sunday rolls back to prior week's Monday.
    sun = _now(2026, 5, 3, 12, 0)
    assert b.week_anchor(sun) == b.week_anchor(fri)


def test_record_close_accumulates_loss():
    b = WeeklyBudget()
    now = _now(2026, 4, 29)
    b.record_open(OpenPosition("t1", contracts=1, entry_premium=4.0))
    b.record_close("t1", realized_pnl=-150.0, now_et=now)
    assert b.realized_loss(now) == 150.0
    assert "t1" not in b.open_positions
