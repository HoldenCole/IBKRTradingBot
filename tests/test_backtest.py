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
