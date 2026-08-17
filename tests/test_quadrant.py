"""Quadrant classifier: all four states, ex-ante shift, fail-closed."""

import numpy as np
import pandas as pd

from src.regime.quadrant import Quadrant, classify, quadrant_series, regime_active


def months(vals):
    idx = pd.date_range("2020-01-31", periods=len(vals), freq="ME")
    return pd.Series(vals, index=idx)


RISING = months(list(np.linspace(100, 150, 12)))
FALLING = months(list(np.linspace(150, 100, 12)))


def test_all_four_quadrants():
    assert classify(RISING, FALLING) is Quadrant.GROWTH
    assert classify(RISING, RISING) is Quadrant.REFLATION
    assert classify(FALLING, RISING) is Quadrant.STAGFLATION
    assert classify(FALLING, FALLING) is Quadrant.DEFLATION


def test_insufficient_history_fails_closed():
    short = months(list(np.linspace(100, 120, 5)))
    assert classify(short, short) is None


def daily(vals_per_month, start="2020-01-01"):
    idx = pd.date_range(start, periods=len(vals_per_month) * 21, freq="B")
    return pd.Series(np.repeat(vals_per_month, 21)[: len(idx)], index=idx)


def test_quadrant_series_classifies_trends():
    spy = daily(list(np.linspace(100, 200, 24)))
    dbc = daily(list(np.linspace(200, 100, 24)))
    series = quadrant_series(spy, dbc)
    assert not series.empty
    # Monotonic rise vs fall -> GROWTH throughout the classified range.
    assert set(series.values) == {Quadrant.GROWTH}


def test_regime_active_gating():
    spy = daily(list(np.linspace(100, 200, 24)))
    dbc = daily(list(np.linspace(200, 100, 24)))
    assert regime_active("equity_reversion", spy, dbc) is True
    assert regime_active("commodity_trend", spy, dbc) is False   # needs REFLATION
    assert regime_active("unknown_family", spy, dbc) is False    # fail closed


def test_regime_active_empty_data_fails_closed():
    empty = pd.Series(dtype=float)
    assert regime_active("equity_reversion", empty, empty) is False
