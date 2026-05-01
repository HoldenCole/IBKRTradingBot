"""Exit logic tests.

We construct synthetic market states and assert each branch fires under the
right conditions, and that priority order is respected.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from src.positions.exits import (
    ExitKind,
    ExitReason,
    MarketState,
    evaluate_exit,
    update_trail_level,
)
from src.positions.position import Position
from src.risk.blackout import (
    BlackoutChecker,
    EconomicEvent,
    EventKind,
    StubCalendar,
)
from src.strategies.base import SignalAction

ET = ZoneInfo("America/New_York")


def _daily_bars(n=250, base=400.0, drift=0.05, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = base + np.cumsum(rng.normal(drift, 0.5, n))
    df = pd.DataFrame({
        "open": closes,
        "high": closes + 1.0,
        "low": closes - 1.0,
        "close": closes,
        "volume": [1_000_000] * n,
    }, index=pd.bdate_range(end="2026-04-15", periods=n))
    return df


def _empty_blackout() -> BlackoutChecker:
    return BlackoutChecker(StubCalendar([]))


def _base_position(**kw) -> Position:
    defaults = dict(
        trade_id="t1",
        strategy_name="ewo",
        strategy_family="mean_reversion",
        underlying="SPY",
        option_etf="UPRO",
        option_contract_id="OPT1",
        direction=SignalAction.LONG,
        entry_time=datetime(2026, 4, 1, 9, 31, tzinfo=ET),
        entry_premium=4.00,
        entry_underlying=400.0,
        entry_atr20=2.0,
        expiry=date(2026, 4, 30),
        initial_contracts=4,
        contracts_remaining=4,
    )
    defaults.update(kw)
    return Position(**defaults)


def _base_market(daily=None, **kw) -> MarketState:
    daily = daily if daily is not None else _daily_bars()
    defaults = dict(
        now=datetime(2026, 4, 15, 12, 0, tzinfo=ET),
        today=date(2026, 4, 15),
        option_premium=4.00,
        underlying_price=400.0,
        daily_bars=daily,
        blackout=_empty_blackout(),
    )
    defaults.update(kw)
    return MarketState(**defaults)


# --- Universal exits ------------------------------------------------------

def test_premium_stop_fires_at_minus_50_pct_and_uses_stop_path():
    pos = _base_position()
    market = _base_market(option_premium=2.00)  # -50%
    a = evaluate_exit(pos, market)
    assert a.kind is ExitKind.CLOSE_ALL
    assert a.reason is ExitReason.PREMIUM_STOP
    assert a.use_stop_loss_path is True
    assert a.contracts_to_close == 4


def test_premium_stop_does_not_fire_at_minus_49_pct():
    pos = _base_position()
    market = _base_market(option_premium=2.05)  # -48.75%
    a = evaluate_exit(pos, market)
    assert a.kind is ExitKind.NONE


def test_dte_stop_fires_at_2_dte():
    pos = _base_position(expiry=date(2026, 4, 17))
    market = _base_market(today=date(2026, 4, 15))  # 2 DTE
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.DTE_STOP


def test_dte_stop_does_not_fire_at_3_dte():
    pos = _base_position(expiry=date(2026, 4, 18))
    market = _base_market(today=date(2026, 4, 15))  # 3 DTE
    # No other exit conditions met
    a = evaluate_exit(pos, market)
    assert a.kind is ExitKind.NONE


def test_blackout_flatten_15m_pre_release():
    cpi = EconomicEvent(EventKind.CPI, datetime(2026, 4, 15, 8, 30, tzinfo=ET))
    chk = BlackoutChecker(StubCalendar([cpi]), flatten_lead=timedelta(minutes=15))
    pos = _base_position()
    # 10 minutes before release
    market = _base_market(
        now=datetime(2026, 4, 15, 8, 20, tzinfo=ET), blackout=chk,
    )
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.BLACKOUT_FLATTEN


# --- Priority order ------------------------------------------------------

def test_priority_premium_stop_overrides_blackout():
    cpi = EconomicEvent(EventKind.CPI, datetime(2026, 4, 15, 8, 30, tzinfo=ET))
    chk = BlackoutChecker(StubCalendar([cpi]))
    pos = _base_position()
    market = _base_market(
        now=datetime(2026, 4, 15, 8, 20, tzinfo=ET),
        blackout=chk,
        option_premium=2.00,  # -50%
    )
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.PREMIUM_STOP


def test_priority_time_stop_before_signal_exit():
    # EWO time stop fires at 3 days held, before checking SMA5 signal.
    pos = _base_position(trading_days_held=3)
    # bars with close strongly above SMA5 (would trigger signal exit too)
    n = 250
    closes = np.concatenate([np.full(n - 1, 380.0), [430.0]])
    df = pd.DataFrame({
        "open": closes, "high": closes + 1, "low": closes - 1,
        "close": closes, "volume": [1e6] * n,
    }, index=pd.bdate_range(end="2026-04-15", periods=n))
    market = _base_market(daily=df)
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.TIME_STOP


# --- Per-strategy signal exits -------------------------------------------

def test_ewo_long_exits_when_close_above_sma5():
    n = 250
    # Last 10 days: stable around 380, then jumps to 430 on the last bar.
    closes = np.concatenate([np.full(n - 5, 380.0), [380.0, 380.0, 380.0, 380.0, 430.0]])
    df = pd.DataFrame({
        "open": closes, "high": closes + 1, "low": closes - 1,
        "close": closes, "volume": [1e6] * n,
    }, index=pd.bdate_range(end="2026-04-15", periods=n))
    pos = _base_position()
    market = _base_market(daily=df)
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.SIGNAL_EXIT
    assert "SMA5" in a.detail


def test_ewo_short_exits_when_close_below_sma5():
    # SHORT_FADE long SQQQ calls; signal exit when underlying close < SMA5.
    n = 250
    closes = np.concatenate([np.full(n - 5, 420.0), [420.0, 420.0, 420.0, 420.0, 380.0]])
    df = pd.DataFrame({
        "open": closes, "high": closes + 1, "low": closes - 1,
        "close": closes, "volume": [1e6] * n,
    }, index=pd.bdate_range(end="2026-04-15", periods=n))
    pos = _base_position(direction=SignalAction.SHORT_FADE, option_etf="SQQQ")
    market = _base_market(daily=df)
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.SIGNAL_EXIT


def test_ibs_long_exits_when_close_above_prior_high():
    n = 250
    closes = np.full(n, 400.0)
    highs = closes + 1.0
    closes[-1] = highs[-2] + 0.5  # close above prior high
    highs[-1] = closes[-1] + 0.1
    lows = closes - 1.0
    df = pd.DataFrame({
        "open": closes, "high": highs, "low": lows,
        "close": closes, "volume": [1e6] * n,
    }, index=pd.bdate_range(end="2026-04-15", periods=n))
    pos = _base_position(strategy_name="ibs")
    market = _base_market(daily=df)
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.SIGNAL_EXIT
    assert "prior high" in a.detail


def test_ibs_long_exits_on_high_ibs():
    n = 250
    closes = np.full(n, 400.0)
    highs = closes + 1.0
    lows = closes - 1.0
    # Last bar: close near high -> IBS ~ 1.0
    highs[-1] = 401.0
    lows[-1] = 399.0
    closes[-1] = 400.95
    # But ensure NOT above prior high so we hit the IBS branch.
    highs[-2] = 401.5
    df = pd.DataFrame({
        "open": closes, "high": highs, "low": lows,
        "close": closes, "volume": [1e6] * n,
    }, index=pd.bdate_range(end="2026-04-15", periods=n))
    pos = _base_position(strategy_name="ibs")
    market = _base_market(daily=df)
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.SIGNAL_EXIT
    assert "IBS" in a.detail


# --- Afternoon Reversion exits -------------------------------------------

def _afternoon_session(bars: int = 10) -> pd.DataFrame:
    times = [datetime(2026, 4, 15, 11, 35, tzinfo=ET) + timedelta(minutes=5 * i)
             for i in range(bars)]
    closes = np.full(bars, 400.0)
    df = pd.DataFrame({
        "open": closes, "high": closes + 0.1, "low": closes - 0.1,
        "close": closes, "volume": [100_000] * bars,
    }, index=pd.DatetimeIndex(times, name="ts"))
    return df


def test_afternoon_hard_stop_below_half_morning_range():
    pos = _base_position(
        strategy_name="afternoon_reversion",
        strategy_family="afternoon",
        morning_low=395.0,
        morning_high=405.0,  # range = 10
    )
    market = _base_market(
        underlying_price=394.0,  # entry was 400, hard stop at 400 - 5 = 395
        intraday_session=_afternoon_session(),
    )
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.AFTERNOON_HARD_STOP
    assert a.use_stop_loss_path is True


def test_afternoon_vwap_reclaim_scales_50_pct():
    # Build a session where VWAP is below current underlying -> reclaim for long.
    times = [datetime(2026, 4, 15, 11, 35, tzinfo=ET) + timedelta(minutes=5 * i)
             for i in range(6)]
    closes = np.array([398.0, 397.5, 397.8, 398.2, 398.8, 399.0])
    df = pd.DataFrame({
        "open": closes, "high": closes + 0.1, "low": closes - 0.1,
        "close": closes, "volume": [100_000] * len(closes),
    }, index=pd.DatetimeIndex(times, name="ts"))
    pos = _base_position(
        strategy_name="afternoon_reversion",
        strategy_family="afternoon",
        morning_low=396.0, morning_high=400.0,
        contracts_remaining=4, initial_contracts=4,
    )
    market = _base_market(
        underlying_price=399.0,  # > VWAP of session
        intraday_session=df,
    )
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.AFTERNOON_VWAP_RECLAIM
    assert a.kind is ExitKind.SCALE_OUT
    assert a.contracts_to_close == 2  # 50% of 4


# --- Scale-outs and trail -----------------------------------------------

def test_scale_out_50_pct_at_premium_plus_50():
    pos = _base_position(initial_contracts=4, contracts_remaining=4)
    market = _base_market(option_premium=6.00)  # +50% from $4
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.SCALE_OUT_50
    assert a.contracts_to_close == 2


def test_scale_out_100_pct_after_50_pct_done():
    pos = _base_position(
        initial_contracts=4, contracts_remaining=2, scaled_50pct=True,
    )
    market = _base_market(option_premium=8.00)  # +100% from $4
    a = evaluate_exit(pos, market)
    assert a.reason is ExitReason.SCALE_OUT_100
    assert a.contracts_to_close == 1  # 25% of 4


def test_trail_activates_only_after_100_pct_scale():
    pos = _base_position(
        initial_contracts=4, contracts_remaining=1,
        scaled_50pct=True, scaled_100pct=False,  # not yet scaled to 100%
    )
    market = _base_market(underlying_price=405.0)
    update_trail_level(pos, market)
    assert pos.trail_level is None
    assert not pos.trail_active


def test_trail_ratchets_and_fires():
    pos = _base_position(
        initial_contracts=4, contracts_remaining=1,
        scaled_50pct=True, scaled_100pct=True,
        entry_atr20=2.0,
    )

    # Tick 1: underlying 410 -> trail = 410 - 1.5*2 = 407
    m1 = _base_market(underlying_price=410.0)
    update_trail_level(pos, m1)
    assert pos.trail_level == pytest.approx(407.0)

    # Tick 2: underlying 415 -> ratchets up to 412
    m2 = _base_market(underlying_price=415.0)
    update_trail_level(pos, m2)
    assert pos.trail_level == pytest.approx(412.0)

    # Tick 3: underlying drops back to 414. Trail level should NOT loosen.
    m3 = _base_market(underlying_price=414.0)
    update_trail_level(pos, m3)
    assert pos.trail_level == pytest.approx(412.0)

    # Tick 4: underlying drops to 411 (below trail) -> CLOSE_ALL
    m4 = _base_market(underlying_price=411.0)
    a = evaluate_exit(pos, m4)
    assert a.reason is ExitReason.TRAIL_STOP
    assert a.kind is ExitKind.CLOSE_ALL


def test_trail_short_inverted():
    pos = _base_position(
        direction=SignalAction.SHORT_FADE,
        option_etf="SQQQ",
        initial_contracts=4, contracts_remaining=1,
        scaled_50pct=True, scaled_100pct=True,
        entry_atr20=2.0,
        entry_underlying=400.0,
    )
    # Daily bars where close is firmly above SMA5 so the EWO short signal exit
    # ("close < SMA5") does NOT fire, isolating the trail-stop branch.
    n = 250
    closes = np.concatenate([np.full(n - 1, 420.0), [430.0]])
    df = pd.DataFrame({
        "open": closes, "high": closes + 1, "low": closes - 1,
        "close": closes, "volume": [1e6] * n,
    }, index=pd.bdate_range(end="2026-04-15", periods=n))

    # Underlying drops to 390 -> trail = 390 + 1.5*2 = 393
    m1 = _base_market(daily=df, underlying_price=390.0)
    update_trail_level(pos, m1)
    assert pos.trail_level == pytest.approx(393.0)

    # Underlying rallies back to 394 -> above trail -> CLOSE_ALL (short side)
    m2 = _base_market(daily=df, underlying_price=394.0)
    a = evaluate_exit(pos, m2)
    assert a.reason is ExitReason.TRAIL_STOP


def test_no_exit_when_quiet():
    pos = _base_position()
    market = _base_market(option_premium=4.10, underlying_price=400.5)
    a = evaluate_exit(pos, market)
    assert a.kind is ExitKind.NONE
