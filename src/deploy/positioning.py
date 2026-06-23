"""Target-driven initial positioning.

`plan_orders` (in orders.py) reacts to FLIPS — it builds the trades for a
single sleeve flipping ON or OFF on a given day. It is not the right tool
for the first daily-check after funding the account, or for re-basing the
portfolio after a reconciliation discrepancy is resolved: those situations
need to compute "where should each sleeve be RIGHT NOW given its current
signal state?" and trade the *difference* from current ledger holdings.

This module is that target-driven path. Given:
  - the basket config (target weights, vehicle selection by NAV)
  - the ledger (authoritative per-sleeve holdings)
  - the broker NAV (authoritative account equity)
  - current quotes
  - the current signal state per strategy (from the daily check)

it produces a PositioningPlan: per-sleeve BUY/SELL trades to take the
portfolio to its target allocation.

LOCKED policy choices:
  - UNKNOWN signal state (warmup not yet complete) -> the sleeve is parked
    in SGOV (the OFF vehicle). Matches the validated backtest convention:
    pre-warmup = OFF.
  - Whole-share rounding (floor). Tiny dollar slivers stay in broker cash;
    this is the same Stage-1 decision as `plan_orders`.
  - Idempotent: re-running positioning when already at target produces an
    empty trade list.
  - Per-sleeve: SGOV sells/buys are sized against THIS sleeve's parked
    SGOV (from the ledger), never the pooled broker balance — the same
    fix CRITICAL-1 applied to plan_orders.

What this module does NOT do:
  - Place orders. Returns a plan; `execute_positioning` (here) submits it.
  - Update the ledger. The orchestrator records fills into the ledger
    after execute_positioning returns broker tickets.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

from src.deploy.baskets import BasketConfig
from src.deploy.broker import OrderTicket, OrderType, StockBroker
from src.deploy.orders import OFF_VEHICLE_SYMBOL, resolve_risk_symbol
from src.deploy.portfolio import Ledger
from src.deploy.signal_state import SignalState

_log = logging.getLogger(__name__)


@dataclass
class PositioningTrade:
    """One per-sleeve trade in a positioning plan."""
    strategy_id: str
    symbol: str
    side: str              # "BUY" | "SELL"
    quantity: int
    reason: str = ""


@dataclass
class PositioningPlan:
    """The complete set of trades to bring the portfolio to target."""
    trades: list[PositioningTrade] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.trades


@dataclass
class PositioningResult:
    """Outcome of executing a positioning plan."""
    plan: PositioningPlan
    submitted: list[OrderTicket] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def plan_positioning(
    cfg: BasketConfig,
    ledger: Ledger,
    nav: float,
    quotes: dict[str, float],
    signal_states: dict[str, SignalState],
) -> PositioningPlan:
    """Build the trade plan to take every enabled sleeve to target.

    For each enabled strategy:
      - If state == ON:  target = floor(target_dollars / risk_quote) shares of risk; 0 SGOV.
      - If state == OFF or UNKNOWN: target = 0 risk; floor(target_dollars / sgov_quote) SGOV.

    Then trade = target - current (signed; positive = BUY, negative = SELL).
    """
    plan = PositioningPlan()
    sgov_quote = quotes.get(OFF_VEHICLE_SYMBOL)
    if sgov_quote is None:
        raise RuntimeError(f"missing quote for {OFF_VEHICLE_SYMBOL}")

    sleeve_sgov = ledger.open_shares_by_strategy(OFF_VEHICLE_SYMBOL)

    for basket in cfg.baskets.values():
        if not basket.enabled or not basket.strategies:
            continue
        per_strat_dollars = (basket.weight * nav) / len(basket.strategies)
        for spec in basket.strategies:
            risk_symbol = resolve_risk_symbol(spec, nav)
            risk_quote = quotes.get(risk_symbol)
            if risk_quote is None:
                raise RuntimeError(f"missing quote for {risk_symbol}")
            state = signal_states.get(spec.id, SignalState.UNKNOWN)

            if state == SignalState.ON:
                target_risk = int(per_strat_dollars // risk_quote)
                target_off = 0
            else:
                # OFF or UNKNOWN (warmup) -> park in SGOV
                target_risk = 0
                target_off = int(per_strat_dollars // sgov_quote)
                if state == SignalState.UNKNOWN:
                    plan.notes.append(
                        f"{spec.id}: signal UNKNOWN (warmup); parking in "
                        f"{OFF_VEHICLE_SYMBOL}")

            current_risk = int(
                ledger.open_shares_by_strategy(risk_symbol).get(spec.id, 0.0))
            current_off = int(sleeve_sgov.get(spec.id, 0.0))

            risk_delta = target_risk - current_risk
            off_delta = target_off - current_off

            if risk_delta != 0:
                plan.trades.append(PositioningTrade(
                    strategy_id=spec.id, symbol=risk_symbol,
                    side="BUY" if risk_delta > 0 else "SELL",
                    quantity=abs(risk_delta),
                    reason=f"state={state.value} target={target_risk} "
                           f"current={current_risk}",
                ))
            if off_delta != 0:
                plan.trades.append(PositioningTrade(
                    strategy_id=spec.id, symbol=OFF_VEHICLE_SYMBOL,
                    side="BUY" if off_delta > 0 else "SELL",
                    quantity=abs(off_delta),
                    reason=f"state={state.value} target={target_off} "
                           f"current={current_off}",
                ))

    return plan


async def execute_positioning(
    plan: PositioningPlan,
    broker: StockBroker,
    order_type: OrderType = OrderType.MOO,
) -> PositioningResult:
    """Submit a positioning plan. SELLs go before BUYs so cash is freed
    before it is needed; otherwise the broker's cash-sufficiency check
    can reject a BUY even though the same plan's SELL would have funded it.
    """
    result = PositioningResult(plan=plan)
    ordered = sorted(plan.trades, key=lambda t: 0 if t.side == "SELL" else 1)
    for trade in ordered:
        try:
            ticket = await broker.place_order(
                trade.symbol, trade.side, trade.quantity, order_type)
            ticket.strategy_id = trade.strategy_id
            result.submitted.append(ticket)
        except Exception as exc:
            result.errors.append(
                f"{trade.strategy_id} {trade.side} {trade.quantity} "
                f"{trade.symbol}: {exc!r}")
            _log.exception("positioning order failed for %s", trade.strategy_id)
    return result
