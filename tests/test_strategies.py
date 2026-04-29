from __future__ import annotations

import numpy as np
import pandas as pd

from src.strategies.afternoon import AfternoonReversionStrategy, attach_daily_atr
from src.strategies.base import SignalAction
from src.strategies.ewo import EWOStrategy
from src.strategies.ibs import IBSStrategy


def _make_oversold_daily(symbol_close_above_sma200: bool = True) -> pd.DataFrame:
    """Construct daily bars guaranteed to fire an EWO long: deep z-score < -2,
    RSI(2) < 10, close > SMA(200).
    """
    n = 400
    rng = np.random.default_rng(7)
    # Long uptrend so SMA200 is well below current price.
    base = np.linspace(300, 420, n) + rng.normal(0, 0.5, n)
    # Add a sharp 5-day pullback at the end.
    base[-5:] -= np.linspace(8, 30, 5)
    if not symbol_close_above_sma200:
        base[-5:] -= 100  # break below SMA200
    high = base + 1.0
    low = base - 1.0
    open_ = base
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": base, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    return df


def test_ewo_long_fires_on_deep_pullback():
    df = _make_oversold_daily()
    sig = EWOStrategy().on_daily_close("SPY", df)
    assert sig is not None
    assert sig.action is SignalAction.LONG
    assert sig.option.underlying_etf == "UPRO"
    assert sig.strategy_family == "mean_reversion"


def test_ewo_does_not_fire_below_sma200():
    df = _make_oversold_daily(symbol_close_above_sma200=False)
    sig = EWOStrategy().on_daily_close("SPY", df)
    assert sig is None


def test_ibs_long_fires_low_close():
    n = 220
    rng = np.random.default_rng(3)
    base = np.linspace(300, 420, n) + rng.normal(0, 0.3, n)
    high = base + 1.0
    low = base - 1.0
    close = base.copy()
    # Last day: close at low (IBS ~ 0); prior day normal (IBS ~ 0.5)
    close[-1] = low[-1] + 0.05  # IBS ~ near 0
    df = pd.DataFrame(
        {"open": base, "high": high, "low": low, "close": close, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    sig = IBSStrategy().on_daily_close("SPY", df)
    assert sig is not None
    assert sig.action is SignalAction.LONG
    assert sig.option.underlying_etf == "UPRO"


def test_afternoon_long_fires_on_morning_selloff(session_5m_bars):
    # The session fixture has a clear morning sell-off then a bounce after 11:00.
    # Attach a daily ATR (decimal price units).
    s = session_5m_bars.copy()
    s.attrs["daily_atr20"] = 1.0  # ATR=$1 on a ~$400 price -> 0.25% threshold

    # Feed bars one by one until we get a signal in the trigger window.
    strat = AfternoonReversionStrategy()
    sig = None
    for ts, row in s.iterrows():
        if ts.time().hour < 11:
            continue
        bar = {"ts": ts, "open": row["open"], "high": row["high"],
               "low": row["low"], "close": row["close"], "volume": row["volume"]}
        sig = strat.on_intraday_bar("SPY", bar, s)
        if sig is not None:
            break
    assert sig is not None, "afternoon long signal should fire after morning sell-off"
    assert sig.action is SignalAction.LONG
    assert sig.option.underlying_etf == "UPRO"
    assert sig.invalidation_price is not None


def test_attach_daily_atr_helper():
    n = 50
    rng = np.random.default_rng(0)
    close = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 400)
    high = close + 1.0
    low = close - 1.0
    daily = pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                          "volume": [1e6] * n})
    session = pd.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []})
    s2 = attach_daily_atr(session, daily)
    assert s2.attrs["daily_atr20"] is not None
    assert s2.attrs["daily_atr20"] > 0
