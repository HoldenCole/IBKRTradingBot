"""Tests for the long-short engine path + signed vol-targeting + LS signals."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.commodity.vol import vol_target_weights_signed, rolling_cov
from src.commodity.engine import run_backtest_ls, EngineConfig
from src.commodity.signals import vol_adj_momentum_ls, carry_signal


def _panel(n=900, k=3, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2014-01-01", periods=n, freq="B")
    syms = [f"A{i}" for i in range(k)]
    rets = pd.DataFrame(rng.standard_normal((n, k)) * 0.01, index=idx, columns=syms)
    return rets, syms


def test_signed_weights_respect_direction_and_cap():
    rets, syms = _panel()
    cov = rolling_cov(rets, lookback=60)
    last = sorted(cov.keys())[-1]
    direction = pd.Series([1.0, -1.0, 0.0], index=syms)
    w = vol_target_weights_signed(cov[last], direction, target_vol=0.15, max_weight=0.25)
    assert w[syms[0]] > 0      # long
    assert w[syms[1]] < 0      # short
    assert w[syms[2]] == 0     # flat
    assert (w.abs() <= 0.25 + 1e-9).all()


def test_signed_weights_hit_vol_target_when_uncapped():
    # Low target so the cap doesn't bind; realized portfolio vol ~ target.
    rets, syms = _panel(seed=1)
    cov = rolling_cov(rets, lookback=60)
    last = sorted(cov.keys())[-1]
    direction = pd.Series([1.0, -1.0, 1.0], index=syms)
    w = vol_target_weights_signed(cov[last], direction, target_vol=0.05, max_weight=0.50)
    port_vol = float(np.sqrt(w.values @ cov[last].values @ w.values))
    assert abs(port_vol - 0.05) < 0.005


def test_ls_engine_runs_and_collateral_floor():
    rets, syms = _panel()
    # all-flat direction -> book is just collateral yield
    direction = pd.DataFrame(0.0, index=rets.index, columns=syms)
    sectors = {s: "Energy" for s in syms}
    res = run_backtest_ls(rets, direction, sectors,
                          EngineConfig(tbill_annual=0.04, apply_costs=True))
    yrs = len(rets) / 252
    assert abs(res.equity.iloc[-1] - 1.04 ** yrs) / (1.04 ** yrs) < 0.02
    assert res.gross_long.sum() == 0


def test_ls_engine_profits_when_short_a_faller():
    # Construct an instrument that steadily falls; a SHORT should make money
    # on top of collateral.
    n = 400
    idx = pd.date_range("2014-01-01", periods=n, freq="B")
    rets = pd.DataFrame({"X": np.full(n, -0.002) + np.random.default_rng(0).standard_normal(n)*0.001},
                        index=idx)
    direction = pd.DataFrame(-1.0, index=idx, columns=["X"])   # always short
    res = run_backtest_ls(rets, direction, {"X": "Energy"},
                          EngineConfig(tbill_annual=0.0, apply_costs=False))
    assert res.equity.iloc[-1] > 1.0       # shorting a faller makes money


def test_ls_engine_no_lookahead():
    rets, syms = _panel(n=300)
    direction = pd.DataFrame(0.0, index=rets.index, columns=syms)
    direction.iloc[-1] = 1.0               # only the last day is ON
    res = run_backtest_ls(rets, direction, {s: "Energy" for s in syms},
                          EngineConfig(tbill_annual=0.0, apply_costs=False))
    assert res.gross_long.sum() == 0       # prior-day signal drives return


def test_momentum_ls_emits_three_states():
    rets, syms = _panel(n=1200, seed=7)
    d = vol_adj_momentum_ls(rets, 252, 504)
    vals = set(np.unique(d.values))
    assert vals.issubset({-1.0, 0.0, 1.0})
    # over a long random panel we expect all three states to appear somewhere
    assert {-1.0, 1.0}.issubset(vals)


def test_carry_signal_directions():
    idx = pd.date_range("2014-01-01", periods=50, freq="B")
    front = pd.DataFrame({"X": np.full(50, 100.0)}, index=idx)
    # backwardation: second < front -> ratio>0 -> LONG
    second_back = pd.DataFrame({"X": np.full(50, 98.0)}, index=idx)
    d = carry_signal(front, second_back, short_threshold_monthly=-0.005)
    assert (d["X"] == 1.0).all()
    # deep contango: second >> front -> ratio<<0 -> SHORT
    second_cont = pd.DataFrame({"X": np.full(50, 102.0)}, index=idx)
    d2 = carry_signal(front, second_cont, short_threshold_monthly=-0.005)
    assert (d2["X"] == -1.0).all()
