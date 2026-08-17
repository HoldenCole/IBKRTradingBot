"""CL surge → USO calls strategy (signal logic).

Systematized from the user's discretionary trade: when CL1 gaps up hard
overnight AND oil is in an uptrend, buy USO calls $1-2 OTM at mid and
hold for several sessions. See CL_SURGE_CALLS.md for the evidence and
the full spec; the trend filter is what makes the rule survive across
regimes, so it is not optional.

This module is pure signal logic (daily cadence). Option order routing
and chain selection are wired separately in the live runner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Sequence


@dataclass(frozen=True)
class SurgeParams:
    surge_threshold: float = 0.02   # overnight CL return to trigger
    sma_fast: int = 50
    sma_slow: int = 200
    otm_offset_usd: float = 1.50    # strike ~ spot + offset ($1-2 OTM)
    target_dte_days: int = 14
    min_dte_days: int = 10
    hold_sessions: int = 5
    premium_stop_pct: float = 0.50  # exit if premium halves
    scale_out_gain_pct: float = 1.00  # sell half at +100%
    premium_budget_usd: float = 1000.0


@dataclass(frozen=True)
class CallPlan:
    """What to buy when the signal fires, handed to the execution layer."""

    signal_date: date
    overnight_cl_return: float
    uso_spot: float
    strike_target: float     # execution snaps to the nearest listed strike
    target_dte_days: int
    min_dte_days: int
    premium_budget_usd: float
    hold_sessions: int
    reason: str


def sma(values: Sequence[float], window: int) -> float:
    if len(values) < window:
        raise ValueError(f"need {window} values, got {len(values)}")
    tail = values[-window:]
    return sum(tail) / window


class ClSurgeCallsStrategy:
    """Evaluated once per day at the USO open (9:30 ET)."""

    name = "cl_surge_calls"

    def __init__(self, params: SurgeParams | None = None):
        self.params = params or SurgeParams()
        self.holding = False  # one position at a time; runner updates this

    def evaluate_open(
        self,
        today: date,
        cl_daily_closes: Sequence[float],  # daily CL closes, oldest -> newest
        cl_at_open: float,                 # CL1 price now (9:30 ET)
        cl_prev_1600: float,               # CL1 price at prior day 16:00 ET
        uso_open: float,
    ) -> CallPlan | None:
        p = self.params
        if self.holding:
            return None
        if len(cl_daily_closes) < p.sma_slow:
            return None
        if cl_at_open <= 0 or cl_prev_1600 <= 0 or uso_open <= 0:
            raise ValueError("non-positive price input")

        overnight = math.log(cl_at_open / cl_prev_1600)
        if overnight <= p.surge_threshold:
            return None

        # Trend filter — the regime gate that makes this survivable.
        fast = sma(cl_daily_closes, p.sma_fast)
        slow = sma(cl_daily_closes, p.sma_slow)
        if not (cl_daily_closes[-1] > fast and fast > slow):
            return None

        return CallPlan(
            signal_date=today,
            overnight_cl_return=overnight,
            uso_spot=uso_open,
            strike_target=uso_open + p.otm_offset_usd,
            target_dte_days=p.target_dte_days,
            min_dte_days=p.min_dte_days,
            premium_budget_usd=p.premium_budget_usd,
            hold_sessions=p.hold_sessions,
            reason=(
                f"cl_surge {overnight:+.2%} overnight, uptrend "
                f"(close>{p.sma_fast}sma>{p.sma_slow}sma)"
            ),
        )
