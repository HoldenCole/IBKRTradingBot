"""Weekly report: formatting helpers and derived facts (no network, no rendering)."""
import numpy as np
import pandas as pd

from src.report import build as B


def test_pct_uses_true_minus_and_sign():
    assert B.pct(0.0123) == "+1.2%"
    assert B.pct(-0.086) == "−8.6%"
    assert B.pct(float("nan")) == "n/a"


def test_yield_change_in_basis_points():
    row = {"kind": "yield", "wk": -24.2, "last": 4.91}
    assert B.chg(row, "wk") == "−24 bp"
    assert B.chg({"kind": "yield", "wk": 0.0}, "wk") == "0 bp"
    assert B.chg({"kind": "price", "wk": 0.05}, "wk") == "+5.0%"


def test_technical_state_flags_a_close_below_the_band():
    idx = pd.bdate_range("2024-01-01", periods=260)
    rng = np.random.default_rng(1)
    close = pd.Series(100 + np.cumsum(rng.normal(0.05, 0.3, 260)), index=idx)
    close.iloc[-2] = close.iloc[-3] * 0.97
    close.iloc[-1] = close.iloc[-2] * 0.96
    st = B.technical_state(close)
    assert st["below"] and st["run"] >= 1 and st["depth"] > 0
    assert st["rsi2"] < 10 and st["r3"] < -0.05 and st["z5"] < -2
    fired = [name for name, fn, _, _ in B.TRIGGERS if fn(st)]
    assert "Close below the lower band" in fired and "Three-day drop of 5% or more" in fired


def test_technical_state_quiet_market_fires_nothing():
    idx = pd.bdate_range("2024-01-01", periods=260)
    close = pd.Series(np.linspace(100, 130, 260), index=idx)
    st = B.technical_state(close)
    assert not st["below"] and st["run"] == 0
    assert not any(fn(st) for _, fn, _, _ in B.TRIGGERS)


def test_wave_mark_has_four_quadrant_segments():
    svg = B.wave_svg()
    assert svg.count("<polyline") == 4
    for q in (1, 2, 3, 4):
        assert B.S.Q[q] in svg
