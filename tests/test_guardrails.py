from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.risk.blackout import BlackoutChecker, StubCalendar
from src.risk.guardrails import EntryRequest, Guardrails, RejectReason
from src.risk.regime import StaticRegime
from src.risk.weekly_budget import OpenPosition, WeeklyBudget

ET = ZoneInfo("America/New_York")


@pytest.fixture
def guardrails():
    return Guardrails(
        budget=WeeklyBudget(),
        blackout=BlackoutChecker(StubCalendar([])),
        regime=StaticRegime({"SPY": True, "QQQ": True}),
        per_trade_risk_cap=200.0,
    )


def _req(**kw):
    defaults = dict(
        strategy_name="ewo",
        strategy_family="mean_reversion",
        underlying="SPY",
        contracts=1,
        entry_premium=3.0,
        bid=2.95,
        ask=3.05,
        nav=8000.0,
    )
    defaults.update(kw)
    return EntryRequest(**defaults)


def test_happy_path(guardrails):
    d = guardrails.check_entry(_req(), datetime(2026, 4, 29, 12, tzinfo=ET), 0, 0, 0.0)
    assert d.allowed and d.reason is RejectReason.OK


def test_regime_off_blocks(guardrails):
    guardrails.regime = StaticRegime({"SPY": False, "QQQ": True})
    d = guardrails.check_entry(_req(), datetime(2026, 4, 29, 12, tzinfo=ET), 0, 0, 0.0)
    assert not d.allowed and d.reason is RejectReason.REGIME_OFF


def test_position_limit(guardrails):
    d = guardrails.check_entry(
        _req(), datetime(2026, 4, 29, 12, tzinfo=ET),
        open_positions_count=2, open_positions_in_family=1, gross_open_premium=0.0,
    )
    assert not d.allowed and d.reason is RejectReason.POSITION_LIMIT


def test_per_trade_risk_cap(guardrails):
    # 1 contract * $5 premium * 100 mult * 0.5 stop = $250 risk > $200 cap
    d = guardrails.check_entry(
        _req(entry_premium=5.0), datetime(2026, 4, 29, 12, tzinfo=ET), 0, 0, 0.0,
    )
    assert not d.allowed and d.reason is RejectReason.PER_TRADE_CAP


def test_spread_too_wide(guardrails):
    d = guardrails.check_entry(
        _req(bid=2.0, ask=2.50), datetime(2026, 4, 29, 12, tzinfo=ET), 0, 0, 0.0,
    )
    # spread = 0.5 / 2.25 = 22% > 15% cap
    assert not d.allowed and d.reason is RejectReason.SPREAD_TOO_WIDE


def test_spread_8pct_only_for_ewo(guardrails):
    # 10% spread is fine for EWO (above 8%, below 15%) but not for IBS.
    req_ewo = _req(strategy_name="ewo", bid=2.85, ask=3.15)  # ~10% spread
    d_ewo = guardrails.check_entry(
        req_ewo, datetime(2026, 4, 29, 12, tzinfo=ET), 0, 0, 0.0,
    )
    assert d_ewo.allowed

    req_ibs = _req(strategy_name="ibs", bid=2.85, ask=3.15)
    d_ibs = guardrails.check_entry(
        req_ibs, datetime(2026, 4, 29, 12, tzinfo=ET), 0, 0, 0.0,
    )
    assert not d_ibs.allowed and d_ibs.reason is RejectReason.SPREAD_TOO_WIDE


def test_hard_gate_blocks(guardrails):
    now = datetime(2026, 4, 29, 12, tzinfo=ET)
    # blow the budget with a fake closed-loss
    guardrails.budget.realized_pnl_by_week[guardrails.budget.week_anchor(now)] = -600.0
    d = guardrails.check_entry(_req(), now, 0, 0, 0.0)
    assert not d.allowed and d.reason is RejectReason.HARD_GATE


def test_gross_premium_cap(guardrails):
    # 1 contract * $3 * 100 = $300 new gross. With $4700 already open and
    # $8000 NAV * 60% = $4800 cap -> $5000 > $4800 should reject.
    d = guardrails.check_entry(
        _req(), datetime(2026, 4, 29, 12, tzinfo=ET),
        open_positions_count=1, open_positions_in_family=1, gross_open_premium=4700.0,
    )
    assert not d.allowed and d.reason is RejectReason.GROSS_PREMIUM_LIMIT
