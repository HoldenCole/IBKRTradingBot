import numpy as np
import pandas as pd
import pytest

from research.crypto.levered import COST, account, trade_table


def _px(closes, highs=None, lows=None):
    idx = pd.date_range("2021-01-01", periods=len(closes), freq="h", tz="UTC")
    c = np.array(closes, float)
    d = pd.DataFrame({"open": c, "high": highs or c, "low": lows or c, "close": c}, index=idx)
    return idx, {"X": d}, {"X": pd.Series(0.0, index=idx)}


def test_long_trade_return_and_cost():
    idx, px, fund = _px([100, 101, 102, 103])
    t = trade_table([(0, 2, 1)], idx, px, fund, "X")
    assert t.gross.iloc[0] == pytest.approx(0.02) and t.net.iloc[0] == pytest.approx(0.02 - 2 * COST)


def test_short_receives_positive_funding():
    idx, px, fund = _px([100, 100, 100])
    fund["X"].iloc[1] = 0.001
    t = trade_table([(0, 2, -1)], idx, px, fund, "X")
    assert t.funding.iloc[0] == pytest.approx(0.001)


def test_adverse_excursion_uses_intrabar_extremes():
    idx, px, fund = _px([100, 100, 100], highs=[100, 100, 100], lows=[100, 90, 100])
    t = trade_table([(0, 2, 1)], idx, px, fund, "X")
    assert t.adverse.iloc[0] == pytest.approx(0.10)


def test_liquidation_at_10x_on_a_10pct_adverse_move():
    t = pd.DataFrame({"entry": pd.to_datetime(["2021-01-01", "2021-06-01"], utc=True),
                      "exit": pd.to_datetime(["2021-01-02", "2022-01-01"], utc=True),
                      "net": [0.05, 0.01], "adverse": [0.10, 0.0]})
    a10 = account(t, 10)
    assert a10["liquidations"] == 1 and a10["multiple"] == pytest.approx(0.05 * 1.1)
    a2 = account(t, 2)
    assert a2["liquidations"] == 0 and a2["multiple"] == pytest.approx(1.10 * 1.02)
