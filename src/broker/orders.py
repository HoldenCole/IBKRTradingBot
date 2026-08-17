"""Order helpers with safety checks. Every order the bot sends goes
through place_limit() — no exceptions (repo safety rule #2).

All orders are LIMIT. Entries price at mid; urgent exits (stop, EOD
flatten) use a marketable limit through the spread to guarantee fills.
"""

from __future__ import annotations

from datetime import date

from loguru import logger

from src.config import Settings
from src.risk.guardrails import Guardrails


class OrderRejected(Exception):
    """Raised when a pre-trade safety check fails."""


# USO's spread is normally 1-2 bps of mid; wider means degraded liquidity.
MAX_ENTRY_SPREAD_BPS = 10.0


def check_entry_spread(bid: float, ask: float) -> None:
    if bid <= 0 or ask <= 0 or ask < bid:
        raise OrderRejected(f"bad quote bid={bid} ask={ask}")
    mid = (bid + ask) / 2
    spread_bps = (ask - bid) / mid * 10_000
    if spread_bps > MAX_ENTRY_SPREAD_BPS:
        raise OrderRejected(f"spread {spread_bps:.1f} bps > {MAX_ENTRY_SPREAD_BPS} bps cap")


class OrderRouter:
    def __init__(self, ib, settings: Settings, guardrails: Guardrails):
        self.ib = ib
        self.settings = settings
        self.guardrails = guardrails

    def place_limit(
        self,
        contract,
        action: str,  # "BUY" | "SELL"
        quantity: int,
        limit_price: float,
        *,
        is_entry: bool,
        today: date,
        reason: str = "",
    ):
        from ib_insync import LimitOrder  # local import, see connection.py

        if action not in ("BUY", "SELL"):
            raise OrderRejected(f"invalid action {action!r}")
        if quantity <= 0:
            raise OrderRejected(f"invalid quantity {quantity}")
        if limit_price <= 0:
            raise OrderRejected(f"invalid limit price {limit_price}")

        if is_entry:
            notional = quantity * limit_price
            allowed, why = self.guardrails.can_open(notional, today)
            if not allowed:
                raise OrderRejected(why)

        order = LimitOrder(action, quantity, round(limit_price, 2), tif="DAY")
        logger.info(
            f"ORDER {action} {quantity} {getattr(contract, 'symbol', contract)} "
            f"@ {limit_price:.2f} entry={is_entry} reason={reason!r} mode={self.settings.mode}"
        )
        trade = self.ib.placeOrder(contract, order)
        return trade
