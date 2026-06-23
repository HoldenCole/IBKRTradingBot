"""Strategy signal state — the result of running a strategy's logic on
a given trading date.

Stage 1 strategies are long-flat with a single ON/OFF signal. This module
defines the canonical state representation and the transition-detection
logic. Pure data + pure functions; no I/O, no broker, no clock. Tested
in isolation; consumed by the daily-check orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Literal

import pandas as pd


class SignalState(str, Enum):
    """Long/flat regime for a single strategy at a single date."""
    ON = "ON"           # holding the risk asset (QQQ / BTC vehicle)
    OFF = "OFF"         # in T-bill OFF vehicle (SGOV)
    UNKNOWN = "UNKNOWN" # warmup or missing data


@dataclass(frozen=True)
class SignalSnapshot:
    """The state of one strategy on one date.

    Carries the diagnostic numbers (close, SMA50, SMA200) so the state can
    be audited after-the-fact without recomputing from the data. `state` is
    the decision; the rest is the evidence.
    """
    strategy_id: str
    as_of: date           # the trading date this snapshot's state applies to
    state: SignalState
    close: float          # the close used to compute SMA50/SMA200 and the gate
    sma50: float | None   # None during warmup
    sma200: float | None  # None during warmup
    # The convention shift: this state was computed from close[as_of], but it
    # determines the position held from close[as_of] forward (Convention 2,
    # signal[t-1] -> ret[t]). Recorded so post-hoc audit can verify the lag.
    governs_returns_from_next_session: bool = True

    def passes_gate(self) -> bool:
        """The validated rule: ON iff close > SMA50 AND SMA50 > SMA200."""
        if self.sma50 is None or self.sma200 is None:
            return False
        return self.close > self.sma50 and self.sma50 > self.sma200


@dataclass(frozen=True)
class StateChange:
    """A flip in a strategy's state between two consecutive trading dates."""
    strategy_id: str
    prev_state: SignalState
    new_state: SignalState
    prev_date: date | None       # None if there was no prior snapshot (first run)
    new_date: date

    @property
    def is_flip(self) -> bool:
        """A flip = ON↔OFF transition that should trigger trading.

        Excluded: UNKNOWN→anything (warmup completion is not a tradeable
        event because nothing was held in UNKNOWN state) and same-state
        sequences (which shouldn't be passed in but are handled defensively).
        """
        if self.prev_state == SignalState.UNKNOWN:
            return False
        return self.prev_state != self.new_state

    @property
    def direction(self) -> Literal["enter", "exit", "noop"]:
        if not self.is_flip:
            return "noop"
        return "enter" if self.new_state == SignalState.ON else "exit"


def compute_signal(strategy_id: str, close_series: pd.Series, as_of: date,
                   fast: int = 50, slow: int = 200) -> SignalSnapshot:
    """Compute one strategy's SignalSnapshot for a given date from a daily
    close series. The series must include all closes through `as_of`.

    Convention 2: the snapshot at date `as_of` is computed from closes
    through `as_of` and determines the position held during the NEXT
    session's bar (no same-bar look-ahead in live trading).

    Returns UNKNOWN with sma fields = None if the series doesn't have
    enough history yet (need at least `slow` closes through `as_of`).
    """
    if close_series.empty:
        return SignalSnapshot(strategy_id, as_of, SignalState.UNKNOWN,
                              close=float("nan"), sma50=None, sma200=None)

    s = close_series.copy()
    # Normalize index to dates (drop any time component)
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    target = pd.Timestamp(as_of)
    if target not in s.index:
        # `as_of` must be a trading date for that asset
        raise ValueError(f"{as_of} not present in close series for {strategy_id}")

    through = s.loc[:target]
    if len(through) < slow:
        return SignalSnapshot(strategy_id, as_of, SignalState.UNKNOWN,
                              close=float(through.iloc[-1]), sma50=None, sma200=None)

    sma_fast = float(through.tail(fast).mean())
    sma_slow = float(through.tail(slow).mean())
    close = float(through.iloc[-1])
    state = SignalState.ON if (close > sma_fast and sma_fast > sma_slow) \
            else SignalState.OFF
    return SignalSnapshot(
        strategy_id=strategy_id, as_of=as_of, state=state,
        close=close, sma50=sma_fast, sma200=sma_slow,
    )


def detect_change(prev: SignalSnapshot | None,
                  curr: SignalSnapshot) -> StateChange:
    """Compute the StateChange from prev->curr. If prev is None (first
    run), the change is treated as UNKNOWN->curr.state (not a tradeable
    flip)."""
    prev_state = prev.state if prev is not None else SignalState.UNKNOWN
    prev_date = prev.as_of if prev is not None else None
    return StateChange(
        strategy_id=curr.strategy_id,
        prev_state=prev_state, new_state=curr.state,
        prev_date=prev_date, new_date=curr.as_of,
    )
