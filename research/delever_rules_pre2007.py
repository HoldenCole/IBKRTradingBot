import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
from research.engine_pre2007 import load_all, build, features, headline
px = load_all(); rets, q, td, months = build(px); feat = features(px, months)
DOWN = {"NDX3": "NDX2", "NDX2": "NDX"}; DOWN2 = {"NDX3": "NDX", "NDX2": "NDX"}
def notch(w, table):
    out = {}
    for a, wt in w.items(): out[table.get(a, a)] = out.get(table.get(a, a), 0.0) + wt
    return out
def make(cond, table=DOWN):
    def t(tier, st, lab, w):
        if lab in ("G","R") and st in feat.index and cond(feat.loc[st]): return notch(w, table)
        return w
    return t
RULES = {
    "baseline": None,
    "R1 re-entry month 1 -> one notch": make(lambda f: f.since_reentry == 1),
    "R2 rvol20 > 20% -> one notch": make(lambda f: f.rvol20 > 0.20),
    "R3 ext < 3% AND rvol20 > 16% -> one notch": make(lambda f: (f.ext < 0.03) and (f.rvol20 > 0.16)),
    "R4 breadth < 40% -> one notch": make(lambda f: f.breadth < 0.40),
    "R5 rvol20 > 25% -> two notches": make(lambda f: f.rvol20 > 0.25, DOWN2),
    "R6 ext < 3% OR rvol20 > 20% -> one notch": make(lambda f: (f.ext < 0.03) or (f.rvol20 > 0.20)),
}
crash = feat[feat.next_spy <= -0.05]
print(f"PRE-2007 risk-on month-ends n={len(feat)}, crash months {len(crash)}; crash-month mean pctile: "
      f"ext {feat.ext.rank(pct=True)[crash.index].mean()*100:.0f}, rvol {feat.rvol20.rank(pct=True)[crash.index].mean()*100:.0f}, "
      f"breadth {feat.breadth.rank(pct=True)[crash.index].mean()*100:.0f}; month-1 crash rate {100*(feat[feat.since_reentry==1].next_spy<=-0.05).mean():.0f}% vs all {100*(feat.next_spy<=-0.05).mean():.0f}%")
print(f"{'rule':<44} {'AGG CAGR/Sortino/DD':>24}   {'VAGG CAGR/Sortino/DD':>24}   fired")
for name, tr in RULES.items():
    rets, q, td, months = build(px, transform=tr)
    fired = sum(1 for st in feat.index if tr is not None and tr("VAGG", st, "G", {"NDX3": 1.0}) != {"NDX3": 1.0})
    a, v = headline(td["AGG"]), headline(td["VAGG"])
    print(f"{name:<44} {a['CAGR']:+.1%} / {a['Sortino']:.2f} / {a['maxDD']:.0%}      {v['CAGR']:+.1%} / {v['Sortino']:.2f} / {v['maxDD']:.0%}      {fired}/{len(feat)}")
