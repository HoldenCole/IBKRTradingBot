"""Four-quadrant macro regime classifier (growth x inflation).

Implements the regime framework in REGIMES.md: growth state = SPY vs its
10-month SMA, inflation state = DBC (broad commodities) vs its 10-month
SMA, both evaluated on month-end closes. Ex-ante by construction: the
quadrant used during month T is computed from data through the end of
month T-1 — callers must use `quadrant_series`, which applies that shift.

This module fills the `regime_active()` interface reserved in
STRATEGIES.md: each strategy family declares the quadrants it may trade
in (ACTIVE_QUADRANTS), and the runner gates entries accordingly.
Fail-closed: no classification (insufficient history) -> no trading.
"""

from __future__ import annotations

from enum import Enum

import pandas as pd

SMA_MONTHS = 10


class Quadrant(Enum):
    GROWTH = "G+I-"        # growth up, inflation down: equities lead
    REFLATION = "G+I+"     # growth up, inflation up: commodities/oil lead
    STAGFLATION = "G-I+"   # growth down, inflation up: nothing works; defense
    DEFLATION = "G-I-"     # growth down, inflation down: bonds by the book,
                           # but hides post-crash equity rebounds (see REGIMES.md)


# Which quadrants each strategy family may trade in. Backtest basis is in
# REGIMES.md; conservative by default — widen only with evidence.
ACTIVE_QUADRANTS: dict[str, set[Quadrant]] = {
    "equity_reversion": {Quadrant.GROWTH},          # EWO / IBS / afternoon suite
    "commodity_trend": {Quadrant.REFLATION},        # CL surge calls, trend variants
    "defense": {Quadrant.STAGFLATION, Quadrant.DEFLATION},  # T-bills / stand down
}


def classify(spy_month_closes: pd.Series, dbc_month_closes: pd.Series) -> Quadrant | None:
    """Quadrant from month-end closes (last value = most recent month-end).

    Returns None when there is not enough history for the SMA.
    """
    if len(spy_month_closes) < SMA_MONTHS or len(dbc_month_closes) < SMA_MONTHS:
        return None
    growth_on = spy_month_closes.iloc[-1] > spy_month_closes.tail(SMA_MONTHS).mean()
    infl_on = dbc_month_closes.iloc[-1] > dbc_month_closes.tail(SMA_MONTHS).mean()
    if growth_on and not infl_on:
        return Quadrant.GROWTH
    if growth_on and infl_on:
        return Quadrant.REFLATION
    if infl_on:
        return Quadrant.STAGFLATION
    return Quadrant.DEFLATION


# --- Shadow classifier (INFORMATIONAL ONLY — drives no allocation) ---
# The user's structural hypothesis: post-2007 markets (indexed,
# systematic) reward faster re-entry off bottoms. Evidence: the
# fast-entry edge is negative in both pre-2007 decades and positive in
# all four modern 5-year windows including both modern grind bears
# (PORTFOLIOS.md). Spec: identical quadrant logic except the equity leg
# enters risk-on via the FAST SMA when currently risk-off; exits stay
# on the 10m SMA; the inflation leg is unchanged. Stateful hysteresis,
# reconstructed deterministically from the price history each run
# (initialized from the plain 10m rule at the first computable month).
# Adoption trigger (pre-registered): promoted only if it wins the
# majority of its first several LIVE re-entry disagreements with the
# primary, as recorded in the forward ledger.
FAST_ENTRY_MONTHS = 5


def _asymmetric_growth_on(spy_month_closes: pd.Series) -> bool | None:
    """Final state of the fast-entry/slow-exit growth flag."""
    if len(spy_month_closes) < SMA_MONTHS:
        return None
    sma_slow = spy_month_closes.rolling(SMA_MONTHS).mean()
    sma_fast = spy_month_closes.rolling(FAST_ENTRY_MONTHS).mean()
    on: bool | None = None
    for i in range(len(spy_month_closes)):
        if pd.isna(sma_slow.iloc[i]):
            continue
        px = spy_month_closes.iloc[i]
        if on is None:
            on = bool(px > sma_slow.iloc[i])
        elif on:
            on = bool(px > sma_slow.iloc[i])
        else:
            on = bool(px > sma_fast.iloc[i])
    return on


def shadow_classify(spy_month_closes: pd.Series, dbc_month_closes: pd.Series) -> Quadrant | None:
    """Shadow quadrant: fast-entry equity leg, standard inflation leg."""
    if len(spy_month_closes) < SMA_MONTHS or len(dbc_month_closes) < SMA_MONTHS:
        return None
    growth_on = _asymmetric_growth_on(spy_month_closes)
    if growth_on is None:
        return None
    infl_on = dbc_month_closes.iloc[-1] > dbc_month_closes.tail(SMA_MONTHS).mean()
    if growth_on and not infl_on:
        return Quadrant.GROWTH
    if growth_on and infl_on:
        return Quadrant.REFLATION
    if infl_on:
        return Quadrant.STAGFLATION
    return Quadrant.DEFLATION


def quadrant_series(spy_daily: pd.Series, dbc_daily: pd.Series) -> pd.Series:
    """Monthly Quadrant series, shifted so month T uses data through T-1.

    Index = month-end stamps; value = the quadrant IN FORCE for the month
    that follows each stamp. Months without enough history are dropped.
    """
    if spy_daily.empty or dbc_daily.empty:
        return pd.Series(dtype=object)
    spy_m = spy_daily.resample("ME").last()
    dbc_m = dbc_daily.resample("ME").last()
    out = {}
    for i in range(SMA_MONTHS - 1, len(spy_m)):
        stamp = spy_m.index[i]
        if stamp not in dbc_m.index:
            continue
        q = classify(spy_m.iloc[: i + 1], dbc_m.loc[:stamp])
        if q is not None:
            out[stamp] = q
    return pd.Series(out)


def regime_active(family: str, spy_daily: pd.Series, dbc_daily: pd.Series) -> bool:
    """Gate for the live runner: may `family` trade right now?

    Uses the most recent COMPLETED month's classification (ex-ante).
    Unknown family or unclassifiable data fails closed.
    """
    allowed = ACTIVE_QUADRANTS.get(family)
    if not allowed:
        return False
    series = quadrant_series(spy_daily, dbc_daily)
    if series.empty:
        return False
    return series.iloc[-1] in allowed
