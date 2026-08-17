"""Strategy state machine: entries, exits, EOD flatten, entry cutoff."""

from datetime import datetime, timedelta

import numpy as np

from src.strategies.base import Action
from src.strategies.cl1_uso_spread import (
    Cl1UsoSpreadStrategy,
    PairBar,
    PositionSide,
    SpreadParams,
)

PARAMS = SpreadParams(min_history=200, beta_lookback=800, z_lookback=200)


def rth_timestamps(n: int, start: datetime | None = None):
    """Sequential 1-min timestamps confined to 9:30-16:00 ET, wrapping days."""
    ts = start or datetime(2026, 8, 10, 9, 30)
    out = []
    while len(out) < n:
        out.append(ts)
        ts += timedelta(minutes=1)
        if ts.hour == 16:
            ts = (ts + timedelta(days=1)).replace(hour=9, minute=30)
    return out


def warmed_strategy(n: int = 600, seed: int = 7):
    """Strategy fed n bars of well-behaved synthetic pair data.

    Returns (strategy, last_cl, last_uso, last_ts); the next RTH minute
    after last_ts is mid-morning, so entry-window gates are open.
    """
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.0008, n)
    cl = 70.0 * np.exp(np.cumsum(r))
    uso = 75.0 * np.exp(np.cumsum(r + rng.normal(0, 1e-4, n)))
    strategy = Cl1UsoSpreadStrategy(params=PARAMS)
    stamps = rth_timestamps(n + 60)  # headroom so follow-up bars stay in RTH
    for i in range(n):
        strategy.on_bar(PairBar(stamps[i], cl[i], uso[i]))
    # Warm-up ignores signals, so drop any noise-triggered paper position.
    strategy.position = None
    return strategy, cl[-1], uso[-1], stamps[n - 1]


def test_long_entry_on_cheap_uso():
    strategy, cl, uso, ts = warmed_strategy()
    # CL gaps up 2%, USO hasn't moved yet -> long USO.
    signal = strategy.on_bar(PairBar(ts + timedelta(minutes=1), cl * 1.02, uso))
    assert signal is not None and signal.action is Action.BUY
    assert strategy.position is not None
    assert strategy.position.side is PositionSide.LONG


def test_short_entry_on_rich_uso():
    strategy, cl, uso, ts = warmed_strategy()
    signal = strategy.on_bar(PairBar(ts + timedelta(minutes=1), cl, uso * 1.02))
    assert signal is not None and signal.action is Action.SELL_SHORT


def test_shorts_disabled_flag():
    strategy, cl, uso, ts = warmed_strategy()
    strategy.params = SpreadParams(
        min_history=200, beta_lookback=800, z_lookback=200, allow_short=False
    )
    signal = strategy.on_bar(PairBar(ts + timedelta(minutes=1), cl, uso * 1.02))
    assert signal is None
    assert strategy.position is None


def test_convergence_exit():
    strategy, cl, uso, ts = warmed_strategy()
    ts += timedelta(minutes=1)
    assert strategy.on_bar(PairBar(ts, cl * 1.02, uso)).action is Action.BUY
    # USO catches up to fair value -> z back inside exit band -> close.
    signal = None
    for i in range(30):
        ts += timedelta(minutes=1)
        signal = strategy.on_bar(PairBar(ts, cl * 1.02, uso * 1.02))
        if signal is not None:
            break
    assert signal is not None and signal.action is Action.CLOSE
    assert "converged" in signal.reason or "stop" in signal.reason
    assert strategy.position is None


def test_time_stop():
    strategy, cl, uso, ts = warmed_strategy()
    ts += timedelta(minutes=1)
    assert strategy.on_bar(PairBar(ts, cl * 1.02, uso)).action is Action.BUY
    # Deviation persists past max_hold_minutes -> time stop.
    signal = None
    for i in range(PARAMS.max_hold_minutes + 5):
        ts += timedelta(minutes=1)
        signal = strategy.on_bar(PairBar(ts, cl * 1.02, uso))
        if signal is not None:
            break
    assert signal is not None and signal.action is Action.CLOSE


def test_eod_flatten():
    strategy, cl, uso, ts = warmed_strategy()
    ts += timedelta(minutes=1)
    assert strategy.on_bar(PairBar(ts, cl * 1.02, uso)).action is Action.BUY
    late = ts.replace(hour=15, minute=56)
    signal = strategy.on_bar(PairBar(late, cl * 1.02, uso))
    assert signal is not None and signal.action is Action.CLOSE
    assert signal.reason == "eod_flatten"


def test_no_new_entries_late_in_session():
    strategy, cl, uso, ts = warmed_strategy()
    late = ts.replace(hour=15, minute=35)
    signal = strategy.on_bar(PairBar(late, cl * 1.02, uso))
    assert signal is None
    assert strategy.position is None


def test_one_position_at_a_time():
    strategy, cl, uso, ts = warmed_strategy()
    ts += timedelta(minutes=1)
    assert strategy.on_bar(PairBar(ts, cl * 1.02, uso)).action is Action.BUY
    ts += timedelta(minutes=1)
    # Still dislocated, but already long -> no second entry.
    signal = strategy.on_bar(PairBar(ts, cl * 1.03, uso))
    assert signal is None or signal.action is Action.CLOSE
