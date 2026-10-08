"""GDX vs GLD in EVERY gold-holding cell, both eras. For each (tier, quadrant)
cell with a gold slot, set that slot to miners or bullion (everything else
fixed at the current matrix), and report (a) the tier's return/Sharpe in that
cell's own regime months and (b) full-tier CAGR / Sortino / maxDD."""
import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
import research.engine as E, research.engine_pre2007 as P
from research.engine import headline
from src.portfolio import matrix
from src.regime.quadrant import Quadrant
G, R, S, D = Quadrant.GROWTH, Quadrant.REFLATION, Quadrant.STAGFLATION, Quadrant.DEFLATION
QN = {G: "G", R: "R", S: "S", D: "D"}
CACHE = Path("research/cache")
def c(name): return pd.read_csv(CACHE / f"{name}.csv", index_col=0, parse_dates=True).iloc[:, 0]

def cell_stats(daily, labels, lab):
    """annualized return / Sharpe of the tier's daily series within regime-lab months."""
    on = pd.Series([ (labels.index[labels.index < d][-1] if len(labels.index[labels.index < d]) else None) for d in daily.index], index=daily.index)
    mask = on.map(lambda st: labels.loc[st] == lab if st is not None else False)
    r = daily[mask.values]
    if len(r) < 20: return float("nan"), float("nan"), 0
    mo = (1 + r).resample("ME").prod() - 1; mo = mo[mo != 0]
    return float(mo.mean() * 12), float(mo.mean() / mo.std() * np.sqrt(12)), len(mo)

CELLS = [("CONS", G), ("CONS", R), ("CONS", D), ("MOD", R), ("MOD", D), ("AGG", R), ("AGG", D), ("VAGG", R), ("VAGG", D)]

# ---------------- modern ----------------
px = E.load_all()
ORIG_M, ORIG_T = copy.deepcopy(matrix.MATRIX), copy.deepcopy(matrix.R_TILT)
def set_modern(tier, quad, inst):
    matrix.MATRIX.clear(); matrix.MATRIX.update(copy.deepcopy(ORIG_M))
    matrix.R_TILT.clear(); matrix.R_TILT.update(copy.deepcopy(ORIG_T))
    cell = matrix.MATRIX[tier][quad]
    cur = "GLD" if "GLD" in cell else "GDX"
    if cur != inst:
        w = cell.pop(cur); cell[inst] = w
        if quad is R:
            matrix.R_TILT[tier] = [inst if a == cur else a for a in matrix.R_TILT[tier]]
print("=" * 100); print("MODERN 2007-2026 — per cell: GLD (bullion) vs GDX (miners); cell-month ann return / Sharpe | full-tier CAGR / Sortino / maxDD"); print("=" * 100)
results_modern = {}
for tier, quad in CELLS:
    row = {}
    for inst in ["GLD", "GDX"]:
        set_modern(tier, quad, inst)
        _, _, td, months = E.build(px)
        labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
        cr, cs, n = cell_stats(td[tier], labels, QN[quad]); h = headline(td[tier])
        row[inst] = (cr, cs, n, h)
    results_modern[(tier, QN[quad])] = row
    cur = "GLD" if "GLD" in ORIG_M[tier][quad] else "GDX"
    line = f"  {tier:>4} {QN[quad]} (now {cur}): "
    for inst in ["GLD", "GDX"]:
        cr, cs, n, h = row[inst]
        line += f"{inst}: cell {cr:+6.1%}/{cs:4.2f}  tier {h['CAGR']:+.1%}/{h['Sortino']:.2f}/{h['maxDD']:.0%}   "
    print(line)
matrix.MATRIX.clear(); matrix.MATRIX.update(ORIG_M); matrix.R_TILT.clear(); matrix.R_TILT.update(ORIG_T)

# ---------------- pre-2007 ----------------
opx = P.load_all(); opx["CEF"] = c("CEF").reindex(opx.index)
ORIG_C = copy.deepcopy(P.CELLS)
GOLD_PROXIES = {"FKRCX", "FSAGX", "CEF"}
def set_old(tier, quad, inst):
    P.CELLS.clear(); P.CELLS.update(copy.deepcopy(ORIG_C))
    cell = P.CELLS[tier][quad]
    cur = next(a for a in cell if a in GOLD_PROXIES)
    if cur != inst:
        w = cell.pop(cur); cell[inst] = w
print("\n" + "=" * 100); print("PRE-2007 1987-2006 — per cell: CEF (bullion) vs FSAGX (miners); baseline cells used FKRCX (a miners fund) as 'gold' outside AGG/VAGG R"); print("=" * 100)
results_old = {}
for tier, quad in CELLS:
    row = {}
    for inst in ["CEF", "FSAGX"]:
        set_old(tier, quad, inst)
        _, _, otd, omonths = P.build(opx)
        labels = pd.Series({st: lab for st, lab, w in omonths}).sort_index()
        cr, cs, n = cell_stats(otd[tier], labels, QN[quad]); h = headline(otd[tier])
        row[inst] = (cr, cs, n, h)
    results_old[(tier, QN[quad])] = row
    cur = next(a for a in ORIG_C[tier][quad] if a in GOLD_PROXIES)
    line = f"  {tier:>4} {QN[quad]} (was {cur}): "
    for inst in ["CEF", "FSAGX"]:
        cr, cs, n, h = row[inst]
        line += f"{inst:>5}: cell {cr:+6.1%}/{cs:4.2f}  tier {h['CAGR']:+.1%}/{h['Sortino']:.2f}/{h['maxDD']:.0%}   "
    print(line)
P.CELLS.clear(); P.CELLS.update(ORIG_C)

print("\n" + "=" * 100); print("VERDICT per cell (winner must beat on full-tier Sortino in BOTH eras; ties -> keep current)"); print("=" * 100)
for tier, quad in CELLS:
    m, o = results_modern[(tier, QN[quad])], results_old[(tier, QN[quad])]
    dm = m["GDX"][3]["Sortino"] - m["GLD"][3]["Sortino"]; do = o["FSAGX"][3]["Sortino"] - o["CEF"][3]["Sortino"]
    dmc = m["GDX"][3]["CAGR"] - m["GLD"][3]["CAGR"]; doc = o["FSAGX"][3]["CAGR"] - o["CEF"][3]["CAGR"]
    cur = "GLD" if "GLD" in ORIG_M[tier][quad] else "GDX"
    if dm > 0.005 and do > 0.005: win = "MINERS (GDX)"
    elif dm < -0.005 and do < -0.005: win = "BULLION (GLD)"
    else: win = "era-split -> keep current"
    print(f"  {tier:>4} {QN[quad]}: now {cur:<3}  miners-minus-bullion Sortino: modern {dm:+.2f} / pre-2007 {do:+.2f}   CAGR: {dmc*100:+.1f}pp / {doc*100:+.1f}pp   -> {win}")
