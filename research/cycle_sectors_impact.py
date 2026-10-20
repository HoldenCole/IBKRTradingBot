"""Fair-leverage impact of phase-sector baskets: the basket is levered to
the same multiple as the equity leg it replaces (daily-reset simulation,
same cost model as the engine), both eras. Variants: (A) every cell's
equity leg -> phase leader basket; (B) only the Reflation cells' equity
leg -> late-cycle leader basket (energy/materials/healthcare/staples/
utilities), since the grid shows tech lagging in late phase both eras."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
import research.engine as E, research.engine_pre2007 as P
from research.engine import headline
from research.cycle_sectors import MAP, MODERN, OLD, phases, c
LEV = {"SPY": 1, "QQQ": 1, "QLD": 2, "TQQQ": 3, "VFINX": 1, "NDX": 1, "NDX2": 2, "NDX3": 3}

def add_levered_baskets(px, symbols, rf_col):
    """pseudo-price columns B_<phase>_<n>x for n=1,2,3."""
    r = px.pct_change(); rf = (px[rf_col] / 100 / 252).reindex(px.index).ffill().fillna(0.0)
    for phase, (lead, _) in MAP.items():
        basket = r[[symbols[k] for k in lead]].mean(axis=1)
        for n in (1, 2, 3):
            lr = n * basket - (n - 1) * (rf + 0.01 / 252) - (0.0095 / 252 if n > 1 else 0.0)
            px[f"B_{phase}_{n}x"] = (1 + lr.fillna(0)).cumprod()
    return px

def transform_factory(lab_series, only_reflation=False):
    ph = phases(lab_series)
    def t(tier, st, lab, w):
        phase = ph.get(st)
        if phase is None: return w
        if only_reflation and lab != "R": return w
        eq = [(a, v) for a, v in w.items() if a in LEV]
        if not eq: return w
        w = {a: v for a, v in w.items() if a not in LEV}
        use = "late" if only_reflation else phase
        for a, v in eq:
            col = f"B_{use}_{LEV[a]}x"; w[col] = w.get(col, 0.0) + v
        return w
    return t

px = E.load_all()
for k, v in MODERN.items():
    if v not in px: px[v] = c(v).reindex(px.index)
px = add_levered_baskets(px, MODERN, "^IRX")
rets, q, td, months = E.build(px); labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
opx = P.load_all()
for k, v in OLD.items():
    if v not in opx: opx[v] = c(f"long_{v}").reindex(opx.index)
opx = add_levered_baskets(opx, OLD, "IRX")
orets, oq, otd, omonths = P.build(opx); olabels = pd.Series({st: lab for st, lab, w in omonths}).sort_index()
print(f"{'variant':<48} {'MOD':>22} {'AGG':>22} {'VAGG':>22}")
def row(name, tdm, tdo):
    for era, tdd in [("modern", tdm), ("pre-2007", tdo)]:
        print(f"  {name + ' (' + era + ')':<46} " + " ".join(f"{headline(tdd[t])['CAGR']:+.1%}/{headline(tdd[t])['Sortino']:.2f}/{headline(tdd[t])['maxDD']:.0%}".rjust(22) for t in ["MOD", "AGG", "VAGG"]))
row("baseline v9", td, otd)
_, _, tdA, _ = E.build(px, transform=transform_factory(labels)); _, _, otdA, _ = P.build(opx, transform=transform_factory(olabels))
row("A: all cells -> phase basket (lev-matched)", tdA, otdA)
_, _, tdB, _ = E.build(px, transform=transform_factory(labels, only_reflation=True)); _, _, otdB, _ = P.build(opx, transform=transform_factory(olabels, only_reflation=True))
row("B: R cells equity -> late basket (lev-matched)", tdB, otdB)
