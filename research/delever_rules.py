"""Fragile-month de-levering rules (pre-declared absolute thresholds), full
tiers, modern era. One notch = TQQQ->QLD, QLD->QQQ (VAGG/AGG equity leg in
G and R cells only). Nothing goes to cash — the rule changes leverage, not
exposure."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
from research.engine import load_all, build, headline

px = load_all()
feat = pd.read_csv("research/cache/crash_fingerprint_modern.csv", index_col=0, parse_dates=True)
DOWN = {"TQQQ": "QLD", "QLD": "QQQ"}
DOWN2 = {"TQQQ": "QQQ", "QLD": "QQQ"}

def notch(w, table):
    out = {}
    for a, wt in w.items():
        out[table.get(a, a)] = out.get(table.get(a, a), 0.0) + wt
    return out

def make(cond, table=DOWN):
    def t(tier, st, lab, w):
        if lab in ("G", "R") and st in feat.index and cond(feat.loc[st]):
            return notch(w, table)
        return w
    return t

RULES = {
    "baseline v8": None,
    "R1 re-entry month 1 -> one notch": make(lambda f: f.since_reentry == 1),
    "R2 rvol20 > 20% -> one notch": make(lambda f: f.rvol20 > 0.20),
    "R3 ext < 3% AND rvol20 > 16% -> one notch": make(lambda f: (f.ext < 0.03) and (f.rvol20 > 0.16)),
    "R4 breadth < 40% -> one notch": make(lambda f: f.breadth < 0.40),
    "R5 rvol20 > 25% -> two notches": make(lambda f: f.rvol20 > 0.25, DOWN2),
    "R6 ext < 3% OR rvol20 > 20% -> one notch": make(lambda f: (f.ext < 0.03) or (f.rvol20 > 0.20)),
}
print(f"{'rule':<44} {'AGG CAGR/Sortino/DD':>24}   {'VAGG CAGR/Sortino/DD':>24}   fired")
for name, tr in RULES.items():
    rets, q, td, months = build(px, transform=tr)
    fired = sum(1 for st in feat.index if tr is not None and tr("VAGG", st, "G", {"TQQQ": 1.0}) != {"TQQQ": 1.0})
    a, v = headline(td["AGG"]), headline(td["VAGG"])
    print(f"{name:<44} {a['CAGR']:+.1%} / {a['Sortino']:.2f} / {a['maxDD']:.0%}      "
          f"{v['CAGR']:+.1%} / {v['Sortino']:.2f} / {v['maxDD']:.0%}      {fired}/{len(feat)}")
