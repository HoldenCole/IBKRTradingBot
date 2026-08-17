"""CL surge → USO calls: signal gating logic."""

from datetime import date

import pytest

from src.strategies.cl_surge_calls import ClSurgeCallsStrategy, SurgeParams

TODAY = date(2026, 8, 17)


def uptrend_closes(n: int = 200, start: float = 50.0, step: float = 0.10):
    """Monotonic rise -> close > SMA50 > SMA200 guaranteed."""
    return [start + i * step for i in range(n)]


def make(**kwargs) -> ClSurgeCallsStrategy:
    return ClSurgeCallsStrategy(SurgeParams(**kwargs))


def test_fires_on_surge_in_uptrend():
    s = make()
    closes = uptrend_closes()
    prev = closes[-1]
    plan = s.evaluate_open(TODAY, closes, prev * 1.025, prev, uso_open=80.0)
    assert plan is not None
    assert plan.strike_target == pytest.approx(81.50)
    assert plan.hold_sessions == 5
    assert plan.overnight_cl_return > 0.02


def test_no_fire_below_threshold():
    s = make()
    closes = uptrend_closes()
    prev = closes[-1]
    assert s.evaluate_open(TODAY, closes, prev * 1.015, prev, 80.0) is None


def test_no_fire_in_downtrend():
    s = make()
    closes = list(reversed(uptrend_closes()))  # falling -> trend filter off
    prev = closes[-1]
    assert s.evaluate_open(TODAY, closes, prev * 1.03, prev, 80.0) is None


def test_no_fire_while_holding():
    s = make()
    s.holding = True
    closes = uptrend_closes()
    prev = closes[-1]
    assert s.evaluate_open(TODAY, closes, prev * 1.03, prev, 80.0) is None


def test_requires_full_sma_history():
    s = make()
    closes = uptrend_closes(150)  # < sma_slow=200
    prev = closes[-1]
    assert s.evaluate_open(TODAY, closes, prev * 1.03, prev, 80.0) is None


def test_surge_measured_against_prev_1600_not_close():
    s = make()
    closes = uptrend_closes()
    # CL fell after the 16:00 mark: open is +2.5% vs yesterday's close but
    # only +1% vs yesterday 16:00 -> no fire (the overnight window rules).
    prev_1600 = closes[-1] * 1.015
    assert s.evaluate_open(TODAY, closes, closes[-1] * 1.025, prev_1600, 80.0) is None


def test_rejects_bad_prices():
    s = make()
    with pytest.raises(ValueError):
        s.evaluate_open(TODAY, uptrend_closes(), 0.0, 70.0, 80.0)
