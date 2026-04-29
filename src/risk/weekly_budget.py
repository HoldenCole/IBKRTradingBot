"""Weekly loss budget tracker.

Spec (STRATEGIES.md):
- Fixed $500 per week, Mon 09:30 ET -> Fri 16:00 ET. Wins do not extend.
- weekly_risk_used = realized_loss_this_week + sum(open trade_risk_at_risk)
- trade_risk_at_risk = contracts * entry_premium * 0.50  (premium stop is 50%)
- Overnight positions count at 1.5x against the budget.
- Gates: <70% normal, 70-100% soft (50% sizing), >=100% hard (no new entries).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


class Gate(str, Enum):
    NORMAL = "normal"
    SOFT = "soft"
    HARD = "hard"


@dataclass(frozen=True)
class OpenPosition:
    trade_id: str
    contracts: int
    entry_premium: float  # per-contract, in dollars (multiply by 100 for $ notional)
    held_overnight: bool = False

    def risk_at_risk(self, overnight_multiplier: float = 1.5) -> float:
        # premium * 100 = $ per contract; 50% premium stop is the trade risk.
        base = self.contracts * self.entry_premium * 100.0 * 0.50
        return base * (overnight_multiplier if self.held_overnight else 1.0)


@dataclass
class WeeklyBudget:
    budget: float = 500.0
    soft_gate_pct: float = 0.70
    overnight_multiplier: float = 1.5

    realized_pnl_by_week: dict[date, float] = field(default_factory=dict)
    open_positions: dict[str, OpenPosition] = field(default_factory=dict)

    @staticmethod
    def week_anchor(now_et: datetime) -> date:
        """Monday of the trading week containing now_et (in ET)."""
        if now_et.tzinfo is None:
            now_et = now_et.replace(tzinfo=ET)
        else:
            now_et = now_et.astimezone(ET)
        # Trading week: Mon 09:30 ET -> Fri 16:00 ET. Anything before Mon 09:30
        # rolls back to the prior week's Monday so we don't reset early.
        monday = (now_et - timedelta(days=now_et.weekday())).date()
        if now_et.weekday() == 0 and now_et.timetz() < time(9, 30, tzinfo=ET):
            monday = monday - timedelta(days=7)
        return monday

    def realized_loss(self, now_et: datetime) -> float:
        wk = self.week_anchor(now_et)
        pnl = self.realized_pnl_by_week.get(wk, 0.0)
        return max(0.0, -pnl)

    def open_risk(self) -> float:
        return sum(p.risk_at_risk(self.overnight_multiplier) for p in self.open_positions.values())

    def risk_used(self, now_et: datetime) -> float:
        return self.realized_loss(now_et) + self.open_risk()

    def gate(self, now_et: datetime) -> Gate:
        used = self.risk_used(now_et)
        if used >= self.budget:
            return Gate.HARD
        if used >= self.budget * self.soft_gate_pct:
            return Gate.SOFT
        return Gate.NORMAL

    def can_enter(self, now_et: datetime, prospective_risk: float) -> tuple[bool, Gate, str]:
        """Check if a new entry of `prospective_risk` dollars is allowed.

        Returns (allowed, current_gate, reason).
        """
        g = self.gate(now_et)
        if g is Gate.HARD:
            return False, g, "hard gate: weekly budget exhausted"
        used = self.risk_used(now_et)
        if used + prospective_risk > self.budget:
            return False, g, (
                f"would exceed budget: used=${used:.0f} + new=${prospective_risk:.0f} > "
                f"${self.budget:.0f}"
            )
        return True, g, "ok"

    def sizing_multiplier(self, now_et: datetime) -> float:
        """Per spec: soft gate halves position size."""
        g = self.gate(now_et)
        return 0.5 if g is Gate.SOFT else 1.0

    def record_open(self, pos: OpenPosition) -> None:
        self.open_positions[pos.trade_id] = pos

    def mark_overnight(self, trade_id: str) -> None:
        if trade_id in self.open_positions:
            p = self.open_positions[trade_id]
            self.open_positions[trade_id] = OpenPosition(
                trade_id=p.trade_id,
                contracts=p.contracts,
                entry_premium=p.entry_premium,
                held_overnight=True,
            )

    def record_close(self, trade_id: str, realized_pnl: float, now_et: datetime) -> None:
        self.open_positions.pop(trade_id, None)
        wk = self.week_anchor(now_et)
        self.realized_pnl_by_week[wk] = self.realized_pnl_by_week.get(wk, 0.0) + realized_pnl

    def snapshot(self, now_et: datetime) -> dict:
        used = self.risk_used(now_et)
        return {
            "week_of": self.week_anchor(now_et).isoformat(),
            "realized_pnl": self.realized_pnl_by_week.get(self.week_anchor(now_et), 0.0),
            "open_risk": self.open_risk(),
            "risk_used": used,
            "budget": self.budget,
            "pct_used": used / self.budget if self.budget else 0.0,
            "gate": self.gate(now_et).value,
            "remaining": max(0.0, self.budget - used),
        }
