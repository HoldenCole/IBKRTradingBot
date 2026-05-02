"""Thin yfinance wrapper for pre-2010 daily bars (FMP only goes back to 2010).

yfinance is free, public, and goes back to 1999 for QQQ. Used as a fallback
for out-of-sample testing on older periods. Same DataFrame shape as
FMPHistorical.daily so callers can swap sources transparently.

Lazy import: yfinance is only required when this module is actually used.
"""
from __future__ import annotations

from datetime import date

import pandas as pd


def daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Return DataFrame with date index and columns [open, high, low, close, volume].

    `start` and `end` are ISO date strings. yfinance auto-handles weekends.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance not installed. Run `pip install yfinance` "
            "or add to pyproject.toml dependencies."
        ) from exc

    df = yf.download(
        symbol, start=start, end=end,
        progress=False, auto_adjust=False, group_by="column",
    )
    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    # yfinance returns multi-level columns like ('Close', 'QQQ'); flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Lowercase columns + rename to match FMP convention
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    return df[["open", "high", "low", "close", "volume"]]
