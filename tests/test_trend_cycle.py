"""Trend & Cycle state-code tests — synthetic series, no network."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.trend_cycle import State, cycle, quadrant_balances, quadrants, state, state_history, to_bars, trend


def osc(vals):
    return pd.Series(np.asarray(vals, dtype=float), index=pd.bdate_range("2026-01-01", periods=len(vals)))


def test_quadrant_definitions():
    #            start  up>0  up>0  down>0 down<0 down<0 up<0  up>0
    q = quadrants(osc([1.0, 2.0, 3.0, 2.0, -1.0, -2.0, -1.0, 0.5]))
    assert np.isnan(q.iloc[0])
    assert list(q.iloc[1:].astype(int)) == [2, 2, 3, 4, 4, 1, 2]


def test_code_counts_quadrant_and_side():
    # above zero for 6 bars; the last 3 of them falling -> Q3, 03, 06
    s = state(osc([-1, 1, 2, 3, 2.5, 2.0, 1.5]))
    assert s == State(3, 3, 6) and s.code == "30306"
    # below zero 4 bars: fall, fall, rise, fall -> Q4 for 1, below zero for 4
    s = state(osc([1, -1, -2, -1.5, -3]))
    assert s == State(4, 1, 4) and s.code == "40104"


def test_side_count_survives_a_quadrant_change():
    h = state_history(osc([-1, 1, 2, 3, 2, 1]))
    assert list(h["quadrant"]) == [2, 2, 2, 3, 3]
    assert list(h["in_quadrant"]) == [1, 2, 3, 1, 2]
    assert list(h["on_side"]) == [1, 2, 3, 4, 5]


def test_cycle_is_sma5_minus_sma15_and_trend_is_coppock():
    c = pd.Series(np.linspace(100, 200, 60), index=pd.bdate_range("2026-01-01", periods=60))
    assert abs(cycle(c).iloc[-1] - (c.tail(5).mean() - c.tail(15).mean())) < 1e-9
    roc = (c.pct_change(14) + c.pct_change(11)) * 100
    w = np.arange(1, 11)
    assert abs(trend(c).iloc[-1] - float(np.dot(roc.tail(10).values, w) / w.sum())) < 1e-9


def test_partial_week_and_month_bars_are_kept():
    c = pd.Series(np.arange(1.0, 41.0), index=pd.bdate_range(end="2026-11-18", periods=40))  # ends on a Wednesday
    assert to_bars(c, "W").iloc[-1] == 40.0 and to_bars(c, "M").iloc[-1] == 40.0
    assert to_bars(c, "D") is c


def test_balances_sum_to_100_and_q1q2_is_the_rising_share():
    idx = pd.bdate_range(end="2026-11-20", periods=900)
    rng = np.random.default_rng(1)
    members = {f"M{i}": pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.015, len(idx))), index=idx) for i in range(60)}
    bal = quadrant_balances(members)
    for tf in ("D", "W", "M"):
        for m in ("cycle", "trend"):
            r = bal[tf][m]
            assert abs(r["q1"] + r["q2"] + r["q3"] + r["q4"] - 100) < 0.05
            assert abs(r["q1q2"] - (r["q1"] + r["q2"])) < 0.02 and r["n"] == 60
    assert quadrant_balances({k: members[k] for k in list(members)[:10]}) is None
