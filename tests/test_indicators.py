from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import atr, ewo, ewo_zscore, ibs, rsi, sma, vwap


def test_sma_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert pd.isna(out.iloc[0]) and pd.isna(out.iloc[1])
    assert out.iloc[2] == 2.0
    assert out.iloc[4] == 4.0


def test_ibs_normal_and_flat():
    high = pd.Series([100.0, 100.0])
    low = pd.Series([99.0, 100.0])  # second bar flat
    close = pd.Series([99.75, 100.0])
    out = ibs(high, low, close)
    assert abs(out.iloc[0] - 0.75) < 1e-9
    assert pd.isna(out.iloc[1])  # flat bar -> NaN, not div-by-zero


def test_rsi_period2_known_oversold():
    # Strictly falling close => RSI(2) -> 0
    s = pd.Series(np.linspace(100.0, 90.0, 30))
    out = rsi(s, period=2)
    assert out.iloc[-1] < 5.0


def test_ewo_zscore_centered():
    rng = np.random.default_rng(1)
    n = 400
    close = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    high = close + 1.0
    low = close - 1.0
    z = ewo_zscore(high, low, close, lookback=252)
    valid = z.dropna()
    # Z-score should be bounded — it's not a perfect zero-mean since we
    # rolling-z-score against a 252-day window, but values should sit in a
    # reasonable range.
    assert valid.abs().mean() < 5.0
    assert valid.abs().max() < 20.0


def test_atr_positive():
    rng = np.random.default_rng(2)
    n = 50
    close = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    high = close + np.abs(rng.normal(0, 0.5, n))
    low = close - np.abs(rng.normal(0, 0.5, n))
    a = atr(high, low, close, period=20)
    assert (a.dropna() > 0).all()


def test_vwap_monotonic_with_constant_price():
    n = 10
    high = pd.Series([100.0] * n)
    low = pd.Series([100.0] * n)
    close = pd.Series([100.0] * n)
    volume = pd.Series([1000] * n)
    v = vwap(high, low, close, volume)
    assert (v == 100.0).all()


def test_ewo_independent_of_zscore():
    # Sanity: ewo() raw and ewo_zscore() are different objects
    rng = np.random.default_rng(3)
    n = 300
    close = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    high = close + 1.0
    low = close - 1.0
    raw = ewo(high, low, close)
    z = ewo_zscore(high, low, close, lookback=252)
    assert raw.shape == z.shape
