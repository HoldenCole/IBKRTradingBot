"""FRED API client — free macro data for systematic strategies.

Used for:
  - VIX (VIXCLS) — daily close index, no auth required
  - Other macro series (DGS10, DTWEXBGS, DCOILWTICO, etc.) as needed

The FRED API has a free endpoint at fred.stlouisfed.org/graph/fredgraph.csv
that doesn't require an API key for daily series. This client uses that
endpoint to keep operational dependencies minimal.

Usage:
    from src.data.fred import fetch_series
    vix = fetch_series("VIXCLS", "2018-01-01", "2026-04-15")
    # Returns pd.DataFrame with date index, single 'close' column
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd
from loguru import logger


_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


@dataclass
class FredClient:
    timeout_sec: float = 30.0
    cache_dir: Path | None = None

    def fetch_series(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        """Fetch a single FRED series. Returns DataFrame with date index
        and 'close' column. Caches to local CSV when cache_dir is set.
        Empty bars (FRED uses '.' for missing values) are dropped.
        """
        cache_path = None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = self.cache_dir / f"{series_id}_{start}_{end}.csv"
            if cache_path.exists():
                logger.debug(f"FRED cache hit: {cache_path}")
                return self._load_csv_to_df(cache_path.read_text(), series_id)

        url = _BASE_URL
        params = {
            "id": series_id,
            "cosd": start,    # observation start date
            "coed": end,      # observation end date
        }
        try:
            r = httpx.get(url, params=params, timeout=self.timeout_sec)
            r.raise_for_status()
        except Exception as exc:
            logger.error(f"FRED fetch failed for {series_id}: {exc!r}")
            raise

        if cache_path is not None:
            cache_path.write_text(r.text)
        return self._load_csv_to_df(r.text, series_id)

    @staticmethod
    def _load_csv_to_df(csv_text: str, series_id: str) -> pd.DataFrame:
        df = pd.read_csv(io.StringIO(csv_text))
        # Standardize column names — FRED returns 'observation_date' (or 'DATE')
        # and the series_id (or other label) for the value
        date_col = next((c for c in df.columns if c.lower() in ("observation_date", "date")),
                        df.columns[0])
        # Find the value column (not the date column)
        val_col = next((c for c in df.columns if c != date_col), None)
        if val_col is None:
            raise ValueError(f"FRED CSV missing value column for {series_id}")

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "date", val_col: "close"}).set_index("date")
        # FRED uses '.' for missing — coerce to NaN then drop
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])
        return df[["close"]]


def fetch_vix(start: str, end: str, cache_dir: Path | None = None) -> pd.DataFrame:
    """Convenience wrapper: VIX daily close from FRED.

    The 'close' column is the VIX index level (e.g., 16.42).
    Index is naive dates (no tz).
    """
    return FredClient(cache_dir=cache_dir).fetch_series("VIXCLS", start, end)


def fetch_tbill_3m(start: str, end: str, cache_dir: Path | None = None) -> pd.DataFrame:
    """3-month Treasury bill rate (DGS3MO series, daily, in percent).

    'close' column is the annualized rate as a PERCENT (e.g., 5.25 means 5.25%).
    Used as the OFF-period cash yield in BAH-on-trend backtests.

    To convert to a daily compounding factor:
        annual_rate = df["close"] / 100.0
        daily_factor = (1 + annual_rate) ** (1/252)
    """
    return FredClient(cache_dir=cache_dir).fetch_series("DGS3MO", start, end)
