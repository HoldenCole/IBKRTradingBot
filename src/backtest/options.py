"""Options pricing for the backtest.

We don't have historical option chains, so we synthesize quotes from
underlying price + assumed implied vol via Black-Scholes. For our use case
(short-DTE ATM/1-strike-ITM calls on liquid ETFs that don't pay material
dividends) this is a reasonable approximation. Real-world deviations
(early exercise, IV smile, weekend decay) are noise relative to the
strategy's edge in backtest sizing.

Spread is modeled as a fixed % of mid per-ETF (configurable).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.broker.orders import Quote


@dataclass(frozen=True)
class OptionParams:
    spot: float           # underlying price
    strike: float
    dte_days: int         # days to expiry, calendar days
    iv: float             # annualized vol, e.g. 0.80 for 80%
    risk_free: float = 0.045


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erf (avoids scipy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_call(p: OptionParams) -> float:
    """European call price. Returns intrinsic if vol or DTE is zero."""
    T = max(p.dte_days, 0) / 365.0
    if T == 0 or p.iv <= 0 or p.spot <= 0 or p.strike <= 0:
        return max(0.0, p.spot - p.strike)
    sigma_sqrt_t = p.iv * math.sqrt(T)
    d1 = (math.log(p.spot / p.strike) + (p.risk_free + 0.5 * p.iv ** 2) * T) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    return p.spot * _norm_cdf(d1) - p.strike * math.exp(-p.risk_free * T) * _norm_cdf(d2)


def synthetic_quote(p: OptionParams, spread_pct_of_mid: float = 0.06) -> Quote:
    """Build a synthetic Quote from BS mid + symmetric spread."""
    mid = black_scholes_call(p)
    if mid <= 0.01:
        # Floor at penny so we can still place orders against deep-OTM trash
        mid = 0.01
    half = (mid * spread_pct_of_mid) / 2.0
    bid = max(0.01, mid - half)
    ask = mid + half
    return Quote(bid=bid, ask=ask)


# IV defaults per ETF. 3x levered ETFs have ~3x the underlying realized vol,
# so option IV runs roughly proportionally higher. These are starting points;
# the user should override with a backtest-time IV regime they trust.
DEFAULT_IV_BY_ETF: dict[str, float] = {
    "SPY": 0.20,
    "QQQ": 0.25,
    "UPRO": 0.65,
    "TQQQ": 0.75,
    "SQQQ": 0.85,
}

DEFAULT_SPREAD_PCT_BY_ETF: dict[str, float] = {
    "UPRO": 0.06,
    "TQQQ": 0.05,
    "SQQQ": 0.07,
}
