"""Daily close-check job — the heart of the deployment.

Runs once per QQQ trading day at 4:01pm ET (after the equity close). For
each enabled strategy in the basket config:
  1. Pull the daily close series (lookback >= 250 days for SMA200 warmup)
  2. Compute the signal snapshot at the latest close
  3. Compare to the persisted previous snapshot
  4. Persist the new snapshot
  5. Return any StateChange events (consumed by the order/alert layers)

Timezone handling (locked decision recorded here):
  - Reference timezone: US/Eastern (US equity market clock).
  - Job is intended to run at 4:01pm ET on equity trading days. The
    `now_et` parameter is injected for testability; production scheduling
    is a separate concern (cron/k8s/launchd outside this module).
  - For BTC: we use the BTC daily-close bar whose date matches today's
    equity trading date (`as_of`). The BTC daily bar that closes at
    00:00 UTC on date D+1 is conventionally labelled date D (the
    convention Yahoo and Databento both use), which aligns naturally
    with the equity trading date.
  - On equity holidays/weekends: the job does NOT run (no `as_of` to
    work with). BTC positions are held flat through the gap. This
    matches the validated backtest convention (QQQ calendar as master).

Idempotency (locked):
  - Running the job twice for the same trading date produces the same
    persisted state and emits the SAME StateChange events the second time
    only if the data has changed (e.g., a late correction to the
    close). The store records `last_check_trading_date`; the caller can
    decide to short-circuit if that matches today and force=False.

What happens if the daily check runs but order placement fails:
  - The signal snapshot is persisted (the strategy *thinks* the order
    went out). Order placement is a separate module and records its own
    fill status. Reconciliation on the next startup will detect any
    state-vs-broker mismatch (see restart-resilience module, #10).
  - The alerting layer (#5) is triggered by StateChange events
    regardless of order-placement success, so the operator sees the
    intended action even if execution fails.
  - This module returns StateChange events; the caller (the runner
    script) decides whether to attempt orders, how to handle failures,
    and whether to roll back the persisted snapshot. The default policy
    (which the runner script will implement) is "persist snapshot only
    after order is acknowledged" — but this module supports both modes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

import pandas as pd

from src.deploy.baskets import BasketConfig, StrategySpec
from src.deploy.signal_state import (
    SignalSnapshot, SignalState, StateChange,
    compute_signal, detect_change,
)
from src.deploy.store import StateStore

_log = logging.getLogger(__name__)


class CloseSeriesProvider(Protocol):
    """Pulls a daily close series for an asset, ending at-or-before
    the given as_of date. Concrete implementations: src/data/yahoo.py
    wrapper and a SimProvider for tests."""

    def closes(self, asset: str, as_of: date, lookback_days: int) -> pd.Series: ...


@dataclass
class DailyCheckResult:
    """The outcome of one daily-check run."""
    trading_date: date
    run_at_utc: datetime
    snapshots: dict[str, SignalSnapshot]   # current state per strategy_id
    changes: list[StateChange]             # state changes since last run
    warnings: list[str]                    # non-fatal issues to surface

    def has_actionable_changes(self) -> bool:
        return any(c.is_flip for c in self.changes)


def run_daily_check(
    cfg: BasketConfig,
    store: StateStore,
    provider: CloseSeriesProvider,
    trading_date: date,
    now_utc: datetime | None = None,
    persist: bool = True,
    lookback_days: int = 250,
) -> DailyCheckResult:
    """Run the daily check for `trading_date`.

    Pure orchestration: pulls closes for each enabled strategy's asset via
    `provider`, computes snapshots, diffs against `store`, optionally
    persists. Returns the result for the caller (runner script) to act on.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    snapshots: dict[str, SignalSnapshot] = {}
    changes: list[StateChange] = []
    warnings: list[str] = []

    for basket in cfg.baskets.values():
        if not basket.enabled:
            continue
        for spec in basket.strategies:
            if spec.signal != "sma_crossover":
                warnings.append(
                    f"{spec.id}: unsupported signal {spec.signal!r}, skipping")
                continue
            fast = int(spec.params.get("fast", 50))
            slow = int(spec.params.get("slow", 200))
            try:
                closes = provider.closes(spec.asset, trading_date, lookback_days)
            except Exception as exc:
                warnings.append(f"{spec.id}: failed to fetch closes: {exc!r}")
                continue
            if closes.empty:
                warnings.append(f"{spec.id}: no closes returned")
                continue

            snap = compute_signal(spec.id, closes, trading_date, fast=fast, slow=slow)
            snapshots[spec.id] = snap
            prev = store.get(spec.id)
            change = detect_change(prev, snap)
            changes.append(change)

            if change.is_flip:
                _log.info("FLIP %s: %s -> %s on %s (close=%.2f sma%d=%s sma%d=%s)",
                          spec.id, change.prev_state.value, change.new_state.value,
                          trading_date, snap.close, fast,
                          f"{snap.sma50:.2f}" if snap.sma50 else "n/a",
                          slow, f"{snap.sma200:.2f}" if snap.sma200 else "n/a")
            elif snap.state == SignalState.UNKNOWN:
                warnings.append(f"{spec.id}: still in warmup (need {slow} bars)")

    if persist:
        for snap in snapshots.values():
            store.put(snap)
        store.mark_check(now_utc, trading_date)
        store.save()

    return DailyCheckResult(
        trading_date=trading_date, run_at_utc=now_utc,
        snapshots=snapshots, changes=changes, warnings=warnings,
    )
