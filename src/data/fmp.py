"""Financial Modeling Prep (FMP) clients.

Two adapters:
  - FMPCalendar    : implements `CalendarProvider` for `BlackoutChecker`.
  - FMPHistorical  : daily + 5-min historical OHLCV (for backtests).

FMP migrated to /stable/ endpoints in Aug 2025; v3/v4 are legacy-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
from loguru import logger

from src.risk.blackout import EconomicEvent, EventKind

ET = ZoneInfo("America/New_York")
_BASE = "https://financialmodelingprep.com"


# --- Event-string mapping ------------------------------------------------
#
# FMP returns dozens of US release names per day. We map only the ones we
# blackout on. Match is by substring (case-insensitive) on the `event` field.
# Order matters: more-specific patterns must precede less-specific ones.
# The same release sometimes generates multiple FMP rows (e.g. CPI MoM + CPI
# YoY at the same timestamp); we de-dupe on (kind, timestamp).
_EVENT_PATTERNS: list[tuple[re.Pattern[str], EventKind]] = [
    (re.compile(r"FOMC Minutes", re.I),                 EventKind.FOMC_MINUTES),
    (re.compile(r"Fed Interest Rate Decision", re.I),   EventKind.FOMC_STATEMENT),
    # CPI: prefer the headline YoY rate, but accept any CPI/Inflation Rate row.
    (re.compile(r"\b(Core\s+)?Inflation Rate (MoM|YoY)", re.I), EventKind.CPI),
    (re.compile(r"\bCPI\b", re.I),                       EventKind.CPI),
    (re.compile(r"PCE Price Index (MoM|YoY)", re.I),     EventKind.PCE),
    (re.compile(r"Non[- ]?Farm Payrolls", re.I),         EventKind.NFP),
    (re.compile(r"GDP Growth Rate QoQ", re.I),           EventKind.GDP),
    (re.compile(r"Gross Domestic Product QoQ", re.I),    EventKind.GDP),
    (re.compile(r"ISM (Manufacturing|Services|Non-Manufacturing) PMI", re.I), EventKind.ISM),
    (re.compile(r"JOLTs Job Openings", re.I),            EventKind.JOLTS),
]


def classify_event(event_name: str) -> EventKind | None:
    for pat, kind in _EVENT_PATTERNS:
        if pat.search(event_name):
            return kind
    return None


def parse_fmp_events(rows: Iterable[dict]) -> list[EconomicEvent]:
    """Convert FMP `economic-calendar` rows into `EconomicEvent`.

    FMP timestamps are naive strings in UTC. We parse as UTC, then convert
    to ET so downstream blackout offsets (defined in ET) work correctly.
    De-duplicates rows that map to the same (kind, timestamp).
    """
    from datetime import timezone

    seen: set[tuple[EventKind, datetime]] = set()
    out: list[EconomicEvent] = []
    for row in rows:
        if row.get("country") != "US":
            continue
        kind = classify_event(row.get("event", ""))
        if kind is None:
            continue
        ts_raw = row.get("date")
        if not ts_raw:
            continue
        try:
            ts = (
                datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=timezone.utc)
                .astimezone(ET)
            )
        except ValueError:
            continue
        key = (kind, ts)
        if key in seen:
            continue
        seen.add(key)
        out.append(EconomicEvent(kind=kind, release_dt=ts))
    return out


# --- Calendar provider ----------------------------------------------------

@dataclass
class FMPCalendar:
    """Implements `CalendarProvider`. Caches events by (from_date, to_date)."""
    api_key: str
    timeout_sec: float = 10.0
    base_url: str = _BASE
    _cache: dict[tuple[str, str], tuple[EconomicEvent, ...]] = field(default_factory=dict)

    def upcoming(self, around: datetime, days: int = 2) -> list[EconomicEvent]:
        if around.tzinfo is None:
            around = around.replace(tzinfo=ET)
        start = (around - timedelta(days=days)).date()
        end = (around + timedelta(days=days)).date()
        return list(self._fetch_window(start.isoformat(), end.isoformat()))

    def _fetch_window(self, start_iso: str, end_iso: str) -> tuple[EconomicEvent, ...]:
        cached = self._cache.get((start_iso, end_iso))
        if cached is not None:
            return cached
        url = f"{self.base_url}/stable/economic-calendar"
        try:
            r = httpx.get(
                url,
                params={"from": start_iso, "to": end_iso, "apikey": self.api_key},
                timeout=self.timeout_sec,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.warning(f"FMP calendar fetch failed {start_iso}..{end_iso}: {exc!r}")
            return tuple()
        if isinstance(data, dict) and "Error Message" in data:
            logger.error(f"FMP error: {data['Error Message']}")
            return tuple()
        events = tuple(parse_fmp_events(data))
        self._cache[(start_iso, end_iso)] = events
        return events


# --- Historical OHLCV -----------------------------------------------------

@dataclass
class FMPHistorical:
    api_key: str
    timeout_sec: float = 30.0
    base_url: str = _BASE

    def daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Daily OHLCV. start/end are YYYY-MM-DD."""
        url = f"{self.base_url}/stable/historical-price-eod/full"
        r = httpx.get(
            url,
            params={"symbol": symbol, "from": start, "to": end, "apikey": self.api_key},
            timeout=self.timeout_sec,
        )
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        return df[["open", "high", "low", "close", "volume"]]

    def intraday_5min(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """5-min intraday OHLCV. ET-naive timestamps; we localize to ET."""
        url = f"{self.base_url}/stable/historical-chart/5min"
        r = httpx.get(
            url,
            params={"symbol": symbol, "from": start, "to": end, "apikey": self.api_key},
            timeout=self.timeout_sec,
        )
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(ET)
        df = df.set_index("date").sort_index()
        return df[["open", "high", "low", "close", "volume"]]
