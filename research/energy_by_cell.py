"""ERX on the same premises as the gold study: what is the right ENERGY
instrument in each energy-holding cell, both eras, on the v9 baseline.
Long slot (R cells): 1x energy equities (XLE / FSENX), 2x energy equities
(ERX sim / FSENX2), 1x oil-commodity (USO / GSCI), 2x oil-commodity (sim).
Short slot (S cells): 2x inverse energy equities (ERY, current), 1x inverse
energy equities, 2x inverse oil (SCO / SH_CO-2x). Plus beta decomposition
and ERX real-vs-sim validation."""
import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
import research.engine as E, research.engine_pre2007 as P
from research.engine import headline
from src.portfolio import matrix
from src.portfolio.matrix import SHORT_ENERGY
from src.regime.quadrant import Quadrant
G, R, S, D = Quadrant.GROWTH, Quadrant.REFLATION, Quadrant.STAGFLATION, Quadrant.DEFLATION
QN = {G: "G", R: "R", S: "S", D: "D"}
CACHE = Path("research/cache")
def c(name): return pd.read_csv(CACHE / f"{name}.csv", index_col=0, parse_dates=True).iloc[:, 0]
def ols(y, X):
    A = np.column_stack([np.ones(len(y))] + [X[k].values for k in X]); b, *_ = np.linalg.lstsq(A, y.values, rcond=None)
    return b, 1 - (y.values - A @ b).var() / y.values.var()
def monthly(s): return s.resample("ME").last().pct_change().dropna()
def cell_stats(daily, labels, lab):
    on = pd.Series([(labels.index[labels.index < d][-1] if len(labels.index[labels.index < d]) else None) for d in daily.index], index=daily.index)
    mask = on.map(lambda st: labels.loc[st] == lab if st is not None else False); r = daily[mask.values]
    if len(r) < 20: return float("nan"), float("nan")
    mo = (1 + r).resample("ME").prod() - 1; mo = mo[mo != 0]
    return float(mo.mean() * 12), float(mo.mean() / mo.std() * np.sqrt(12))

# ---- modern data: add real ERX, UCO; synthetic 2x oil ----
px = E.load_all()
for sym in ["ERX_real", "UCO"]:
    try: px[sym] = c(sym).reindex(px.index)
    except Exception: pass
rets0, _, td0, months0 = E.build(px)
print("=" * 100); print("MODERN — v9 baseline reproduced by engine:"); print("=" * 100)
for t in matrix.TIERS:
    h = headline(td0[t]); print(f"  {t:>4}: {h['CAGR']:+.1%} / {h['Sortino']:.2f} / {h['maxDD']:.0%}")
M = {k: monthly(px[k].dropna()) for k in ["XLE", "USO", "SPY", "TLT", "DBC", "GLD"]}
df = pd.DataFrame({k: M[k] for k in ["XLE", "USO", "SPY", "TLT"]}).dropna().loc["2007-01-31":]
b, r2 = ols(df.XLE, df[["USO", "SPY", "TLT"]])
print(f"\nA) XLE = {b[0]*12:+.1%}/yr + {b[1]:.2f}*USO + {b[2]:.2f}*SPY + {b[3]:.2f}*TLT   R2 {r2:.2f}   corr(XLE,SPY) {df.XLE.corr(df.SPY):+.2f}  corr(USO,SPY) {df.USO.corr(df.SPY):+.2f}")
down = df[df.SPY <= -0.03]; print(f"   SPY down≥3% months (n={len(down)}): SPY {down.SPY.mean():+.1%}  XLE {down.XLE.mean():+.1%}  USO {down.USO.mean():+.1%}")
if "ERX_real" in px:
    rf = (px["^IRX"] / 100 / 252).reindex(px.index).ffill().fillna(0.0)
    sim = (2 * px["XLE"].pct_change() - (rf + 0.01/252) - 0.0095/252)
    real = px["ERX_real"].pct_change()
    u = pd.DataFrame({"real": (1 + real).resample("ME").prod() - 1, "sim": (1 + sim).resample("ME").prod() - 1}).dropna().loc["2020-04-01":]
    print(f"E) ERX real vs 2x-XLE sim since Apr 2020 (2x era): n={len(u)} corr {u.real.corr(u.sim):.3f}  mean real {u.real.mean()*12:+.1%}/yr vs sim {u.sim.mean()*12:+.1%}/yr  tracking {(u.real-u.sim).std()*np.sqrt(12):.1%}")

# synthetic instruments injected as pseudo-prices
rf = (px["^IRX"] / 100 / 252).reindex(px.index).ffill().fillna(0.0)
r_ = px.pct_change()
px["USO2"] = (1 + (2 * r_["USO"] - (rf + 0.01/252) - 0.0095/252).fillna(0)).cumprod()
px["XLE_SH1"] = (1 + (-r_["XLE"] + 2*rf - 0.02/252).fillna(0)).cumprod()        # 1x inverse energy equities
ORIG_M, ORIG_T = copy.deepcopy(matrix.MATRIX), copy.deepcopy(matrix.R_TILT)
LONG_CELLS = [("CONS", R, "XLE"), ("MOD", R, "XLE"), ("AGG", R, "ERX"), ("VAGG", R, "ERX")]
LONG_INST = ["XLE", "ERX", "USO", "USO2"]
def reset():
    matrix.MATRIX.clear(); matrix.MATRIX.update(copy.deepcopy(ORIG_M)); matrix.R_TILT.clear(); matrix.R_TILT.update(copy.deepcopy(ORIG_T))
print("\n" + "=" * 100); print("B) MODERN long energy slot per Reflation cell: cell-month ann ret / Sharpe | full-tier CAGR / Sortino / maxDD"); print("=" * 100)
res_m = {}
for tier, quad, cur in LONG_CELLS:
    row = {}
    for inst in LONG_INST:
        reset(); cell = matrix.MATRIX[tier][quad]
        if inst != cur:
            w = cell.pop(cur); cell[inst] = w; matrix.R_TILT[tier] = [inst if a == cur else a for a in matrix.R_TILT[tier]]
        _, _, td, months = E.build(px); labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
        row[inst] = (*cell_stats(td[tier], labels, "R"), headline(td[tier]))
    res_m[tier] = row
    print(f"  {tier:>4} R (now {cur}): " + "   ".join(f"{i}: {v[0]:+6.1%}/{v[1]:4.2f} | {v[2]['CAGR']:+.1%}/{v[2]['Sortino']:.2f}/{v[2]['maxDD']:.0%}" for i, v in row.items()))
reset()
# short slot in S cells
print("\nC) MODERN short energy slot per Stagflation cell (MOD/AGG/VAGG): ERY 2x inverse eq (current) vs 1x inverse eq vs SCO 2x inverse oil")
SHORT_INST = {"ERY": None, "XLE_SH1": "XLE_SH1", "SCO": "SCO"}
res_ms = {}
for tier in ["MOD", "AGG", "VAGG"]:
    row = {}
    for name, inst in SHORT_INST.items():
        reset()
        if inst is not None:
            from src.portfolio import matrix as mx
            mx.SHORT_IMPL[SHORT_ENERGY] = (inst, 2.0 if inst == "SCO" else 1.0)
        _, _, td, months = E.build(px); labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
        row[name] = (*cell_stats(td[tier], labels, "S"), headline(td[tier]))
        matrix.SHORT_IMPL[SHORT_ENERGY] = ("ERY", 2.0)
    res_ms[tier] = row
    print(f"  {tier:>4} S: " + "   ".join(f"{i}: {v[0]:+6.1%}/{v[1]:4.2f} | {v[2]['CAGR']:+.1%}/{v[2]['Sortino']:.2f}/{v[2]['maxDD']:.0%}" for i, v in row.items()))
reset(); matrix.SHORT_IMPL[SHORT_ENERGY] = ("ERY", 2.0)

# ---- pre-2007 ----
opx = P.load_all()
orets, _, otd0, omonths0 = P.build(opx)
print("\n" + "=" * 100); print("PRE-2007 — v9-analog baseline:"); print("=" * 100)
for t in P.CELLS:
    h = headline(otd0[t]); print(f"  {t:>4}: {h['CAGR']:+.1%} / {h['Sortino']:.2f} / {h['maxDD']:.0%}")
OM = {k: monthly(opx[k].dropna()).loc["1987-01-01":"2006-12-31"] for k in ["FSENX", "GSCI", "VFINX", "VUSTX"]}
d = pd.DataFrame(OM).dropna(); b, r2 = ols(d.FSENX, d[["GSCI", "VFINX", "VUSTX"]])
print(f"\nA) FSENX = {b[0]*12:+.1%}/yr + {b[1]:.2f}*GSCI + {b[2]:.2f}*VFINX + {b[3]:.2f}*VUSTX   R2 {r2:.2f}   corr(FSENX,S&P) {d.FSENX.corr(d.VFINX):+.2f}  corr(GSCI,S&P) {d.GSCI.corr(d.VFINX):+.2f}")
down = d[d.VFINX <= -0.03]; print(f"   S&P down≥3% months (n={len(down)}): S&P {down.VFINX.mean():+.1%}  FSENX {down.FSENX.mean():+.1%}  GSCI {down.GSCI.mean():+.1%}")
orf = (opx["IRX"] / 100 / 252).reindex(opx.index).ffill().fillna(0.0); r_ = opx.pct_change()
opx["GSCI2"] = (1 + (2 * r_["GSCI"] - (orf + 0.01/252) - 0.0095/252).fillna(0)).cumprod()
opx["FSENX2P"] = (1 + (2 * r_["FSENX"] - (orf + 0.01/252) - 0.0095/252).fillna(0)).cumprod()  # pseudo-price for 2x energy eq
opx["SH_EN2P"] = (1 + (-2 * r_["FSENX"] + 3*orf - 0.02/252).fillna(0)).cumprod()           # 2x inverse energy eq
opx["SH_CO2P"] = (1 + (-2 * r_["GSCI"] + 3*orf - 0.02/252).fillna(0)).cumprod()            # 2x inverse commodity
ORIG_C = copy.deepcopy(P.CELLS)
def oreset(): P.CELLS.clear(); P.CELLS.update(copy.deepcopy(ORIG_C))
OLONG = [("CONS", "FSENX"), ("MOD", "FSENX"), ("AGG", "FSENX2"), ("VAGG", "FSENX2")]
OINST = {"FSENX": "FSENX", "FSENX2": "FSENX2P", "GSCI": "GSCI", "GSCI2": "GSCI2"}
print("\nB) PRE-2007 long energy slot per Reflation cell:")
res_o = {}
for tier, cur in OLONG:
    row = {}
    for name, inst in OINST.items():
        oreset(); cell = P.CELLS[tier][R]
        if inst != cur and name != cur:
            w = cell.pop(cur); cell[inst] = cell.get(inst, 0) + w
        _, _, otd, om = P.build(opx); labels = pd.Series({st: lab for st, lab, w in om}).sort_index()
        row[name] = (*cell_stats(otd[tier], labels, "R"), headline(otd[tier]))
    res_o[tier] = row
    print(f"  {tier:>4} R (now {cur}): " + "   ".join(f"{i}: {v[0]:+6.1%}/{v[1]:4.2f} | {v[2]['CAGR']:+.1%}/{v[2]['Sortino']:.2f}/{v[2]['maxDD']:.0%}" for i, v in row.items()))
oreset()
print("\nC) PRE-2007 short energy slot per Stagflation cell: SH_EN 1x inverse eq (baseline proxy) vs 2x inverse eq vs 2x inverse commodity")
OSHORT = {"SH_EN(1x)": "SH_EN", "SH_EN2": "SH_EN2P", "SH_CO2": "SH_CO2P"}
res_os = {}
for tier in ["MOD", "AGG", "VAGG"]:
    row = {}
    for name, inst in OSHORT.items():
        oreset(); cell = P.CELLS[tier][S]
        if inst != "SH_EN":
            w = cell.pop("SH_EN"); cell[inst] = w
        _, _, otd, om = P.build(opx); labels = pd.Series({st: lab for st, lab, w in om}).sort_index()
        row[name] = (*cell_stats(otd[tier], labels, "S"), headline(otd[tier]))
    res_os[tier] = row
    print(f"  {tier:>4} S: " + "   ".join(f"{i}: {v[0]:+6.1%}/{v[1]:4.2f} | {v[2]['CAGR']:+.1%}/{v[2]['Sortino']:.2f}/{v[2]['maxDD']:.0%}" for i, v in row.items()))
oreset()
print("\n" + "=" * 100); print("VERDICTS (full-tier Sortino vs current, both eras; threshold 0.005)"); print("=" * 100)
pairs = {"XLE": "FSENX", "ERX": "FSENX2", "USO": "GSCI", "USO2": "GSCI2"}
for tier, quad, cur in LONG_CELLS:
    ocur = dict(OLONG)[tier]
    base_m = res_m[tier][cur][2]["Sortino"]; base_o = res_o[tier][ocur][2]["Sortino"]
    for inst in LONG_INST:
        if inst == cur: continue
        dm = res_m[tier][inst][2]["Sortino"] - base_m; do = res_o[tier][pairs[inst]][2]["Sortino"] - base_o
        dmc = res_m[tier][inst][2]["CAGR"] - res_m[tier][cur][2]["CAGR"]; doc = res_o[tier][pairs[inst]][2]["CAGR"] - res_o[tier][ocur][2]["CAGR"]
        tag = "BOTH ERAS BETTER" if dm > 0.005 and do > 0.005 else "both worse" if dm < -0.005 and do < -0.005 else "era-split"
        print(f"  {tier:>4} R: {cur} -> {inst:<5} Sortino {dm:+.2f} / {do:+.2f}   CAGR {dmc*100:+.1f}pp / {doc*100:+.1f}pp   -> {tag}")
spairs = {"XLE_SH1": "SH_EN(1x)", "SCO": "SH_CO2"}
for tier in ["MOD", "AGG", "VAGG"]:
    bm = res_ms[tier]["ERY"][2]["Sortino"]; bo = res_os[tier]["SH_EN2"][2]["Sortino"]  # pre-2007 analog of ERY = 2x inverse eq
    for inst, oi in spairs.items():
        dm = res_ms[tier][inst][2]["Sortino"] - bm; do = res_os[tier][oi][2]["Sortino"] - bo
        tag = "BOTH ERAS BETTER" if dm > 0.005 and do > 0.005 else "both worse" if dm < -0.005 and do < -0.005 else "era-split"
        print(f"  {tier:>4} S: ERY -> {inst:<8} Sortino {dm:+.2f} / {do:+.2f}   -> {tag}")
