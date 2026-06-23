"""Tests for the daily-check orchestrator. Uses a SimProvider — no
network, no I/O, fully deterministic. Verifies the locked invariants:

  - On a normal day with no state change, no flip events are emitted
  - On a transition day, a flip event is emitted with the right direction
  - Re-running the same date is idempotent (state file unchanged; no
    new flip events) — locks in our no-duplicate-orders guarantee
  - State changes are persisted only when persist=True
  - Warmup periods do not emit flip events
  - A data-fetch failure for one strategy doesn't break the others
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.deploy.baskets import BasketConfig
from src.deploy.daily_check import run_daily_check
from src.deploy.signal_state import SignalState
from src.deploy.store import StateStore


@dataclass
class SimProvider:
    """In-memory close-series provider for tests. Just hold a dict of
    {asset: pd.Series}; closes() slices to the requested as_of."""
    data: dict[str, pd.Series] = field(default_factory=dict)
    failures: set[str] = field(default_factory=set)  # assets that should raise

    def closes(self, asset: str, as_of: date, lookback_days: int) -> pd.Series:
        if asset in self.failures:
            raise RuntimeError(f"simulated fetch failure for {asset}")
        s = self.data.get(asset, pd.Series(dtype=float))
        return s.loc[:pd.Timestamp(as_of)]


def _uptrend(n: int = 300, start_date: date = date(2024, 1, 2)) -> pd.Series:
    idx = pd.date_range(start=start_date, periods=n, freq="B")
    return pd.Series(np.linspace(100.0, 200.0, n), index=idx)


def _downtrend(n: int = 300, start_date: date = date(2024, 1, 2)) -> pd.Series:
    idx = pd.date_range(start=start_date, periods=n, freq="B")
    return pd.Series(np.linspace(200.0, 100.0, n), index=idx)


def _falling_after_rise(n: int = 350, start_date: date = date(2024, 1, 2)
                        ) -> pd.Series:
    """250 rising bars then 100 falling — engineered to flip OFF near the end."""
    idx = pd.date_range(start=start_date, periods=n, freq="B")
    rising = list(np.linspace(100.0, 200.0, 250))
    falling = list(np.linspace(200.0, 130.0, n - 250))
    return pd.Series(rising + falling, index=idx)


def test_stage1_first_run_no_flips_just_warmup_completion(tmp_path: Path):
    cfg = BasketConfig.load()
    store = StateStore(tmp_path / "state.json")
    qqq = _uptrend()
    btc = _uptrend()
    provider = SimProvider({"QQQ": qqq, "BTC": btc})
    target = qqq.index[-1].date()

    res = run_daily_check(cfg, store, provider, trading_date=target)
    # Two enabled strategies in Stage 1 config
    assert set(res.snapshots) == {"qqq_trend_50_200", "btc_trend_50_200"}
    # First run: prev is None, so no FLIP events (UNKNOWN->ON is not actionable)
    assert not res.has_actionable_changes()
    # Both should be ON given the uptrend
    assert res.snapshots["qqq_trend_50_200"].state == SignalState.ON
    assert res.snapshots["btc_trend_50_200"].state == SignalState.ON
    # And persisted
    assert store.last_check_trading_date == target


def test_transition_day_emits_flip_event(tmp_path: Path):
    cfg = BasketConfig.load()
    store = StateStore(tmp_path / "state.json")
    series = _falling_after_rise()
    provider = SimProvider({"QQQ": series, "BTC": series})

    # Step 1: run on a date deep in the uptrend, where signal is ON.
    # Rising portion is bars 0..249; falling starts at 250.
    on_date = series.index[245].date()
    res1 = run_daily_check(cfg, store, provider, trading_date=on_date)
    assert res1.snapshots["qqq_trend_50_200"].state == SignalState.ON

    # Step 2: run on the last date, by which point the signal has flipped OFF
    off_date = series.index[-1].date()
    res2 = run_daily_check(cfg, store, provider, trading_date=off_date)
    assert res2.snapshots["qqq_trend_50_200"].state == SignalState.OFF
    flips = [c for c in res2.changes if c.is_flip]
    assert len(flips) == 2  # both QQQ and BTC sleeves flipped
    for ch in flips:
        assert ch.prev_state == SignalState.ON
        assert ch.new_state == SignalState.OFF
        assert ch.direction == "exit"


def test_idempotent_rerun_same_date(tmp_path: Path):
    """LOCKED INVARIANT: running the job twice on the same trading date
    produces the same persisted state and emits NO new flip events on the
    second run (since prev now equals curr)."""
    cfg = BasketConfig.load()
    store = StateStore(tmp_path / "state.json")
    series = _uptrend()
    provider = SimProvider({"QQQ": series, "BTC": series})
    target = series.index[-1].date()

    res1 = run_daily_check(cfg, store, provider, trading_date=target)
    file_after_first = (tmp_path / "state.json").read_text()

    res2 = run_daily_check(cfg, store, provider, trading_date=target)
    file_after_second = (tmp_path / "state.json").read_text()

    # State is identical between runs (apart from run_at_utc timestamp,
    # which is part of the in-memory result, not the persisted snapshots)
    # Persisted snapshots block should be identical:
    import json
    p1 = json.loads(file_after_first); p2 = json.loads(file_after_second)
    assert p1["snapshots"] == p2["snapshots"]

    # And the second run emits no flip events
    assert not res2.has_actionable_changes()


def test_persist_false_does_not_write(tmp_path: Path):
    cfg = BasketConfig.load()
    p = tmp_path / "state.json"
    store = StateStore(p)
    series = _uptrend()
    provider = SimProvider({"QQQ": series, "BTC": series})
    target = series.index[-1].date()

    run_daily_check(cfg, store, provider, trading_date=target, persist=False)
    assert not p.exists()


def test_warmup_does_not_emit_flips(tmp_path: Path):
    cfg = BasketConfig.load()
    store = StateStore(tmp_path / "state.json")
    # Only 150 bars; SMA200 not yet computable
    short = _uptrend(n=150)
    provider = SimProvider({"QQQ": short, "BTC": short})
    target = short.index[-1].date()
    res = run_daily_check(cfg, store, provider, trading_date=target)
    assert res.snapshots["qqq_trend_50_200"].state == SignalState.UNKNOWN
    assert res.snapshots["btc_trend_50_200"].state == SignalState.UNKNOWN
    assert not res.has_actionable_changes()
    assert any("warmup" in w for w in res.warnings)


def test_fetch_failure_one_strategy_doesnt_break_other(tmp_path: Path):
    cfg = BasketConfig.load()
    store = StateStore(tmp_path / "state.json")
    series = _uptrend()
    provider = SimProvider({"QQQ": series, "BTC": series}, failures={"BTC"})
    target = series.index[-1].date()
    res = run_daily_check(cfg, store, provider, trading_date=target)
    # QQQ still computed
    assert "qqq_trend_50_200" in res.snapshots
    # BTC failed - no snapshot, but recorded as warning
    assert "btc_trend_50_200" not in res.snapshots
    assert any("BTC" in w and "fetch" in w for w in res.warnings)
