from datetime import date

import pandas as pd
import pytest

from src.portfolio.watch import boundary, provisional_quadrant
from src.regime.quadrant import Quadrant


def _daily(vals_by_month, last_partial=None):
    """Synthetic daily series: one close per business day, level per month."""
    frames = []
    for month, level in vals_by_month:
        days = pd.bdate_range(month + "-01", pd.Timestamp(month + "-01") + pd.offsets.MonthEnd(0))
        frames.append(pd.Series(level, index=days))
    s = pd.concat(frames)
    if last_partial:
        month, level, ndays = last_partial
        days = pd.bdate_range(month + "-01", periods=ndays)
        s = pd.concat([s, pd.Series(level, index=days)])
    return s


def test_boundary_uses_prior_nine_completed_months_only():
    months = [(f"2026-{m:02d}", 100.0) for m in range(1, 9)]
    months += [("2025-12", 100.0)]
    s = _daily(sorted(months), last_partial=("2026-09", 110.0, 10))
    px, th, dist = boundary(s, date(2026, 9, 15))
    assert px == 110.0 and th == 100.0
    assert dist == pytest.approx(0.10)


def test_boundary_ignores_current_partial_month_in_threshold():
    # partial month at 200 must not contaminate the threshold
    months = [("2025-12", 100.0)] + [(f"2026-{m:02d}", 100.0) for m in range(1, 9)]
    s = _daily(months, last_partial=("2026-09", 200.0, 5))
    _, th, _ = boundary(s, date(2026, 9, 8))
    assert th == 100.0


def test_provisional_quadrant_mapping():
    assert provisional_quadrant(True, False) is Quadrant.GROWTH
    assert provisional_quadrant(True, True) is Quadrant.REFLATION
    assert provisional_quadrant(False, True) is Quadrant.STAGFLATION
    assert provisional_quadrant(False, False) is Quadrant.DEFLATION


def test_boundary_requires_history():
    s = _daily([("2026-07", 100.0), ("2026-08", 100.0)])
    with pytest.raises(ValueError):
        boundary(s, date(2026, 9, 1))
