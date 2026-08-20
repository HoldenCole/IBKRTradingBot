"""Playbook matrix v3 — locked allocation per (risk tier, quadrant).

Design rules (PORTFOLIOS.md): MOD defines WHAT each regime owns; CONS
dilutes with cash; AGG/VAGG escalate octane only. v3 changes (validated
on both the 2007-2026 and 1987-2007 samples):

- S (stagflation) cells: cash + TREND-CONDITIONAL DURATION — the
  COND_DURATION placeholder resolves to TLT when TLT is above its
  10-month SMA (growth-scare stagflation) and to SHY otherwise
  (inflation-shock stagflation). Gold removed (negative both eras).
- R (reflation) cells: cross-sectional momentum tilt — the cell's
  commodity trio is reweighted 45/32.5/22.5 by trailing 6-month
  momentum at resolution time.

All tickers are real ETFs so the paper ledger marks to market without
simulation. The IBS options overlay is a separate sleeve, not part of
this rotation ledger.
"""

from __future__ import annotations

from src.regime.quadrant import Quadrant

G, R, Q_S, D = Quadrant.GROWTH, Quadrant.REFLATION, Quadrant.STAGFLATION, Quadrant.DEFLATION

_MOD_R = {"SPY": 0.30, "XLE": 0.25, "GLD": 0.25, "DBC": 0.20}

MATRIX_VERSION = "v3"

# Placeholder resolved by resolve_allocation(): TLT in a bond uptrend,
# SHY (cash) otherwise. Fail-closed: unknown trend -> cash.
COND_DURATION = "COND_DURATION"

MATRIX: dict[str, dict[Quadrant, dict[str, float]]] = {
    "CONS": {
        G: {"SPY": 0.40, "IEF": 0.40, "GLD": 0.20},
        R: {**{k: round(v * 0.7, 3) for k, v in _MOD_R.items()}, "SHY": 0.30},
        Q_S: {"SHY": 0.60, COND_DURATION: 0.40},
        D: {"TLT": 0.45, "SHY": 0.35, "XLP": 0.20},
    },
    "MOD": {
        G: {"QQQ": 0.70, "IEF": 0.30},
        R: dict(_MOD_R),
        Q_S: {"SHY": 0.50, COND_DURATION: 0.50},
        D: {"TLT": 0.55, "XLP": 0.25, "GLD": 0.20},
    },
    "AGG": {
        G: {"QLD": 1.00},
        R: {"QLD": 0.30, "XLE": 0.25, "GDX": 0.25, "DBC": 0.20},
        Q_S: {"SHY": 0.40, COND_DURATION: 0.60},
        D: {"TLT": 0.60, "TMF": 0.20, "GLD": 0.20},
    },
    "VAGG": {
        G: {"TQQQ": 1.00},
        R: {"TQQQ": 0.30, "ERX": 0.25, "GDX": 0.25, "DBC": 0.20},
        Q_S: {"SHY": 0.30, COND_DURATION: 0.70},
        D: {"TMF": 0.50, "TLT": 0.30, "GLD": 0.20},
    },
}

TIERS = list(MATRIX)

# Each tier's reflation commodity trio, tilted by 6-month momentum.
R_TILT: dict[str, list[str]] = {
    "CONS": ["XLE", "GLD", "DBC"],
    "MOD": ["XLE", "GLD", "DBC"],
    "AGG": ["XLE", "GDX", "DBC"],
    "VAGG": ["ERX", "GDX", "DBC"],
}
TILT_SHARES = (0.45, 0.325, 0.225)  # best -> worst momentum


def all_tickers() -> list[str]:
    """Concrete tickers the ledger may hold (placeholder resolved)."""
    out: set[str] = set()
    for tier in MATRIX.values():
        for weights in tier.values():
            out.update(weights)
    out.discard(COND_DURATION)
    out.update({"TLT", "SHY"})
    return sorted(out)


def resolve_allocation(
    tier: str,
    quadrant: Quadrant,
    tlt_trend_up: bool | None = None,
    commodity_momentum: dict[str, float] | None = None,
) -> dict[str, float]:
    """Concrete weights for a tier/quadrant given the resolution signals.

    - COND_DURATION -> TLT if tlt_trend_up else SHY (None fails closed to SHY)
    - In REFLATION, the tier's commodity trio is reweighted by momentum
      rank when commodity_momentum covers all three assets.
    """
    base = dict(MATRIX[tier][quadrant])
    if COND_DURATION in base:
        w = base.pop(COND_DURATION)
        bond = "TLT" if tlt_trend_up else "SHY"
        base[bond] = round(base.get(bond, 0.0) + w, 4)
    if quadrant is R and commodity_momentum:
        trio = [a for a in R_TILT[tier] if a in base]
        if len(trio) == 3 and all(a in commodity_momentum for a in trio):
            pool = sum(base[a] for a in trio)
            ranked = sorted(trio, key=lambda a: -commodity_momentum[a])
            total = sum(TILT_SHARES)
            for asset, share in zip(ranked, TILT_SHARES):
                base[asset] = round(pool * share / total, 4)
    return base


def allocation(tier: str, quadrant: Quadrant) -> dict[str, float]:
    """Signal-free resolution (conditional duration fails closed to cash)."""
    return resolve_allocation(tier, quadrant)
