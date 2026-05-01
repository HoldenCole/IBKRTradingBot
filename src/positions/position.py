"""Position state model.

A Position is created when an entry order fills. It tracks everything the
exit logic needs:
- entry context (premium, underlying, ATR at entry, expiry)
- contract state (initial vs remaining after scale-outs)
- scale-out flags (have we hit +50%? +100%?)
- ATR trail state (active? current trail level?)
- afternoon-only morning-range context
- trading-day counter for time stops
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from src.strategies.base import SignalAction


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Position:
    trade_id: str
    strategy_name: str           # "ewo" | "ibs" | "afternoon_reversion"
    strategy_family: str         # "mean_reversion" | "afternoon"
    underlying: str              # signal underlying: "SPY" | "QQQ"
    option_etf: str              # actual option underlying: UPRO | TQQQ | SQQQ
    option_contract_id: str      # broker-side identifier
    direction: SignalAction      # LONG or SHORT_FADE

    entry_time: datetime         # tz-aware
    entry_premium: float         # per-contract option price at entry
    entry_underlying: float      # underlying price at entry
    entry_atr20: float           # daily ATR(20) at entry, in price units
    expiry: date                 # option expiration

    initial_contracts: int
    contracts_remaining: int

    # Scale-out flags
    scaled_50pct: bool = False
    scaled_100pct: bool = False

    # ATR trailing stop state (activates after +100% scale-out)
    trail_active: bool = False
    trail_level: float | None = None  # underlying price floor (long) / ceiling (short)

    # Afternoon-only morning-range context (set by AfternoonReversion at entry)
    morning_low: float | None = None
    morning_high: float | None = None

    # Per-day extreme tracking for trail ratcheting
    high_water_underlying: float | None = None
    low_water_underlying: float | None = None

    # Trading-day counter for time stops. Day of entry = 0.
    trading_days_held: int = 0

    held_overnight: bool = False
    status: PositionStatus = PositionStatus.OPEN
    realized_pnl: float = 0.0  # cumulative across scale-outs

    # Audit trail of partial/full closes for reporting.
    closes: list[dict] = field(default_factory=list)

    @property
    def is_long(self) -> bool:
        return self.direction is SignalAction.LONG

    def days_to_expiry(self, today: date) -> int:
        return (self.expiry - today).days

    def morning_range(self) -> float | None:
        if self.morning_high is None or self.morning_low is None:
            return None
        return self.morning_high - self.morning_low

    def update_high_water(self, underlying_price: float) -> None:
        if self.is_long:
            if self.high_water_underlying is None or underlying_price > self.high_water_underlying:
                self.high_water_underlying = underlying_price
        else:
            if self.low_water_underlying is None or underlying_price < self.low_water_underlying:
                self.low_water_underlying = underlying_price

    def trade_risk_at_risk(self, overnight_multiplier: float = 1.5) -> float:
        """For weekly-budget accounting. 50% premium stop on remaining contracts."""
        base = self.contracts_remaining * self.entry_premium * 100.0 * 0.50
        return base * (overnight_multiplier if self.held_overnight else 1.0)
