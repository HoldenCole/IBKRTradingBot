"""Atomic JSON persistence for deployment state.

Reuses the write-temp-then-rename pattern from src/runner/store.py — that
pattern is correct and battle-tested — but with a new schema that fits the
Stage-1 deployment (signal-state snapshots per strategy, plus a header).

The state file is a single JSON object with versioning so future schema
migrations are clean. Atomic save means a crash mid-write cannot leave a
half-written or corrupt state file: we write to a sibling `.tmp` and
rename it on top of the live file.

Schema v1:
{
  "schema_version": 1,
  "last_check_utc": "2026-06-22T20:01:00Z",
  "last_check_trading_date": "2026-06-20",
  "snapshots": {
    "qqq_trend_50_200": {
      "strategy_id": "qqq_trend_50_200",
      "as_of": "2026-06-20",
      "state": "ON",
      "close": 540.00,
      "sma50": 525.00,
      "sma200": 510.00,
      "governs_returns_from_next_session": true
    },
    "btc_trend_50_200": { ... }
  }
}
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from src.deploy.signal_state import SignalSnapshot, SignalState

_SCHEMA_VERSION = 1


def _snap_to_dict(s: SignalSnapshot) -> dict:
    return {
        "strategy_id": s.strategy_id,
        "as_of": s.as_of.isoformat(),
        "state": s.state.value,
        "close": s.close,
        "sma50": s.sma50,
        "sma200": s.sma200,
        "governs_returns_from_next_session": s.governs_returns_from_next_session,
    }


def _dict_to_snap(d: dict) -> SignalSnapshot:
    return SignalSnapshot(
        strategy_id=d["strategy_id"],
        as_of=date.fromisoformat(d["as_of"]),
        state=SignalState(d["state"]),
        close=float(d["close"]),
        sma50=d.get("sma50"),
        sma200=d.get("sma200"),
        governs_returns_from_next_session=d.get("governs_returns_from_next_session", True),
    )


class StateStore:
    """Persisted strategy-state, atomically written."""

    def __init__(self, path: Path):
        self.path = path
        self._snapshots: dict[str, SignalSnapshot] = {}
        self._last_check_utc: datetime | None = None
        self._last_check_trading_date: date | None = None

    # ----- I/O -----
    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text())
        if raw.get("schema_version") != _SCHEMA_VERSION:
            raise RuntimeError(
                f"State file schema v{raw.get('schema_version')} != "
                f"expected v{_SCHEMA_VERSION}: {self.path}. "
                "Migration not implemented.")
        if raw.get("last_check_utc"):
            self._last_check_utc = datetime.fromisoformat(raw["last_check_utc"])
        if raw.get("last_check_trading_date"):
            self._last_check_trading_date = date.fromisoformat(raw["last_check_trading_date"])
        self._snapshots = {sid: _dict_to_snap(d)
                           for sid, d in raw.get("snapshots", {}).items()}

    def save(self) -> None:
        """Atomic write: temp file then rename. A crash before the rename
        leaves the previous state intact; a crash after the rename has the
        new state. There is no in-between."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "last_check_utc": (
                self._last_check_utc.isoformat() if self._last_check_utc else None),
            "last_check_trading_date": (
                self._last_check_trading_date.isoformat()
                if self._last_check_trading_date else None),
            "snapshots": {sid: _snap_to_dict(s) for sid, s in self._snapshots.items()},
        }
        # Write to temp in the same directory (cross-device rename would fail)
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # ----- accessors -----
    def get(self, strategy_id: str) -> SignalSnapshot | None:
        return self._snapshots.get(strategy_id)

    def put(self, snapshot: SignalSnapshot) -> None:
        self._snapshots[snapshot.strategy_id] = snapshot

    def mark_check(self, when_utc: datetime, trading_date: date) -> None:
        self._last_check_utc = when_utc
        self._last_check_trading_date = trading_date

    @property
    def last_check_utc(self) -> datetime | None:
        return self._last_check_utc

    @property
    def last_check_trading_date(self) -> date | None:
        return self._last_check_trading_date

    def all_snapshots(self) -> dict[str, SignalSnapshot]:
        return dict(self._snapshots)
