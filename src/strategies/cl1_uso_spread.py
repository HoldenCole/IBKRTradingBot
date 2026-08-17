"""CL1/USO time-difference strategy.

USO holds front-month-ish CL futures but only trades during equity RTH,
while CL trades ~23h/day. Overnight and intraday CL moves therefore reach
USO with a lag. We measure USO's deviation from its CL-implied fair value
as a z-scored residual spread and trade USO shares toward convergence.

CL is a signal input only — the future is never traded (v1).
See CL1_USO_STRATEGY.md for the full spec.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum

import numpy as np

from src.strategies.base import Action, Signal, Strategy


@dataclass(frozen=True)
class PairBar:
    """One synchronized 1-minute observation: both instruments printed."""

    ts: datetime  # ET, naive or tz-aware; only .time() is used for session logic
    cl_close: float
    uso_close: float


@dataclass(frozen=True)
class SpreadParams:
    beta_lookback: int = 1950      # ~5 RTH days of 1-min returns
    # Beta is estimated on returns up to beta_exclude_recent bars ago so the
    # dislocation being measured can't contaminate its own hedge ratio.
    beta_exclude_recent: int = 60
    z_lookback: int = 390          # ~1 RTH day
    entry_z: float = 2.0
    exit_z: float = 0.25
    stop_z: float = 4.0
    max_hold_minutes: int = 120
    min_history: int = 450
    allow_short: bool = True
    no_new_entries_after: time = time(15, 30)
    flatten_at: time = time(15, 55)


@dataclass(frozen=True)
class SpreadState:
    beta: float
    spread: float
    z: float


class FairValueModel:
    """Rolling beta + z-scored residual spread of log(USO) vs beta*log(CL).

    Works in log space so CL contract rolls (price gaps between months)
    only contaminate a single return observation instead of every level.
    """

    def __init__(self, params: SpreadParams):
        self.params = params
        maxlen = (
            max(params.beta_lookback + params.beta_exclude_recent, params.z_lookback) + 1
        )
        self._log_cl: deque[float] = deque(maxlen=maxlen)
        self._log_uso: deque[float] = deque(maxlen=maxlen)

    @property
    def n_obs(self) -> int:
        return len(self._log_cl)

    def update(self, cl_close: float, uso_close: float) -> SpreadState | None:
        if cl_close <= 0 or uso_close <= 0:
            raise ValueError(f"non-positive price: cl={cl_close} uso={uso_close}")
        self._log_cl.append(math.log(cl_close))
        self._log_uso.append(math.log(uso_close))

        if self.n_obs < self.params.min_history:
            return None

        log_cl = np.asarray(self._log_cl)
        log_uso = np.asarray(self._log_uso)

        # Beta from 1-min log returns, excluding the most recent bars so a
        # dislocation in progress can't drag its own hedge ratio around.
        r_cl_all = np.diff(log_cl)
        r_uso_all = np.diff(log_uso)
        exclude = self.params.beta_exclude_recent
        if len(r_cl_all) > exclude + 60:  # keep at least ~an hour of returns
            r_cl_all = r_cl_all[:-exclude] if exclude else r_cl_all
            r_uso_all = r_uso_all[:-exclude] if exclude else r_uso_all
        n_ret = min(self.params.beta_lookback, len(r_cl_all))
        r_cl = r_cl_all[-n_ret:]
        r_uso = r_uso_all[-n_ret:]
        var_cl = float(np.var(r_cl))
        if var_cl <= 0:
            return None
        beta = float(np.cov(r_uso, r_cl)[0, 1] / var_cl)

        # Residual spread over the z window, scored against its own history.
        n_z = min(self.params.z_lookback, len(log_cl))
        spread = log_uso[-n_z:] - beta * log_cl[-n_z:]
        std = float(np.std(spread))
        if std <= 1e-12:
            return None
        z = float((spread[-1] - np.mean(spread)) / std)
        return SpreadState(beta=beta, spread=float(spread[-1]), z=z)


class PositionSide(Enum):
    FLAT = 0
    LONG = 1
    SHORT = -1


@dataclass
class _OpenPosition:
    side: PositionSide
    entry_ts: datetime
    entry_z: float


@dataclass
class Cl1UsoSpreadStrategy(Strategy):
    name: str = "cl1_uso_spread"
    params: SpreadParams = field(default_factory=SpreadParams)

    def __post_init__(self) -> None:
        self.model = FairValueModel(self.params)
        self.position: _OpenPosition | None = None
        self.last_state: SpreadState | None = None

    # -- helpers ---------------------------------------------------------

    def _held_minutes(self, now: datetime) -> float:
        assert self.position is not None
        return (now - self.position.entry_ts).total_seconds() / 60.0

    def _close(self, reason: str) -> Signal:
        self.position = None
        return Signal(action=Action.CLOSE, reason=reason)

    # -- main entrypoint -------------------------------------------------

    def on_bar(self, bar: PairBar) -> Signal | None:
        state = self.model.update(bar.cl_close, bar.uso_close)
        self.last_state = state

        # Flatten at EOD regardless of whether the model has a reading.
        if self.position is not None and bar.ts.time() >= self.params.flatten_at:
            return self._close("eod_flatten")

        if state is None:
            return None
        z = state.z
        p = self.params

        if self.position is not None:
            side = self.position.side
            # Exit priority: stop, convergence, time stop (spec order).
            if side is PositionSide.LONG and z <= -p.stop_z:
                return self._close(f"stop z={z:.2f}")
            if side is PositionSide.SHORT and z >= p.stop_z:
                return self._close(f"stop z={z:.2f}")
            if abs(z) <= p.exit_z:
                return self._close(f"converged z={z:.2f}")
            if self._held_minutes(bar.ts) >= p.max_hold_minutes:
                return self._close(f"time_stop z={z:.2f}")
            return None

        # Flat: look for entries.
        if bar.ts.time() >= p.no_new_entries_after:
            return None
        if z < -p.entry_z:
            self.position = _OpenPosition(PositionSide.LONG, bar.ts, z)
            return Signal(action=Action.BUY, reason=f"uso_cheap z={z:.2f}")
        if z > p.entry_z and p.allow_short:
            self.position = _OpenPosition(PositionSide.SHORT, bar.ts, z)
            return Signal(action=Action.SELL_SHORT, reason=f"uso_rich z={z:.2f}")
        return None
