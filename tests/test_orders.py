"""Tests for the fill-chase ladder against a fake OrderRouter."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from src.broker.orders import (
    FillChase,
    OrderResult,
    OrderStatus,
    Quote,
    LADDER_STEPS_PCT,
)


@dataclass
class FakeRouter:
    quotes: list[Quote]
    fill_at_step: int | None = None  # 0..4, or None to never fill
    placed: list[tuple[str, str, int, float]] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    _step: int = 0

    async def quote(self, contract_id: str) -> Quote:
        return self.quotes[min(self._step, len(self.quotes) - 1)]

    async def place_limit(self, contract_id, side, contracts, limit_price):
        self.placed.append((contract_id, side, contracts, limit_price))
        order_id = f"o{self._step}"
        return order_id

    async def cancel(self, order_id):
        self.cancelled.append(order_id)

    async def status(self, order_id):
        if self.fill_at_step is not None and self._step == self.fill_at_step:
            price = self.placed[-1][3]
            return OrderResult(OrderStatus.FILLED, price, self.placed[-1][2], "fill")
        # advance step on each status check so the chase doesn't stall
        self._step += 1
        return OrderResult(OrderStatus.PENDING, None, self.placed[-1][2], "pending")


_FAST = dict(ladder_interval_sec=0.05, poll_interval_sec=0.005)


@pytest.mark.asyncio
async def test_first_step_fills_at_mid():
    quotes = [Quote(2.0, 2.10)] * 5
    router = FakeRouter(quotes=quotes, fill_at_step=0)
    chase = FillChase(router=router, contract_id="OPT", side="buy", contracts=1, **_FAST)
    res = await asyncio.wait_for(chase.run(), timeout=2.0)
    assert res.status is OrderStatus.FILLED
    # First placed price should be the mid (2.05)
    assert abs(router.placed[0][3] - 2.05) < 1e-9


@pytest.mark.asyncio
async def test_ladder_walks_up_when_unfilled():
    quotes = [Quote(2.0, 2.10)] * 10
    router = FakeRouter(quotes=quotes, fill_at_step=None)
    chase = FillChase(router=router, contract_id="OPT", side="buy", contracts=1, **_FAST)
    # Should attempt all ladder steps then cancel (entry) — the chase takes
    # ~5 ladder steps * 0.05s = 0.25s, well under the 2s timeout.
    await asyncio.wait_for(chase.run(), timeout=2.0)
    prices = [p[3] for p in router.placed[: len(LADDER_STEPS_PCT)]]
    # Prices should be strictly non-decreasing (mid then more aggressive)
    assert prices == sorted(prices)
    assert prices[0] < prices[-1]


@pytest.mark.asyncio
async def test_stop_loss_skips_ladder():
    quotes = [Quote(2.0, 2.10)]
    router = FakeRouter(quotes=quotes, fill_at_step=0)
    chase = FillChase(
        router=router, contract_id="OPT", side="sell", contracts=1,
        is_stop_loss_exit=True, **_FAST,
    )
    res = await asyncio.wait_for(chase.run(), timeout=2.0)
    assert res.status is OrderStatus.FILLED
    # Should have placed exactly one order at bid - 0.05 = 1.95
    assert len(router.placed) == 1
    assert abs(router.placed[0][3] - 1.95) < 1e-9
