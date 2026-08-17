"""Position-size cap and daily-loss kill switch.

Kill switch policy (matches CL1_USO_STRATEGY.md): trips on *realized* daily
PnL, blocks new entries for the rest of the day, and never force-closes an
existing position — its normal exits still run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Guardrails:
    max_position_usd: float
    max_daily_loss_usd: float
    _day: date | None = None
    _realized_pnl: float = field(default=0.0)

    def _roll_day(self, today: date) -> None:
        if self._day != today:
            self._day = today
            self._realized_pnl = 0.0

    def record_realized_pnl(self, pnl: float, today: date) -> None:
        self._roll_day(today)
        self._realized_pnl += pnl

    def realized_pnl(self, today: date) -> float:
        self._roll_day(today)
        return self._realized_pnl

    def kill_switch_tripped(self, today: date) -> bool:
        self._roll_day(today)
        return self._realized_pnl <= -self.max_daily_loss_usd

    def can_open(self, notional_usd: float, today: date) -> tuple[bool, str]:
        """Gate a prospective new entry. Returns (allowed, reason)."""
        if notional_usd <= 0:
            return False, "non-positive notional"
        if notional_usd > self.max_position_usd:
            return False, (
                f"notional ${notional_usd:.2f} exceeds cap ${self.max_position_usd:.2f}"
            )
        if self.kill_switch_tripped(today):
            return False, (
                f"kill switch: realized daily PnL ${self._realized_pnl:.2f} "
                f"breaches -${self.max_daily_loss_usd:.2f}"
            )
        return True, "ok"

    def size_shares(self, price: float) -> int:
        """Max whole shares under the per-position cap (0 if price too high)."""
        if price <= 0:
            raise ValueError(f"non-positive price {price}")
        return int(self.max_position_usd // price)
