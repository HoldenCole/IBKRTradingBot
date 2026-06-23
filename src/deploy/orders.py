"""Order workflow — translates StateChange events into broker orders.

Pure orchestration over the StockBroker Protocol. Given:
  - the daily-check result (StateChange events + snapshots)
  - the basket config (target weights, vehicle selection by account size)
  - the broker (NAV, positions, place_order)
  - current quotes for the affected symbols (for sizing)

decides what to trade and submits the orders. Returns a record of every
order placed for the persistence/audit layer.

LOCKED DECISIONS from the operational scoping (re-stated in code):
  - Order type: MOO (market-on-open) for next-session execution.
    Convention 2 lag: signal at close N, fill at open N+1.
  - On EXIT (ON->OFF): sell ALL of the risk-asset position;
                       buy SGOV with the proceeds (target = current basket weight * NAV).
  - On ENTER (OFF->ON): sell ALL SGOV held by that sleeve;
                        buy risk asset (target = current basket weight * NAV).
  - Whole-share sizing: round DOWN to integer shares. Tiny cash sliver
    stays in the broker cash position (typically small at $8k; can be
    optimized later by routing sliver to SGOV).
  - Drift-band rebalancing: at filter transitions only. Each sleeve is
    independent; one sleeve flipping doesn't touch the other.
  - SGOV is the OFF vehicle for ALL strategies in Stage 1 (locked).

What this module DOES NOT do:
  - Wait for fills (caller polls order_status; restart-resilience #10
    handles "submitted but not yet known to be filled" on next startup).
  - Cancel/replace partial fills (MOO either fills or doesn't; we log).
  - Compute taxes (item #9, separate module).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

from src.deploy.baskets import BasketConfig, StrategySpec
from src.deploy.broker import OrderType, OrderTicket, Position, StockBroker
from src.deploy.signal_state import SignalState, StateChange

_log = logging.getLogger(__name__)

# Locked: SGOV is the OFF vehicle for Stage 1.
OFF_VEHICLE_SYMBOL = "SGOV"

# Map from (asset, vehicle_code) to the actual broker-side symbol to trade.
# The basket config resolves vehicle codes by account size (e.g. QQQ_SHARES,
# MNQ, IBIT, MBT); this map converts the code to the broker symbol.
_VEHICLE_TO_SYMBOL = {
    "QQQ_SHARES": "QQQ",
    "IBIT": "IBIT",
    # Futures vehicles (MNQ, MBT) require futures contracts, not stocks.
    # Not supported in Stage 1; assert in code if they appear.
}


@dataclass
class OrderPlan:
    """The set of orders the workflow intends to place for one flip.

    Built first, then submitted as a batch. Lets callers inspect/log
    the plan before commit.
    """
    strategy_id: str
    direction: str                          # "enter" | "exit"
    risk_symbol: str                        # e.g. QQQ, IBIT
    risk_side: str                          # BUY (enter) or SELL (exit)
    risk_quantity: int
    off_symbol: str = OFF_VEHICLE_SYMBOL
    off_side: str = ""                      # opposite of risk_side
    off_quantity: int = 0
    note: str = ""

    def __post_init__(self):
        if self.risk_side == "BUY":
            self.off_side = "SELL"
        elif self.risk_side == "SELL":
            self.off_side = "BUY"


@dataclass
class WorkflowResult:
    """What the workflow actually did (or attempted)."""
    plans: list[OrderPlan] = field(default_factory=list)
    submitted: list[OrderTicket] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)         # human-readable reasons
    errors: list[str] = field(default_factory=list)

    @property
    def any_orders_placed(self) -> bool:
        return len(self.submitted) > 0


def _resolve_symbol(spec: StrategySpec, equity_usd: float) -> str:
    """Convert a strategy's vehicle code (from baskets.json) to the broker
    symbol. Fails loudly for unsupported vehicles (e.g. futures in Stage 1)."""
    vehicle = spec.vehicle_for_account(equity_usd)
    if vehicle in _VEHICLE_TO_SYMBOL:
        return _VEHICLE_TO_SYMBOL[vehicle]
    raise NotImplementedError(
        f"Vehicle {vehicle!r} not supported by Stage-1 stock broker. "
        f"Futures (MNQ/MBT) require a futures order path — not in scope until "
        f"account-size thresholds are reached.")


def _strategy_lookup(cfg: BasketConfig) -> dict[str, tuple[str, StrategySpec]]:
    """Map strategy_id -> (basket_id, spec) for all enabled strategies."""
    out: dict[str, tuple[str, StrategySpec]] = {}
    for b in cfg.baskets.values():
        if not b.enabled:
            continue
        for s in b.strategies:
            out[s.id] = (b.id, s)
    return out


async def plan_orders(
    changes: Sequence[StateChange],
    cfg: BasketConfig,
    broker: StockBroker,
    quotes: dict[str, float],
) -> list[OrderPlan]:
    """Build the order plan for a set of state changes. Pure: no orders
    placed. The result can be inspected/logged before submit."""
    nav = await broker.nav()
    positions = await broker.positions()
    strats = _strategy_lookup(cfg)
    plans: list[OrderPlan] = []

    for ch in changes:
        if not ch.is_flip:
            continue
        if ch.strategy_id not in strats:
            _log.warning("flip for unknown strategy %s; skipping", ch.strategy_id)
            continue
        basket_id, spec = strats[ch.strategy_id]
        basket_weight = cfg.baskets[basket_id].weight
        risk_symbol = _resolve_symbol(spec, nav)

        if ch.direction == "exit":
            # Sell ALL risk asset held; buy SGOV with proceeds (sized to
            # basket weight * NAV; SGOV is shared across sleeves but we
            # size per-sleeve for accounting clarity).
            held = positions.get(risk_symbol)
            risk_qty = int(held.quantity) if held else 0
            if risk_qty <= 0:
                plans.append(OrderPlan(
                    strategy_id=ch.strategy_id, direction="exit",
                    risk_symbol=risk_symbol, risk_side="SELL", risk_quantity=0,
                    off_quantity=0,
                    note=f"no {risk_symbol} held; nothing to sell. "
                         f"(Possible cause: state-store/broker mismatch.)",
                ))
                continue
            risk_quote = quotes.get(risk_symbol)
            if risk_quote is None:
                raise RuntimeError(f"missing quote for {risk_symbol}")
            proceeds = risk_qty * risk_quote
            sgov_quote = quotes.get(OFF_VEHICLE_SYMBOL)
            if sgov_quote is None:
                raise RuntimeError(f"missing quote for {OFF_VEHICLE_SYMBOL}")
            off_qty = int(proceeds // sgov_quote)
            plans.append(OrderPlan(
                strategy_id=ch.strategy_id, direction="exit",
                risk_symbol=risk_symbol, risk_side="SELL",
                risk_quantity=risk_qty, off_quantity=off_qty,
                note=f"sell {risk_qty} {risk_symbol} ~${proceeds:,.0f} -> "
                     f"buy {off_qty} {OFF_VEHICLE_SYMBOL}",
            ))

        elif ch.direction == "enter":
            # Sell SGOV up to this sleeve's target, then buy risk asset.
            # Stage 1: each sleeve targets basket_weight * NAV in its risk
            # asset. SGOV held by THIS sleeve is conceptually basket_weight
            # * NAV worth; we can't separate per-sleeve at the broker
            # level. Treat it as: sell `sleeve_target / sgov_quote` shares
            # of SGOV, buy risk asset with the proceeds.
            target_dollars = basket_weight * nav
            sgov_quote = quotes.get(OFF_VEHICLE_SYMBOL)
            if sgov_quote is None:
                raise RuntimeError(f"missing quote for {OFF_VEHICLE_SYMBOL}")
            sgov_held = positions.get(OFF_VEHICLE_SYMBOL)
            sgov_available_dollars = (sgov_held.quantity * sgov_quote
                                      if sgov_held else 0.0)
            sleeve_sgov_dollars = min(target_dollars, sgov_available_dollars)
            off_qty = int(sleeve_sgov_dollars // sgov_quote)

            risk_quote = quotes.get(risk_symbol)
            if risk_quote is None:
                raise RuntimeError(f"missing quote for {risk_symbol}")
            risk_qty = int(target_dollars // risk_quote)
            if risk_qty <= 0:
                plans.append(OrderPlan(
                    strategy_id=ch.strategy_id, direction="enter",
                    risk_symbol=risk_symbol, risk_side="BUY", risk_quantity=0,
                    off_quantity=0,
                    note=f"target ${target_dollars:.0f} < 1 share of "
                         f"{risk_symbol} @ ${risk_quote:.2f}; skipping",
                ))
                continue
            plans.append(OrderPlan(
                strategy_id=ch.strategy_id, direction="enter",
                risk_symbol=risk_symbol, risk_side="BUY", risk_quantity=risk_qty,
                off_quantity=off_qty,
                note=f"sell {off_qty} {OFF_VEHICLE_SYMBOL} ~"
                     f"${sleeve_sgov_dollars:,.0f} -> buy {risk_qty} "
                     f"{risk_symbol} @ ~${risk_quote:.2f}",
            ))

    return plans


async def execute_plans(
    plans: Sequence[OrderPlan], broker: StockBroker,
    order_type: OrderType = OrderType.MOO,
) -> WorkflowResult:
    """Submit a planned set of orders. Per the locked decision, defaults
    to MOO (next-session open). MKT can be passed for backfills / manual
    intervention.

    Order ordering: on EXIT we sell risk first (frees cash), then buy
    OFF; on ENTER we sell OFF first (frees cash), then buy risk. This
    avoids cash-sufficiency rejections.
    """
    result = WorkflowResult(plans=list(plans))
    for plan in plans:
        if plan.risk_quantity <= 0 and plan.off_quantity <= 0:
            result.skipped.append(f"{plan.strategy_id}: {plan.note}")
            continue
        try:
            if plan.direction == "exit":
                # SELL risk first, then BUY off
                if plan.risk_quantity > 0:
                    t = await broker.place_order(
                        plan.risk_symbol, plan.risk_side, plan.risk_quantity,
                        order_type)
                    result.submitted.append(t)
                if plan.off_quantity > 0:
                    t = await broker.place_order(
                        plan.off_symbol, plan.off_side, plan.off_quantity,
                        order_type)
                    result.submitted.append(t)
            else:  # "enter"
                # SELL off first, then BUY risk
                if plan.off_quantity > 0:
                    t = await broker.place_order(
                        plan.off_symbol, plan.off_side, plan.off_quantity,
                        order_type)
                    result.submitted.append(t)
                if plan.risk_quantity > 0:
                    t = await broker.place_order(
                        plan.risk_symbol, plan.risk_side, plan.risk_quantity,
                        order_type)
                    result.submitted.append(t)
        except Exception as exc:
            result.errors.append(
                f"{plan.strategy_id} {plan.direction}: {exc!r}")
            _log.exception("order execution failed for %s", plan.strategy_id)
    return result
