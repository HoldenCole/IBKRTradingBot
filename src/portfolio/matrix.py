"""Playbook matrix v5 — locked allocation per (risk tier, quadrant).

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

v4 change (validated on both eras, no pre-2007 degradation):
- D (deflation) cells: gold raised to 25-30% (gold earned +25%/+31%
  annualized in D-months in the two samples) and a 10-15% equity
  rebound slice added (positive in both eras); duration stays
  UNCONDITIONAL — the trend filter was tested and rejected for D
  (70-96% of D-months already have bonds trending up).

v5 change (two-sample short screen, PORTFOLIOS.md):
- D cells gain a SHORT_OIL sleeve in MOD (10%), AGG and VAGG (15%),
  funded from TLT. Oil is the only asset negative in absolute terms in
  a regime in BOTH eras (USO -43%/yr modern D-months, GSCI negative
  pre-2007); D-classification itself requires commodities below their
  10-month SMA, so the short is the trend filter's short side and is
  self-limiting (an oil spike flips the regime out of D). CONS stays
  long-only.
- INCLUDE_SHORTS is the global on/off switch for the whole short book —
  this sleeve and any future validated short resolves through it. OFF
  reverts every short placeholder to its long fallback (TLT), restoring
  the v4 cells exactly.
- Margin-free implementation: each short resolves to a 2x inverse ETF
  at HALF the sleeve weight plus SHY for the remainder (10% short oil
  -> 5% SCO + 5% SHY), so the ledger marks to market with real ETFs.

All tickers are real ETFs so the paper ledger marks to market without
simulation. The IBS options overlay is a separate sleeve, not part of
this rotation ledger.
"""

from __future__ import annotations

from src.regime.quadrant import Quadrant

G, R, Q_S, D = Quadrant.GROWTH, Quadrant.REFLATION, Quadrant.STAGFLATION, Quadrant.DEFLATION

_MOD_R = {"SPY": 0.30, "XLE": 0.25, "GLD": 0.25, "DBC": 0.20}

MATRIX_VERSION = "v5"

# Global switch for the short book. OFF -> every short placeholder
# resolves to its long fallback, restoring the v4 long-only cells.
INCLUDE_SHORTS = True

# Placeholder resolved by resolve_allocation(): TLT in a bond uptrend,
# SHY (cash) otherwise. Fail-closed: unknown trend -> cash.
COND_DURATION = "COND_DURATION"

# Short placeholders. Each maps to (2x-inverse ETF, leverage) for the
# margin-free implementation, and to a long fallback used when shorts
# are switched off. Future validated shorts register here.
SHORT_OIL = "SHORT_OIL"
SHORT_IMPL: dict[str, tuple[str, float]] = {SHORT_OIL: ("SCO", 2.0)}
SHORT_FALLBACK: dict[str, str] = {SHORT_OIL: "TLT"}

MATRIX: dict[str, dict[Quadrant, dict[str, float]]] = {
    "CONS": {
        G: {"SPY": 0.40, "IEF": 0.40, "GLD": 0.20},
        R: {**{k: round(v * 0.7, 3) for k, v in _MOD_R.items()}, "SHY": 0.30},
        Q_S: {"SHY": 0.60, COND_DURATION: 0.40},
        D: {"TLT": 0.40, "SHY": 0.25, "GLD": 0.25, "SPY": 0.10},
    },
    "MOD": {
        G: {"QQQ": 0.70, "IEF": 0.30},
        R: dict(_MOD_R),
        Q_S: {"SHY": 0.50, COND_DURATION: 0.50},
        D: {"TLT": 0.35, SHORT_OIL: 0.10, "GLD": 0.30, "XLP": 0.15, "SPY": 0.10},
    },
    "AGG": {
        G: {"QLD": 1.00},
        R: {"QLD": 0.30, "XLE": 0.25, "GDX": 0.25, "DBC": 0.20},
        Q_S: {"SHY": 0.40, COND_DURATION: 0.60},
        D: {"TLT": 0.25, SHORT_OIL: 0.15, "TMF": 0.15, "GLD": 0.30, "QQQ": 0.15},
    },
    "VAGG": {
        G: {"TQQQ": 1.00},
        R: {"TQQQ": 0.30, "ERX": 0.25, "GDX": 0.25, "DBC": 0.20},
        Q_S: {"SHY": 0.30, COND_DURATION: 0.70},
        D: {"TMF": 0.35, "TLT": 0.05, SHORT_OIL: 0.15, "GLD": 0.30, "QLD": 0.15},
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
    """Concrete tickers the ledger may hold (placeholders resolved)."""
    out: set[str] = set()
    for tier in MATRIX.values():
        for weights in tier.values():
            out.update(weights)
    out.discard(COND_DURATION)
    for placeholder, (etf, _lev) in SHORT_IMPL.items():
        out.discard(placeholder)
        out.add(etf)
        out.add(SHORT_FALLBACK[placeholder])
    out.update({"TLT", "SHY"})
    return sorted(out)


def resolve_allocation(
    tier: str,
    quadrant: Quadrant,
    tlt_trend_up: bool | None = None,
    commodity_momentum: dict[str, float] | None = None,
    include_shorts: bool | None = None,
) -> dict[str, float]:
    """Concrete weights for a tier/quadrant given the resolution signals.

    - COND_DURATION -> TLT if tlt_trend_up else SHY (None fails closed to SHY)
    - Short placeholders (include_shorts defaults to the module-level
      INCLUDE_SHORTS switch): ON -> inverse ETF at weight/leverage plus
      SHY for the remainder; OFF -> the long fallback (v4 cells).
    - In REFLATION, the tier's commodity trio is reweighted by momentum
      rank when commodity_momentum covers all three assets.
    """
    if include_shorts is None:
        include_shorts = INCLUDE_SHORTS
    base = dict(MATRIX[tier][quadrant])
    if COND_DURATION in base:
        w = base.pop(COND_DURATION)
        bond = "TLT" if tlt_trend_up else "SHY"
        base[bond] = round(base.get(bond, 0.0) + w, 4)
    for placeholder, (etf, leverage) in SHORT_IMPL.items():
        if placeholder not in base:
            continue
        w = base.pop(placeholder)
        if include_shorts:
            inv = round(w / leverage, 4)
            base[etf] = round(base.get(etf, 0.0) + inv, 4)
            if w - inv > 1e-9:
                base["SHY"] = round(base.get("SHY", 0.0) + (w - inv), 4)
        else:
            fallback = SHORT_FALLBACK[placeholder]
            base[fallback] = round(base.get(fallback, 0.0) + w, 4)
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
