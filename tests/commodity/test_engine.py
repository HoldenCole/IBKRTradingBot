"""Smoke + sanity tests for the backtest engine and metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.commodity.engine import run_backtest, EngineConfig
from src.commodity import metrics as M


def _panel(n=400, k=3, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2015-01-01", periods=n, freq="B")
    syms = [f"A{i}" for i in range(k)]
    rets = pd.DataFrame(rng.standard_normal((n, k)) * 0.01 + 0.0003,
                        index=idx, columns=syms)
    close = (1 + rets).cumprod() * 100
    return close, rets, syms


def test_engine_runs_and_equity_positive():
    close, rets, syms = _panel()
    on = pd.DataFrame(True, index=rets.index, columns=syms)
    sectors = {s: "Energy" for s in syms}
    res = run_backtest(close, rets, on, sectors,
                       EngineConfig(cov_lookback=60, apply_costs=True))
    assert len(res.equity) == len(rets)
    assert res.equity.iloc[-1] > 0
    # gross long should be > 0 once warmed up (all signals ON)
    assert res.gross_long.iloc[100:].mean() > 0


def test_flat_signal_earns_tbill_only():
    close, rets, syms = _panel()
    off = pd.DataFrame(False, index=rets.index, columns=syms)
    sectors = {s: "Energy" for s in syms}
    res = run_backtest(close, rets, off, sectors,
                       EngineConfig(cov_lookback=60, tbill_annual=0.05,
                                    apply_costs=True))
    # No commodity exposure -> equity grows at ~5% annual T-bill
    yrs = len(rets) / 252
    expected = 1.05 ** yrs
    assert abs(res.equity.iloc[-1] - expected) / expected < 0.02
    assert res.gross_long.sum() == 0


def test_costs_reduce_return():
    close, rets, syms = _panel(seed=2)
    # alternating signal to force turnover
    on = pd.DataFrame(False, index=rets.index, columns=syms)
    on.iloc[::4] = True
    sectors = {s: "Energy" for s in syms}
    res_nc = run_backtest(close, rets, on, sectors,
                          EngineConfig(apply_costs=False))
    res_c = run_backtest(close, rets, on, sectors,
                         EngineConfig(apply_costs=True))
    assert res_c.equity.iloc[-1] <= res_nc.equity.iloc[-1]
    assert res_c.cost_drag.sum() > 0


def test_metrics_basic():
    rng = np.random.default_rng(5)
    r = pd.Series(rng.standard_normal(1000) * 0.01 + 0.0004,
                  index=pd.date_range("2015-01-01", periods=1000, freq="B"))
    m = M.compute(r)
    assert m.n_days == 1000
    assert -1 < m.cagr < 5
    assert m.vol > 0
    assert m.after_tax_cagr <= m.cagr  # tax never increases return on a gain


def test_no_lookahead_signal_shift():
    """Engine must use signal at t-1 for return at t. Construct a signal that
    is ON only on the LAST day; it should produce zero commodity exposure on
    every return day (since the prior-day signal is always OFF until the very
    end, which has no next day)."""
    close, rets, syms = _panel(n=300)
    on = pd.DataFrame(False, index=rets.index, columns=syms)
    on.iloc[-1] = True
    sectors = {s: "Energy" for s in syms}
    res = run_backtest(close, rets, on, sectors, EngineConfig(apply_costs=False))
    # gross_long earned on any day comes from prior-day signal; only the very
    # last signal flips ON but there's no day after it -> never deployed
    assert res.gross_long.sum() == 0
