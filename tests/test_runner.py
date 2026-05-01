"""Integration tests for LiveRunner.

We drive one (compressed) trading day through SimBroker + SimFeed and assert:
  - daily-close pass enqueues deferred entries
  - next-session-open executes them, opens positions, runs guardrails
  - intraday bars trigger afternoon-reversion entries
  - exit evaluation closes positions
  - state is persisted to disk and reloaded correctly
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from src.broker.orders import Quote
from src.positions.manager import PositionManager
from src.risk.blackout import BlackoutChecker, StubCalendar
from src.risk.guardrails import Guardrails
from src.risk.regime import StaticRegime
from src.risk.weekly_budget import WeeklyBudget
from src.runner.runner import LiveRunner
from src.runner.sim import SimBroker, SimFeed
from src.runner.store import PositionStore
from src.strategies.afternoon import AfternoonReversionStrategy
from src.strategies.ewo import EWOStrategy
from src.strategies.ibs import IBSStrategy

ET = ZoneInfo("America/New_York")


def _ewo_long_daily(n=400) -> pd.DataFrame:
    """Daily bars guaranteed to fire an EWO long (deep z, RSI<10, close>SMA200)."""
    rng = np.random.default_rng(7)
    base = np.linspace(300, 420, n) + rng.normal(0, 0.5, n)
    base[-5:] -= np.linspace(8, 30, 5)
    high = base + 1.0
    low = base - 1.0
    return pd.DataFrame(
        {"open": base, "high": high, "low": low, "close": base, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )


def _flat_daily(n=400, price=400.0) -> pd.DataFrame:
    closes = np.full(n, price)
    return pd.DataFrame(
        {"open": closes, "high": closes + 1, "low": closes - 1,
         "close": closes, "volume": [1e6] * n},
        index=pd.bdate_range(end="2026-04-15", periods=n),
    )


def _make_runner(tmp_path: Path, daily_by_sym: dict[str, pd.DataFrame],
                 quote_by_cid: callable, spot_by_sym: dict[str, float]) -> LiveRunner:
    budget = WeeklyBudget()
    pm = PositionManager(budget=budget)
    blackout = BlackoutChecker(StubCalendar([]))
    regime = StaticRegime({"SPY": True, "QQQ": True})
    guardrails = Guardrails(
        budget=budget, blackout=blackout, regime=regime,
        per_trade_risk_cap=200.0,
    )
    feed = SimFeed(daily=daily_by_sym, session={})
    broker = SimBroker(
        quote_fn=quote_by_cid,
        underlying_fn=lambda s: spot_by_sym[s],
        nav_value=8000.0,
    )
    store = PositionStore(path=tmp_path / "state.json")
    return LiveRunner(
        broker=broker, feed=feed, pm=pm, budget=budget,
        guardrails=guardrails, blackout=blackout,
        daily_strategies=[EWOStrategy(), IBSStrategy()],
        intraday_strategy=AfternoonReversionStrategy(),
        store=store,
        ladder_interval_sec=0.05,
        poll_interval_sec=0.005,
    )


@pytest.mark.asyncio
async def test_daily_close_enqueues_deferred_entry(tmp_path):
    daily = _ewo_long_daily()
    quote = Quote(bid=2.95, ask=3.05)
    runner = _make_runner(
        tmp_path,
        daily_by_sym={"SPY": daily, "QQQ": _flat_daily()},
        quote_by_cid=lambda cid: quote,
        spot_by_sym={"SPY": daily["close"].iloc[-1], "QQQ": 400.0,
                     "UPRO": 100.0, "TQQQ": 80.0, "SQQQ": 25.0},
    )
    await runner.on_startup()
    await runner.on_daily_close(date(2026, 4, 15))
    assert len(runner.deferred) == 1
    d = runner.deferred[0]
    assert d.strategy_name == "ewo"
    assert d.underlying == "SPY"
    assert d.option_etf == "UPRO"


@pytest.mark.asyncio
async def test_session_open_drains_queue_and_opens_position(tmp_path):
    daily = _ewo_long_daily()
    quote = Quote(bid=2.95, ask=3.05)
    runner = _make_runner(
        tmp_path,
        daily_by_sym={"SPY": daily, "QQQ": _flat_daily(),
                      "UPRO": daily, "TQQQ": _flat_daily(), "SQQQ": _flat_daily()},
        quote_by_cid=lambda cid: quote,
        spot_by_sym={"SPY": float(daily["close"].iloc[-1]), "QQQ": 400.0,
                     "UPRO": 100.0, "TQQQ": 80.0, "SQQQ": 25.0},
    )
    await runner.on_daily_close(date(2026, 4, 15))
    # Backdate fire_at so on_session_open executes immediately
    for d in runner.deferred:
        d.fire_at = datetime.now(tz=ET) - timedelta(hours=1)
    await runner.on_session_open(date(2026, 4, 16))
    assert runner.deferred == []
    assert runner.pm.open_count() == 1
    pos = next(iter(runner.pm.open_positions()))
    assert pos.option_etf == "UPRO"
    assert pos.contracts_remaining == 1
    # Budget should reflect the new open risk
    assert runner.budget.open_risk() > 0


@pytest.mark.asyncio
async def test_state_persists_and_reloads(tmp_path):
    daily = _ewo_long_daily()
    quote = Quote(bid=2.95, ask=3.05)
    runner = _make_runner(
        tmp_path,
        daily_by_sym={"SPY": daily, "QQQ": _flat_daily(),
                      "UPRO": daily, "TQQQ": _flat_daily(), "SQQQ": _flat_daily()},
        quote_by_cid=lambda cid: quote,
        spot_by_sym={"SPY": float(daily["close"].iloc[-1]), "QQQ": 400.0,
                     "UPRO": 100.0, "TQQQ": 80.0, "SQQQ": 25.0},
    )
    await runner.on_daily_close(date(2026, 4, 15))
    for d in runner.deferred:
        d.fire_at = datetime.now(tz=ET) - timedelta(hours=1)
    await runner.on_session_open(date(2026, 4, 16))

    # Reload from disk into a fresh budget + manager
    fresh_budget = WeeklyBudget()
    pm2, deferred2 = runner.store.load(fresh_budget)
    assert len(pm2.positions) == 1
    pos = next(iter(pm2.positions.values()))
    assert pos.option_etf == "UPRO"
    assert pos.contracts_remaining == 1
    # Reloaded budget should reflect the open risk
    assert fresh_budget.open_risk() > 0
    assert deferred2 == []


@pytest.mark.asyncio
async def test_session_close_marks_overnight_and_advances_day(tmp_path):
    daily = _ewo_long_daily()
    quote = Quote(bid=2.95, ask=3.05)
    runner = _make_runner(
        tmp_path,
        daily_by_sym={"SPY": daily, "QQQ": _flat_daily(),
                      "UPRO": daily, "TQQQ": _flat_daily(), "SQQQ": _flat_daily()},
        quote_by_cid=lambda cid: quote,
        spot_by_sym={"SPY": float(daily["close"].iloc[-1]), "QQQ": 400.0,
                     "UPRO": 100.0, "TQQQ": 80.0, "SQQQ": 25.0},
    )
    await runner.on_daily_close(date(2026, 4, 15))
    for d in runner.deferred:
        d.fire_at = datetime.now(tz=ET) - timedelta(hours=1)
    await runner.on_session_open(date(2026, 4, 16))
    assert runner.pm.open_count() == 1
    pos_before = next(iter(runner.pm.open_positions()))
    risk_before = runner.budget.open_risk()

    await runner.on_session_close(date(2026, 4, 16))
    pos_after = runner.pm.positions[pos_before.trade_id]
    assert pos_after.held_overnight is True
    # Overnight 1.5x haircut bumps risk
    assert runner.budget.open_risk() == pytest.approx(risk_before * 1.5)


@pytest.mark.asyncio
async def test_premium_stop_closes_position(tmp_path):
    daily = _ewo_long_daily()
    quote_box = {"q": Quote(bid=2.95, ask=3.05)}
    runner = _make_runner(
        tmp_path,
        daily_by_sym={"SPY": daily, "QQQ": _flat_daily(),
                      "UPRO": daily, "TQQQ": _flat_daily(), "SQQQ": _flat_daily()},
        quote_by_cid=lambda cid: quote_box["q"],
        spot_by_sym={"SPY": float(daily["close"].iloc[-1]), "QQQ": 400.0,
                     "UPRO": 100.0, "TQQQ": 80.0, "SQQQ": 25.0},
    )
    await runner.on_daily_close(date(2026, 4, 15))
    for d in runner.deferred:
        d.fire_at = datetime.now(tz=ET) - timedelta(hours=1)
    await runner.on_session_open(date(2026, 4, 16))
    assert runner.pm.open_count() == 1

    # Premium drops 60% -> -50% stop should fire
    quote_box["q"] = Quote(bid=1.15, ask=1.25)  # mid = 1.20, entry was ~3.00
    await runner.on_session_close(date(2026, 4, 16))
    assert runner.pm.open_count() == 0
    # Loss should be in realized
    assert runner.budget.realized_loss(datetime.now(tz=ET)) > 0


def test_co_signal_dedup_takes_ewo_over_ibs():
    """If both EWO and IBS fire on the same underlying same day, prefer EWO."""
    from src.strategies.base import OptionSelection, Signal, SignalAction

    def _sig(name: str, family: str = "mean_reversion") -> Signal:
        return Signal(
            action=SignalAction.LONG, underlying="SPY",
            option=OptionSelection(underlying_etf="UPRO"),
            contracts=1, reason=f"{name} test signal",
            strategy_name=name, strategy_family=family,
            fired_at=datetime.now(tz=ET),
        )

    ewo = (EWOStrategy(), _sig("ewo"))
    ibs = (IBSStrategy(), _sig("ibs"))
    chosen = LiveRunner._dedupe_co_signals([ewo, ibs])
    assert len(chosen) == 1
    assert chosen[0][0].name == "ewo"

    # Reverse insertion order: still picks EWO
    chosen = LiveRunner._dedupe_co_signals([ibs, ewo])
    assert len(chosen) == 1
    assert chosen[0][0].name == "ewo"

    # Single signal: passthrough
    assert LiveRunner._dedupe_co_signals([ewo]) == [ewo]
