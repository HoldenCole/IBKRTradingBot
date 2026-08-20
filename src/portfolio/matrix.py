"""Playbook matrix v2 — locked allocation per (risk tier, quadrant).

Design rule (PORTFOLIOS.md): MOD defines WHAT each regime owns; CONS
dilutes with cash; AGG/VAGG escalate octane only (QQQ->QLD->TQQQ,
GLD->GDX, XLE->ERX 2x, TLT->TMF). All tickers are real ETFs so the
paper ledger can be marked to market without simulation.

The IBS options overlay for AGG/VAGG is a separate strategy sleeve and
is NOT part of this rotation ledger.
"""

from __future__ import annotations

from src.regime.quadrant import Quadrant

G, R, Q_S, D = Quadrant.GROWTH, Quadrant.REFLATION, Quadrant.STAGFLATION, Quadrant.DEFLATION

_MOD_R = {"SPY": 0.30, "XLE": 0.25, "GLD": 0.25, "DBC": 0.20}

MATRIX_VERSION = "v2"

MATRIX: dict[str, dict[Quadrant, dict[str, float]]] = {
    "CONS": {
        G: {"SPY": 0.40, "IEF": 0.40, "GLD": 0.20},
        R: {**{k: round(v * 0.7, 3) for k, v in _MOD_R.items()}, "SHY": 0.30},
        Q_S: {"SHY": 0.70, "GLD": 0.15, "XLP": 0.15},
        D: {"TLT": 0.45, "SHY": 0.35, "XLP": 0.20},
    },
    "MOD": {
        G: {"QQQ": 0.70, "IEF": 0.30},
        R: dict(_MOD_R),
        Q_S: {"SHY": 0.60, "GLD": 0.20, "XLP": 0.20},
        D: {"TLT": 0.55, "XLP": 0.25, "GLD": 0.20},
    },
    "AGG": {
        G: {"QLD": 1.00},
        R: {"QLD": 0.30, "XLE": 0.25, "GDX": 0.25, "DBC": 0.20},
        Q_S: {"SHY": 0.50, "GLD": 0.25, "XLE": 0.25},
        D: {"TLT": 0.60, "TMF": 0.20, "GLD": 0.20},
    },
    "VAGG": {
        G: {"TQQQ": 1.00},
        R: {"TQQQ": 0.30, "ERX": 0.25, "GDX": 0.25, "DBC": 0.20},
        Q_S: {"SHY": 0.40, "GLD": 0.30, "XLE": 0.30},
        D: {"TMF": 0.50, "TLT": 0.30, "GLD": 0.20},
    },
}

TIERS = list(MATRIX)


def all_tickers() -> list[str]:
    out: set[str] = set()
    for tier in MATRIX.values():
        for weights in tier.values():
            out.update(weights)
    return sorted(out)


def allocation(tier: str, quadrant: Quadrant) -> dict[str, float]:
    return dict(MATRIX[tier][quadrant])
