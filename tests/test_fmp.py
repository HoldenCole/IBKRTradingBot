"""FMP adapter tests — operate on canned JSON, no network."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.fmp import classify_event, parse_fmp_events
from src.risk.blackout import EventKind

ET = ZoneInfo("America/New_York")


def test_classify_event_mappings():
    assert classify_event("FOMC Minutes") is EventKind.FOMC_MINUTES
    assert classify_event("Fed Interest Rate Decision") is EventKind.FOMC_STATEMENT
    assert classify_event("Inflation Rate YoY (Apr)") is EventKind.CPI
    assert classify_event("Core Inflation Rate MoM (Apr)") is EventKind.CPI
    assert classify_event("CPI (Apr)") is EventKind.CPI
    assert classify_event("PCE Price Index YoY (Mar)") is EventKind.PCE
    assert classify_event("Non Farm Payrolls (Apr)") is EventKind.NFP
    assert classify_event("Non-Farm Payrolls (Apr)") is EventKind.NFP
    assert classify_event("GDP Growth Rate QoQ (Q1)") is EventKind.GDP
    assert classify_event("ISM Manufacturing PMI (Apr)") is EventKind.ISM
    assert classify_event("ISM Services PMI (Apr)") is EventKind.ISM
    assert classify_event("JOLTs Job Openings (Mar)") is EventKind.JOLTS

    # Things we explicitly do NOT blackout on
    assert classify_event("MBA 30-Year Mortgage Rate (Apr/03)") is None
    assert classify_event("EIA Crude Oil Stocks Change (May/01)") is None
    assert classify_event("Existing Home Sales (Mar)") is None
    assert classify_event("US President Trump Speech") is None


def test_parse_fmp_events_filters_to_us_and_dedupes():
    # All timestamps are UTC. CPI release at 12:30 UTC == 08:30 ET.
    rows = [
        {"date": "2026-05-13 12:30:00", "country": "US",
         "event": "Inflation Rate MoM (Apr)"},
        {"date": "2026-05-13 12:30:00", "country": "US",
         "event": "Inflation Rate YoY (Apr)"},
        {"date": "2026-05-13 12:30:00", "country": "US",
         "event": "Core Inflation Rate MoM (Apr)"},
        # Non-US: skipped
        {"date": "2026-05-13 12:30:00", "country": "DE",
         "event": "Inflation Rate YoY"},
        # Unrelated US event: skipped
        {"date": "2026-05-14 14:00:00", "country": "US",
         "event": "Existing Home Sales (Apr)"},
        # NFP at 12:30 UTC == 08:30 ET
        {"date": "2026-05-01 12:30:00", "country": "US",
         "event": "Non Farm Payrolls (Apr)"},
    ]
    events = parse_fmp_events(rows)
    assert len(events) == 2  # one CPI + one NFP, dedupe collapsed three CPI rows
    kinds = {e.kind for e in events}
    assert kinds == {EventKind.CPI, EventKind.NFP}

    # FMP timestamps are UTC; CPI is released at 12:30 UTC = 08:30 ET.
    cpi = next(e for e in events if e.kind is EventKind.CPI)
    assert cpi.release_dt == datetime(2026, 5, 13, 8, 30, tzinfo=ET)


def test_parse_handles_bad_rows():
    rows = [
        {"date": "not-a-date", "country": "US", "event": "CPI (Apr)"},
        {"country": "US", "event": "CPI (Apr)"},  # missing date
        {"date": "2026-05-13 12:30:00", "country": "US"},  # missing event
    ]
    assert parse_fmp_events(rows) == []
