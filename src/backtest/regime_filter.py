"""Regime filter — gates strategy entries at signal time.

Pure-function classifiers over `daily_bars[underlying]` data already in the
pipeline. No external data sources, no IV history, no VIX feed required.
The user's separate regime model can drop in later via the same Protocol;
the rules here are the explicit baseline to beat.

Three candidate filters, all evaluated on the SIGNAL DAY (the day the
strategy fires its on_daily_close):

  V0_drawdown_30d    — exclude when 30d drawdown from rolling 30d high
                       exceeds threshold (default -7%). Captures
                       "active correction in progress."

  V1_sma200_band     — exclude when |close - SMA200| / SMA200 < band
                       (default 5%). Captures "uncertain trend zone"
                       where neither bullish nor bearish dominates.

  V2_trend_coherence — keep when price > SMA50 > SMA200 (bullish trend)
                       OR price < SMA50 < SMA200 (bearish trend).
                       Exclude all other configurations (chop/transition).

Plus composite filters (logical AND of multiple). The hypothesis we're
testing:

  - 2018 chop_to_correction (40 trades, -$877, Sortino -0.65) and
    2026 mixed (8 trades, -$785, Sortino -1.56) drag the LS_full
    overall Sortino from a weighted ~1.5+ down to 0.59.
  - A filter that excludes those regimes' entry days mechanically
    lifts the overall metric.

Risk: the filter excludes profitable regimes too. Per-regime data
suggests crisis_recovery (2020) and bear (2022) might be partially
excluded by some filter candidates. We test each candidate explicitly
and pick the one with the best lift, not the best-in-theory.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd


class RegimeFilter(Protocol):
    """Returns True if entries are allowed at `today`. False means skip."""

    name: str

    def is_active(self, daily: pd.DataFrame, today: date) -> bool: ...


def _index_of(daily: pd.DataFrame, today: date) -> int | None:
    for i, ts in enumerate(daily.index):
        d = ts.date() if hasattr(ts, "date") else ts
        if d == today:
            return i
    return None


@dataclass
class NoFilter:
    """Sanity-check baseline: never blocks. Same as no filter at all."""
    name: str = "none"

    def is_active(self, daily: pd.DataFrame, today: date) -> bool:
        return True


@dataclass
class DrawdownFilter:
    """V0 — exclude when N-day drawdown from rolling N-day high exceeds
    `threshold`. Default: 30-day drawdown > 7% triggers regime-off.

    Mechanism: identifies "active correction" periods where the underlying
    is more than X% below its recent peak. These are the regimes where IBS
    long-mean-reversion bounces fail to materialize and shorts haven't
    yet established a sustained downtrend.
    """
    lookback: int = 30
    threshold: float = -0.07
    name: str = "V0_drawdown_30d_7pct"

    def is_active(self, daily: pd.DataFrame, today: date) -> bool:
        i = _index_of(daily, today)
        if i is None or i < self.lookback:
            return True
        window = daily["close"].iloc[i - self.lookback: i + 1]
        rolling_high = float(window.max())
        current = float(window.iloc[-1])
        if rolling_high <= 0:
            return True
        dd = (current - rolling_high) / rolling_high
        return dd >= self.threshold


@dataclass
class Sma200BandFilter:
    """V1 — exclude when close is within `band` of SMA200 (uncertain trend).

    Mechanism: when price oscillates around its 200-day moving average,
    neither bull nor bear pattern dominates and IBS reversal signals
    have weak follow-through. Adding a buffer zone above/below SMA200
    forces entries to occur only when trend direction is decided.
    """
    sma_period: int = 200
    band: float = 0.05
    name: str = "V1_sma200_band_5pct"

    def is_active(self, daily: pd.DataFrame, today: date) -> bool:
        i = _index_of(daily, today)
        if i is None or i < self.sma_period:
            return True
        sma = float(daily["close"].iloc[i - self.sma_period + 1: i + 1].mean())
        close = float(daily["close"].iloc[i])
        if sma <= 0:
            return True
        distance = abs(close - sma) / sma
        return distance >= self.band


@dataclass
class TrendCoherenceFilter:
    """V2 — keep only when price > SMA50 > SMA200 (bull) OR
    price < SMA50 < SMA200 (bear). Exclude otherwise.

    Mechanism: a coherent trend (price aligned with both moving averages
    in the same direction) is the regime where IBS reversal signals
    work. When the alignment breaks (price > SMA200 but < SMA50, etc.),
    the regime is in transition or chop — exactly the conditions where
    IBS performs poorly per the data.
    """
    fast_sma: int = 50
    slow_sma: int = 200
    name: str = "V2_trend_coherence_50_200"

    def is_active(self, daily: pd.DataFrame, today: date) -> bool:
        i = _index_of(daily, today)
        if i is None or i < self.slow_sma:
            return True
        close = float(daily["close"].iloc[i])
        sma_fast = float(daily["close"].iloc[i - self.fast_sma + 1: i + 1].mean())
        sma_slow = float(daily["close"].iloc[i - self.slow_sma + 1: i + 1].mean())
        bullish = close > sma_fast > sma_slow
        bearish = close < sma_fast < sma_slow
        return bullish or bearish


@dataclass
class YearExclusionFilter:
    """Diagnostic only — explicitly excludes specific years.

    Not a real-world filter (uses hindsight). Used to answer the
    diagnostic question: if a filter could perfectly identify the
    bad regime years, would it lift overall metrics? If not, the
    per-regime Sortino structure is mostly equity-curve-slicing
    artifact and the filter approach is fundamentally limited.
    """
    excluded_years: set[int]
    name: str = "diagnostic_year_exclusion"

    def is_active(self, daily: pd.DataFrame, today: date) -> bool:
        return today.year not in self.excluded_years


@dataclass
class CompositeAndFilter:
    """Combine multiple filters with AND — all must be active to allow."""
    filters: list[RegimeFilter]
    name: str = "composite_and"

    def is_active(self, daily: pd.DataFrame, today: date) -> bool:
        return all(f.is_active(daily, today) for f in self.filters)


@dataclass
class CompositeOrFilter:
    """Combine multiple filters with OR — any active allows entry. Used
    for inverse-pattern combos like 'in trend OR not in deep drawdown'."""
    filters: list[RegimeFilter]
    name: str = "composite_or"

    def is_active(self, daily: pd.DataFrame, today: date) -> bool:
        return any(f.is_active(daily, today) for f in self.filters)
