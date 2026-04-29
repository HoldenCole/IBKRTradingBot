"""Order execution helpers. Every order MUST go through `submit_entry` /
`submit_exit` — these enforce the safety checks documented in STRATEGIES.md.

This module currently implements the fill-chase ladder logic against an
abstract OrderRouter so we can unit-test the timing/price progression without
a live IB connection. The IB-backed router is the production implementation.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from loguru import logger

from src.logging_setup import order_logger


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        return self.spread / self.mid if self.mid else float("inf")


@dataclass
class OrderResult:
    status: OrderStatus
    fill_price: float | None
    contracts: int
    detail: str


class OrderRouter(Protocol):
    """Abstract router. Production impl wraps ib_insync; tests use a fake."""

    async def quote(self, contract_id: str) -> Quote: ...

    async def place_limit(
        self, contract_id: str, side: str, contracts: int, limit_price: float
    ) -> str:  # returns order_id
        ...

    async def cancel(self, order_id: str) -> None: ...

    async def status(self, order_id: str) -> OrderResult: ...


# Spec: ladder = [0%, 25%, 50%, 75%, 100% of spread] every 15 seconds.
LADDER_STEPS_PCT = [0.0, 0.25, 0.50, 0.75, 1.00]
LADDER_INTERVAL_SEC = 15.0
SPREAD_BLOWOUT_PCT = 5.00  # 500% of mid


def _entry_price(side: str, q: Quote, step_pct: float) -> float:
    """Compute the next ladder price.

    side='buy'  -> mid + step% of spread, capped at ask
    side='sell' -> mid - step% of spread, floored at bid
    """
    if side == "buy":
        return min(q.mid + step_pct * q.spread, q.ask)
    return max(q.mid - step_pct * q.spread, q.bid)


@dataclass
class FillChase:
    router: OrderRouter
    contract_id: str
    side: str             # "buy" | "sell"
    contracts: int
    invalidation_price: float | None = None
    last_underlying: float | None = None
    is_stop_loss_exit: bool = False  # if True, skip ladder entirely
    ladder_interval_sec: float = LADDER_INTERVAL_SEC
    poll_interval_sec: float = 0.5

    async def run(self) -> OrderResult:
        olog = order_logger()

        if self.is_stop_loss_exit:
            # Spec: stop-loss exits skip the ladder; limit at bid - 0.05 immediately.
            q = await self.router.quote(self.contract_id)
            price = max(0.01, q.bid - 0.05)
            order_id = await self.router.place_limit(
                self.contract_id, "sell", self.contracts, price
            )
            olog.info(
                f"stop-loss exit {self.contract_id} x{self.contracts} @ ${price:.2f} order={order_id}"
            )
            return await self._wait(order_id, timeout_sec=30.0)

        for i, step in enumerate(LADDER_STEPS_PCT):
            q = await self.router.quote(self.contract_id)
            if q.spread_pct > SPREAD_BLOWOUT_PCT:
                olog.warning(f"spread blowout {q.spread_pct:.0%} on {self.contract_id} — abort")
                return OrderResult(OrderStatus.CANCELLED, None, self.contracts, "spread blowout")

            price = _entry_price(self.side, q, step)
            order_id = await self.router.place_limit(
                self.contract_id, self.side, self.contracts, price
            )
            olog.info(
                f"ladder step {i} {self.side} {self.contract_id} x{self.contracts} "
                f"@ ${price:.2f} (mid=${q.mid:.2f} spread={q.spread_pct:.1%}) order={order_id}"
            )
            res = await self._wait(order_id, timeout_sec=self.ladder_interval_sec)
            if res.status is OrderStatus.FILLED:
                return res
            await self.router.cancel(order_id)

        # Spec: entries that exhaust the ladder cancel and re-evaluate.
        # Exits drop to bid and take what's there.
        if self.side == "sell":
            q = await self.router.quote(self.contract_id)
            order_id = await self.router.place_limit(
                self.contract_id, "sell", self.contracts, q.bid
            )
            olog.info(f"exit fallback at bid ${q.bid:.2f} order={order_id}")
            return await self._wait(order_id, timeout_sec=30.0)

        return OrderResult(OrderStatus.CANCELLED, None, self.contracts, "ladder exhausted")

    async def _wait(self, order_id: str, timeout_sec: float) -> OrderResult:
        end = time.monotonic() + timeout_sec
        while time.monotonic() < end:
            res = await self.router.status(order_id)
            if res.status in (OrderStatus.FILLED, OrderStatus.REJECTED):
                return res
            await asyncio.sleep(self.poll_interval_sec)
        return await self.router.status(order_id)
