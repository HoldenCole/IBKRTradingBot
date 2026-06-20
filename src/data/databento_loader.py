"""Databento loader for continuous futures daily bars.

Used as the modern-era (2010+) data source for the commodity-trend research.
Pre-2010 history and the ICE instruments (Brent/Sugar/Coffee) are backfilled
separately from Norgate; this module only covers what Databento serves cleanly:
the CME-listed commodities on GLBX.MDP3 from 2010-06-06 onward.

Continuous-contract symbology (Databento "smart symbology"):
  ROOT.c.N  — calendar-roll continuous, Nth contract (0 = front month)
  ROOT.v.N  — volume-roll continuous
  ROOT.n.N  — open-interest-roll continuous

We pull CALENDAR-roll (.c.) as the primary series: it is deterministic and
does not depend on the volume field (which on the continuous series looks
unreliable — see pull_commodity_data.py validation notes). The raw continuous
series is UNADJUSTED (front-month prices stitched with gaps at each roll);
back-adjustment (Panama/difference) is applied downstream as a separate,
validated step, per locked methodology Q2.

For back-adjustment we need both the front (.c.0) and second (.c.1) month so
the roll gap can be isolated: on the day before a roll,
    roll_gap = price(.c.1) - price(.c.0)
i.e. the second-month contract (about to become front) minus the expiring
front. This avoids contaminating the gap with the genuine overnight move.

Output DataFrame shape matches src/data/yahoo.daily():
  date index (naive, UTC date) + columns [open, high, low, close, volume].

Caching: one CSV per (symbol, schema) under data/commodities/databento_raw/,
which is gitignored (licensed data — not redistributable).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from loguru import logger

_REPO = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CACHE = _REPO / "data" / "commodities" / "databento_raw"
_DEFAULT_KEY_FILE = _REPO / ".secrets" / "databento.key"

# CME commodities Databento can serve (GLBX.MDP3, 2010-06-06 onward).
# root -> human label. ICE instruments (BRN/SB/KC) are NOT here — Norgate backfill.
CME_COMMODITY_ROOTS: dict[str, str] = {
    "CL": "WTI crude",
    "NG": "Natural gas",
    "HO": "Heating oil (ULSD)",
    "RB": "RBOB gasoline",
    "GC": "Gold",
    "SI": "Silver",
    "HG": "Copper",
    "ZC": "Corn",
    "ZS": "Soybeans",
    "ZW": "Wheat",
}

GLBX = "GLBX.MDP3"
_GLBX_START = "2010-06-06"   # dataset inception


def _read_key(key_file: Path | None = None) -> str:
    """Load the Databento API key from env or the gitignored key file."""
    import os
    env = os.environ.get("DATABENTO_API_KEY")
    if env:
        return env.strip()
    kf = key_file or _DEFAULT_KEY_FILE
    if kf.exists():
        return kf.read_text().strip()
    raise RuntimeError(
        "No Databento API key found. Set DATABENTO_API_KEY or write it to "
        f"{kf} (gitignored)."
    )


@dataclass
class DatabentoLoader:
    cache_dir: Path = _DEFAULT_CACHE
    key_file: Path | None = None

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, symbol: str, start: str, end: str) -> Path:
        safe = symbol.replace(".", "_")
        return self.cache_dir / f"{safe}__{start}__{end}.csv"

    def continuous(
        self,
        root: str,
        depth: int = 0,
        start: str = _GLBX_START,
        end: str = "2026-06-20",
        roll: str = "c",
        dataset: str = GLBX,
        force: bool = False,
    ) -> pd.DataFrame:
        """Fetch one continuous daily-bar series.

        root  : CME root symbol, e.g. "CL"
        depth : 0 = front month, 1 = second month (needed for back-adjustment)
        roll  : "c" calendar / "v" volume / "n" open-interest
        Returns date-indexed DataFrame [open, high, low, close, volume].
        Cached to CSV; pass force=True to re-download.
        """
        symbol = f"{root}.{roll}.{depth}"
        cache = self._cache_path(symbol, start, end)
        if cache.exists() and not force:
            logger.debug(f"Databento cache hit: {cache.name}")
            return self._load_csv(cache)

        try:
            import databento as db
        except ImportError as exc:
            raise ImportError("databento not installed: pip install databento") from exc

        client = db.Historical(_read_key(self.key_file))
        logger.info(f"Databento fetch {symbol} {start}->{end} ({dataset})")
        data = client.timeseries.get_range(
            dataset=dataset,
            symbols=[symbol],
            stype_in="continuous",
            schema="ohlcv-1d",
            start=start,
            end=end,
        )
        df = data.to_df()
        out = self._normalize(df)
        out.to_csv(cache)
        return out

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        d = df.copy()
        # ts_event is the bar timestamp (UTC). Reduce to naive date index.
        if "ts_event" in d.columns:
            idx = pd.to_datetime(d["ts_event"])
        else:
            idx = pd.to_datetime(d.index)
        d.index = pd.DatetimeIndex(idx).tz_localize(None).normalize()
        d.index.name = "date"
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in d.columns]
        d = d[cols]
        d = d[~d.index.duplicated(keep="last")].sort_index()
        return d

    @staticmethod
    def _load_csv(path: Path) -> pd.DataFrame:
        df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        return df[[c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]]
