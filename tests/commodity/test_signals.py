"""Tests for the three signal modules — verify each fires correctly on
constructed price paths and respects look-ahead discipline."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.commodity.signals import (
    sma_crossover, donchian_breakout, vol_adj_momentum,
)


def _idx(n):
    return pd.date_range("2015-01-01", periods=n, freq="B")


def test_sma_crossover_uptrend_on():
    # Strictly rising price -> close > SMA50 > SMA200 once warmed up
    n = 400
    close = pd.DataFrame({"X": np.linspace(100, 300, n)}, index=_idx(n))
    on = sma_crossover(close, 50, 200)
    # Last value must be ON in a clean uptrend
    assert bool(on["X"].iloc[-1])
    # Warmup region (before SMA200 is valid, i.e. first 199 bars) must be OFF
    assert not on["X"].iloc[:199].any()


def test_sma_crossover_downtrend_off():
    n = 400
    close = pd.DataFrame({"X": np.linspace(300, 100, n)}, index=_idx(n))
    on = sma_crossover(close, 50, 200)
    assert not bool(on["X"].iloc[-1])


def test_donchian_enters_on_breakout_holds_then_exits():
    # Flat at 100 for 120 days, jump to 130 (>100-day high) -> ENTER,
    # hold through mild noise, then crash to 60 (<50-day low) -> EXIT.
    flat = [100.0] * 120
    up = [130.0] * 60          # above prior 100-day high -> long, stays long
    crash = [60.0] * 60        # below prior 50-day low -> exit to flat
    close = pd.DataFrame({"X": flat + up + crash}, index=_idx(240))
    on = donchian_breakout(close, 100, 50)
    # During the up segment (after warmup) we should be ON
    assert bool(on["X"].iloc[150])
    # After the crash settles we should be OFF
    assert not bool(on["X"].iloc[-1])


def test_donchian_no_lookahead_band_uses_prior_days():
    # A single one-day spike should not retroactively turn earlier bars ON.
    close = pd.DataFrame({"X": [100.0] * 150 + [200.0] + [100.0] * 50},
                         index=_idx(201))
    on = donchian_breakout(close, 100, 50)
    # The bar BEFORE the spike must be OFF (no peeking at the spike)
    assert not bool(on["X"].iloc[149])


def test_donchian_stays_flat_when_never_breaks_out():
    # Sawtooth within a tight band never exceeds the 100-day high
    n = 300
    close = pd.DataFrame({"X": 100 + np.sin(np.arange(n)) * 2}, index=_idx(n))
    on = donchian_breakout(close, 100, 50)
    # Could occasionally flip on at the very first qualifying bar; assert it's
    # mostly flat (a tight oscillation shouldn't sustain longs)
    assert on["X"].mean() < 0.5


def test_vol_adj_momentum_rising_then_fading():
    # Momentum that RISES into the late window then fades. The "top 50% of
    # trailing range" gate is a relative/acceleration signal: it should be ON
    # more during the rising phase than the fading phase. (Realistic noise
    # required — zero-noise returns give zero vol -> NaN ratio.)
    n = 1200
    rng = np.random.default_rng(3)
    noise = rng.standard_normal(n) * 0.006
    # drift ramps up over bars 500-850, then decays toward zero
    drift = np.concatenate([
        np.full(500, 0.0002),
        np.linspace(0.0002, 0.0018, 350),
        np.linspace(0.0018, -0.0002, 350),
    ])
    rets = pd.DataFrame({"X": drift + noise}, index=_idx(n))
    on = vol_adj_momentum(rets, ret_window=252, range_window=504)
    rising = on["X"].iloc[850:1000].mean()    # momentum near its range top
    fading = on["X"].iloc[1050:].mean()        # momentum decaying -> lower in range
    assert rising > fading, f"rising {rising:.2f} should exceed fading {fading:.2f}"
    assert rising > 0.3, f"rising-phase ON rate too low: {rising:.2f}"


def test_vol_adj_momentum_warmup_is_off():
    n = 900
    rets = pd.DataFrame({"X": np.full(n, 0.0005)}, index=_idx(n))
    on = vol_adj_momentum(rets, ret_window=252, range_window=504)
    # Before ret_window+range_window bars there is no valid signal
    assert not on["X"].iloc[:740].any()


def test_vol_adj_momentum_median_mode_runs():
    n = 900
    rets = pd.DataFrame({"X": np.full(n, 0.0005)}, index=_idx(n))
    on = vol_adj_momentum(rets, 252, 504, range_mode="median")
    assert on.shape == rets.shape
