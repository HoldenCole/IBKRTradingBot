"""Guardrails: position cap, kill switch, daily reset, sizing."""

from datetime import date

import pytest

from src.risk.guardrails import Guardrails

TODAY = date(2026, 8, 17)
TOMORROW = date(2026, 8, 18)


def make() -> Guardrails:
    return Guardrails(max_position_usd=500, max_daily_loss_usd=200)


def test_notional_cap():
    g = make()
    allowed, _ = g.can_open(499, TODAY)
    assert allowed
    allowed, reason = g.can_open(501, TODAY)
    assert not allowed and "cap" in reason


def test_kill_switch_trips_and_blocks():
    g = make()
    g.record_realized_pnl(-150, TODAY)
    assert not g.kill_switch_tripped(TODAY)
    g.record_realized_pnl(-60, TODAY)
    assert g.kill_switch_tripped(TODAY)
    allowed, reason = g.can_open(100, TODAY)
    assert not allowed and "kill switch" in reason


def test_kill_switch_resets_next_day():
    g = make()
    g.record_realized_pnl(-300, TODAY)
    assert g.kill_switch_tripped(TODAY)
    assert not g.kill_switch_tripped(TOMORROW)
    allowed, _ = g.can_open(100, TOMORROW)
    assert allowed


def test_wins_offset_losses():
    g = make()
    g.record_realized_pnl(100, TODAY)
    g.record_realized_pnl(-250, TODAY)
    assert not g.kill_switch_tripped(TODAY)  # net -150 > -200


def test_size_shares():
    g = make()
    assert g.size_shares(75.0) == 6  # floor(500 / 75)
    assert g.size_shares(600.0) == 0
    with pytest.raises(ValueError):
        g.size_shares(0)


def test_rejects_bad_notional():
    g = make()
    allowed, _ = g.can_open(0, TODAY)
    assert not allowed
