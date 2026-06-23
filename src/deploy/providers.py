"""Production CloseSeriesProvider implementations.

YahooCloseProvider: pulls daily bars via src/data/yahoo.py. Used for QQQ
(equity ETF) and BTC-USD (crypto). The same provider works for both
because Yahoo serves both on a single API.

Asset symbol mapping is intentionally narrow: this module knows only
about the assets the deployment uses. New assets require an explicit
mapping addition — failing loudly is correct here.

For tests, use src.deploy.daily_check.CloseSeriesProvider protocol +
the SimProvider in tests/deploy/test_daily_check.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


_ASSET_TO_YAHOO_TICKER = {
    "QQQ": "QQQ",
    "BTC": "BTC-USD",
}


@dataclass
class YahooCloseProvider:
    """Pulls daily close series via src/data/yahoo.py.

    `closes(asset, as_of, lookback_days)` returns the close series ending
    at-or-before `as_of`, with `lookback_days` of history. The series
    index is normalized to naive dates (no timezone).

    Caches per call via Yahoo's underlying HTTP cache; not memoized at
    this layer because the daily-check job runs once a day and a fresh
    pull is appropriate.
    """

    def closes(self, asset: str, as_of: date, lookback_days: int) -> pd.Series:
        ticker = _ASSET_TO_YAHOO_TICKER.get(asset)
        if ticker is None:
            raise ValueError(
                f"Unknown asset {asset!r}. Supported: {list(_ASSET_TO_YAHOO_TICKER)}")

        # Pad start by ~30% to account for non-trading days within the lookback
        # window. We want >= `lookback_days` of actual trading data.
        start = as_of - timedelta(days=int(lookback_days * 1.5))
        end = as_of + timedelta(days=1)   # Yahoo end is exclusive

        # Lazy import to keep the deploy package importable without yfinance
        from src.data import yahoo as yahoo_loader

        df = yahoo_loader.daily(ticker, start.isoformat(), end.isoformat())
        if df is None or df.empty:
            return pd.Series(dtype=float, name=ticker)

        close = df["close"].copy()
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
        # Trim to exactly the requested as_of (inclusive) and lookback
        close = close.loc[:pd.Timestamp(as_of)]
        return close.tail(lookback_days)
