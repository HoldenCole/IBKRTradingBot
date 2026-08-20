"""Matrix integrity and paper-ledger mechanics (no network)."""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.portfolio.matrix import MATRIX, TIERS, all_tickers, allocation
from src.portfolio.paper_logger import (
    append_entry,
    load_ledger,
    mark_to_market,
)
from src.regime.quadrant import Quadrant


def test_matrix_weights_sum_to_one():
    for tier, cells in MATRIX.items():
        for quadrant, weights in cells.items():
            total = sum(weights.values())
            assert total == pytest.approx(1.0, abs=0.01), f"{tier}/{quadrant}: {total}"


def test_matrix_covers_all_tiers_and_quadrants():
    assert TIERS == ["CONS", "MOD", "AGG", "VAGG"]
    for cells in MATRIX.values():
        assert set(cells) == set(Quadrant)


def test_allocation_returns_copy():
    a = allocation("MOD", Quadrant.GROWTH)
    a["QQQ"] = 0.0
    assert MATRIX["MOD"][Quadrant.GROWTH]["QQQ"] == 0.70


def daily(vals_per_month, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(vals_per_month) * 21, freq="B")
    return pd.Series(np.repeat(vals_per_month, 21)[: len(idx)], index=idx)


def test_append_is_idempotent_per_month(tmp_path):
    path = tmp_path / "ledger.csv"
    today = date(2026, 8, 19)
    assert append_entry(Quadrant.REFLATION, today, path) is True
    assert append_entry(Quadrant.GROWTH, today, path) is False  # same month -> no-op
    ledger = load_ledger(path)
    assert len(ledger) == 1
    assert ledger.loc[0, "quadrant"] == "REFLATION"
    allocs = json.loads(ledger.loc[0, "allocations"])
    assert set(allocs) == set(TIERS)
    assert allocs["VAGG"]["TQQQ"] == 0.30


def test_mark_to_market_computes_returns(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry(Quadrant.GROWTH, date(2026, 1, 5), path)
    ledger = load_ledger(path)
    idx = pd.date_range("2026-01-05", periods=30, freq="B")
    # every ticker rises 1%/day -> every tier must be up, no drawdown
    prices = pd.DataFrame({t: 100 * (1.01 ** np.arange(30)) for t in all_tickers() + ["SPY"]}, index=idx)
    report = mark_to_market(ledger, prices)
    assert not report.empty
    tiers_reported = set(report.tier)
    assert set(TIERS).issubset(tiers_reported)
    assert (report.ret > 0).all()
    assert (report.maxDD == 0).all()


def test_mark_to_market_empty_ledger():
    assert mark_to_market(load_ledger(pd.io.common.Path("nonexistent.csv")), pd.DataFrame()).empty


# ---- v3 additions ----
from datetime import date as _date
import pandas as _pd
from src.portfolio.matrix import COND_DURATION, R_TILT, resolve_allocation
from src.portfolio.paper_logger import completed_month_closes, compute_signals


def test_no_placeholder_in_tickers():
    assert COND_DURATION not in all_tickers()
    assert "TLT" in all_tickers() and "SHY" in all_tickers()


def test_conditional_duration_resolution():
    up = resolve_allocation("MOD", Quadrant.STAGFLATION, tlt_trend_up=True)
    dn = resolve_allocation("MOD", Quadrant.STAGFLATION, tlt_trend_up=False)
    unk = resolve_allocation("MOD", Quadrant.STAGFLATION, tlt_trend_up=None)
    assert up == {"SHY": 0.50, "TLT": 0.50}
    assert dn == {"SHY": 1.0}
    assert unk == {"SHY": 1.0}  # fail closed to cash
    for a in (up, dn, unk):
        assert sum(a.values()) == pytest.approx(1.0, abs=0.01)


def test_reflation_momentum_tilt():
    mom = {"XLE": 0.30, "GLD": 0.10, "DBC": -0.05}
    tilted = resolve_allocation("MOD", Quadrant.REFLATION, commodity_momentum=mom)
    assert tilted["XLE"] > tilted["GLD"] > tilted["DBC"]
    assert sum(tilted.values()) == pytest.approx(1.0, abs=0.01)
    # pool preserved: trio total unchanged vs untilted
    base = resolve_allocation("MOD", Quadrant.REFLATION)
    assert sum(tilted[a] for a in ("XLE","GLD","DBC")) == pytest.approx(
        sum(base[a] for a in ("XLE","GLD","DBC")), abs=0.01)


def test_tilt_requires_full_trio():
    tilted = resolve_allocation("MOD", Quadrant.REFLATION, commodity_momentum={"XLE": 0.3})
    assert tilted == resolve_allocation("MOD", Quadrant.REFLATION)


def test_completed_month_truncation():
    idx = _pd.date_range("2026-06-01", "2026-08-19", freq="B")
    s = _pd.Series(range(len(idx)), index=idx, dtype=float)
    m = completed_month_closes(s, _date(2026, 8, 19))
    # August (partial) must be excluded
    assert m.index.max().month == 7


def test_append_entry_snapshots_resolved_s_cell(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry(Quadrant.STAGFLATION, date(2026, 9, 1), path, tlt_trend_up=True)
    allocs = json.loads(load_ledger(path).loc[0, "allocations"])
    assert allocs["VAGG"] == {"SHY": 0.30, "TLT": 0.70}
    assert allocs["CONS"] == {"SHY": 0.60, "TLT": 0.40}


def test_compute_signals_end_to_end():
    idx = _pd.date_range("2024-01-01", "2026-08-19", freq="B")
    n = len(idx)
    prices = {}
    up = _pd.Series(np.linspace(100, 200, n), index=idx)
    dn = _pd.Series(np.linspace(200, 100, n), index=idx)
    for t in ["SPY", "TLT", "XLE", "GLD", "GDX"]: prices[t] = up.copy()
    for t in ["DBC", "ERX"]: prices[t] = dn.copy()
    sig = compute_signals(prices, _date(2026, 8, 19))
    assert sig["quadrant"] is Quadrant.GROWTH   # SPY up, DBC down
    assert sig["tlt_trend_up"] is True
    assert sig["commodity_momentum"]["XLE"] > 0 > sig["commodity_momentum"]["DBC"]
