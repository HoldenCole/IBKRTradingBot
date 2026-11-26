"""Trial log and hold-out lock.

trials.csv       one row per (trial, pair, sample, stress) ever evaluated: the
                 multiple-testing denominator. Append-only.
holdout_log.csv  one row per rule whose hold-out was opened. A rule appears at
                 most once; data.load() accepts only tokens recorded here.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRIALS = HERE / "trials.csv"
HOLDOUT = HERE / "holdout_log.csv"


def _append(path: Path, row: dict) -> None:
    new = not path.exists()
    if not new:
        with path.open() as fh:
            header = next(csv.reader(fh), [])
        if header and header != list(row):
            raise ValueError(f"{path.name}: column mismatch {header} vs {list(row)}")
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def log_trial(row: dict) -> None:
    _append(TRIALS, {"logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row})


def opened() -> dict[str, dict]:
    if not HOLDOUT.exists():
        return {}
    with HOLDOUT.open() as fh:
        return {r["rule"]: r for r in csv.DictReader(fh)}


def open_holdout(rule: str, pair: str, gates: str, log_path: Path | None = None) -> str:
    """Issue the one-time token for a rule that passed every development gate."""
    path = log_path or HOLDOUT
    done = opened() if path == HOLDOUT else {}
    key = f"{rule}@{pair}"
    if key in done:
        raise PermissionError(f"hold-out for {key} was already opened on {done[key]['opened_at']}; it cannot be reopened")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    token = hashlib.sha256(f"{key}|{ts}".encode()).hexdigest()[:16]
    _append(path, {"rule": key, "opened_at": ts, "gates": gates, "token": token})
    return token


def check_token(token: str) -> None:
    if token not in {r["token"] for r in opened().values()}:
        raise PermissionError("unknown hold-out token")
