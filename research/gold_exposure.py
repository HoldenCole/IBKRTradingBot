"""GDX vs GLD vs alternatives: what is the right gold instrument for the
Reflation cell (AGG/VAGG hold GDX 15.75%)? Both eras.
A) beta decomposition of miners on bullion + equities + bonds
B) per-regime leg stats for every candidate
C) full-tier impact of swapping GDX in AGG/VAGG R cells
D) financing-cost angle: miners-minus-bullion spread vs equities/rates
E) UGL (2x gold) real vs simulated"""
import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
import research.engine as E
import research.engine_pre2007 as P
from research.engine import headline
from src.regime.quadrant import Quadrant
CACHE = Path("research/cache")
def c(name): return pd.read_csv(CACHE / f"{name}.csv", index_col=0, parse_dates=True).iloc[:, 0]

def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + [X[k].values for k in X])
    b, *_ = np.linalg.lstsq(X, y.values, rcond=None)
    resid = y.values - X @ b; r2 = 1 - resid.var() / y.values.var()
    return b, r2

def monthly(s): return s.resample("ME").last().pct_change().dropna()

# ---------------- modern ----------------
px = E.load_all()
for sym in ["GDXJ", "SLV", "UGL", "NUGT", "GC_F", "CEF", "IAU"]:
    px[sym] = c(sym).reindex(px.index)
rets, q, td, months = E.build(px)
labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
rf = (px["^IRX"] / 100 / 252).reindex(rets.index).ffill().fillna(0.0)
rets["GLD2"] = 2 * rets["GLD"] - (rf + 0.01/252) - 0.0095/252
rets["GLD3"] = 3 * rets["GLD"] - 2 * (rf + 0.01/252) - 0.0095/252
M = {k: monthly(px[k].dropna()) for k in ["GLD", "GDX", "GDXJ", "SLV", "UGL", "SPY", "TLT", "XLE"]}
M["GLD2"] = (1 + rets["GLD2"]).resample("ME").prod() - 1
M["GLD3"] = (1 + rets["GLD3"]).resample("ME").prod() - 1
start = pd.Timestamp("2007-01-31")
def lab_at(d):
    p = labels.index[labels.index < d]; return labels.loc[p[-1]] if len(p) else None

print("=" * 90); print("A) MODERN beta decomposition (monthly returns, 2007-2026)"); print("=" * 90)
df = pd.DataFrame({k: M[k] for k in ["GDX", "GLD", "SPY", "TLT"]}).dropna().loc[start:]
b, r2 = ols(df.GDX, df[["GLD", "SPY", "TLT"]])
print(f"  GDX = {b[0]*12:+.1%}/yr + {b[1]:.2f}*GLD + {b[2]:.2f}*SPY + {b[3]:.2f}*TLT   R2 {r2:.2f}")
for k in ["GDXJ", "SLV", "UGL"]:
    d = pd.DataFrame({"y": M[k], "GLD": M["GLD"], "SPY": M["SPY"], "TLT": M["TLT"]}).dropna()
    bb, rr = ols(d.y, d[["GLD", "SPY", "TLT"]])
    print(f"  {k:>4} = {bb[0]*12:+.1%}/yr + {bb[1]:.2f}*GLD + {bb[2]:.2f}*SPY + {bb[3]:.2f}*TLT   R2 {rr:.2f}  (from {d.index[0].date()})")
print(f"  corr with SPY: GLD {df.GLD.corr(df.SPY):+.2f}   GDX {df.GDX.corr(df.SPY):+.2f}")
down = df[df.SPY <= -0.03]
print(f"  SPY down ≥3% months (n={len(down)}): SPY {down.SPY.mean():+.1%}  GLD {down.GLD.mean():+.1%}  GDX {down.GDX.mean():+.1%}")
# by regime
lab = pd.Series([lab_at(d) for d in df.index], index=df.index)
for L in ["G", "R", "S", "D"]:
    x = df[lab == L]
    if len(x) > 6:
        print(f"  regime {L} (n={len(x)}): corr(GDX,SPY) {x.GDX.corr(x.SPY):+.2f}  corr(GLD,SPY) {x.GLD.corr(x.SPY):+.2f}  corr(GDX,GLD) {x.GDX.corr(x.GLD):+.2f}")

print("\n" + "=" * 90); print("B) MODERN per-regime leg stats (monthly mean / ann Sharpe / hit)"); print("=" * 90)
cands = ["GLD", "GLD2", "GLD3", "UGL", "GDX", "GDXJ", "SLV"]
allm = pd.DataFrame({k: M[k] for k in cands}).loc[start:]
lab = pd.Series([lab_at(d) for d in allm.index], index=allm.index)
print(f"  {'':>5} " + "  ".join(f"{k:>18}" for k in cands))
for L in ["R", "G", "S", "D", "all"]:
    x = allm if L == "all" else allm[lab == L]
    row = []
    for k in cands:
        v = x[k].dropna()
        row.append(f"{v.mean():+.2%}/{(v.mean()/v.std()*np.sqrt(12)) if v.std() else 0:4.2f}/{100*(v>0).mean():3.0f}%")
    print(f"  {L:>5} " + "  ".join(f"{r:>18}" for r in row) + f"   n={len(x)}")

print("\n" + "=" * 90); print("D) financing-cost angle: (GDX - GLD) monthly spread regressed on SPY and TLT"); print("=" * 90)
sp = (df.GDX - df.GLD)
bb, rr = ols(sp, df[["SPY", "TLT"]])
print(f"  GDX-GLD spread = {bb[0]*12:+.1%}/yr + {bb[1]:.2f}*SPY + {bb[2]:.2f}*TLT   R2 {rr:.2f}   (spread mean {sp.mean()*12:+.1%}/yr, corr w/ SPY {sp.corr(df.SPY):+.2f})")

print("\n" + "=" * 90); print("E) UGL real vs 2x-GLD simulation (monthly, since Jan 2009)"); print("=" * 90)
u = pd.DataFrame({"real": M["UGL"], "sim": M["GLD2"]}).dropna().loc["2009-01-01":]
print(f"  n={len(u)}  corr {u.real.corr(u.sim):.3f}  mean real {u.real.mean()*12:+.1%}/yr vs sim {u.sim.mean()*12:+.1%}/yr  "
      f"ann tracking diff {(u.real-u.sim).std()*np.sqrt(12):.1%}  cum real {(1+u.real).prod()-1:+.0%} vs sim {(1+u.sim).prod()-1:+.0%}")

print("\n" + "=" * 90); print("C) MODERN full-tier impact: AGG/VAGG Reflation cell GDX -> X"); print("=" * 90)
def swap(new):
    def t(tier, st, lab, w):
        if lab == "R" and tier in ("AGG", "VAGG") and "GDX" in w:
            w = dict(w); w[new] = w.get(new, 0.0) + w.pop("GDX")
        return w
    return t
E_rets_extra = {"GLD2": rets["GLD2"], "GLD3": rets["GLD3"], "UGL": rets["UGL"] if "UGL" in rets else None}
# engine's rets lacks GLD2/GLD3 columns during build — inject via px? build recomputes rets; so patch E.build via a wrapper
import types
orig_build = E.build
def build_with_extra(px, first_stamp="2006-12-01", transform=None):
    # monkeypatch: run original, but extra synthetic columns must exist in rets inside build.
    # Simplest: append GLD2/GLD3 as pseudo-price series to px (cumulative) so pct_change reproduces them.
    px2 = px.copy()
    for k, r in [("GLD2", rets["GLD2"]), ("GLD3", rets["GLD3"])]:
        px2[k] = (1 + r.fillna(0)).cumprod()
    return orig_build(px2, first_stamp, transform)
E.build = build_with_extra
base = {t: headline(td[t]) for t in ["AGG", "VAGG"]}
print(f"  {'variant':<30} {'AGG CAGR/Sortino/DD':>24}   {'VAGG CAGR/Sortino/DD':>24}")
print(f"  {'baseline v8 (GDX)':<30} {base['AGG']['CAGR']:+.1%} / {base['AGG']['Sortino']:.2f} / {base['AGG']['maxDD']:.0%}      {base['VAGG']['CAGR']:+.1%} / {base['VAGG']['Sortino']:.2f} / {base['VAGG']['maxDD']:.0%}")
for new in ["GLD", "GLD2", "GLD3", "SLV", "GDXJ"]:
    _, _, td2, _ = E.build(px, transform=swap(new))
    a, v = headline(td2["AGG"]), headline(td2["VAGG"])
    print(f"  {'R: GDX -> ' + new:<30} {a['CAGR']:+.1%} / {a['Sortino']:.2f} / {a['maxDD']:.0%}      {v['CAGR']:+.1%} / {v['Sortino']:.2f} / {v['maxDD']:.0%}")

# ---------------- pre-2007 ----------------
print("\n" + "=" * 90); print("PRE-2007 (1987-2006): bullion proxy = CEF (Central Fund of Canada, gold+silver bullion CEF); miners = FSAGX / FKRCX / ^XAU"); print("=" * 90)
opx = P.load_all()
opx["CEF"] = c("CEF").reindex(opx.index); opx["XAU"] = c("XAU").reindex(opx.index)
orets, oq, otd, omonths = P.build(opx)
olab = pd.Series({st: lab for st, lab, w in omonths}).sort_index()
OM = {k: monthly(opx[k].dropna()).loc["1987-01-01":"2006-12-31"] for k in ["CEF", "FSAGX", "FKRCX", "XAU", "VFINX", "VUSTX"]}
d = pd.DataFrame({k: OM[k] for k in ["FSAGX", "CEF", "VFINX", "VUSTX"]}).dropna()
bb, rr = ols(d.FSAGX, d[["CEF", "VFINX", "VUSTX"]])
print(f"  FSAGX = {bb[0]*12:+.1%}/yr + {bb[1]:.2f}*CEF + {bb[2]:.2f}*VFINX + {bb[3]:.2f}*VUSTX   R2 {rr:.2f}")
d2 = pd.DataFrame({k: OM[k] for k in ["XAU", "CEF", "VFINX", "VUSTX"]}).dropna()
bb, rr = ols(d2.XAU, d2[["CEF", "VFINX", "VUSTX"]])
print(f"  ^XAU  = {bb[0]*12:+.1%}/yr + {bb[1]:.2f}*CEF + {bb[2]:.2f}*VFINX + {bb[3]:.2f}*VUSTX   R2 {rr:.2f}")
print(f"  corr with VFINX: CEF {d.CEF.corr(d.VFINX):+.2f}   FSAGX {d.FSAGX.corr(d.VFINX):+.2f}")
down = d[d.VFINX <= -0.03]
print(f"  S&P down ≥3% months (n={len(down)}): S&P {down.VFINX.mean():+.1%}  CEF {down.CEF.mean():+.1%}  FSAGX {down.FSAGX.mean():+.1%}")
def olab_at(dd):
    p = olab.index[olab.index < dd]; return olab.loc[p[-1]] if len(p) else None
orf = (opx["IRX"] / 100 / 252).reindex(orets.index).ffill().fillna(0.0)
orets["CEF2"] = 2 * orets["CEF"] - (orf + 0.01/252) - 0.0095/252
OM["CEF2"] = (1 + orets["CEF2"]).resample("ME").prod() - 1
ocands = ["CEF", "CEF2", "FSAGX", "FKRCX", "XAU"]
oall = pd.DataFrame({k: OM[k] for k in ocands}).loc["1987-01-31":"2006-12-31"]
ol = pd.Series([olab_at(dd) for dd in oall.index], index=oall.index)
print(f"  {'':>5} " + "  ".join(f"{k:>18}" for k in ocands))
for L in ["R", "G", "S", "D", "all"]:
    x = oall if L == "all" else oall[ol == L]
    row = []
    for k in ocands:
        v = x[k].dropna(); row.append(f"{v.mean():+.2%}/{(v.mean()/v.std()*np.sqrt(12)) if v.std() else 0:4.2f}/{100*(v>0).mean():3.0f}%")
    print(f"  {L:>5} " + "  ".join(f"{r:>18}" for r in row) + f"   n={len(x)}")
sp = d.FSAGX - d.CEF; bb, rr = ols(sp, d[["VFINX", "VUSTX"]])
print(f"  FSAGX-CEF spread = {bb[0]*12:+.1%}/yr + {bb[1]:.2f}*VFINX + {bb[2]:.2f}*VUSTX  R2 {rr:.2f}  (corr w/ S&P {sp.corr(d.VFINX):+.2f})")
# full-tier pre-2007: AGG/VAGG R cell FSAGX -> CEF / CEF2
def oswap(new):
    def t(tier, st, lab, w):
        if lab == "R" and tier in ("AGG", "VAGG") and "FSAGX" in w:
            w = dict(w); w[new] = w.get(new, 0.0) + w.pop("FSAGX")
        return w
    return t
obase = {t: headline(otd[t]) for t in ["AGG", "VAGG"]}
print(f"\n  {'variant':<30} {'AGG CAGR/Sortino/DD':>24}   {'VAGG CAGR/Sortino/DD':>24}")
print(f"  {'baseline (FSAGX miners)':<30} {obase['AGG']['CAGR']:+.1%} / {obase['AGG']['Sortino']:.2f} / {obase['AGG']['maxDD']:.0%}      {obase['VAGG']['CAGR']:+.1%} / {obase['VAGG']['Sortino']:.2f} / {obase['VAGG']['maxDD']:.0%}")
opx2 = opx.copy(); opx2["CEF2"] = (1 + orets["CEF2"].fillna(0)).cumprod()
for new in ["CEF", "CEF2"]:
    _, _, otd2, _ = P.build(opx2, transform=oswap(new))
    a, v = headline(otd2["AGG"]), headline(otd2["VAGG"])
    print(f"  {'R: FSAGX -> ' + new:<30} {a['CAGR']:+.1%} / {a['Sortino']:.2f} / {a['maxDD']:.0%}      {v['CAGR']:+.1%} / {v['Sortino']:.2f} / {v['maxDD']:.0%}")
