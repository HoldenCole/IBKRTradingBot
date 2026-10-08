"""Official tier statistics for the CURRENT matrix (modern engine) in the
exact conventions the workbook/evidence use: CAGR, Sortino = CAGR/ann
downside dev, Sharpe = CAGR/ann dev, maxDD (daily), beta = daily OLS vs
SPY, calendar-year returns, per-tier x regime monthly mean/std, regime
frequency and mean duration. Writes research/evidence_current.json."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
import research.engine as E
from src.portfolio.matrix import MATRIX_VERSION, TIERS

def stats(r, spy):
    r = r.dropna(); yrs = len(r) / 252
    cagr = (1 + r).prod() ** (1 / yrs) - 1
    dn = r[r < 0].std() * np.sqrt(252); sd = r.std() * np.sqrt(252); eq = (1 + r).cumprod()
    a = pd.concat([r, spy], axis=1).dropna()
    out = {"CAGR": float(cagr), "Sortino": float(cagr / dn), "Sharpe": float(cagr / sd),
           "maxDD": float((eq / eq.cummax() - 1).min()),
           "beta": float(np.cov(a.iloc[:, 0], a.iloc[:, 1])[0, 1] / a.iloc[:, 1].var())}
    for y in [2008, 2020, 2022, 2025, 2026]:
        x = r[r.index.year == y]; out[f"y{y}"] = float((1 + x).prod() - 1) if len(x) else None
    return out

if __name__ == "__main__":
    px = E.load_all(); rets, q, td, months = E.build(px)
    spy = rets["SPY"].loc[td["MOD"].index[0]:]
    ev = {t: stats(td[t], spy) for t in TIERS}
    ev["SPY"] = stats(spy, spy); ev["QQQ"] = stats(rets["QQQ"].loc[spy.index[0]:], spy)
    labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
    regime = {}
    for t in TIERS:
        mo = (1 + td[t]).resample("ME").prod() - 1
        lab = pd.Series([labels.loc[labels.index[labels.index < d][-1]] if len(labels.index[labels.index < d]) else None for d in mo.index], index=mo.index)
        regime[t] = {L: {"mean_m": float(mo[lab == L].mean()), "std_m": float(mo[lab == L].std())} for L in ["G", "R", "S", "D"]}
    labs = list(labels.values); freq = pd.Series(labs).value_counts(normalize=True).to_dict()
    runs, cur, n = [], labs[0], 1
    for x in labs[1:]:
        if x == cur: n += 1
        else: runs.append((cur, n)); cur, n = x, 1
    runs.append((cur, n)); dur = pd.DataFrame(runs, columns=["q", "n"]).groupby("q").n.mean().to_dict()
    out = {"matrix_version": MATRIX_VERSION, "window": [str(td["MOD"].index[0].date()), str(td["MOD"].index[-1].date())],
           "evidence": ev, "regime_stats": regime, "freq": freq, "duration_months": dur}
    json.dump(out, open(Path(__file__).resolve().parent / "evidence_current.json", "w"), indent=1)
    print(f"matrix {MATRIX_VERSION}  window {out['window']}")
    for t in TIERS + ["SPY", "QQQ"]:
        d = ev[t]; print(f"  {t:>4}: CAGR {d['CAGR']:+.1%} Sortino {d['Sortino']:.2f} Sharpe {d['Sharpe']:.2f} maxDD {d['maxDD']:.1%} beta {d['beta']:.2f} "
                         f"2008 {d['y2008']:+.1%} 2020 {d['y2020']:+.1%} 2022 {d['y2022']:+.1%} 2025 {d['y2025']:+.1%} 2026 {d['y2026']:+.1%}")
    print("  freq", {k: round(v, 3) for k, v in freq.items()}, "dur", {k: round(v, 1) for k, v in dur.items()})
