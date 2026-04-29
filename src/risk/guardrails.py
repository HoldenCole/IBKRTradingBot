"""Pre-trade guardrails. Every order must pass through `check_entry`.

This is the single chokepoint enforcing position cap, weekly budget,
correlation/concentration, spread, and per-trade risk cap.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.risk.blackout import BlackoutChecker
from src.risk.regime import RegimeProvider
from src.risk.weekly_budget import Gate, WeeklyBudget


class RejectReason(str, Enum):
    OK = "ok"
    HARD_GATE = "hard_gate"
    BUDGET_EXCEEDED = "budget_exceeded"
    PER_TRADE_CAP = "per_trade_cap"
    POSITION_LIMIT = "position_limit"
    STRATEGY_FAMILY_LIMIT = "strategy_family_limit"
    GROSS_PREMIUM_LIMIT = "gross_premium_limit"
    SPREAD_TOO_WIDE = "spread_too_wide"
    BLACKOUT = "blackout"
    REGIME_OFF = "regime_off"
    BAD_PRICE = "bad_price"


@dataclass(frozen=True)
class EntryRequest:
    strategy_name: str
    strategy_family: str  # "mean_reversion" | "afternoon"
    underlying: str       # "SPY" | "QQQ"
    contracts: int
    entry_premium: float  # per-contract dollars (option price)
    bid: float
    ask: float
    nav: float


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    reason: RejectReason
    detail: str
    sizing_multiplier: float = 1.0  # 0.5 under soft gate
    gate: Gate = Gate.NORMAL


@dataclass
class Guardrails:
    budget: WeeklyBudget
    blackout: BlackoutChecker
    regime: RegimeProvider
    per_trade_risk_cap: float = 200.0
    max_concurrent_positions: int = 2
    max_per_family: int = 2
    max_gross_premium_pct: float = 0.60

    def _spread_check(self, req: EntryRequest) -> tuple[bool, str]:
        if req.bid <= 0 or req.ask <= 0 or req.ask <= req.bid:
            return False, "bad bid/ask"
        mid = (req.bid + req.ask) / 2.0
        spread_pct = (req.ask - req.bid) / mid
        if spread_pct > 0.15:
            return False, f"spread {spread_pct:.1%} > 15% of mid"
        if spread_pct > 0.08 and req.strategy_name != "ewo":
            return False, f"spread {spread_pct:.1%} > 8%; only EWO can absorb"
        return True, "ok"

    def check_entry(
        self,
        req: EntryRequest,
        now_et: datetime,
        open_positions_count: int,
        open_positions_in_family: int,
        gross_open_premium: float,
    ) -> GuardrailDecision:
        # 1. Bad-price guard
        if req.entry_premium <= 0 or req.contracts <= 0:
            return GuardrailDecision(False, RejectReason.BAD_PRICE,
                                     "premium or contracts non-positive")

        # 2. Spread
        ok, msg = self._spread_check(req)
        if not ok:
            return GuardrailDecision(False, RejectReason.SPREAD_TOO_WIDE, msg)

        # 3. Regime gate
        if not self.regime.is_active(req.underlying):
            return GuardrailDecision(False, RejectReason.REGIME_OFF,
                                     f"regime OFF for {req.underlying}")

        # 4. Blackout window
        if req.strategy_family == "afternoon":
            if self.blackout.is_blackout_day_for_afternoon_reversion(now_et):
                return GuardrailDecision(False, RejectReason.BLACKOUT,
                                         "afternoon-reversion blocked all session on blackout day")
        active = self.blackout.active_event(now_et)
        if active is not None:
            return GuardrailDecision(False, RejectReason.BLACKOUT,
                                     f"in blackout window for {active.kind.value}")

        # 5. Concurrent position limits
        if open_positions_count >= self.max_concurrent_positions:
            return GuardrailDecision(False, RejectReason.POSITION_LIMIT,
                                     f"already {open_positions_count} positions open")
        if open_positions_in_family >= self.max_per_family:
            return GuardrailDecision(False, RejectReason.STRATEGY_FAMILY_LIMIT,
                                     f"family {req.strategy_family} at limit")

        # 6. Per-trade risk cap (50% premium stop)
        trade_risk = req.contracts * req.entry_premium * 100.0 * 0.50
        if trade_risk > self.per_trade_risk_cap:
            return GuardrailDecision(False, RejectReason.PER_TRADE_CAP,
                                     f"trade risk ${trade_risk:.0f} > cap ${self.per_trade_risk_cap:.0f}")

        # 7. Gross premium concentration
        new_gross = gross_open_premium + req.contracts * req.entry_premium * 100.0
        cap = self.max_gross_premium_pct * req.nav
        if new_gross > cap:
            return GuardrailDecision(False, RejectReason.GROSS_PREMIUM_LIMIT,
                                     f"gross premium ${new_gross:.0f} > cap ${cap:.0f}")

        # 8. Weekly budget
        ok, gate, reason = self.budget.can_enter(now_et, trade_risk)
        if not ok:
            kind = RejectReason.HARD_GATE if gate is Gate.HARD else RejectReason.BUDGET_EXCEEDED
            return GuardrailDecision(False, kind, reason, gate=gate)

        sizing = self.budget.sizing_multiplier(now_et)
        return GuardrailDecision(True, RejectReason.OK, "ok",
                                 sizing_multiplier=sizing, gate=gate)
