"""Cost model (fixed in PREREGISTRATION.md).

Effective full spread at a bar = max(feed spread at the bar open, base spread) x stress.
Buys pay mid + half of it, sells receive mid - half. Stop orders slip a further
STOP_SLIP_PIPS x stress. Limit orders do not slip.
"""
from __future__ import annotations

import numpy as np

from research.fx_intraday.data import pip

# OANDA US spread-only account, from the report; EURGBP and AUDNZD are assumptions.
BASE_SPREAD_PIPS = {"EURUSD": 1.4, "GBPUSD": 2.0, "USDJPY": 1.4, "EURGBP": 2.0, "AUDNZD": 3.0}
STOP_SLIP_PIPS = 0.2
MAX_SPREAD_MULT = 2.5          # no entry when the feed spread exceeds this multiple of base
STRESS_LEVELS = (1.0, 1.5, 2.0)


def half_spread(feed_spread: np.ndarray, pair: str, stress: float) -> np.ndarray:
    base = BASE_SPREAD_PIPS[pair] * pip(pair)
    return np.maximum(feed_spread, base) * stress / 2.0


def stop_slip(pair: str, stress: float) -> float:
    return STOP_SLIP_PIPS * pip(pair) * stress


def spread_ok(feed_spread: np.ndarray, pair: str) -> np.ndarray:
    return feed_spread <= MAX_SPREAD_MULT * BASE_SPREAD_PIPS[pair] * pip(pair)
