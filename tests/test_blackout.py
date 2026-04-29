from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.risk.blackout import BlackoutChecker, EconomicEvent, EventKind, StubCalendar

ET = ZoneInfo("America/New_York")


def test_cpi_blackout_window():
    # CPI release at 08:30 ET -> 07:00 to 11:00 blocked.
    cpi = EconomicEvent(EventKind.CPI, datetime(2026, 5, 13, 8, 30, tzinfo=ET))
    chk = BlackoutChecker(StubCalendar([cpi]))
    assert chk.is_in_blackout(datetime(2026, 5, 13, 8, 0, tzinfo=ET))
    assert chk.is_in_blackout(datetime(2026, 5, 13, 10, 59, tzinfo=ET))
    assert not chk.is_in_blackout(datetime(2026, 5, 13, 11, 1, tzinfo=ET))
    assert not chk.is_in_blackout(datetime(2026, 5, 13, 6, 59, tzinfo=ET))


def test_afternoon_reversion_blocked_all_day():
    cpi = EconomicEvent(EventKind.CPI, datetime(2026, 5, 13, 8, 30, tzinfo=ET))
    chk = BlackoutChecker(StubCalendar([cpi]))
    afternoon = datetime(2026, 5, 13, 14, 0, tzinfo=ET)
    assert chk.is_blackout_day_for_afternoon_reversion(afternoon)
    # But the active blackout window has ended by then.
    assert not chk.is_in_blackout(afternoon)


def test_imminent_release_15m_lead():
    cpi = EconomicEvent(EventKind.CPI, datetime(2026, 5, 13, 8, 30, tzinfo=ET))
    chk = BlackoutChecker(StubCalendar([cpi]), flatten_lead=timedelta(minutes=15))
    # 17 min before -> not imminent
    assert chk.imminent_release(datetime(2026, 5, 13, 8, 13, tzinfo=ET)) is None
    # 10 min before -> imminent
    assert chk.imminent_release(datetime(2026, 5, 13, 8, 20, tzinfo=ET)) is not None
