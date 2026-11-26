"""Intraday forex harness: fill rules, costs, look-ahead and the hold-out lock (synthetic data, no network)."""
import numpy as np
import pandas as pd
import pytest

from research.fx_intraday import costs, data, registry, rules
from research.fx_intraday.engine import Bars, one_at_a_time, simulate, stop_entries

P = 0.0001


def bars(mid, spread=0.5 * P, start="2020-03-02 09:00", high=None, low=None, pair="EURUSD"):
    mid = np.asarray(mid, float)
    n = len(mid)
    idx = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    hi = mid if high is None else np.asarray(high, float)
    lo = mid if low is None else np.asarray(low, float)
    return Bars(pair=pair, time=idx, mid_o=mid, mid_h=hi, mid_l=lo, mid_c=mid, spread=np.full(n, spread))


def test_market_round_trip_costs_the_base_spread_when_feed_is_tighter():
    b = bars([1.1] * 10)
    t = simulate(b, [1], [1], [1.0], [2.0], [5])
    base = costs.BASE_SPREAD_PIPS["EURUSD"] * P
    assert t.loc[0, "entry_px"] == pytest.approx(1.1 + base / 2)
    assert t.loc[0, "exit_px"] == pytest.approx(1.1 - base / 2)
    assert t.loc[0, "gross_bp"] == pytest.approx(0.0, abs=1e-9)
    assert t.loc[0, "cost_bp"] == pytest.approx(base / 1.1 * 1e4)
    assert t.loc[0, "kind"] == 2


def test_stress_scales_cost_and_wider_feed_spread_wins():
    b = bars([1.1] * 10)
    c1 = simulate(b, [1], [1], [1.0], [2.0], [5], stress=1.0).loc[0, "cost_bp"]
    c2 = simulate(b, [1], [1], [1.0], [2.0], [5], stress=2.0).loc[0, "cost_bp"]
    assert c2 == pytest.approx(2 * c1)
    wide = bars([1.1] * 10, spread=5 * P)
    assert simulate(wide, [1], [1], [1.0], [2.0], [5]).loc[0, "cost_bp"] == pytest.approx(5 * P / 1.1 * 1e4)


def test_stop_and_target_in_one_minute_takes_the_stop():
    mid = [1.1] * 10
    hi = mid.copy(); lo = mid.copy()
    hi[3], lo[3] = 1.1030, 1.0970
    b = bars(mid, high=hi, low=lo)
    t = simulate(b, [1], [1], [1.0980], [1.1020], [9])
    assert t.loc[0, "kind"] == 0 and t.loc[0, "exit_idx"] == 3
    assert t.loc[0, "exit_px"] == pytest.approx(1.0980 - costs.stop_slip("EURUSD", 1.0))


def test_gap_through_stop_fills_at_the_open_and_target_fills_at_its_price():
    mid = [1.1, 1.1, 1.1, 1.0950, 1.0950]
    b = bars(mid)
    t = simulate(b, [1], [1], [1.0980], [1.2], [4])
    h = costs.half_spread(np.array([0.5 * P]), "EURUSD", 1.0)[0]
    assert t.loc[0, "exit_px"] == pytest.approx(1.0950 - h - costs.stop_slip("EURUSD", 1.0))
    up = [1.1, 1.1, 1.1, 1.1, 1.1]
    hi = [1.1, 1.1, 1.1025, 1.1, 1.1]
    t2 = simulate(bars(up, high=hi), [1], [1], [1.0], [1.1010], [4])
    assert t2.loc[0, "kind"] == 1 and t2.loc[0, "exit_px"] == pytest.approx(1.1010)


def test_short_side_mirrors_long():
    mid = [1.1] * 10
    hi = mid.copy(); hi[4] = 1.1030
    t = simulate(bars(mid, high=hi), [1], [-1], [1.1020], [1.0], [9])
    assert t.loc[0, "kind"] == 0 and t.loc[0, "net_bp"] < 0


def test_one_at_a_time_skips_overlapping_trades():
    t = pd.DataFrame({"entry_idx": [1, 3, 6, 6], "exit_idx": [5, 7, 8, 9], "net_bp": [1, 2, 3, 4]})
    kept = one_at_a_time(t)
    assert list(kept["entry_idx"]) == [1, 6]


def test_stop_entry_skips_a_minute_that_triggers_both_sides():
    mid = [1.1] * 6
    hi = mid.copy(); lo = mid.copy()
    hi[2], lo[2] = 1.1050, 1.0950
    b = bars(mid, high=hi, low=lo)
    idx, side, px, slip = stop_entries(b, [0], [6], [1.1020], [1.0980])
    assert idx[0] == -1


def test_next_flat_is_1645_new_york_across_daylight_saving():
    t = pd.DatetimeIndex(["2024-03-08 15:00", "2024-03-11 15:00", "2024-03-11 22:00"], tz="UTC")
    f = rules.next_flat(t).tz_convert("America/New_York")
    assert [x.strftime("%m-%d %H:%M") for x in f] == ["03-08 16:45", "03-11 16:45", "03-12 16:45"]


def test_hourly_signals_enter_only_after_the_hour_closes():
    rng = np.random.default_rng(1)
    n = 60 * 24 * 10
    mid = 1.1 + np.cumsum(rng.normal(0, 0.0002, n))
    b = bars(mid, start="2020-03-02 00:00")
    hb = rules.hourly(b)
    cand = rules.mr_candidates(b, hb, 1.0)
    assert len(cand) > 0
    entry_t = b.time[cand["entry_idx"].to_numpy()]
    assert (entry_t >= cand.index + pd.Timedelta(hours=1)).all()


def test_round_filter_keeps_longs_just_above_a_level():
    mid = np.array([1.1003, 1.1033, 1.0997])
    b = bars(mid)
    cand = pd.DataFrame({"entry_idx": [0, 1, 2], "side": [1, 1, -1]})
    kept = rules.round_filter(b, cand)
    assert list(kept["entry_idx"]) == [0, 2]


def test_holdout_is_locked_without_a_token():
    with pytest.raises(data.HoldoutLocked):
        data.load("EURUSD", start="2025-01-01", end="2025-02-01")


def test_holdout_opens_once_per_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "HOLDOUT", tmp_path / "h.csv")
    tok = registry.open_holdout("drift_A", "EURUSD", "all")
    registry.check_token(tok)
    with pytest.raises(PermissionError):
        registry.open_holdout("drift_A", "EURUSD", "all")
    with pytest.raises(PermissionError):
        registry.check_token("not-a-token")
