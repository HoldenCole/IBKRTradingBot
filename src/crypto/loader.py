"""Crypto data loader — spot daily bars via Yahoo.

Crypto is far simpler than commodity futures: spot prices, 24/7 trading (no
weekend/holiday gaps, ~365 bars/year), no contracts/rolls/back-adjustment.
We research on the underlying coins (long history) and note the deployable
vehicle separately (spot ETFs IBIT/ETHA, launched 2024, are securities).

Yahoo tickers: BTC-USD, ETH-USD, LTC-USD. Daily close is 00:00 UTC.

Cached to data/crypto_cache/ (committable — public Yahoo data, not licensed).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from loguru import logger

_REPO = Path(__file__).resolve().parent.parent.parent
_CACHE = _REPO / "data" / "crypto_cache"

COINS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "LTC": "LTC-USD",
}


def _fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(ticker, start=start, end=end, progress=False,
                     auto_adjust=False, group_by="column")
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    return df[["open", "high", "low", "close", "volume"]]


def daily(symbol: str, start: str = "2014-01-01", end: str = "2026-06-21",
          cache: bool = True) -> pd.DataFrame:
    """Daily OHLCV for one coin key ('BTC') or raw ticker ('BTC-USD')."""
    ticker = COINS.get(symbol, symbol)
    if cache:
        _CACHE.mkdir(parents=True, exist_ok=True)
        path = _CACHE / f"{ticker}_{start}_{end}.csv"
        if path.exists():
            return pd.read_csv(path, parse_dates=["date"]).set_index("date")
    df = _fetch(ticker, start, end)
    if cache and not df.empty:
        df.to_csv(_CACHE / f"{ticker}_{start}_{end}.csv")
    return df


@dataclass
class CryptoPanel:
    close: pd.DataFrame      # date x coin
    symbols: list[str]

    def returns(self) -> pd.DataFrame:
        return self.close.pct_change()


def load(symbols: list[str] | None = None,
         start: str = "2014-01-01", end: str = "2026-06-21") -> CryptoPanel:
    """Load a panel of coin closes on the union calendar (crypto trades daily,
    so calendars align except for each coin's inception)."""
    syms = symbols or list(COINS.keys())
    closes = {}
    for s in syms:
        df = daily(s, start, end)
        if df.empty:
            logger.warning(f"no data for {s}")
            continue
        closes[s] = df["close"]
    panel = pd.DataFrame(closes).sort_index()
    return CryptoPanel(close=panel, symbols=list(closes.keys()))
