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

import numpy as np
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


def _six_month_windows(start: str, end: str) -> list[tuple[str, str]]:
    """Split [start, end] into consecutive <=6-month [cs, ce) windows.

    Databento streaming get_range drops on long ranges from this environment;
    6-month chunks pull reliably. Windows are half-open in effect because the
    loader dedups overlapping boundary dates after concatenation.
    """
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    out: list[tuple[str, str]] = []
    cur = s
    while cur < e:
        nxt = min(cur + pd.DateOffset(months=6), e)
        out.append((cur.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")))
        cur = nxt
    return out


def collapse_to_trade_date(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse CME Sunday-evening sessions into the following trade date.

    Databento `ohlcv-1d` buckets by UTC calendar day, so the CME Sunday-evening
    electronic session (which belongs to Monday's CME trade date) appears as a
    separate, tiny-volume Sunday bar. Left in place these ~partial-session bars
    inflate the calendar (~310 bars/yr vs ~252) and distort SMA/Donchian/
    momentum signals and realized-vol estimates.

    Fix: reassign each Sunday (dow=6) bar's date to date+1 (Monday), then
    aggregate any same-date bars OHLCV-correctly:
        open = first, high = max, low = min, close = last, volume = sum
    Holiday-Monday edge cases (Sunday session but Monday closed) leave the
    merged bar labelled Monday rather than the next session — a handful of
    days over 16 years; documented and immaterial for daily trend signals.

    Returns a faithful one-bar-per-trade-date daily series. Applied on load;
    the raw cache stays as-fetched.
    """
    if df is None or df.empty:
        return df
    d = df.copy()
    dow = d.index.dayofweek
    new_idx = d.index.where(dow != 6, d.index + pd.Timedelta(days=1))
    d.index = pd.DatetimeIndex(new_idx)
    d.index.name = "date"
    agg = {}
    for c, fn in (("open", "first"), ("high", "max"), ("low", "min"),
                  ("close", "last"), ("volume", "sum"), ("instrument_id", "last")):
        if c in d.columns:
            agg[c] = fn
    out = d.groupby(d.index).agg(agg).sort_index()
    return out


def panama_adjust(v0: pd.DataFrame, v1: pd.DataFrame) -> pd.DataFrame:
    """Panama (difference) back-adjustment of a volume-roll continuous series.

    Reusable across futures classes (commodities, bonds, FX). Detects rolls
    from the front-month instrument_id changing; the gap at each roll is the
    same-day old-front minus new-front (v0.close[t-1] - v1.close[t-1]); the
    cumulative future gaps are subtracted from history so the series is
    continuous at each seam and anchored to the present (latest close
    unchanged). Difference (not ratio) adjustment — sign-safe.

    Both v0 and v1 must carry 'instrument_id' (the loader preserves it) and be
    trade-date collapsed. Returns the adjusted OHLC(V) frame.
    """
    if "instrument_id" not in v0.columns:
        raise ValueError("v0 needs instrument_id for roll detection")
    common = v0.index
    iid = v0["instrument_id"]
    rolls = common[iid.ne(iid.shift(1)) & iid.shift(1).notna()]
    v1c = v1["close"].reindex(common)

    gaps = {}
    for t in rolls:
        pos = common.get_loc(t)
        if pos == 0:
            continue
        tm1 = common[pos - 1]
        nf = v1c.loc[tm1]
        if pd.isna(nf):
            continue
        gaps[t] = float(v0["close"].iloc[pos - 1]) - float(nf)

    if not gaps:
        return v0.copy()
    gap_s = pd.Series(gaps).sort_index()
    offs = np.zeros(len(common))
    for k in range(len(common)):
        offs[k] = float(gap_s[gap_s.index > common[k]].sum())
    offset = pd.Series(offs, index=common)

    adj = v0.copy()
    for col in ("open", "high", "low", "close"):
        if col in adj.columns:
            adj[col] = adj[col] - offset
    return adj


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
        roll: str = "v",
        dataset: str = GLBX,
        force: bool = False,
    ) -> pd.DataFrame:
        """Fetch one continuous daily-bar series.

        root  : CME root symbol, e.g. "CL"
        depth : 0 = front month, 1 = second month (needed for back-adjustment)
        roll  : "v" volume (default) / "c" calendar / "n" open-interest.
                Volume-roll follows the most-liquid contract, which trades
                every session. Calendar-roll lands on illiquid metal months
                (silver Mar/May/Jul/Sep/Dec) producing no-trade gaps (SI lost
                ~30% of days). Volume-roll is also the standard CTA convention.
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
        # Streaming get_range drops the connection on long ranges from this
        # environment (works <=6mo, fails at 1yr with "Error streaming
        # response"). Chunk into <=6-month windows with retries, concatenate.
        frames = []
        for cs, ce in _six_month_windows(start, end):
            frames.append(self._fetch_chunk(client, dataset, symbol, cs, ce))
        out = (pd.concat(frames) if frames else pd.DataFrame())
        out = self._normalize(out) if not out.empty else \
            pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        out.to_csv(cache)
        return out

    @staticmethod
    def _fetch_chunk(client, dataset: str, symbol: str, start: str, end: str,
                     retries: int = 3) -> pd.DataFrame:
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                data = client.timeseries.get_range(
                    dataset=dataset, symbols=[symbol], stype_in="continuous",
                    schema="ohlcv-1d", start=start, end=end,
                )
                df = data.to_df()
                logger.info(f"  {symbol} {start}->{end}: {len(df)} bars")
                return df
            except Exception as exc:  # streaming error -> retry
                last_exc = exc
                logger.warning(f"  {symbol} {start}->{end} attempt {attempt} "
                               f"failed: {repr(exc)[:80]}")
        raise RuntimeError(f"chunk {symbol} {start}->{end} failed after "
                           f"{retries} tries: {last_exc!r}")

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
        # Keep instrument_id: roll detection (Panama back-adjustment) needs to
        # know which underlying contract each bar belongs to.
        cols = [c for c in ["open", "high", "low", "close", "volume", "instrument_id"]
                if c in d.columns]
        d = d[cols]
        d = d[~d.index.duplicated(keep="last")].sort_index()
        return d

    @staticmethod
    def _load_csv(path: Path) -> pd.DataFrame:
        df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        cols = [c for c in ["open", "high", "low", "close", "volume", "instrument_id"]
                if c in df.columns]
        return df[cols]
