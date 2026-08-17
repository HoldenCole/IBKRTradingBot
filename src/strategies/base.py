"""Strategy abstract base class and the Signal type strategies emit.

Strategies contain only signal logic. Sizing, order routing, guardrails,
and connection plumbing live elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Action(Enum):
    BUY = "BUY"          # open (or add to) a long
    SELL_SHORT = "SELL"  # open a short
    CLOSE = "CLOSE"      # flatten the current position


@dataclass(frozen=True)
class Signal:
    action: Action
    reason: str
    # Quantity is optional: when None, the runner sizes the order from the
    # per-position notional cap.
    quantity: int | None = None


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def on_bar(self, bar: Any) -> Signal | None:
        """Called once per bar. Return a Signal or None to do nothing."""

    def on_fill(self, fill: Any) -> None:  # pragma: no cover - optional hook
        """Called when an order fills. Optional override."""
