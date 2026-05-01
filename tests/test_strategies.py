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


def test_ibs_short_suppressed_when_flag_disabled():
    """Default sqqq_short_enabled=True allows the IBS short branch; setting
    it False must suppress SQQQ short signals even when conditions hold.
    """
    n = 220
    rng = np.random.default_rng(5)
    base = np.linspace(420, 320, n) + rng.normal(0, 0.3, n)  # downtrend
    high = base + 1.0
    low = base - 1.0
    close = base.copy()
    # Force last bar IBS very high (close near high) and prior low
    high[-1] = base[-1] + 2.0
    low[-1] = base[-1] - 0.1
    close[-1] = high[-1] - 0.05
    # Prior IBS low
    high[-2] = base[-2] + 1.0
    low[-2] = base[-2] - 1.0
    close[-2] = low[-2] + 0.1
    df = pd.DataFrame(
        {"open": base, "high": high, "low": low, "close": close, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )

    # Default (enabled): a short signal should fire on QQQ
    sig_on = IBSStrategy().on_daily_close("QQQ", df)
    if sig_on is not None:
        assert sig_on.action is SignalAction.SHORT_FADE
        assert sig_on.option.underlying_etf == "SQQQ"

    # Disabled: regardless of whether signal would fire, no SQQQ short emitted
    sig_off = IBSStrategy(sqqq_short_enabled=False).on_daily_close("QQQ", df)
    assert sig_off is None or sig_off.action is not SignalAction.SHORT_FADE


def test_ewo_short_suppressed_when_flag_disabled():
    """Symmetric flag check for EWO."""
    n = 400
    rng = np.random.default_rng(11)
    # Downtrend with a sharp final-day rip to drive z-score positive and RSI high
    base = np.linspace(420, 320, n) + rng.normal(0, 0.3, n)
    base[-1] += 25.0
    df = pd.DataFrame(
        {"open": base, "high": base + 1, "low": base - 1, "close": base,
         "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    # Default firing depends on the EXACT z-score so we don't assert that
    # the short fires; we only assert the flag's suppression invariant.
    sig_off = EWOStrategy(sqqq_short_enabled=False).on_daily_close("QQQ", df)
    assert sig_off is None or sig_off.action is not SignalAction.SHORT_FADE


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
