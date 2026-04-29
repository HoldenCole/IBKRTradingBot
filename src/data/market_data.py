"""Market data fetching against IBKR.

Kept thin on purpose: strategies receive pandas DataFrames; this module is the
only place that knows ib_insync request shapes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ib_insync import IB, Contract


@dataclass
class MarketData:
    ib: "IB"

    def historical_daily(self, symbol: str, lookback_days: int = 400) -> pd.DataFrame:
        """Fetch daily bars for a stock/ETF underlying."""
        from ib_insync import Stock

        contract: "Contract" = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(contract)
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=f"{lookback_days} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        return _bars_to_df(bars)

    def historical_intraday(
        self, symbol: str, bar_size: str = "5 mins", duration: str = "1 D"
    ) -> pd.DataFrame:
        from ib_insync import Stock

        contract = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(contract)
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        return _bars_to_df(bars)


def _bars_to_df(bars) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(
        [
            {
                "ts": _bar_ts(b),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ]
    )
    df = df.set_index("ts").sort_index()
    return df


def _bar_ts(b) -> datetime:
    """ib_insync returns either date or datetime depending on bar size."""
    d = b.date
    if isinstance(d, datetime):
        return d
    return datetime.combine(d, datetime.min.time())
