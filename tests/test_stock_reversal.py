import numpy as np
import pandas as pd
import pytest

from research.stock_reversal.events import HOLDOUT_FLAG, _session_index, build
from research.stock_reversal.run import clustered_t, holm


def test_filing_maps_to_next_session_after_close():
    sess = pd.DatetimeIndex(["2020-01-06", "2020-01-07", "2020-01-08"])
    close_t = (sess + pd.Timedelta(hours=16)).values
    acc = pd.Series(pd.to_datetime(["2020-01-06 16:05", "2020-01-07 07:30", "2020-01-07 16:00", "2020-01-06 15:59"]))
    k = _session_index(acc, close_t)
    # after close Jan 6 -> Jan 7; pre-market Jan 7 -> Jan 7; exactly 16:00 Jan 7 -> Jan 7; intraday Jan 6 -> Jan 6
    assert list(k) == [1, 1, 1, 0]


def test_clustered_t_matches_plain_t_without_clusters():
    rng = np.random.default_rng(0)
    x = rng.normal(0.1, 1, 2000)
    t_plain = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    assert abs(clustered_t(x, np.arange(len(x))) - t_plain) / t_plain < 0.01


def test_clustering_widens_se_for_same_day_events():
    rng = np.random.default_rng(1)
    day = np.repeat(np.arange(200), 10)
    x = 0.05 + np.repeat(rng.normal(0, 1, 200), 10) + rng.normal(0, 0.1, 2000)
    assert abs(clustered_t(x, day)) < abs(clustered_t(x, np.arange(2000))) / 2


def test_holm_is_monotone_and_bounded():
    p = np.array([0.001, 0.04, 0.03, 0.5])
    a = holm(p)
    assert a[0] == pytest.approx(0.004) and a.max() <= 1 and a[2] == pytest.approx(0.09) and a[1] == pytest.approx(0.09)


def test_holdout_locked():
    with pytest.raises(PermissionError):
        build(holdout="please")
    assert "once" in HOLDOUT_FLAG


def _sim(o, h, l, c, i, open_entry, s, T=0.03, S=0.06, cap=20):
    from research.stock_reversal.price_exits import simulate
    a = lambda x: np.array(x, float)
    r, held, hit = simulate(a(o), a(h), a(l), a(c), np.array([i]), open_entry, np.array([float(s)]), T, S, cap, 0.0, 0.0)
    return r[0], held[0], hit[0]


def test_short_from_open_hits_target_same_day():
    r, held, hit = _sim([100, 99], [101, 99], [96, 98], [97, 98], 0, True, -1)
    assert hit == 1 and held == 1 and r == pytest.approx(0.03)


def test_stop_taken_when_both_touched_in_one_bar():
    r, _, hit = _sim([100, 100], [107, 107], [96, 96], [100, 100], 0, True, -1)
    assert hit == -1 and r == pytest.approx(-0.06)


def test_close_entry_gap_through_target_fills_at_open():
    r, held, hit = _sim([100, 104], [100, 105], [100, 103], [100, 104], 0, False, 1)
    assert hit == 1 and held == 1 and r == pytest.approx(0.04)


def test_time_cap_exits_at_close():
    r, held, hit = _sim([100] * 4, [101] * 4, [99] * 4, [100, 100, 100, 101], 0, False, 1, cap=3)
    assert hit == 0 and held == 3 and r == pytest.approx(0.01)
