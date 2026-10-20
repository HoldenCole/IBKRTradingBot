"""Business-cycle sector rotation (the Fidelity 'business cycle approach')
tested against our regimes, both eras, pre-registered.

Phase definitions (price-based, ex-ante, from our own classifier):
  recession  = S or D months
  early      = first EARLY_N risk-on months (G/R) after an S/D exit
  mid        = G beyond the early window
  late       = R beyond the early window
Fidelity map (predicted leaders / laggards):
  early:     + financials, discretionary, industrials, real estate | - utilities, staples, healthcare, energy
  mid:       + tech, communication/industrials                     | - materials, utilities
  late:      + energy, materials, healthcare, staples, utilities   | - tech, discretionary, financials
  recession: + staples, utilities, healthcare                      | - tech, industrials, discretionary, real estate
Tests: (1) sector excess return vs broad market by phase, both eras;
(2) the 'long right / avoid wrong' spread per phase (leaders EW minus
laggards EW), both eras; (3) full-tier impact of swapping the broad
equity leg in each cell for the phase's leader basket."""
import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
import research.engine as E, research.engine_pre2007 as P
from research.engine import headline
CACHE = Path("research/cache")
def c(name): return pd.read_csv(CACHE / f"{name}.csv", index_col=0, parse_dates=True).iloc[:, 0]
EARLY_N = 4
MAP = {"early": (["fin", "disc", "ind", "re"], ["util", "stap", "hc", "energy"]),
       "mid":   (["tech", "ind"], ["mat", "util"]),
       "late":  (["energy", "mat", "hc", "stap", "util"], ["tech", "disc", "fin"]),
       "recession": (["stap", "util", "hc"], ["tech", "ind", "disc", "re"])}
MODERN = {"tech": "XLK", "hc": "XLV", "fin": "XLF", "ind": "XLI", "disc": "XLY", "stap": "XLP", "util": "XLU", "energy": "XLE", "mat": "XLB", "re": "IYR"}
OLD = {"tech": "FSPTX", "hc": "FSPHX", "fin": "FIDSX", "ind": "FSRFX", "disc": "FSRPX", "stap": "FDFAX", "util": "FSUTX", "energy": "FSENX", "mat": "FSCHX", "re": "FSHOX"}

def phases(labels):
    """month-end stamp -> phase, from the quadrant label sequence."""
    out, since = {}, 0
    for st, lab in labels.items():
        if lab in ("S", "D"):
            since = 0; out[st] = "recession"
        else:
            since += 1
            out[st] = "early" if since <= EARLY_N else ("mid" if lab == "G" else "late")
    return pd.Series(out)

def grid(px, labels, symbols, bench, lo, hi, title):
    mo = px[[*symbols.values(), bench]].resample("ME").last().pct_change().loc[lo:hi]
    ph = phases(labels)
    ph_m = pd.Series([ph.loc[ph.index[ph.index < d][-1]] if len(ph.index[ph.index < d]) else None for d in mo.index], index=mo.index)
    print("=" * 100); print(title); print("=" * 100)
    print(f"  {'phase':>9} {'n':>3} | " + " ".join(f"{k:>7}" for k in symbols) + " |  leaders-laggards spread (ann, Sharpe)")
    spreads = {}
    for phase in ["early", "mid", "late", "recession"]:
        x = mo[ph_m == phase]
        if len(x) < 6: continue
        ex = {k: float((x[v] - x[bench]).mean() * 12) for k, v in symbols.items()}
        lead, lag = MAP[phase]
        sp = x[[symbols[k] for k in lead]].mean(axis=1) - x[[symbols[k] for k in lag]].mean(axis=1)
        spreads[phase] = (float(sp.mean() * 12), float(sp.mean() / sp.std() * np.sqrt(12)), len(x))
        print(f"  {phase:>9} {len(x):>3} | " + " ".join(f"{ex[k]*100:+6.1f}%" for k in symbols) + f" |  {sp.mean()*12:+6.1%}  {sp.mean()/sp.std()*np.sqrt(12):5.2f}")
    print("  (cells = annualized excess return of the sector over the broad market in that phase)")
    return spreads

# ---------------- modern ----------------
px = E.load_all()
for k, v in MODERN.items():
    if v not in px: px[v] = c(v).reindex(px.index)
rets, q, td, months = E.build(px)
labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
sm = grid(px, labels, MODERN, "SPY", "2007-01-31", "2026-12-31", "MODERN 2007-2026 — sector excess vs SPY by cycle phase")

# ---------------- pre-2007 ----------------
opx = P.load_all()
for k, v in OLD.items():
    if v not in opx: opx[v] = c(f"long_{v}").reindex(opx.index)
orets, oq, otd, omonths = P.build(opx)
olabels = pd.Series({st: lab for st, lab, w in omonths}).sort_index()
so = grid(opx, olabels, OLD, "VFINX", "1987-01-31", "2006-12-31", "PRE-2007 1987-2006 — Fidelity Select sector excess vs VFINX by cycle phase")

print("\n" + "=" * 100); print("Leaders-minus-laggards spread, era by era (the 'long the right industries, avoid the wrong ones' claim)"); print("=" * 100)
for phase in ["early", "mid", "late", "recession"]:
    m, o = sm.get(phase), so.get(phase)
    if m and o:
        tag = "BOTH ERAS POSITIVE" if m[0] > 0 and o[0] > 0 else "era-split" if (m[0] > 0) != (o[0] > 0) else "both negative"
        print(f"  {phase:>9}: modern {m[0]:+6.1%}/yr (Sharpe {m[1]:4.2f}, n={m[2]})   pre-2007 {o[0]:+6.1%}/yr (Sharpe {o[1]:4.2f}, n={o[2]})   -> {tag}")

# ---------------- impact: swap the broad equity leg for the phase's leader basket ----------------
print("\n" + "=" * 100); print("IMPACT — equity leg of each cell replaced by the phase leader basket (EW), everything else fixed"); print("=" * 100)
from src.portfolio import matrix
from src.regime.quadrant import Quadrant
EQ = {"SPY", "QQQ", "QLD", "TQQQ"}
def make_transform(symbols, lab_series):
    ph = phases(lab_series)
    def t(tier, st, lab, w):
        phase = ph.get(st)
        if phase is None: return w
        lead = [symbols[k] for k in MAP[phase][0]]
        eqw = sum(v for a, v in w.items() if a in EQ)
        if eqw == 0: return w
        w = {a: v for a, v in w.items() if a not in EQ}
        for s in lead: w[s] = w.get(s, 0.0) + eqw / len(lead)
        return w
    return t
for tier in ["MOD", "AGG"]:
    b = headline(td[tier])
    _, _, td2, _ = E.build(px, transform=make_transform(MODERN, labels))
    n = headline(td2[tier])
    print(f"  MODERN {tier:>4}: baseline {b['CAGR']:+.1%}/{b['Sortino']:.2f}/{b['maxDD']:.0%}  ->  phase-sector equity leg {n['CAGR']:+.1%}/{n['Sortino']:.2f}/{n['maxDD']:.0%}   (note: leverage lost where the leg was QLD/TQQQ)")
OEQ = {"VFINX", "NDX", "NDX2", "NDX3"}
def make_otransform(symbols, lab_series):
    ph = phases(lab_series)
    def t(tier, st, lab, w):
        phase = ph.get(st)
        if phase is None: return w
        lead = [symbols[k] for k in MAP[phase][0]]
        eqw = sum(v for a, v in w.items() if a in OEQ)
        if eqw == 0: return w
        w = {a: v for a, v in w.items() if a not in OEQ}
        for s in lead: w[s] = w.get(s, 0.0) + eqw / len(lead)
        return w
    return t
for tier in ["MOD", "AGG"]:
    b = headline(otd[tier])
    _, _, otd2, _ = P.build(opx, transform=make_otransform(OLD, olabels))
    n = headline(otd2[tier])
    print(f"  PRE-2007 {tier:>4}: baseline {b['CAGR']:+.1%}/{b['Sortino']:.2f}/{b['maxDD']:.0%}  ->  phase-sector equity leg {n['CAGR']:+.1%}/{n['Sortino']:.2f}/{n['maxDD']:.0%}")
