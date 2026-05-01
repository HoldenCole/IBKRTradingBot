"""Broker protocol — abstracts ib_insync so the runner is testable.

The IBKR-backed implementation lives in src/runner/ibkr_adapter.py and is
a direct translation. The simulated implementation (src/runner/sim.py) drives
the integration test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from src.broker.orders import Quote


@dataclass(frozen=True)
class OptionContract:
    """An option resolved to a tradable contract.

    `id` is the broker-side identifier (IBKR conId, or any opaque string).
    `strike` and `expiry` are returned for logging / state persistence.
    """
    id: str
    underlying_etf: str
    right: str          # "C" | "P"
    strike: float
    expiry: date


class Broker(Protocol):
    """Anything the runner needs from the brokerage."""

    async def quote(self, contract_id: str) -> Quote: ...

    async def underlying_price(self, symbol: str) -> float: ...

    async def select_option(
        self,
        underlying_etf: str,
        right: str,
        strike_offset: int,
        target_dte_min: int,
        target_dte_max: int,
    ) -> OptionContract:
        """Pick a contract matching the requested DTE range and strike offset
        (0 = ATM, -1 = 1 strike ITM for calls). Implementations qualify the
        contract before returning so its id is usable.
        """

    async def place_limit(
        self,
        contract_id: str,
        side: str,
        contracts: int,
        limit_price: float,
    ) -> str: ...

    async def cancel(self, order_id: str) -> None: ...

    async def order_status(self, order_id: str):  # -> OrderResult
        ...

    async def nav(self) -> float:
        """Net liquidation value for the gross-premium guardrail."""
