"""Pre-2007 (1987-2006) replication engine — the out-of-sample era.
Proxies: VFINX (SPY), ^NDX (QQQ; NDX2/NDX3 simulated), VUSTX (TLT; VUSTX3
simulated), FKRCX (GLD), FSENX (XLE; FSENX2 simulated), FSAGX (GDX),
FDFAX (XLP), ^SPGSCI (DBC), ^IRX cash. Cells mirror the live matrix at v8
(AGG R = 1x equity + 2x energy). Shorts synthetic. Same transform hook as
research.engine so rules can be era-checked with identical code."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
from src.regime.quadrant import Quadrant, quadrant_series
from research.engine import headline, QMAP  # noqa: F401

CACHE = Path(__file__).resolve().parent / "cache"
G, R, S, D = Quadrant.GROWTH, Quadrant.REFLATION, Quadrant.STAGFLATION, Quadrant.DEFLATION
def load(sym): return pd.read_csv(CACHE / f"long_{sym.replace('^','')}.csv", index_col=0, parse_dates=True).iloc[:, 0]
SECTORS = ["FSPTX", "FSELX", "FBIOX", "FSRPX", "FIDSX", "FSPHX", "FSUTX", "FSDPX", "FSCSX",
           "FSRFX", "FSCHX", "FDLSX", "FSHOX", "FSTCX", "FSAVX", "FSENX"]

CELLS = {
 "CONS": {G: {"VFINX":.40,"VUSTX":.40,"FKRCX":.20}, R: {"VFINX":.21,"FSENX":.175,"FKRCX":.175,"GSCI":.14,"CASH":.30},
          S: {"CASH":.60,"COND":.40}, D: {"VUSTX":.40,"CASH":.25,"FKRCX":.25,"VFINX":.10}},
 "MOD":  {G: {"NDX":.70,"VUSTX":.30}, R: {"VFINX":.30,"FSENX":.25,"FKRCX":.25,"GSCI":.20},
          S: {"CASH":.40,"SH_EN":.10,"COND":.50}, D: {"VUSTX":.35,"SH_CO":.10,"FKRCX":.30,"FDFAX":.15,"VFINX":.10}},
 "AGG":  {G: {"NDX2":1.0}, R: {"NDX":.30,"FSENX2":.25,"FSAGX":.25,"GSCI":.20},
          S: {"CASH":.25,"SH_EN":.15,"COND":.60}, D: {"VUSTX":.25,"SH_CO":.15,"VUSTX3":.15,"FKRCX":.30,"NDX":.15}},
 "VAGG": {G: {"NDX3":1.0}, R: {"NDX3":.30,"FSENX2":.25,"FSAGX":.25,"GSCI":.20},
          S: {"CASH":.15,"SH_EN":.15,"COND":.70}, D: {"VUSTX3":.35,"VUSTX":.05,"SH_CO":.15,"FKRCX":.30,"NDX2":.15}},
}

def load_all():
    syms = ["VFINX", "VUSTX", "FKRCX", "FSENX", "FDFAX", "FSAGX", "SPGSCI", "NDX", "IRX", "GSPC"] + SECTORS
    px = pd.DataFrame({s: load(s) for s in syms}).sort_index()
    return px.rename(columns={"SPGSCI": "GSCI"})

def build(px, start="1987-01-01", end="2006-12-31", transform=None):
    rets = px.drop(columns=["IRX"]).pct_change()
    rf = (px["IRX"] / 100 / 252).reindex(rets.index).ffill().fillna(0.0)
    rets["CASH"] = rf
    def lev(b, n): return n * rets[b] - (n - 1) * (rf + 0.01/252) - 0.0095/252
    rets["NDX2"] = lev("NDX", 2); rets["NDX3"] = lev("NDX", 3); rets["VUSTX3"] = lev("VUSTX", 3); rets["FSENX2"] = lev("FSENX", 2)
    rets["SH_EN"] = -rets["FSENX"] + 2*rf - 0.02/252; rets["SH_CO"] = -rets["GSCI"] + 2*rf - 0.02/252
    q = quadrant_series(px["VFINX"].dropna(), px["GSCI"].dropna())
    vustx_m = px["VUSTX"].resample("ME").last()
    me = q.index; td, months = {}, []
    for tier in CELLS:
        parts = []
        for i, st in enumerate(me):
            if st < pd.Timestamp(start) or st > pd.Timestamp(end): continue
            quad = q.loc[st]; h = vustx_m.loc[:st].dropna()
            up = bool(h.iloc[-1] > h.tail(10).mean()) if len(h) >= 10 else None
            nxt = me[i+1] if i+1 < len(me) else pd.Timestamp(end)
            win = rets.loc[(rets.index > st) & (rets.index <= nxt)]
            if win.empty: continue
            w = dict(CELLS[tier][quad])
            if "COND" in w:
                x = w.pop("COND"); k = "VUSTX" if up else "CASH"; w[k] = w.get(k, 0) + x
            if transform is not None: w = transform(tier, st, QMAP[quad], dict(w))
            parts.append(sum(win[a].fillna(0.0)*wt for a, wt in w.items()))
            if tier == "CONS": months.append((st, QMAP[quad], w))
        td[tier] = pd.concat(parts)
    return rets, q, td, months

def features(px, months):
    """Same ex-ante features as crash_fingerprint, on VFINX + sector funds."""
    spy = px["VFINX"].dropna(); m = spy.resample("ME").last(); sma10 = m.rolling(10).mean()
    sect_m = {s: px[s].resample("ME").last().dropna() for s in SECTORS if s in px}
    dr = spy.pct_change(); labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
    rows, prev, since = [], None, 0
    for st in labels.index:
        lab = labels.loc[st]
        since = since + 1 if lab in ("G","R") and prev in ("G","R") else (1 if lab in ("G","R") else 0); prev = lab
        if lab not in ("G","R"): continue
        flags = [float(sm.asof(st) > sm.loc[:st].tail(10).mean()) for sm in sect_m.values() if len(sm.loc[:st]) >= 10]
        nxt_idx = labels.index[labels.index > st]; nxt = nxt_idx[0] if len(nxt_idx) else spy.index[-1]
        rows.append(dict(stamp=st, cell=lab, since_reentry=since, breadth=np.mean(flags) if flags else np.nan,
                         ext=float(m.asof(st)/sma10.asof(st)-1), rvol20=float(dr.loc[:st].tail(20).std()*np.sqrt(252)),
                         next_spy=float(spy.asof(nxt)/spy.asof(st)-1)))
    return pd.DataFrame(rows).set_index("stamp")

if __name__ == "__main__":
    px = load_all(); rets, q, td, months = build(px)
    print("window:", td["MOD"].index[0].date(), "->", td["MOD"].index[-1].date())
    for t in CELLS:
        h = headline(td[t]); print(f"  {t:>4}: CAGR {h['CAGR']:+.1%}  Sortino {h['Sortino']:.2f}  maxDD {h['maxDD']:.1%}")
