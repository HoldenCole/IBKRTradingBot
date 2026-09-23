"""Where do the AGG/VAGG drawdowns actually come from? For each of the
largest drawdown episodes: which quadrant cells the book sat in, how much
of the loss happened while classified risk-on (G/R) vs defensive (S/D),
and how far SPY had already fallen by the time the exit signal fired."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.engine import load_all, build, drawdown_episodes, headline

px = load_all()
rets, q, tier_daily, months = build(px)
labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
def label_on(day):
    prior = labels.index[labels.index < day]
    return labels.loc[prior[-1]] if len(prior) else None
spy = px["SPY"].dropna()

for tier in ["AGG", "VAGG"]:
    r = tier_daily[tier].dropna()
    print("=" * 96); print(f"{tier}  (full-period maxDD {headline(r)['maxDD']:.1%})"); print("=" * 96)
    for ep in drawdown_episodes(r, n=4):
        seg = r.loc[ep["peak"]:ep["trough"]]
        lab = pd.Series([label_on(d) for d in seg.index], index=seg.index)
        by = {}
        for L in ["G", "R", "S", "D"]:
            x = seg[lab == L]
            if len(x): by[L] = (float((1 + x).prod() - 1), len(x))
        # exit lag: first month-end inside the episode where the label turned defensive
        risk_on_start = lab.iloc[0] in ("G", "R")
        exit_day = None
        for d, L in lab.items():
            if L in ("S", "D"):
                exit_day = d; break
        spy_peak = spy.loc[:ep["peak"]].max()
        rec = ep["recovered"].date() if ep["recovered"] is not None else "not yet"
        print(f"\n  peak {ep['peak'].date()}  trough {ep['trough'].date()}  depth {ep['depth']:.1%}  recovered {rec}")
        print("    loss by quadrant in force: " + ", ".join(f"{L}: {v:+.1%} over {n}d" for L, (v, n) in by.items()))
        if risk_on_start and exit_day is not None:
            spy_at_exit = float(spy.asof(exit_day) / spy_peak - 1)
            book_at_exit = float((1 + seg.loc[:exit_day]).prod() - 1)
            print(f"    exit signal took effect {exit_day.date()}: SPY was {spy_at_exit:+.1%} from its peak; "
                  f"the {tier} book was already {book_at_exit:+.1%}")
        elif risk_on_start:
            print("    no defensive reclassification during this episode — the book rode it in a risk-on cell")
        else:
            print(f"    episode began while DEFENSIVE ({lab.iloc[0]}) — not an exit-timing problem")

    # worst single months and the cell in force
    m = r.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    worst = m.nsmallest(6)
    print("\n  worst months:", ", ".join(f"{d.strftime('%Y-%m')} {v:+.1%} ({label_on(d)})" for d, v in worst.items()))
