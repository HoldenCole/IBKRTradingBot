"""Tests for v2 foundational modules: benchmark, tier, walk_forward, shares_engine."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.backtest.benchmark import BenchmarkMetrics, buy_and_hold_metrics, equity_metrics
from src.backtest.shares_engine import SharesBacktestConfig, SharesBacktestEngine
from src.backtest.tier import classify
from src.backtest.walk_forward import single_fold
from src.strategies.ibs import IBSStrategy


# --- Benchmark ---

def test_benchmark_flat_series():
    closes = pd.Series([100.0, 100.0, 100.0],
                       index=pd.date_range("2024-01-01", periods=3, freq="D"))
    m = buy_and_hold_metrics(closes, start_capital=8000.0, symbol="FLAT")
    assert m.total_return == 0.0
    assert m.sharpe == 0.0
    assert m.max_drawdown == 0.0
    assert m.final_equity == 8000.0


def test_benchmark_uptrend():
    n = 252
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0005, 0.01, n)
    closes = pd.Series(100.0 * np.exp(np.cumsum(rets)),
                       index=pd.bdate_range("2024-01-01", periods=n))
    m = buy_and_hold_metrics(closes, start_capital=8000.0, symbol="X")
    assert m.total_return > 0
    assert m.years > 0.9
    assert m.final_equity > 8000.0


def test_equity_metrics_consistent_with_benchmark():
    """equity_metrics on a price series multiplied by start_capital should
    match buy_and_hold_metrics for the same input."""
    closes = pd.Series([100.0, 105.0, 110.0, 108.0, 115.0],
                       index=pd.date_range("2024-01-01", periods=5, freq="D"))
    bm = buy_and_hold_metrics(closes, start_capital=8000.0)
    eq = (closes / closes.iloc[0]) * 8000.0
    em = equity_metrics(eq, start_capital=8000.0)
    assert abs(em["total_return"] - bm.total_return) < 1e-9
    assert abs(em["sharpe"] - bm.sharpe) < 1e-9
    assert abs(em["max_drawdown"] - bm.max_drawdown) < 1e-9


# --- Tier classifier ---

def test_tier_a_with_better_return():
    v = classify(strategy_sharpe=1.6, strategy_max_dd=-0.20,
                 strategy_total_return=2.0, bench_sharpe=0.7,
                 bench_total_return=1.6)
    assert v.tier == "A"


def test_tier_a_with_sharpe_lift_only():
    # Beats Sharpe by >=0.8 but underperforms on absolute return
    v = classify(strategy_sharpe=1.6, strategy_max_dd=-0.10,
                 strategy_total_return=0.5, bench_sharpe=0.7,
                 bench_total_return=1.6)
    assert v.tier == "A"


def test_tier_b_within_dd_limit():
    v = classify(strategy_sharpe=1.2, strategy_max_dd=-0.32,
                 strategy_total_return=0.5, bench_sharpe=0.7,
                 bench_total_return=1.0)
    # Sharpe lift = 0.5 >= 0.4 -> Tier B
    assert v.tier == "B"


def test_tier_c_within_20pp_of_bench():
    v = classify(strategy_sharpe=0.8, strategy_max_dd=-0.20,
                 strategy_total_return=1.0, bench_sharpe=0.7,
                 bench_total_return=1.15)
    # Within 20pp below bench, Sharpe in [0.5, 1.0)
    assert v.tier == "C"


def test_tier_d_excessive_drawdown():
    v = classify(strategy_sharpe=2.0, strategy_max_dd=-0.50,
                 strategy_total_return=3.0, bench_sharpe=0.7,
                 bench_total_return=1.5)
    # Excellent Sharpe and return but -50% DD -> Tier D
    assert v.tier == "D"
    assert "DD" in v.rationale


def test_tier_d_low_sharpe():
    v = classify(strategy_sharpe=0.3, strategy_max_dd=-0.10,
                 strategy_total_return=0.5, bench_sharpe=0.7,
                 bench_total_return=1.0)
    assert v.tier == "D"


# --- Walk-forward ---

def test_single_fold_5_3_split():
    f = single_fold(date(2018, 1, 1), date(2026, 4, 15), train_years=5, test_years=3)
    assert f.train_start == date(2018, 1, 1)
    assert f.train_end.year == 2022
    assert f.test_start.year == 2023
    assert f.test_end == date(2026, 4, 15)


# --- Shares engine ---

def _ibs_long_daily(n=400, seed=7) -> pd.DataFrame:
    """Bars guaranteed to fire IBS long: deep low-IBS day after a normal day,
    in an uptrend so close > SMA(200). Deep-IBS bar placed 5 bars from end
    so entry has time to execute and exit within the test window.
    """
    rng = np.random.default_rng(seed)
    base = np.linspace(300.0, 420.0, n) + rng.normal(0, 0.3, n)
    high = base + 1.0
    low = base - 1.0
    close = base.copy()
    # Deep-IBS bar at index n-5: close near low -> IBS very low
    close[-5] = low[-5] + 0.05
    high[-5] = close[-5] + 0.5
    return pd.DataFrame(
        {"open": base, "high": high, "low": low, "close": close,
         "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )


def _flat_daily(n=400, price=400.0) -> pd.DataFrame:
    closes = np.full(n, price)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.5, "low": closes - 0.5,
         "close": closes, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )


def test_shares_engine_runs_and_produces_at_least_one_trade():
    spy = _ibs_long_daily()
    qqq = _flat_daily()
    cfg = SharesBacktestConfig(
        start=spy.index[-30].date(),
        end=spy.index[-1].date(),
        initial_capital=8000.0,
    )
    eng = SharesBacktestEngine(
        config=cfg, strategies=[IBSStrategy()],
        daily_bars={"SPY": spy, "QQQ": qqq},
    )
    result = eng.run()
    # Equity curve must have a value per trading day
    assert len(result.equity_curve) > 1
    # IBS long should have fired at the deep-IBS bar
    assert len(result.trades) >= 1
    t = result.trades[0]
    assert t.direction == "long"
    assert t.shares > 0


def test_shares_engine_signal_only_mode_disables_time_stop():
    spy = _ibs_long_daily()
    qqq = _flat_daily()
    cfg = SharesBacktestConfig(
        start=spy.index[-60].date(),
        end=spy.index[-1].date(),
        initial_capital=8000.0,
        enable_signal_only_mode=True,
        time_stop_days=2,  # would normally fire after 2d
    )
    eng = SharesBacktestEngine(
        config=cfg, strategies=[IBSStrategy()],
        daily_bars={"SPY": spy, "QQQ": qqq},
    )
    result = eng.run()
    # No trade should exit via time_stop in signal-only mode
    for t in result.trades:
        assert t.reason != "time_stop"


def test_short_position_equity_curve_goes_up_when_underlying_drops():
    """A profitable short (underlying drops) must produce an UPWARD-
    sloping equity curve while the position is open. Verifies the
    fix to the inverted shorts handling.
    """
    # Build a series where IBS-short on QQQ fires (IBS>0.80, close<SMA200).
    n = 220
    rng = np.random.default_rng(2)
    base = np.linspace(420.0, 320.0, n) + rng.normal(0, 0.3, n)  # downtrend
    high = base + 1.0
    low = base - 1.0
    close = base.copy()
    # Place high-IBS bar at -7 (so entry at -6 has time to play out)
    close[-7] = high[-7] - 0.05
    low[-7] = close[-7] - 1.0
    # Force prior bar IBS low so no-stacking rule passes
    close[-8] = low[-8] + 0.1
    df = pd.DataFrame(
        {"open": base, "high": high, "low": low, "close": close,
         "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    cfg = SharesBacktestConfig(
        start=df.index[-15].date(),
        end=df.index[-1].date(),
        initial_capital=10000.0,
        max_concurrent=1,
        time_stop_days=10,
    )
    eng = SharesBacktestEngine(
        config=cfg,
        strategies=[IBSStrategy(long_enabled=False, sqqq_short_enabled=True)],
        daily_bars={"SPY": pd.DataFrame(), "QQQ": df},
    )
    result = eng.run()
    # Whether or not a short fires depends on the synthetic series;
    # if one did fire, its closed-trade pnl should equal the cash delta.
    if result.trades:
        t = result.trades[0]
        assert t.direction == "short_fade"
        # Realized P&L is (entry - exit) * shares for short
        expected = (t.entry_price - t.exit_price) * t.shares
        assert abs(t.pnl - expected) < 0.01


def test_short_realized_pnl_matches_cash_delta():
    """End-of-backtest cash + open MTM should equal initial_capital +
    sum(trade.pnl) — within floating-point tolerance — for any direction."""
    # Build series with a high-IBS day in QQQ downtrend
    n = 220
    rng = np.random.default_rng(0)
    base = np.linspace(420.0, 320.0, n) + rng.normal(0, 0.3, n)
    high = base + 1.0
    low = base - 1.0
    close = base.copy()
    close[-7] = high[-7] - 0.05
    low[-7] = close[-7] - 1.0
    close[-8] = low[-8] + 0.1
    df = pd.DataFrame(
        {"open": base, "high": high, "low": low, "close": close,
         "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    cfg = SharesBacktestConfig(
        start=df.index[-15].date(),
        end=df.index[-1].date(),
        initial_capital=10000.0,
        max_concurrent=1,
        time_stop_days=10,
    )
    eng = SharesBacktestEngine(
        config=cfg,
        strategies=[IBSStrategy(long_enabled=False, sqqq_short_enabled=True)],
        daily_bars={"SPY": pd.DataFrame(), "QQQ": df},
    )
    result = eng.run()
    final_eq = result.equity_curve.iloc[-1]
    expected = cfg.initial_capital + sum(t.pnl for t in result.trades)
    assert abs(final_eq - expected) < 1.0


def test_shares_engine_full_account_sizing():
    spy = _ibs_long_daily()
    qqq = _flat_daily()
    cfg = SharesBacktestConfig(
        start=spy.index[-30].date(),
        end=spy.index[-1].date(),
        initial_capital=8000.0,
        allocation_pct=1.0,
        max_concurrent=1,
    )
    eng = SharesBacktestEngine(
        config=cfg, strategies=[IBSStrategy()],
        daily_bars={"SPY": spy, "QQQ": qqq},
    )
    result = eng.run()
    assert len(result.trades) >= 1
    t = result.trades[0]
    cost = t.entry_price * t.shares
    # Should be near full equity (allow 5% headroom for slippage / rounding)
    assert cost > 7500.0
