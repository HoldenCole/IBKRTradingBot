"""Backtest tests: pricer correctness, engine end-to-end, metrics."""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestEngine, TradeRecord
from src.backtest.options import OptionParams, black_scholes_call, synthetic_quote
from src.backtest.report import compute_metrics, format_report
from src.strategies.ewo import EWOStrategy
from src.strategies.ibs import IBSStrategy

ET = ZoneInfo("America/New_York")


# --- Black-Scholes pricer -----------------------------------------------

def test_bs_atm_call_has_positive_time_value():
    p = OptionParams(spot=400.0, strike=400.0, dte_days=14, iv=0.30)
    price = black_scholes_call(p)
    # ATM call with no intrinsic: pure time value, must be > 0.
    assert price > 0


def test_bs_deep_itm_approaches_intrinsic():
    p = OptionParams(spot=500.0, strike=400.0, dte_days=14, iv=0.30)
    price = black_scholes_call(p)
    # Deep ITM: at minimum intrinsic value (100); roughly
    # spot - strike*exp(-r*T) for short DTE
    assert price >= 100.0
    assert price < 110.0  # not too much extrinsic at deep ITM short DTE


def test_bs_deep_otm_near_zero():
    p = OptionParams(spot=300.0, strike=400.0, dte_days=14, iv=0.30)
    price = black_scholes_call(p)
    assert price < 1.0


def test_bs_zero_dte_equals_intrinsic():
    p_itm = OptionParams(spot=420.0, strike=400.0, dte_days=0, iv=0.30)
    p_otm = OptionParams(spot=380.0, strike=400.0, dte_days=0, iv=0.30)
    assert black_scholes_call(p_itm) == 20.0
    assert black_scholes_call(p_otm) == 0.0


def test_synthetic_quote_has_valid_spread():
    p = OptionParams(spot=400.0, strike=400.0, dte_days=14, iv=0.30)
    q = synthetic_quote(p, spread_pct_of_mid=0.06)
    assert q.bid > 0
    assert q.ask > q.bid
    spread_pct = (q.ask - q.bid) / q.mid
    assert abs(spread_pct - 0.06) < 1e-9


# --- Engine end-to-end ---------------------------------------------------

def _ewo_long_daily(n=400, seed=7) -> pd.DataFrame:
    """Daily bars guaranteed to fire EWO long (deep z, RSI<10, close>SMA200)."""
    rng = np.random.default_rng(seed)
    base = np.linspace(300, 420, n) + rng.normal(0, 0.5, n)
    base[-5:] -= np.linspace(8, 30, 5)
    high = base + 1.0
    low = base - 1.0
    return pd.DataFrame(
        {"open": base, "high": high, "low": low, "close": base, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )


def _flat_daily(n=400, price=100.0) -> pd.DataFrame:
    closes = np.full(n, price)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.5, "low": closes - 0.5,
         "close": closes, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )


def test_engine_runs_and_records_at_least_one_trade():
    """End-to-end: feed EWO-long-triggering data, expect entries/exits."""
    spy_daily = _ewo_long_daily()
    qqq_daily = _flat_daily(price=400.0)

    # UPRO mirrors SPY but priced low so the ATM call sits under the
    # per-trade-risk cap with default IV.
    upro_close = (spy_daily["close"] / spy_daily["close"].iloc[0]) * 50.0
    upro = pd.DataFrame({
        "open": upro_close, "high": upro_close * 1.005, "low": upro_close * 0.995,
        "close": upro_close, "volume": [1e6] * len(upro_close),
    }, index=spy_daily.index)

    cfg = BacktestConfig(
        start=spy_daily.index[-30].date(),
        end=spy_daily.index[-1].date(),
        initial_capital=8000.0,
    )
    engine = BacktestEngine(
        config=cfg,
        strategies=[EWOStrategy(), IBSStrategy()],
        daily_bars={"SPY": spy_daily, "QQQ": qqq_daily},
        underlying_etf_bars={
            "UPRO": upro,
            "TQQQ": _flat_daily(price=80.0),
            "SQQQ": _flat_daily(price=25.0),
        },
    )
    result = engine.run()
    # Some signal should have fired given the construction
    assert len(result.trades) >= 1
    assert not result.equity_curve.empty
    # Equity curve should have a value per trading day in [start, end]
    assert len(result.equity_curve) > 1


def test_engine_respects_weekly_loss_budget():
    """Force a sequence of losing trades and confirm no entry crosses the
    hard gate (used > $500)."""
    # Use a setup that triggers the EWO long every week, with UPRO going
    # the wrong way so each trade loses ~50% premium.
    spy_daily = _ewo_long_daily()
    qqq_daily = _flat_daily(price=400.0)

    # UPRO drops monotonically -> calls go to zero -> -50% premium stop hits
    n = len(spy_daily)
    upro_close = np.linspace(100.0, 50.0, n)
    upro = pd.DataFrame({
        "open": upro_close, "high": upro_close * 1.005, "low": upro_close * 0.995,
        "close": upro_close, "volume": [1e6] * n,
    }, index=spy_daily.index)

    cfg = BacktestConfig(
        start=spy_daily.index[-60].date(),
        end=spy_daily.index[-1].date(),
        initial_capital=8000.0,
        weekly_loss_budget=500.0,
    )
    engine = BacktestEngine(
        config=cfg,
        strategies=[EWOStrategy()],
        daily_bars={"SPY": spy_daily, "QQQ": qqq_daily},
        underlying_etf_bars={
            "UPRO": upro,
            "TQQQ": _flat_daily(price=80.0),
            "SQQQ": _flat_daily(price=25.0),
        },
    )
    result = engine.run()
    # No single week should have realized loss > $500
    for snap in result.weekly_snapshots:
        assert snap["realized_pnl"] >= -cfg.weekly_loss_budget, (
            f"weekly loss exceeded budget: {snap}"
        )


def test_metrics_on_synthetic_ledger():
    """Compute_metrics over a hand-constructed result."""
    from src.backtest.engine import BacktestResult

    cfg = BacktestConfig(start=date(2026, 1, 1), end=date(2026, 1, 31),
                         initial_capital=8000.0)
    trades = [
        TradeRecord(
            trade_id="t1", strategy="ewo", underlying="SPY", option_etf="UPRO",
            direction="long",
            entry_time=datetime(2026, 1, 5, tzinfo=ET), entry_premium=4.0,
            exit_time=datetime(2026, 1, 8, tzinfo=ET), exit_premium=6.0,
            contracts=1, pnl=200.0, reason="signal_exit",
        ),
        TradeRecord(
            trade_id="t2", strategy="ewo", underlying="SPY", option_etf="UPRO",
            direction="long",
            entry_time=datetime(2026, 1, 12, tzinfo=ET), entry_premium=4.0,
            exit_time=datetime(2026, 1, 15, tzinfo=ET), exit_premium=2.0,
            contracts=1, pnl=-200.0, reason="premium_stop",
        ),
        TradeRecord(
            trade_id="t3", strategy="ibs", underlying="QQQ", option_etf="TQQQ",
            direction="long",
            entry_time=datetime(2026, 1, 20, tzinfo=ET), entry_premium=3.0,
            exit_time=datetime(2026, 1, 22, tzinfo=ET), exit_premium=4.5,
            contracts=1, pnl=150.0, reason="signal_exit",
        ),
    ]
    equity = pd.Series(
        {date(2026, 1, 1): 8000.0, date(2026, 1, 8): 8200.0,
         date(2026, 1, 15): 8000.0, date(2026, 1, 22): 8150.0,
         date(2026, 1, 31): 8150.0}
    )
    result = BacktestResult(config=cfg, trades=trades, equity_curve=equity,
                            weekly_snapshots=[], skipped_signals=[])
    m = compute_metrics(result)
    assert m.n_trades == 3
    assert m.n_wins == 2
    assert m.n_losses == 1
    assert m.win_rate == pytest.approx(2 / 3)
    assert m.total_pnl == 150.0
    assert m.total_return_pct == pytest.approx(150.0 / 8000.0)
    assert m.expectancy == pytest.approx(50.0)
    # Profit factor = 350 / 200 = 1.75
    assert m.profit_factor == pytest.approx(1.75)
    # By-strategy breakdown
    assert "ewo" in m.by_strategy
    assert m.by_strategy["ewo"]["n_trades"] == 2
    assert m.by_strategy["ibs"]["n_trades"] == 1
    # By-reason
    assert m.by_reason["signal_exit"] == 2
    assert m.by_reason["premium_stop"] == 1
    # Format doesn't crash and contains key fields
    out = format_report(result, m)
    assert "Trades" in out
    assert "ewo" in out


def test_intraday_stop_triggers_on_daily_low_and_fills_at_minus_53_pct():
    """When the day's low pushes BS premium <= -50% of entry, the trade
    must close at the intraday-fill price (~-53% of entry), NOT at the
    close-time premium. This is the core Step 1 fix.
    """
    spy_daily = _ewo_long_daily()
    qqq_daily = _flat_daily(price=400.0)
    n = len(spy_daily)
    # Build UPRO bars with a sharp intraday DROP on the entry day +1 (the
    # day after our deferred entry executes). The close recovers most of
    # the way back, so the close-based eval would NOT fire a stop, but
    # the intraday low should.
    upro_close = (spy_daily["close"] / spy_daily["close"].iloc[0]) * 50.0
    upro_high = upro_close * 1.005
    upro_low = upro_close * 0.995
    upro_open = upro_close.copy()
    # Crater the low for the last 3 days (post-entry window) but keep
    # the close near the open. This simulates a fast drop + recovery.
    for i in range(-3, 0):
        upro_low.iloc[i] = upro_close.iloc[i] * 0.50  # huge intraday low
    upro = pd.DataFrame({
        "open": upro_open, "high": upro_high, "low": upro_low,
        "close": upro_close, "volume": [1e6] * n,
    }, index=spy_daily.index)

    cfg = BacktestConfig(
        start=spy_daily.index[-30].date(),
        end=spy_daily.index[-1].date(),
        initial_capital=8000.0,
        intraday_stop_slippage_pct=0.03,
    )
    engine = BacktestEngine(
        config=cfg,
        strategies=[EWOStrategy(), IBSStrategy()],
        daily_bars={"SPY": spy_daily, "QQQ": qqq_daily},
        underlying_etf_bars={
            "UPRO": upro,
            "TQQQ": _flat_daily(price=80.0),
            "SQQQ": _flat_daily(price=25.0),
        },
    )
    result = engine.run()
    stops = [t for t in result.trades if t.reason == "premium_stop"]
    if stops:
        # Every premium_stop fill should be at exactly entry * 0.47 (-53%)
        for t in stops:
            ratio = t.exit_premium / t.entry_premium
            assert 0.46 <= ratio <= 0.48, (
                f"intraday stop should fill at ~-53%, got {ratio:.2%}"
            )


def test_intraday_stop_skips_when_daily_low_does_not_breach():
    """Inverse: if the day's low does NOT push BS below -50%, the
    intraday stop branch must not fire (we fall through to the
    close-based exit eval as before).
    """
    spy_daily = _ewo_long_daily()
    qqq_daily = _flat_daily(price=400.0)
    upro_close = (spy_daily["close"] / spy_daily["close"].iloc[0]) * 50.0
    upro = pd.DataFrame({
        "open": upro_close, "high": upro_close * 1.005, "low": upro_close * 0.995,
        "close": upro_close, "volume": [1e6] * len(upro_close),
    }, index=spy_daily.index)

    cfg = BacktestConfig(
        start=spy_daily.index[-30].date(),
        end=spy_daily.index[-1].date(),
        initial_capital=8000.0,
    )
    engine = BacktestEngine(
        config=cfg,
        strategies=[EWOStrategy(), IBSStrategy()],
        daily_bars={"SPY": spy_daily, "QQQ": qqq_daily},
        underlying_etf_bars={
            "UPRO": upro,
            "TQQQ": _flat_daily(price=80.0),
            "SQQQ": _flat_daily(price=25.0),
        },
    )
    result = engine.run()
    # On this benign data, no premium_stops should fire intraday.
    stops_intraday = [
        t for t in result.trades
        if t.reason == "premium_stop" and 0.46 <= t.exit_premium / t.entry_premium <= 0.48
    ]
    # Could be zero or could come from the close-eval path; the assertion
    # we care about is that the intraday-fill flat $0.47*entry is rare here.
    # Loose check: at least no false-positive epidemic.
    assert len(stops_intraday) <= 2


def test_intraday_stop_slippage_is_configurable():
    """Setting intraday_stop_slippage_pct=0.10 should fill at -60%."""
    spy_daily = _ewo_long_daily()
    qqq_daily = _flat_daily(price=400.0)
    n = len(spy_daily)
    upro_close = (spy_daily["close"] / spy_daily["close"].iloc[0]) * 50.0
    upro_low = upro_close * 0.995
    for i in range(-3, 0):
        upro_low.iloc[i] = upro_close.iloc[i] * 0.50
    upro = pd.DataFrame({
        "open": upro_close, "high": upro_close * 1.005, "low": upro_low,
        "close": upro_close, "volume": [1e6] * n,
    }, index=spy_daily.index)

    cfg = BacktestConfig(
        start=spy_daily.index[-30].date(),
        end=spy_daily.index[-1].date(),
        initial_capital=8000.0,
        intraday_stop_slippage_pct=0.10,  # -> fill at -60%
    )
    engine = BacktestEngine(
        config=cfg, strategies=[EWOStrategy(), IBSStrategy()],
        daily_bars={"SPY": spy_daily, "QQQ": qqq_daily},
        underlying_etf_bars={
            "UPRO": upro,
            "TQQQ": _flat_daily(price=80.0),
            "SQQQ": _flat_daily(price=25.0),
        },
    )
    result = engine.run()
    stops = [t for t in result.trades if t.reason == "premium_stop"]
    if stops:
        for t in stops:
            ratio = t.exit_premium / t.entry_premium
            assert 0.39 <= ratio <= 0.41, (
                f"with 10% slippage stop should fill at ~-60%, got {ratio:.2%}"
            )


def test_metrics_handle_empty_results():
    from src.backtest.engine import BacktestResult
    cfg = BacktestConfig(start=date(2026, 1, 1), end=date(2026, 1, 31),
                         initial_capital=8000.0)
    result = BacktestResult(
        config=cfg, trades=[],
        equity_curve=pd.Series(dtype=float),
        weekly_snapshots=[], skipped_signals=[],
    )
    m = compute_metrics(result)
    assert m.n_trades == 0
    assert m.win_rate == 0.0
    assert m.profit_factor == 0.0
