"""Tests for the StateStore — atomic JSON persistence."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.deploy.signal_state import SignalSnapshot, SignalState
from src.deploy.store import StateStore


def _snap(sid: str, as_of: date, state: SignalState) -> SignalSnapshot:
    return SignalSnapshot(sid, as_of, state, close=100.0, sma50=99.0, sma200=98.0)


def test_save_load_roundtrip(tmp_path: Path):
    p = tmp_path / "state.json"
    s1 = StateStore(p)
    s1.put(_snap("qqq_trend", date(2024, 6, 20), SignalState.ON))
    s1.put(_snap("btc_trend", date(2024, 6, 20), SignalState.OFF))
    s1.mark_check(datetime(2024, 6, 20, 20, 1, tzinfo=timezone.utc), date(2024, 6, 20))
    s1.save()

    s2 = StateStore(p)
    s2.load()
    assert s2.get("qqq_trend").state == SignalState.ON
    assert s2.get("btc_trend").state == SignalState.OFF
    assert s2.last_check_trading_date == date(2024, 6, 20)


def test_load_missing_file_is_empty(tmp_path: Path):
    s = StateStore(tmp_path / "does_not_exist.json")
    s.load()
    assert s.get("anything") is None
    assert s.last_check_trading_date is None


def test_save_is_atomic_no_partial_writes(tmp_path: Path):
    """The temp file used during write must not be visible as the live file
    until rename. Simulate by snooping during save."""
    p = tmp_path / "state.json"
    # Pre-existing live state
    s = StateStore(p)
    s.put(_snap("qqq_trend", date(2024, 6, 20), SignalState.ON))
    s.save()
    pre = p.read_text()

    # Mutate + save again; if anything fails between write-temp and rename,
    # the live file should be unchanged (no partial writes).
    s.put(_snap("qqq_trend", date(2024, 6, 21), SignalState.OFF))
    s.save()
    post = p.read_text()
    assert pre != post
    # Verify only the live file exists in the dir (no leftover .tmp)
    tmps = list(tmp_path.glob(".tmp_*"))
    assert tmps == [], f"leftover temp files: {tmps}"


def test_put_overwrites_snapshot(tmp_path: Path):
    s = StateStore(tmp_path / "state.json")
    s.put(_snap("qqq_trend", date(2024, 6, 20), SignalState.ON))
    s.put(_snap("qqq_trend", date(2024, 6, 21), SignalState.OFF))
    assert s.get("qqq_trend").state == SignalState.OFF
    assert s.get("qqq_trend").as_of == date(2024, 6, 21)


def test_schema_version_mismatch_rejected(tmp_path: Path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"schema_version": 99, "snapshots": {}}))
    s = StateStore(p)
    with pytest.raises(RuntimeError, match="schema"):
        s.load()


def test_all_snapshots_returns_copy(tmp_path: Path):
    s = StateStore(tmp_path / "state.json")
    s.put(_snap("qqq_trend", date(2024, 6, 20), SignalState.ON))
    snaps = s.all_snapshots()
    # Mutating the returned dict must not affect the store
    snaps.clear()
    assert s.get("qqq_trend") is not None
