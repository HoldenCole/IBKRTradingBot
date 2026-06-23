"""Startup reconciliation — handles "broker says X, our state says Y".

Runs on every daily-check startup BEFORE any new orders are placed. Compares
the broker's authoritative position list against our internal ledger and
produces a Reconciliation report with three kinds of findings:

  1. PHANTOM_LOT — our ledger has a lot the broker doesn't (we think we
     own shares, broker says we don't)
  2. ORPHAN_POSITION — broker holds shares our ledger doesn't know about
     (someone bought outside our system, or a prior order filled after
     our state was persisted)
  3. QUANTITY_MISMATCH — same symbol, different quantities (partial fill
     that didn't update our ledger; manual sale; broker corporate action)

Policy (LOCKED — per scoping doc decision "default policy: persist
before order; reconcile on startup"):
  - PHANTOM_LOT: log + alert CRITICAL. Do NOT auto-resolve (could be a
    real broker outage, not a state corruption). Operator decides.
  - ORPHAN_POSITION: log + alert CRITICAL. Same reason.
  - QUANTITY_MISMATCH: log + alert CRITICAL.

In all three cases the reconciliation result has `safe_to_trade=False`
until the operator inspects and either (a) corrects state or (b) confirms
the broker reality. The daily-check orchestrator MUST refuse to place new
orders when safe_to_trade is False — preventing automated overwriting of
a broker reality the system doesn't understand.

The reconciliation tolerance is exact (no fuzzy quantity comparison) for
shares — Stage 1 is integer-shares for equities. Fractional handling can
be added when futures vehicles activate at $50k+.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from src.deploy.broker import Position, StockBroker
from src.deploy.portfolio import Ledger

_log = logging.getLogger(__name__)


class FindingType(str, Enum):
    PHANTOM_LOT = "phantom_lot"
    ORPHAN_POSITION = "orphan_position"
    QUANTITY_MISMATCH = "quantity_mismatch"


@dataclass
class Finding:
    type: FindingType
    symbol: str
    ledger_quantity: float
    broker_quantity: float
    detail: str


@dataclass
class Reconciliation:
    findings: list[Finding] = field(default_factory=list)
    safe_to_trade: bool = True
    summary: str = ""

    def has_findings(self) -> bool:
        return len(self.findings) > 0


async def reconcile_startup(
    broker: StockBroker, ledger: Ledger,
    tolerance: float = 1e-6,
) -> Reconciliation:
    """Compare broker reality vs our ledger view. Returns a report; does
    NOT auto-correct.
    """
    broker_positions = await broker.positions()
    # Aggregate ledger open lots by symbol (across strategies — broker
    # doesn't know about sleeve attribution)
    ledger_qty_by_symbol: dict[str, float] = {}
    for lot in ledger.open_lots():
        ledger_qty_by_symbol[lot.symbol] = (
            ledger_qty_by_symbol.get(lot.symbol, 0.0) + lot.quantity)

    findings: list[Finding] = []
    all_symbols = set(broker_positions) | set(ledger_qty_by_symbol)

    for sym in sorted(all_symbols):
        b_qty = broker_positions[sym].quantity if sym in broker_positions else 0.0
        l_qty = ledger_qty_by_symbol.get(sym, 0.0)
        diff = b_qty - l_qty
        if abs(diff) <= tolerance:
            continue
        if l_qty > 0 and b_qty == 0:
            findings.append(Finding(
                type=FindingType.PHANTOM_LOT, symbol=sym,
                ledger_quantity=l_qty, broker_quantity=b_qty,
                detail=f"ledger holds {l_qty:g} {sym}; broker holds 0"))
        elif b_qty > 0 and l_qty == 0:
            findings.append(Finding(
                type=FindingType.ORPHAN_POSITION, symbol=sym,
                ledger_quantity=l_qty, broker_quantity=b_qty,
                detail=f"broker holds {b_qty:g} {sym}; ledger has no lots"))
        else:
            findings.append(Finding(
                type=FindingType.QUANTITY_MISMATCH, symbol=sym,
                ledger_quantity=l_qty, broker_quantity=b_qty,
                detail=f"ledger {l_qty:g} vs broker {b_qty:g} {sym} "
                       f"(diff {diff:+g})"))

    if findings:
        summary = (f"{len(findings)} discrepancies; trading PAUSED until "
                   f"operator review")
    else:
        summary = "ledger matches broker; safe to trade"

    safe = len(findings) == 0
    return Reconciliation(findings=findings, safe_to_trade=safe, summary=summary)
