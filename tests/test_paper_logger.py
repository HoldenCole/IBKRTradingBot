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
    # shorts off isolates the conditional-duration leg (v5 S-cells)
    up = resolve_allocation("MOD", Quadrant.STAGFLATION, tlt_trend_up=True, include_shorts=False)
    dn = resolve_allocation("MOD", Quadrant.STAGFLATION, tlt_trend_up=False, include_shorts=False)
    unk = resolve_allocation("MOD", Quadrant.STAGFLATION, tlt_trend_up=None, include_shorts=False)
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
    # v6: VAGG S = 15% energy short (7.5% ERY + 7.5% SHY) + conditional TLT
    assert allocs["VAGG"] == {"SHY": 0.225, "TLT": 0.70, "ERY": 0.075}
    assert allocs["CONS"] == {"SHY": 0.60, "TLT": 0.40}


# ---- v5 additions: the short book and its global switch ----
from src.portfolio.matrix import SHORT_FALLBACK, SHORT_IMPL, SHORT_OIL


def test_short_placeholders_not_in_tickers():
    tickers = all_tickers()
    assert SHORT_OIL not in tickers
    assert "SCO" in tickers  # the margin-free implementation ETF


def test_short_sleeve_resolves_to_inverse_etf_plus_cash():
    # 10% MOD sleeve -> 5% SCO (2x inverse) + 5% SHY
    a = resolve_allocation("MOD", Quadrant.DEFLATION, include_shorts=True)
    assert a["SCO"] == pytest.approx(0.05)
    assert a["SHY"] == pytest.approx(0.05)
    assert SHORT_OIL not in a
    assert sum(a.values()) == pytest.approx(1.0, abs=0.01)
    # 15% AGG sleeve -> 7.5% SCO + 7.5% SHY
    a = resolve_allocation("AGG", Quadrant.DEFLATION, include_shorts=True)
    assert a["SCO"] == pytest.approx(0.075)
    assert a["SHY"] == pytest.approx(0.075)
    assert sum(a.values()) == pytest.approx(1.0, abs=0.01)


def test_shorts_off_restores_v4_long_only_cells():
    v4_d = {
        "MOD": {"TLT": 0.45, "GLD": 0.30, "XLP": 0.15, "SPY": 0.10},
        "AGG": {"TLT": 0.40, "TMF": 0.15, "GLD": 0.30, "QQQ": 0.15},
        "VAGG": {"TMF": 0.35, "TLT": 0.20, "GLD": 0.30, "QLD": 0.15},
    }
    for tier, expected in v4_d.items():
        a = resolve_allocation(tier, Quadrant.DEFLATION, include_shorts=False)
        assert a == pytest.approx(expected), tier


def test_shorts_off_restores_long_only_s_cells():
    # energy sleeve falls back to SHY -> the pre-v6 S-cells exactly
    for tier, cash in [("MOD", 0.50), ("AGG", 0.40), ("VAGG", 0.30)]:
        a = resolve_allocation(tier, Quadrant.STAGFLATION, tlt_trend_up=True,
                               include_shorts=False)
        assert a == pytest.approx({"SHY": cash, "TLT": round(1 - cash, 2)}), tier


def test_energy_short_resolves_in_s_cell():
    # MOD S, bonds trending up: 10% sleeve -> 5% ERY + 5% SHY
    a = resolve_allocation("MOD", Quadrant.STAGFLATION, tlt_trend_up=True,
                           include_shorts=True)
    assert a == pytest.approx({"SHY": 0.45, "TLT": 0.50, "ERY": 0.05})
    assert sum(a.values()) == pytest.approx(1.0, abs=0.01)
    # CONS S stays long-only
    c = resolve_allocation("CONS", Quadrant.STAGFLATION, tlt_trend_up=True,
                           include_shorts=True)
    assert "ERY" not in c


def test_cons_stays_long_only_either_way():
    on = resolve_allocation("CONS", Quadrant.DEFLATION, include_shorts=True)
    off = resolve_allocation("CONS", Quadrant.DEFLATION, include_shorts=False)
    assert on == off
    assert "SCO" not in on


def test_short_registry_consistent():
    # every registered short has an implementation and a long fallback
    assert set(SHORT_IMPL) == set(SHORT_FALLBACK)
    for etf, leverage in SHORT_IMPL.values():
        assert leverage >= 1.0
        assert etf in all_tickers()


def test_append_entry_snapshots_short_sleeve(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry(Quadrant.DEFLATION, date(2026, 10, 1), path)
    row = load_ledger(path).loc[0]
    allocs = json.loads(row["allocations"])
    assert allocs["MOD"]["SCO"] == 0.05
    assert "SCO" not in allocs["CONS"]
    assert json.loads(row["signals"])["include_shorts"] is True


# ---- v7 additions: washout-conditional D rebound slice ----
from src.portfolio.matrix import WASHOUT_REBOUND, WASHOUT_SHIFT


def test_washout_tilt_resolves_in_d_cell():
    # MOD D washed out: TLT 35->25, SPY 10->20 (shorts on)
    a = resolve_allocation("MOD", Quadrant.DEFLATION, include_shorts=True,
                           breadth_washout=True)
    assert a["TLT"] == pytest.approx(0.25)
    assert a["SPY"] == pytest.approx(0.20)
    assert sum(a.values()) == pytest.approx(1.0, abs=0.01)


def test_washout_shift_caps_at_tlt_weight():
    # VAGG D has only 5% TLT after short resolution -> shift caps at 5pp
    a = resolve_allocation("VAGG", Quadrant.DEFLATION, include_shorts=True,
                           breadth_washout=True)
    assert "TLT" not in a
    assert a["QLD"] == pytest.approx(0.20)
    assert sum(a.values()) == pytest.approx(1.0, abs=0.01)


def test_washout_fails_closed_and_excludes_cons():
    base = resolve_allocation("MOD", Quadrant.DEFLATION, include_shorts=True)
    assert resolve_allocation("MOD", Quadrant.DEFLATION, include_shorts=True,
                              breadth_washout=None) == base
    assert resolve_allocation("MOD", Quadrant.DEFLATION, include_shorts=True,
                              breadth_washout=False) == base
    cons = resolve_allocation("CONS", Quadrant.DEFLATION, include_shorts=True)
    assert resolve_allocation("CONS", Quadrant.DEFLATION, include_shorts=True,
                              breadth_washout=True) == cons
    # non-D quadrants unaffected
    g = resolve_allocation("MOD", Quadrant.GROWTH)
    assert resolve_allocation("MOD", Quadrant.GROWTH, breadth_washout=True) == g


def test_append_entry_snapshots_washout(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry(Quadrant.DEFLATION, date(2026, 11, 1), path,
                 breadth=0.15, breadth_washout=True)
    row = load_ledger(path).loc[0]
    sig = json.loads(row["signals"])
    assert sig["breadth"] == 0.15 and sig["breadth_washout"] is True
    allocs = json.loads(row["allocations"])
    assert allocs["MOD"]["SPY"] == 0.20
    assert allocs["CONS"]["SPY"] == 0.10  # CONS untouched


def test_compute_signals_breadth():
    idx = _pd.date_range("2024-01-01", "2026-08-19", freq="B")
    n = len(idx)
    up = _pd.Series(np.linspace(100, 200, n), index=idx)
    dn = _pd.Series(np.linspace(200, 100, n), index=idx)
    prices = {t: up.copy() for t in ["SPY", "TLT", "XLE", "GLD", "GDX"]}
    prices["DBC"] = dn.copy(); prices["ERX"] = dn.copy()
    from src.portfolio.paper_logger import BREADTH_TICKERS
    # 15 breadth names all in downtrend -> breadth ~0 -> washout True
    for t in BREADTH_TICKERS[:15]:
        prices[t] = dn.copy()
    sig = compute_signals(prices, _date(2026, 8, 19))
    assert sig["breadth"] is not None and sig["breadth"] < 0.25
    assert sig["breadth_washout"] is True
    # too few names -> unknown, fail closed
    prices2 = {k: v for k, v in prices.items() if k not in BREADTH_TICKERS[:10]}
    sig2 = compute_signals(prices2, _date(2026, 8, 19))
    assert sig2["breadth"] is None and sig2["breadth_washout"] is None


# ---- S&P 500 quadrant balance (informational ledger line) ----
from src.portfolio.paper_logger import member_phase, quadrant_balance


def _mseries(vals):
    idx = _pd.date_range("2024-01-31", periods=len(vals), freq="ME")
    return _pd.Series(vals, index=idx, dtype=float)


def test_member_phase_quadrants():
    assert member_phase(_mseries([100, 99, 97, 96, 95.5, 95.2])) == 1  # falling, decelerating
    assert member_phase(_mseries([100, 100.5, 101.5, 103, 105, 108])) == 2  # rising, accelerating
    assert member_phase(_mseries([100, 104, 107, 109, 110, 110.5])) == 3  # rising, decelerating
    assert member_phase(_mseries([100, 99.5, 98.5, 97, 95, 92])) == 4  # falling, accelerating
    assert member_phase(_mseries([100, 101])) is None  # too short


def test_quadrant_balance_counts_and_threshold():
    closes = {}
    for i in range(160):
        closes[f"UP{i}"] = _mseries([100, 100.5, 101.5, 103, 105, 108])
    for i in range(40):
        closes[f"DN{i}"] = _mseries([100, 99.5, 98.5, 97, 95, 92])
    bal = quadrant_balance(closes)
    assert bal["n"] == 200 and bal["dominant"] == 2
    assert bal["q2"] == pytest.approx(0.8) and bal["q4"] == pytest.approx(0.2)
    assert quadrant_balance(dict(list(closes.items())[:100])) is None  # < MIN_BALANCE_NAMES


def test_append_entry_snapshots_sp500_balance(tmp_path):
    path = tmp_path / "ledger.csv"
    bal = {"q1": 0.14, "q2": 0.48, "q3": 0.20, "q4": 0.18, "dominant": 2, "n": 499}
    append_entry(Quadrant.REFLATION, date(2026, 12, 1), path, sp500_balance=bal)
    sig = json.loads(load_ledger(path).loc[0, "signals"])
    assert sig["sp500_balance"]["dominant"] == 2
    # and None (fetch failure) must serialize cleanly too
    append_entry(Quadrant.REFLATION, date(2027, 1, 1), path, sp500_balance=None)
    sig2 = json.loads(load_ledger(path).loc[1, "signals"])
    assert sig2["sp500_balance"] is None


# ---- shadow classifier (informational fast-entry variant) ----
from src.regime.quadrant import shadow_classify


def test_shadow_agrees_in_steady_trends():
    idx = _pd.date_range("2023-01-31", periods=24, freq="ME")
    up = _pd.Series(np.linspace(100, 200, 24), index=idx)
    dn = _pd.Series(np.linspace(200, 100, 24), index=idx)
    from src.regime.quadrant import classify
    assert shadow_classify(up, dn) is Quadrant.GROWTH
    assert shadow_classify(up, dn) is classify(up, dn)
    assert shadow_classify(dn, dn) is Quadrant.DEFLATION


def test_shadow_enters_faster_after_decline():
    # long decline (flag OFF), then a 5-month recovery: price crosses the
    # 5m SMA but is still below the 10m SMA -> shadow risk-on, primary
    # still defensive. The exact asymmetry being trialed.
    # NOTE: the shadow re-evaluates monthly (matching the backtested
    # rule exactly): in the 5m<px<10m band it can flip back off the
    # following month. This test ends at the fast-entry month.
    from src.regime.quadrant import classify
    vals = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100,
            104, 108, 112]
    idx = _pd.date_range("2023-01-31", periods=len(vals), freq="ME")
    spy = _pd.Series(vals, index=idx, dtype=float)
    dn = _pd.Series(np.linspace(300, 100, len(vals)), index=idx)  # inflation off
    assert spy.iloc[-1] > spy.tail(5).mean()          # above fast SMA
    assert spy.iloc[-1] < spy.tail(10).mean()         # still below slow SMA
    assert classify(spy, dn) is Quadrant.DEFLATION    # primary: defensive
    assert shadow_classify(spy, dn) is Quadrant.GROWTH  # shadow: re-entered


def test_append_entry_snapshots_shadow(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry(Quadrant.DEFLATION, date(2027, 2, 1), path, shadow_quadrant="GROWTH")
    sig = json.loads(load_ledger(path).loc[0, "signals"])
    assert sig["shadow_quadrant"] == "GROWTH"


# ---- managed-futures watchlist (informational) ----
def test_compute_signals_managed_futures():
    idx = _pd.date_range("2024-01-01", "2026-08-19", freq="B")
    n = len(idx)
    up = _pd.Series(np.linspace(100, 200, n), index=idx)
    dn = _pd.Series(np.linspace(200, 100, n), index=idx)
    prices = {t: up.copy() for t in ["SPY", "TLT", "XLE", "GLD", "GDX", "DBMF"]}
    prices["DBC"] = dn.copy(); prices["ERX"] = dn.copy()
    sig = compute_signals(prices, _date(2026, 8, 19))
    assert "DBMF" in sig["managed_futures"] and sig["managed_futures"]["DBMF"] > 0
    assert "KMLM" not in sig["managed_futures"]  # missing ticker tolerated


def test_append_entry_snapshots_managed_futures(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry(Quadrant.STAGFLATION, date(2027, 3, 1), path,
                 managed_futures={"DBMF": 0.021, "KMLM": 0.035})
    sig = json.loads(load_ledger(path).loc[0, "signals"])
    assert sig["managed_futures"]["KMLM"] == 0.035
    append_entry(Quadrant.STAGFLATION, date(2027, 4, 1), path)  # None -> {}
    assert json.loads(load_ledger(path).loc[1, "signals"])["managed_futures"] == {}


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
