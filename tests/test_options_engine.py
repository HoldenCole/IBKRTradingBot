"""Options engine: Black-Scholes sanity and end-to-end on synthetic data."""

from src.backtest.options_engine import (
    OptionsBacktestConfig,
    bs_price,
    run_options_backtest,
)
from src.strategies.cl1_uso_spread import SpreadParams
from tests.test_backtest import synthetic_frames

PARAMS = SpreadParams(min_history=200, beta_lookback=800, z_lookback=200)


def test_bs_price_sanity():
    # ATM call, 7 DTE, 30% vol on a $75 underlying: small positive premium.
    price = bs_price(75.0, 75.0, 7 / 365, 0.30, 0.04, is_call=True)
    assert 0.3 < price < 3.0
    # Put-call parity at the same strike.
    put = bs_price(75.0, 75.0, 7 / 365, 0.30, 0.04, is_call=False)
    assert abs(price - put) < 0.10  # small rate carry only
    # Deep ITM call ~ intrinsic.
    itm = bs_price(75.0, 50.0, 7 / 365, 0.30, 0.04, is_call=True)
    assert abs(itm - 25.0) < 0.5
    # Expiry: pure intrinsic.
    assert bs_price(75.0, 70.0, 0.0, 0.30, 0.04, True) == 5.0


def test_options_backtest_runs_and_flattens():
    cl, uso = synthetic_frames(days=10, lag_minutes=15)
    result = run_options_backtest(cl, uso, OptionsBacktestConfig(params=PARAMS))
    assert result.metrics["n_trades"] > 0
    trades = result.trades
    # Same-day exits only — options never held overnight either.
    assert (trades["exit_ts"].dt.date == trades["entry_ts"].dt.date).all()
    # Both directions expressed as long premium.
    assert set(trades["type"]).issubset({"call", "put"})


def test_options_position_budget_respected():
    cl, uso = synthetic_frames(days=10, lag_minutes=15)
    config = OptionsBacktestConfig(params=PARAMS, position_usd=1000)
    result = run_options_backtest(cl, uso, config)
    trades = result.trades
    deployed = trades["entry_premium"] * 100 * trades["contracts"]
    assert (deployed <= 1000 + 1e-6).all()
