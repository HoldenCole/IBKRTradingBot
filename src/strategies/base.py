"""Strategy base class and Signal type."""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

import pandas as pd


class SignalAction(str, Enum):
    LONG = "long"
    SHORT_FADE = "short_fade"  # via SQQQ calls (long SQQQ exposure)
    CLOSE = "close"


@dataclass(frozen=True)
class OptionSelection:
    """Concrete option contract spec the executor should price + qualify."""
    underlying_etf: str             # UPRO | TQQQ | SQQQ
    right: Literal["C"] = "C"       # calls only per spec
    target_dte_days: tuple[int, int] = (7, 14)  # min, max
    strike_offset: int = 0          # 0=ATM, -1=1-strike-ITM (for calls, lower strike)


@dataclass(frozen=True)
class Signal:
    action: SignalAction
    underlying: str                 # SPY | QQQ (signal universe)
    option: OptionSelection
    contracts: int
    reason: str                     # human-readable why
    strategy_name: str
    strategy_family: str            # "mean_reversion" | "afternoon"
    fired_at: datetime
    invalidation_price: float | None = None  # underlying price past which to abort fill chase


class Strategy(ABC):
    name: str = "base"
    family: str = "mean_reversion"

    def on_daily_close(self, symbol: str, daily: pd.DataFrame) -> Signal | None:
        """Called after the 16:00 ET daily close on each underlying.

        `daily` is a DataFrame indexed by date with columns
        [open, high, low, close, volume] for `symbol`.
        Return a Signal (action LONG/SHORT_FADE) or None. Default: no-op.
        """
        return None

    def on_intraday_bar(self, symbol: str, bar: dict, session: pd.DataFrame) -> Signal | None:
        """Called per 5-min bar during the session for intraday strategies.
        Default: do nothing. Afternoon Reversion overrides this.
        """
        return None
