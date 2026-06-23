"""Tests for signal_state — the pure logic of computing ON/OFF and
detecting transitions. No I/O."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.deploy.signal_state import (
    SignalSnapshot, SignalState, StateChange,
    compute_signal, detect_change,
)


def _series(values: list[float], start_date: date = date(2024, 1, 2)) -> pd.Series:
    """Daily series; weekdays only, mirrors equity calendar."""
    idx = pd.date_range(start=start_date, periods=len(values), freq="B")
    return pd.Series(values, index=idx)


def test_unknown_during_warmup():
    s = _series([100.0] * 50)
    snap = compute_signal("test", s, s.index[-1].date())
    assert snap.state == SignalState.UNKNOWN
    assert snap.sma50 is None and snap.sma200 is None


def test_on_when_uptrending_and_above_smas():
    # 250 strictly increasing prices -> close > SMA50 > SMA200
    s = _series(list(np.linspace(100.0, 200.0, 250)))
    snap = compute_signal("test", s, s.index[-1].date())
    assert snap.state == SignalState.ON
    assert snap.close > (snap.sma50 or -float("inf"))
    assert (snap.sma50 or -float("inf")) > (snap.sma200 or -float("inf"))


def test_off_when_downtrending():
    s = _series(list(np.linspace(200.0, 100.0, 250)))
    snap = compute_signal("test", s, s.index[-1].date())
    assert snap.state == SignalState.OFF


def test_off_when_close_below_sma50_but_smas_bullish():
    # Long uptrend then a sharp pullback below SMA50; SMA50 still > SMA200
    rising = list(np.linspace(100.0, 200.0, 230))
    pullback = list(np.linspace(200.0, 150.0, 20))
    s = _series(rising + pullback)
    snap = compute_signal("test", s, s.index[-1].date())
    # SMA200 should still be lower than SMA50; close pulled below SMA50
    assert snap.sma50 > snap.sma200
    assert snap.close < snap.sma50
    assert snap.state == SignalState.OFF


def test_raises_when_as_of_not_in_series():
    s = _series([100.0] * 250)
    with pytest.raises(ValueError, match="not present"):
        compute_signal("test", s, date(1999, 1, 1))


def test_governs_returns_from_next_session_flag():
    s = _series(list(np.linspace(100.0, 200.0, 250)))
    snap = compute_signal("test", s, s.index[-1].date())
    # Recorded so post-hoc audit can verify the Convention 2 lag
    assert snap.governs_returns_from_next_session is True


def test_passes_gate_method():
    snap = SignalSnapshot("t", date(2024, 6, 1), SignalState.ON,
                         close=110.0, sma50=105.0, sma200=100.0)
    assert snap.passes_gate() is True
    bear = SignalSnapshot("t", date(2024, 6, 1), SignalState.OFF,
                          close=95.0, sma50=100.0, sma200=105.0)
    assert bear.passes_gate() is False
    warmup = SignalSnapshot("t", date(2024, 6, 1), SignalState.UNKNOWN,
                            close=100.0, sma50=None, sma200=None)
    assert warmup.passes_gate() is False


# ----- StateChange / detect_change -----

def _snap(state: SignalState, as_of: date) -> SignalSnapshot:
    return SignalSnapshot("t", as_of, state, close=100.0, sma50=99.0, sma200=98.0)


def test_detect_change_off_to_on_is_flip_enter():
    prev = _snap(SignalState.OFF, date(2024, 6, 20))
    curr = _snap(SignalState.ON, date(2024, 6, 21))
    ch = detect_change(prev, curr)
    assert ch.is_flip is True
    assert ch.direction == "enter"


def test_detect_change_on_to_off_is_flip_exit():
    prev = _snap(SignalState.ON, date(2024, 6, 20))
    curr = _snap(SignalState.OFF, date(2024, 6, 21))
    ch = detect_change(prev, curr)
    assert ch.is_flip is True
    assert ch.direction == "exit"


def test_detect_change_same_state_is_not_flip():
    prev = _snap(SignalState.ON, date(2024, 6, 20))
    curr = _snap(SignalState.ON, date(2024, 6, 21))
    ch = detect_change(prev, curr)
    assert ch.is_flip is False
    assert ch.direction == "noop"


def test_detect_change_no_prev_is_not_flip():
    # First-ever run: prev is None, "change" is UNKNOWN -> whatever.
    # UNKNOWN->ON is NOT a tradeable flip (nothing was held in UNKNOWN).
    curr = _snap(SignalState.ON, date(2024, 6, 21))
    ch = detect_change(None, curr)
    assert ch.prev_state == SignalState.UNKNOWN
    assert ch.is_flip is False


def test_detect_change_unknown_to_state_is_not_flip():
    # Warmup completion: not a tradeable event (we held nothing in UNKNOWN).
    prev = _snap(SignalState.UNKNOWN, date(2024, 6, 20))
    curr = _snap(SignalState.ON, date(2024, 6, 21))
    ch = detect_change(prev, curr)
    assert ch.is_flip is False
    assert ch.direction == "noop"
