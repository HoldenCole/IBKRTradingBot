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
    div_yield: float = 0.0   # continuous dividend yield (e.g., 0.015 for SPY)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erf (avoids scipy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1_d2(p: "OptionParams") -> tuple[float, float] | None:
    """Compute BS d1, d2. Returns None when degenerate."""
    T = max(p.dte_days, 0) / 365.0
    if T == 0 or p.iv <= 0 or p.spot <= 0 or p.strike <= 0:
        return None
    sigma_sqrt_t = p.iv * math.sqrt(T)
    d1 = (math.log(p.spot / p.strike) +
          (p.risk_free - p.div_yield + 0.5 * p.iv ** 2) * T) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    return d1, d2


def black_scholes_call(p: OptionParams) -> float:
    """European call price with continuous dividend yield (Merton extension).
    Returns intrinsic if vol/DTE/spot/strike degenerate."""
    T = max(p.dte_days, 0) / 365.0
    if T == 0 or p.iv <= 0 or p.spot <= 0 or p.strike <= 0:
        return max(0.0, p.spot - p.strike)
    d12 = _d1_d2(p)
    if d12 is None:
        return max(0.0, p.spot - p.strike)
    d1, d2 = d12
    return (p.spot * math.exp(-p.div_yield * T) * _norm_cdf(d1)
            - p.strike * math.exp(-p.risk_free * T) * _norm_cdf(d2))


def black_scholes_call_delta(p: OptionParams) -> float:
    """Delta of a European call with continuous dividend yield.
    Returns 0 when option is degenerate, 1 when deep ITM at zero-vol."""
    if p.dte_days <= 0 or p.iv <= 0:
        return 1.0 if p.spot > p.strike else 0.0
    d12 = _d1_d2(p)
    if d12 is None:
        return 1.0 if p.spot > p.strike else 0.0
    d1, _ = d12
    T = p.dte_days / 365.0
    return math.exp(-p.div_yield * T) * _norm_cdf(d1)


def find_strike_for_delta(
    spot: float, dte_days: int, iv: float,
    target_delta: float,
    risk_free: float = 0.045, div_yield: float = 0.0,
    tol: float = 1e-4, max_iter: int = 50,
) -> float:
    """Solve for the call strike that produces the requested delta.

    Bisection on a strike grid wider than [10% spot, 200% spot]. Robust
    enough for our LEAPS use case (deltas in 0.5-0.95 range produce
    strikes between roughly 70%-110% of spot for typical IV).
    """
    if not (0.0 < target_delta < 1.0):
        raise ValueError(f"target_delta must be in (0,1), got {target_delta}")
    # Higher strike -> lower delta. Bisect on strike.
    lo = spot * 0.10
    hi = spot * 2.50
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        d = black_scholes_call_delta(OptionParams(
            spot=spot, strike=mid, dte_days=dte_days, iv=iv,
            risk_free=risk_free, div_yield=div_yield,
        ))
        if abs(d - target_delta) < tol:
            return mid
        if d > target_delta:   # too much delta -> raise strike
            lo = mid
        else:
            hi = mid
    return mid


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


# IV defaults per ETF. Calibrated against typical 2024-2026 realized IV
# regimes for these tickers. Levered ETFs (UPRO/TQQQ/SQQQ) sit roughly 3x the
# underlying realized vol but the prior values (65/75/85%) overstated mid-
# regime IV by 10-20 points, inflating option prices and P&L magnitudes in
# backtests. Override per-run if you want to test stress scenarios.
DEFAULT_IV_BY_ETF: dict[str, float] = {
    "SPY": 0.20,
    "QQQ": 0.25,
    "UPRO": 0.45,
    "TQQQ": 0.55,
    "SQQQ": 0.75,
}

# Spread defaults reflect typical bid-ask % of mid on ATM weekly/monthly
# options for these ETFs. Prior values were both too tight on UPRO (which
# trades thinner than its underlying suggests) and too wide on TQQQ
# (whose option chain is among the most-liquid retail options).
DEFAULT_SPREAD_PCT_BY_ETF: dict[str, float] = {
    "UPRO": 0.05,
    "TQQQ": 0.025,
    "SQQQ": 0.05,
}
