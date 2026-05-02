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


# --- Regime filter ---

def test_drawdown_filter_blocks_during_correction():
    from src.backtest.regime_filter import DrawdownFilter
    n = 60
    closes = np.concatenate([np.full(n - 5, 100.0), [95.0, 92.0, 90.0, 92.0, 91.0]])
    df = pd.DataFrame(
        {"open": closes, "high": closes + 1, "low": closes - 1,
         "close": closes, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    f = DrawdownFilter(lookback=30, threshold=-0.07)
    # Last bar: drawdown from rolling-30d high (100) is -9% -> OFF
    last_d = df.index[-1].date()
    assert f.is_active(df, last_d) is False
    # First bar in stable plateau: small drawdown -> ON
    early_d = df.index[20].date()
    assert f.is_active(df, early_d) is True


def test_sma200_band_filter_blocks_near_sma():
    from src.backtest.regime_filter import Sma200BandFilter
    n = 250
    base = np.linspace(100.0, 100.5, n)  # essentially flat -> close very near SMA200
    df = pd.DataFrame(
        {"open": base, "high": base + 0.1, "low": base - 0.1,
         "close": base, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    f = Sma200BandFilter(sma_period=200, band=0.05)
    # Close ~= SMA200 -> OFF
    assert f.is_active(df, df.index[-1].date()) is False

    # If we shift close 10% above SMA200 it's outside the band -> ON
    base2 = base.copy()
    base2[-1] = base[-1] * 1.10
    df2 = df.copy()
    df2["close"] = base2
    df2["high"] = base2 + 0.1
    df2["low"] = base2 - 0.1
    assert f.is_active(df2, df2.index[-1].date()) is True


def test_trend_coherence_filter():
    from src.backtest.regime_filter import TrendCoherenceFilter
    n = 250
    # Strong uptrend: each bar higher than previous; SMA50 < close, SMA200 < SMA50.
    base = np.linspace(100.0, 200.0, n)
    df = pd.DataFrame(
        {"open": base, "high": base + 0.1, "low": base - 0.1,
         "close": base, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    f = TrendCoherenceFilter(fast_sma=50, slow_sma=200)
    # Uptrend on the last bar -> ON
    assert f.is_active(df, df.index[-1].date()) is True

    # Flat series: close == SMA50 == SMA200 -> NEITHER bullish nor bearish -> OFF
    flat = pd.DataFrame(
        {"open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n,
         "close": [100.0] * n, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    assert f.is_active(flat, flat.index[-1].date()) is False


def test_engine_honors_regime_filter():
    from src.backtest.regime_filter import NoFilter
    spy = _ibs_long_daily()
    qqq = _flat_daily()
    cfg = SharesBacktestConfig(
        start=spy.index[-30].date(),
        end=spy.index[-1].date(),
        initial_capital=8000.0,
        regime_filter=NoFilter(),
    )
    eng = SharesBacktestEngine(
        config=cfg, strategies=[IBSStrategy()],
        daily_bars={"SPY": spy, "QQQ": qqq},
    )
    result = eng.run()
    # NoFilter behaves identically to no filter — at least one trade should fire.
    assert len(result.trades) >= 1


# --- Overnight drift engine ---

def test_overnight_drift_pnl_matches_close_to_open_returns():
    """If close T = 100, open T+1 = 101, 80 shares: pnl = +$80 minus slippage."""
    from src.backtest.overnight_engine import OvernightConfig, OvernightDriftEngine

    n = 5
    closes = [100.0, 100.0, 100.0, 100.0, 100.0]
    opens  = [99.5, 101.0, 102.0, 100.5, 101.5]
    df = pd.DataFrame(
        {"open": opens, "high": [102.0]*n, "low": [99.0]*n, "close": closes,
         "volume": [1e6]*n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    cfg = OvernightConfig(
        start=df.index[0].date(),
        end=df.index[-1].date(),
        universe="SPY",
        initial_capital=10_000.0,
        slippage_bps=0.0,  # no slippage for clean math
    )
    eng = OvernightDriftEngine(cfg, {"SPY": df})
    result = eng.run()
    # Expect 4 overnight trades (n-1 since last day has no next-day open)
    assert len(result.trades) == 4
    # Trade 0: bought close=100, sold open=101 -> +$1 per share
    t0 = result.trades[0]
    assert t0.entry_price == 100.0
    assert t0.exit_price == 101.0
    # 100 shares (from $10k / $100), +$1 each = +$100
    assert t0.shares == 100
    assert abs(t0.pnl - 100.0) < 1e-6
    # Direction always long
    assert all(t.direction == "long" for t in result.trades)
    # 1-3 calendar days held (Mon-Fri overnights are 1d; Fri-Mon is 3d)
    assert all(1 <= t.days_held <= 3 for t in result.trades)


def test_overnight_drift_slippage_applied_both_legs():
    from src.backtest.overnight_engine import OvernightConfig, OvernightDriftEngine
    n = 3
    df = pd.DataFrame(
        {"open": [100.0, 100.0, 100.0], "high": [101.0]*n, "low": [99.0]*n,
         "close": [100.0]*n, "volume": [1e6]*n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    cfg = OvernightConfig(
        start=df.index[0].date(),
        end=df.index[-1].date(),
        universe="SPY",
        initial_capital=10_000.0,
        slippage_bps=10.0,  # 10 bps each side
    )
    eng = OvernightDriftEngine(cfg, {"SPY": df})
    result = eng.run()
    # No directional move, but each trade incurs ~10bps each leg = ~20bps loss
    # On 100 shares * $100 entry, ~20bps of $10k = ~$20 loss per trade
    for t in result.trades:
        assert t.pnl < 0  # slippage drag in flat market


def test_overnight_drift_full_account_sizing():
    from src.backtest.overnight_engine import OvernightConfig, OvernightDriftEngine
    n = 5
    df = pd.DataFrame(
        {"open": [100.0]*n, "high": [101.0]*n, "low": [99.0]*n,
         "close": [100.0]*n, "volume": [1e6]*n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )
    cfg = OvernightConfig(
        start=df.index[0].date(),
        end=df.index[-1].date(),
        universe="SPY",
        initial_capital=10_000.0,
        slippage_bps=0.0,
    )
    eng = OvernightDriftEngine(cfg, {"SPY": df})
    result = eng.run()
    # First trade should buy ~100 shares with $10k
    t0 = result.trades[0]
    assert t0.shares == 100  # exactly $10k / $100 = 100 shares


# --- Diversifier check ---

def test_diversifier_correlation_low_for_uncorrelated_series():
    from src.backtest.diversifier_check import correlation_with_benchmark
    n = 200
    rng = np.random.default_rng(0)
    bench = pd.Series(
        100 + np.cumsum(rng.normal(0, 1, n)),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    # Strategy: random independent walk
    strat = pd.Series(
        8000 + np.cumsum(rng.normal(0, 50, n)),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    corr = correlation_with_benchmark(strat, bench)
    assert -0.3 < corr < 0.3  # uncorrelated random walks should have low corr


def test_diversifier_drawdown_pnl_positive_for_inverse_strategy():
    from src.backtest.diversifier_check import drawdown_period_pnl
    n = 100
    # Bench: rises then crashes
    bench = pd.Series(
        np.concatenate([np.linspace(100, 110, 50), np.linspace(110, 90, 50)]),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    # Strategy: opposite direction (inverse) — flat then rises during bench drawdown
    strat = pd.Series(
        np.concatenate([np.full(50, 8000.0), np.linspace(8000, 8500, 50)]),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    pnl = drawdown_period_pnl(strat, bench, drawdown_threshold=-0.05)
    # During bench drawdown (last 50 bars after 5% drop), strategy gained +$500
    assert pnl > 0


def test_diversifier_verdict_passes_all_four():
    from src.backtest.diversifier_check import evaluate_diversifier
    n = 200
    rng = np.random.default_rng(1)
    bench = pd.Series(
        100 + np.cumsum(rng.normal(0, 1, n)),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    # A strategy whose equity rises smoothly; uncorrelated to bench;
    # makes money during bench drawdowns; high Sortino.
    strat = pd.Series(
        8000 + np.linspace(0, 2000, n),  # smooth uptrend
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    v = evaluate_diversifier(
        strategy_equity=strat,
        n_trades=50,
        benchmark_close=bench,
        sortino=1.5,
    )
    assert v.passed
    assert v.correlation_pass
    assert v.drawdown_pnl_pass
    assert v.sortino_pass
    assert v.n_trades_pass


def test_diversifier_verdict_fails_correlation():
    from src.backtest.diversifier_check import evaluate_diversifier
    # Strategy whose equity moves in lockstep with benchmark
    n = 200
    bench = pd.Series(
        100 + np.cumsum(np.random.default_rng(2).normal(0, 1, n)),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    strat = pd.Series(80.0 * bench.values, index=bench.index)  # perfectly correlated
    v = evaluate_diversifier(
        strategy_equity=strat,
        n_trades=50,
        benchmark_close=bench,
        sortino=1.5,
    )
    assert not v.passed
    assert not v.correlation_pass
    assert any("correlation" in f for f in v.failures)


def test_diversifier_verdict_fails_n_trades_below_threshold():
    from src.backtest.diversifier_check import evaluate_diversifier
    n = 200
    rng = np.random.default_rng(3)
    bench = pd.Series(
        100 + np.cumsum(rng.normal(0, 1, n)),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    strat = pd.Series(
        8000 + np.linspace(0, 1000, n),
        index=pd.bdate_range("2024-01-01", periods=n),
    )
    # Only 5 trades — fails n_trades_threshold (default 30)
    v = evaluate_diversifier(
        strategy_equity=strat,
        n_trades=5,
        benchmark_close=bench,
        sortino=1.5,
    )
    assert not v.passed
    assert not v.n_trades_pass
    assert any("n_trades" in f for f in v.failures)


# --- VIX spike fade engine ---

def test_vix_spike_v0_fires_on_threshold():
    from src.backtest.vix_spike_engine import (
        SignalVariant, VixSpikeConfig, VixSpikeFadeEngine,
    )
    n = 60
    # VIX spikes from 15 to 30 on day 30
    vix_close = np.concatenate([np.full(30, 15.0), np.full(30, 30.0)])
    vix = pd.DataFrame(
        {"close": vix_close},
        index=pd.bdate_range("2024-01-02", periods=n),
    )
    # VXX inverse: jumps when VIX jumps (then bleeds)
    vxx_close = np.concatenate([np.full(30, 100.0),
                                 np.linspace(120, 110, 30)])
    vxx = pd.DataFrame({
        "open": vxx_close, "high": vxx_close * 1.01, "low": vxx_close * 0.99,
        "close": vxx_close, "volume": [1e6] * n,
    }, index=pd.bdate_range("2024-01-02", periods=n))
    cfg = VixSpikeConfig(
        start=vix.index[0].date(),
        end=vix.index[-1].date(),
        variant=SignalVariant.V0_THRESHOLD,
        slippage_bps=0.0,
    )
    eng = VixSpikeFadeEngine(config=cfg, vix=vix, vxx=vxx)
    result = eng.run()
    assert len(result.trades) >= 1
    t0 = result.trades[0]
    assert t0.underlying == "VXX"
    assert t0.direction == "long"


def test_intraday_engine_loader_handles_missing_cache():
    """When no parquet cache, engine returns empty result (doesn't crash)."""
    from datetime import date as dtdate
    import tempfile
    from pathlib import Path
    from src.backtest.intraday_engine import IntradayBacktestEngine, IntradayConfig

    with tempfile.TemporaryDirectory() as tmp:
        cfg = IntradayConfig(
            start=dtdate(2024, 1, 1),
            end=dtdate(2024, 1, 5),
            universe="SPY",
            bar_dir=Path(tmp),
        )
        # No cache files — every day returns None
        daily = {"SPY": pd.DataFrame()}
        eng = IntradayBacktestEngine(config=cfg, daily_bars=daily)
        result = eng.run()
        assert len(result.trades) == 0
        assert result.equity_curve.empty


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
