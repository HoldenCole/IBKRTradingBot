"""Walk-forward train/test split utility.

For an 8-year backtest with fixed-threshold strategies (no fitting), the
"walk-forward" we care about is: report metrics on an early-period sample
AND a late-period sample, and verify they're consistent. Big divergence
between in-sample and out-of-sample = the strategy worked in one regime
and not another, which is information.

Default: 5-year train (in-sample) / 3-year test (out-of-sample). Single
fold, since we don't refit anything. Multi-fold rolling walk-forward is
a future extension if/when fitted parameters get added.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: date
    train_end: date     # inclusive
    test_start: date
    test_end: date      # inclusive

    @property
    def train_label(self) -> str:
        return f"{self.train_start.isoformat()}..{self.train_end.isoformat()}"

    @property
    def test_label(self) -> str:
        return f"{self.test_start.isoformat()}..{self.test_end.isoformat()}"


def single_fold(
    start: date,
    end: date,
    train_years: int = 5,
    test_years: int = 3,
) -> WalkForwardFold:
    """One non-overlapping (train, test) split, oldest-data-first.
    `train_years + test_years` should equal `(end - start).years` roughly.
    """
    train_end = date(start.year + train_years, start.month, start.day) - timedelta(days=1)
    test_start = train_end + timedelta(days=1)
    return WalkForwardFold(
        train_start=start,
        train_end=train_end,
        test_start=test_start,
        test_end=end,
    )
