"""Persistence for positions and deferred-entry queue.

Single JSON file written atomically (write-temp-then-rename) so a crash
mid-write can't corrupt state. Loaded once on startup, rewritten after every
state-changing event (open, partial close, full close, mark-overnight,
advance-day, deferred-entry enqueue/dequeue).

State is intentionally simple: it's a serialized snapshot of all `Position`
objects in `PositionManager`, the realized-PnL-by-week dict from
`WeeklyBudget`, and the deferred-entries queue. Reconstruction at startup
rehydrates every object so the bot resumes mid-stream.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from src.positions.manager import PositionManager
from src.positions.position import Position, PositionStatus
from src.risk.weekly_budget import OpenPosition, WeeklyBudget
from src.strategies.base import SignalAction


@dataclass
class DeferredEntry:
    """An entry signal that fires at daily close but executes at next-day open.

    Persisted overnight so a restart between 16:00 ET and 09:31 ET doesn't
    lose the queued trades.
    """
    fire_at: datetime          # earliest time this can be executed
    strategy_name: str
    strategy_family: str
    underlying: str
    option_etf: str
    right: str
    strike_offset: int
    target_dte_min: int
    target_dte_max: int
    contracts: int
    reason: str

    def to_json(self) -> dict:
        return {
            "fire_at": self.fire_at.isoformat(),
            "strategy_name": self.strategy_name,
            "strategy_family": self.strategy_family,
            "underlying": self.underlying,
            "option_etf": self.option_etf,
            "right": self.right,
            "strike_offset": self.strike_offset,
            "target_dte_min": self.target_dte_min,
            "target_dte_max": self.target_dte_max,
            "contracts": self.contracts,
            "reason": self.reason,
        }

    @classmethod
    def from_json(cls, d: dict) -> "DeferredEntry":
        return cls(
            fire_at=datetime.fromisoformat(d["fire_at"]),
            strategy_name=d["strategy_name"],
            strategy_family=d["strategy_family"],
            underlying=d["underlying"],
            option_etf=d["option_etf"],
            right=d["right"],
            strike_offset=d["strike_offset"],
            target_dte_min=d["target_dte_min"],
            target_dte_max=d["target_dte_max"],
            contracts=d["contracts"],
            reason=d["reason"],
        )


@dataclass
class _Snapshot:
    positions: list[dict] = field(default_factory=list)
    realized_pnl_by_week: dict[str, float] = field(default_factory=dict)
    deferred: list[dict] = field(default_factory=list)


def _position_to_json(p: Position) -> dict:
    return {
        "trade_id": p.trade_id,
        "strategy_name": p.strategy_name,
        "strategy_family": p.strategy_family,
        "underlying": p.underlying,
        "option_etf": p.option_etf,
        "option_contract_id": p.option_contract_id,
        "direction": p.direction.value,
        "entry_time": p.entry_time.isoformat(),
        "entry_premium": p.entry_premium,
        "entry_underlying": p.entry_underlying,
        "entry_atr20": p.entry_atr20,
        "expiry": p.expiry.isoformat(),
        "initial_contracts": p.initial_contracts,
        "contracts_remaining": p.contracts_remaining,
        "scaled_50pct": p.scaled_50pct,
        "scaled_100pct": p.scaled_100pct,
        "trail_active": p.trail_active,
        "trail_level": p.trail_level,
        "morning_low": p.morning_low,
        "morning_high": p.morning_high,
        "high_water_underlying": p.high_water_underlying,
        "low_water_underlying": p.low_water_underlying,
        "trading_days_held": p.trading_days_held,
        "held_overnight": p.held_overnight,
        "status": p.status.value,
        "realized_pnl": p.realized_pnl,
        "closes": p.closes,
    }


def _position_from_json(d: dict) -> Position:
    return Position(
        trade_id=d["trade_id"],
        strategy_name=d["strategy_name"],
        strategy_family=d["strategy_family"],
        underlying=d["underlying"],
        option_etf=d["option_etf"],
        option_contract_id=d["option_contract_id"],
        direction=SignalAction(d["direction"]),
        entry_time=datetime.fromisoformat(d["entry_time"]),
        entry_premium=d["entry_premium"],
        entry_underlying=d["entry_underlying"],
        entry_atr20=d["entry_atr20"],
        expiry=date.fromisoformat(d["expiry"]),
        initial_contracts=d["initial_contracts"],
        contracts_remaining=d["contracts_remaining"],
        scaled_50pct=d["scaled_50pct"],
        scaled_100pct=d["scaled_100pct"],
        trail_active=d["trail_active"],
        trail_level=d["trail_level"],
        morning_low=d["morning_low"],
        morning_high=d["morning_high"],
        high_water_underlying=d.get("high_water_underlying"),
        low_water_underlying=d.get("low_water_underlying"),
        trading_days_held=d["trading_days_held"],
        held_overnight=d["held_overnight"],
        status=PositionStatus(d["status"]),
        realized_pnl=d["realized_pnl"],
        closes=d.get("closes", []),
    )


@dataclass
class PositionStore:
    """JSON-on-disk snapshot of PositionManager + deferred-entry queue.

    This is intentionally not a database. State is small (max ~10 positions)
    and a single JSON file is auditable, easy to back up, and survives
    restarts. Atomic write via tempfile + rename.
    """
    path: Path

    def save(
        self,
        pm: PositionManager,
        budget: WeeklyBudget,
        deferred: list[DeferredEntry],
    ) -> None:
        snapshot = _Snapshot(
            positions=[_position_to_json(p) for p in pm.positions.values()],
            realized_pnl_by_week={
                k.isoformat(): v for k, v in budget.realized_pnl_by_week.items()
            },
            deferred=[d.to_json() for d in deferred],
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        fd, tmp = tempfile.mkstemp(prefix=".store-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(asdict(snapshot), f, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def load(
        self,
        budget: WeeklyBudget,
    ) -> tuple[PositionManager, list[DeferredEntry]]:
        pm = PositionManager(budget=budget)
        deferred: list[DeferredEntry] = []
        if not self.path.exists():
            return pm, deferred

        with open(self.path) as f:
            raw = json.load(f)

        # Rehydrate realized PnL
        budget.realized_pnl_by_week = {
            date.fromisoformat(k): v for k, v in raw.get("realized_pnl_by_week", {}).items()
        }
        # Rehydrate positions
        for d in raw.get("positions", []):
            pos = _position_from_json(d)
            pm.positions[pos.trade_id] = pos
            if pos.status is PositionStatus.OPEN:
                budget.open_positions[pos.trade_id] = OpenPosition(
                    trade_id=pos.trade_id,
                    contracts=pos.contracts_remaining,
                    entry_premium=pos.entry_premium,
                    held_overnight=pos.held_overnight,
                )
        # Rehydrate deferred
        for d in raw.get("deferred", []):
            deferred.append(DeferredEntry.from_json(d))
        return pm, deferred
