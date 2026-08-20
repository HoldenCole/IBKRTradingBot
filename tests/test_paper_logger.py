"""Matrix integrity and paper-ledger mechanics (no network)."""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.portfolio.matrix import MATRIX, TIERS, all_tickers, allocation
from src.portfolio.paper_logger import (
    append_entry,
    classify_current_month,
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


def test_classify_current_month_growth():
    spy = daily(list(np.linspace(100, 200, 24)))
    dbc = daily(list(np.linspace(200, 100, 24)))
    assert classify_current_month(spy, dbc) is Quadrant.GROWTH


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
