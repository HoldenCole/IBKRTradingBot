"""Tests for per-basket reporting + drawdown calc + history CSV."""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.deploy.baskets import BasketConfig
from src.deploy.portfolio import Ledger
from src.deploy.reporting import (
    EquityHistoryRow, append_daily_history,
    build_portfolio_report, compute_drawdown, format_report,
)


def _stage1_setup() -> tuple[BasketConfig, Ledger, dict[str, float]]:
    cfg = BasketConfig.load()
    L = Ledger()
    # Both sleeves entered: 7 QQQ @ 540, 66 IBIT @ 60
    L.record_buy(strategy_id="qqq_trend_50_200", symbol="QQQ", quantity=7,
                 price=540.0, trade_date=date(2024, 6, 20))
    L.record_buy(strategy_id="btc_trend_50_200", symbol="IBIT", quantity=66,
                 price=60.0, trade_date=date(2024, 6, 20))
    quotes = {"QQQ": 540.0, "IBIT": 60.0, "SGOV": 100.0}
    return cfg, L, quotes


def test_basic_report_at_entry_zero_pnl():
    cfg, L, quotes = _stage1_setup()
    nav = 8000.0
    r = build_portfolio_report(cfg, L, quotes, nav, date(2024, 6, 20))
    assert r.as_of == date(2024, 6, 20)
    assert r.nav == 8000.0
    # Two enabled baskets
    enabled = [b for b in r.baskets if b.enabled]
    assert len(enabled) == 2
    for b in enabled:
        # No moves yet -> unrealized P&L is 0
        assert b.unrealized_pnl == pytest.approx(0.0)
        assert b.realized_pnl == 0.0


def test_unrealized_pnl_reflects_mark_to_market():
    cfg, L, quotes = _stage1_setup()
    # QQQ appreciates 10%, IBIT drops 5%
    quotes_now = {"QQQ": 594.0, "IBIT": 57.0, "SGOV": 100.0}
    nav = 7 * 594.0 + 66 * 57.0   # = 4158 + 3762 = 7920
    r = build_portfolio_report(cfg, L, quotes_now, nav, date(2024, 7, 1))
    by_basket = {b.basket_id: b for b in r.baskets}
    # B3 (QQQ): 7 * (594 - 540) = +378
    assert by_basket["3"].unrealized_pnl == pytest.approx(378.0)
    # B2 (IBIT): 66 * (57 - 60) = -198
    assert by_basket["2"].unrealized_pnl == pytest.approx(-198.0)


def test_realized_pnl_aggregates_to_basket():
    cfg, L, quotes = _stage1_setup()
    L.record_sell(strategy_id="qqq_trend_50_200", symbol="QQQ", quantity=7,
                  price=600.0, trade_date=date(2024, 7, 1))   # +420 realized
    nav = 8420.0
    r = build_portfolio_report(cfg, L, {"QQQ":600,"IBIT":60,"SGOV":100}, nav,
                                date(2024, 7, 1))
    by_basket = {b.basket_id: b for b in r.baskets}
    assert by_basket["3"].realized_pnl == pytest.approx(420.0)
    assert by_basket["2"].realized_pnl == 0.0


def test_drift_pct_computed_when_basket_holds_position():
    cfg, L, quotes = _stage1_setup()
    # QQQ drops; basket 3's MV becomes ~3500 of an 8000 NAV -> realized weight = 44%
    quotes_now = {"QQQ": 500.0, "IBIT": 60.0, "SGOV": 100.0}
    mv_qqq = 7 * 500.0  # 3500
    mv_btc = 66 * 60.0  # 3960
    nav = mv_qqq + mv_btc + 280  # add cash sliver
    r = build_portfolio_report(cfg, L, quotes_now, nav, date(2024, 7, 1))
    b3 = next(b for b in r.baskets if b.basket_id == "3")
    # realized_weight = 3500/7740 ~= 0.452; target 0.5; drift = |0.452-0.5|/0.5 = 0.096
    assert b3.drift_pct is not None
    assert b3.drift_pct == pytest.approx(abs(mv_qqq/nav - 0.5) / 0.5)


def test_format_report_produces_readable_text():
    cfg, L, quotes = _stage1_setup()
    r = build_portfolio_report(cfg, L, quotes, 8000.0, date(2024, 6, 20))
    text = format_report(r)
    assert "PORTFOLIO REPORT" in text
    assert "2024-06-20" in text
    assert "NAV: $8,000.00" in text
    assert "Higher returns" in text or "Stability" in text
    # Disabled baskets shown but marked off
    assert "off" in text


# ===== Drawdown =====

def test_drawdown_empty_series():
    dd = compute_drawdown([])
    assert dd["max_dd"] == 0.0


def test_drawdown_monotonic_rise_is_zero():
    series = [(date(2024, 1, i+1), 100.0 + i) for i in range(10)]
    dd = compute_drawdown(series)
    assert dd["max_dd"] == 0.0
    assert dd["current_dd"] == 0.0


def test_drawdown_peak_to_trough_basic():
    series = [
        (date(2024, 1, 1), 100.0),
        (date(2024, 1, 2), 110.0),
        (date(2024, 1, 3), 120.0),   # peak
        (date(2024, 1, 4), 90.0),    # trough; DD from 120 = 25%
        (date(2024, 1, 5), 100.0),
    ]
    dd = compute_drawdown(series)
    assert dd["max_dd"] == pytest.approx(0.25)
    assert dd["max_dd_start"] == date(2024, 1, 3)
    assert dd["max_dd_trough"] == date(2024, 1, 4)
    assert dd["peak"] == 120.0
    # Current DD: peak 120 vs current 100 -> 20/120 = 16.67%
    assert dd["current_dd"] == pytest.approx(20/120)


def test_drawdown_recovers_to_new_peak_then_drops():
    series = [
        (date(2024, 1, 1), 100.0),
        (date(2024, 1, 2), 80.0),    # drawdown 20%
        (date(2024, 1, 3), 110.0),   # new peak (recovered)
        (date(2024, 1, 4), 99.0),    # drawdown from 110 = 10%
    ]
    dd = compute_drawdown(series)
    # The deeper drawdown was the first one (20%)
    assert dd["max_dd"] == pytest.approx(0.20)


# ===== History CSV =====

def test_append_daily_history_creates_file(tmp_path: Path):
    p = tmp_path / "history.csv"
    row = EquityHistoryRow(
        trading_date=date(2024, 6, 20),
        nav=8000.0, basket_mv={"2": 4000, "3": 3780, "cash": 220},
    )
    append_daily_history(p, row, basket_ids=["1", "2", "3", "4", "5"])
    assert p.exists()
    with p.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["trading_date"] == "2024-06-20"
    assert float(rows[0]["nav"]) == 8000.0
    assert float(rows[0]["basket_2_mv"]) == 4000
    assert float(rows[0]["basket_3_mv"]) == 3780
    assert float(rows[0]["cash"]) == 220


def test_append_daily_history_is_idempotent_per_date(tmp_path: Path):
    """Re-running the daily check for the same date overwrites that date's
    row, not appends a duplicate."""
    p = tmp_path / "history.csv"
    row1 = EquityHistoryRow(date(2024, 6, 20), 8000.0,
                            {"2": 4000, "3": 3780, "cash": 220})
    row2 = EquityHistoryRow(date(2024, 6, 20), 8100.0,
                            {"2": 4050, "3": 3830, "cash": 220})
    append_daily_history(p, row1, basket_ids=["2", "3"])
    append_daily_history(p, row2, basket_ids=["2", "3"])
    with p.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert float(rows[0]["nav"]) == 8100.0      # the later row wins


def test_append_daily_history_appends_distinct_dates(tmp_path: Path):
    p = tmp_path / "history.csv"
    for d in [date(2024, 6, 20), date(2024, 6, 21), date(2024, 6, 22)]:
        append_daily_history(
            p,
            EquityHistoryRow(d, 8000.0, {"2": 4000, "3": 3780, "cash": 220}),
            basket_ids=["2", "3"],
        )
    with p.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    # Sorted ascending
    assert rows[0]["trading_date"] < rows[-1]["trading_date"]
