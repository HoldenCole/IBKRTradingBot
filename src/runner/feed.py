"""Market-data feed protocol.

The runner asks the feed for:
  - daily history for indicator computation
  - the current intraday session (5-min bars, today's RTH so far)
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd


class DataFeed(Protocol):
    async def daily_bars(self, symbol: str, lookback_days: int = 400) -> pd.DataFrame:
        """Return daily OHLCV indexed by date. Most recent bar last."""

    async def session_bars(self, symbol: str, bar_size: str = "5 mins") -> pd.DataFrame:
        """Return today's RTH bars (so far) indexed by tz-aware ET timestamp."""
