"""Backtest engine end-to-end on synthetic data with an injected lag."""

from datetime import time

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestConfig, align_pair, run_backtest
from src.strategies.cl1_uso_spread import SpreadParams

PARAMS = SpreadParams(min_history=200, beta_lookback=800, z_lookback=200)


def rth_index(days: int, minutes_per_day: int = 390) -> pd.DatetimeIndex:
    stamps = []
    base = pd.Timestamp("2026-07-06 09:30")  # a Monday
    day = 0
    added = 0
    while added < days:
        d = base + pd.Timedelta(days=day)
        day += 1
        if d.weekday() >= 5:
            continue
        stamps.extend(d + pd.Timedelta(minutes=m) for m in range(minutes_per_day))
        added += 1
    return pd.DatetimeIndex(stamps)


def synthetic_frames(days: int = 5, lag_minutes: int = 0, seed: int = 3):
    """USO tracks CL; optional lag makes USO reflect CL moves N minutes late."""
    idx = rth_index(days)
    n = len(idx)
    rng = np.random.default_rng(seed)
    r_cl = rng.normal(0, 0.0008, n)
    r_uso = np.roll(r_cl, lag_minutes) if lag_minutes else r_cl.copy()
    if lag_minutes:
        r_uso[:lag_minutes] = 0.0
    r_uso += rng.normal(0, 5e-5, n)
    cl_close = 70.0 * np.exp(np.cumsum(r_cl))
    uso_close = 75.0 * np.exp(np.cumsum(r_uso))

    def frame(close):
        return pd.DataFrame(
            {"open": np.r_[close[0], close[:-1]], "close": close}, index=idx
        )

    return frame(cl_close), frame(uso_close)


def test_align_pair_inner_joins():
    cl, uso = synthetic_frames(days=2)
    df = align_pair(cl, uso.iloc[10:])
    assert len(df) == len(uso) - 10


def test_lag_drives_trade_frequency():
    """A lagged pair should dislocate far more often than a synchronized one."""
    config = BacktestConfig(params=PARAMS)
    n_sync = run_backtest(*synthetic_frames(days=5, lag_minutes=0), config).metrics["n_trades"]
    n_lag = run_backtest(*synthetic_frames(days=5, lag_minutes=15), config).metrics["n_trades"]
    assert n_lag > n_sync


def test_lagged_pair_generates_trades_and_flat_eod():
    cl, uso = synthetic_frames(days=10, lag_minutes=15)
    result = run_backtest(cl, uso, BacktestConfig(params=PARAMS))
    assert result.metrics["n_trades"] > 0
    trades = result.trades
    # EOD flatten: every exit at or before 16:00, none held overnight.
    assert (trades["exit_ts"].dt.date == trades["entry_ts"].dt.date).all()
    assert (trades["exit_ts"].dt.time <= time(16, 0)).all()


def test_lagged_pair_profitable_before_costs():
    """A genuine lag should be captured: positive gross PnL on synthetic data."""
    cl, uso = synthetic_frames(days=10, lag_minutes=15)
    config = BacktestConfig(
        params=PARAMS, slippage_bps=0.0, commission_per_share=0.0, min_commission=0.0
    )
    result = run_backtest(cl, uso, config)
    assert result.trades["pnl"].sum() > 0


def test_equity_curve_shape():
    cl, uso = synthetic_frames(days=5, lag_minutes=15)
    result = run_backtest(cl, uso, BacktestConfig(params=PARAMS))
    assert len(result.equity) == len(align_pair(cl, uso))
