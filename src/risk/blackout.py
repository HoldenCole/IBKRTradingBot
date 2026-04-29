"""Event blackout windows.

The provider returns a list of upcoming/active EconomicEvents. The checker
answers two questions:
  1. is_in_blackout(now): block new entries
  2. should_flatten(now, position): flatten 15m before non-afternoon-reversion
     positions when a release is imminent
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


class EventKind(str, Enum):
    FOMC_STATEMENT = "fomc_statement"
    FOMC_MINUTES = "fomc_minutes"
    CPI = "cpi"
    PCE = "pce"
    NFP = "nfp"
    GDP = "gdp"
    ISM = "ism"
    JOLTS = "jolts"


@dataclass(frozen=True)
class EconomicEvent:
    kind: EventKind
    release_dt: datetime  # tz-aware ET


# Per-event blackout rules: (start_offset_min_relative_to_release, end_offset_min)
# Where the spec says T-0 09:30 -> T-0 11:00 around an 08:30 release, we encode
# offsets relative to release_dt.
_BLACKOUT_OFFSETS: dict[EventKind, tuple[timedelta, timedelta]] = {
    # FOMC statement (typically 14:00 ET): block from 11:00 same day -> next open (09:30).
    EventKind.FOMC_STATEMENT: (timedelta(hours=-3), timedelta(hours=19, minutes=30)),
    # FOMC minutes (typically 14:00 ET): 13:00 -> 16:00 same day.
    EventKind.FOMC_MINUTES: (timedelta(hours=-1), timedelta(hours=2)),
    # 08:30 releases: 07:00 -> 11:00 ET.
    EventKind.CPI:   (timedelta(hours=-1, minutes=-30), timedelta(hours=2, minutes=30)),
    EventKind.PCE:   (timedelta(hours=-1, minutes=-30), timedelta(hours=2, minutes=30)),
    EventKind.NFP:   (timedelta(hours=-1, minutes=-30), timedelta(hours=2, minutes=30)),
    EventKind.GDP:   (timedelta(hours=-1, minutes=-30), timedelta(hours=2, minutes=30)),
    # 10:00 releases: 09:30 -> 11:00 ET.
    EventKind.ISM:   (timedelta(minutes=-30), timedelta(hours=1)),
    EventKind.JOLTS: (timedelta(minutes=-30), timedelta(hours=1)),
}


class CalendarProvider(Protocol):
    def upcoming(self, around: datetime, days: int = 2) -> Iterable[EconomicEvent]: ...


class StubCalendar:
    """Test/dev calendar. Returns whatever events you load into it."""

    def __init__(self, events: Iterable[EconomicEvent] = ()):
        self._events = list(events)

    def upcoming(self, around: datetime, days: int = 2) -> list[EconomicEvent]:
        if around.tzinfo is None:
            around = around.replace(tzinfo=ET)
        window_start = around - timedelta(days=days)
        window_end = around + timedelta(days=days)
        return [e for e in self._events if window_start <= e.release_dt <= window_end]


@dataclass
class BlackoutChecker:
    provider: CalendarProvider
    flatten_lead: timedelta = timedelta(minutes=15)

    def _ensure_et(self, dt: datetime) -> datetime:
        return dt.astimezone(ET) if dt.tzinfo else dt.replace(tzinfo=ET)

    def active_event(self, now: datetime) -> EconomicEvent | None:
        now = self._ensure_et(now)
        for ev in self.provider.upcoming(now, days=2):
            start_off, end_off = _BLACKOUT_OFFSETS[ev.kind]
            start = ev.release_dt + start_off
            end = ev.release_dt + end_off
            if start <= now <= end:
                return ev
        return None

    def is_in_blackout(self, now: datetime) -> bool:
        return self.active_event(now) is not None

    def is_blackout_day_for_afternoon_reversion(self, now: datetime) -> bool:
        """Afternoon reversion is blocked for the entire session on any
        blackout day (premise is non-news-driven)."""
        now = self._ensure_et(now)
        today: date = now.date()
        for ev in self.provider.upcoming(now, days=1):
            if ev.release_dt.date() == today:
                return True
        return False

    def imminent_release(self, now: datetime) -> EconomicEvent | None:
        """Return an event releasing within `flatten_lead` of `now`.
        Used to flatten EWO/IBS positions ahead of news.
        """
        now = self._ensure_et(now)
        horizon = now + self.flatten_lead
        for ev in self.provider.upcoming(now, days=1):
            if now <= ev.release_dt <= horizon:
                return ev
        return None
