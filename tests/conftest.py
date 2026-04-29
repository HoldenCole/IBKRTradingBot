"""Shared test fixtures."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

ET = ZoneInfo("America/New_York")


@pytest.fixture
def synthetic_daily_bars() -> pd.DataFrame:
    """500 days of OHLCV with a deterministic random walk."""
    rng = np.random.default_rng(42)
    n = 500
    dates = pd.bdate_range(end="2026-04-01", periods=n)
    rets = rng.normal(0.0005, 0.012, n)
    close = 400 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    open_ = close + rng.normal(0, 0.5, n)
    vol = rng.integers(50_000_000, 120_000_000, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=dates,
    )


@pytest.fixture
def session_5m_bars() -> pd.DataFrame:
    """5-min bars for one trading session, 09:30 ET to 11:30 ET."""
    start = datetime(2026, 4, 28, 9, 30, tzinfo=ET)
    n = 25  # 09:30..11:30 inclusive at 5-min spacing = 25 bars
    times = [start + timedelta(minutes=5 * i) for i in range(n)]
    rng = np.random.default_rng(0)

    # Construct a clear morning sell-off, then small bounce after 11:00.
    base = 400.0
    closes = []
    cur = base
    for i, t in enumerate(times):
        if t.hour < 11:
            cur -= rng.uniform(0.05, 0.20)  # falling
        else:
            cur += rng.uniform(0.02, 0.10)  # bouncing
        closes.append(cur)
    closes = np.array(closes)
    highs = closes + np.abs(rng.normal(0, 0.05, n))
    lows = closes - np.abs(rng.normal(0, 0.05, n))
    opens = np.concatenate([[base], closes[:-1]])
    vols = rng.integers(500_000, 2_000_000, n)
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=pd.DatetimeIndex(times, name="ts"),
    )
    return df
