"""Entry 85b — refined tie-ins, and the disagreement we are in now
(classifier turning growth-OFF while the monthly quadrant balances are intact).

  W   WASHOUT+TURN   in S/D months, growth -> ON when a monthly washout was seen
                     in the last 6 months (>=50% of members in cycle Q4) AND the
                     index's monthly cycle is rising again (Q1 or Q2)
  W2  same with the <=25%-rising washout definition
  C2  STAY-IN, BROAD in S/D months, growth -> ON while index monthly cycle and
                     trend are above zero AND under 25% of members are in monthly
                     Q4 on both measures (participation intact)
  E   EARLY-OUT      in G/R months, growth -> OFF when the index monthly trend is
                     falling (Q3/Q4) AND >= 30% of members are in monthly trend Q4

    python3 -m research.trend_cycle.study_integration2
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import engine  # noqa: E402
import engine_pre2007 as pre  # noqa: E402
from research.trend_cycle.study_integration import D, G, ON, OFF, R, S, TIERS, fmt, run  # noqa: E402
from src.regime.quadrant import quadrant_series as _orig_qs  # noqa: E402


def mk(sig, off=None, on=None):
    def f(q):
        out = q.copy(); n = 0
        for st in q.index:
            if st not in sig.index:
                continue
            cur = q.loc[st]; new = cur
            if off is not None and bool(off.loc[st]) and cur in OFF:
                new = OFF[cur]
            if on is not None and bool(on.loc[st]) and cur in ON:
                new = ON[cur]
            if new is not cur:
                out.loc[st] = new; n += 1
        f.changed = n
        return out
    return f


def main():
    sig = pd.read_pickle("research/cache/qb_monthly_signals.pkl")
    rising = sig["idx_cycle_q"].isin([1, 2])
    both_above = sig["idx_cycle_q"].isin([2, 3]) & sig["idx_trend_q"].isin([2, 3])
    armed = (sig["cyc_q4"] >= 50).rolling(6, min_periods=1).max().astype(bool)
    armed2 = (sig["cyc_q1q2"] <= 25).rolling(6, min_periods=1).max().astype(bool)
    broad = (sig["cyc_q4"] < 25) & (sig["trd_q4"] < 25)
    rules = {"W  WASHOUT+TURN (washout in last 6m, index cycle rising)": mk(sig, on=armed & rising),
             "W2 WASHOUT+TURN (<=25% rising version)": mk(sig, on=armed2 & rising),
             "C2 STAY-IN, BROAD (monthly above zero, <25% members Q4)": mk(sig, on=both_above & broad),
             "E  EARLY-OUT (trend falling, >=30% members trend Q4)": mk(sig, off=sig["idx_trend_q"].isin([3, 4]) & (sig["trd_q4"] >= 30))}
    eras = (("2007-2026", engine, engine.load_all()), ("1987-2006", pre, pre.load_all()))
    base = {era: run(mod, px, None) for era, mod, px in eras}
    print("cells = CAGR/Sortino/maxDD (change in CAGR; ✓ = all three at least as good)\n")
    for era, mod, px in eras:
        print(f"{'BASELINE v9':58s} {era:10s} {'':>4s} | " + " | ".join(f"{fmt(base[era][0][t]):30s}" for t in TIERS))
    for name, fn in rules.items():
        tot = 0
        for era, mod, px in eras:
            h, td = run(mod, px, fn)
            b = base[era][0]
            tot += sum(h[t]["CAGR"] >= b[t]["CAGR"] and h[t]["Sortino"] >= b[t]["Sortino"] and h[t]["maxDD"] >= b[t]["maxDD"] for t in TIERS)
            print(f"{name:58s} {era:10s} {fn.changed:4d} | " + " | ".join(f"{fmt(h[t], b[t]):30s}" for t in TIERS))
        print(f"{'':58s} -> improves all three metrics in {tot} of 8 tier-era cells")

    # ---- the disagreement we are in now ----
    print("\n=== Months when the classifier was growth-OFF (S or D) — split by the monthly quadrant-balance state at that month-end ===")
    print("    next-month return of: S&P 500 | the AGG book as held (defensive) | the AGG book if growth had been kept ON")
    for era, mod, px in eras:
        (hb, tdb) = base[era]
        on_all = mk(sig, on=pd.Series(True, index=sig.index))
        (ho, tdo) = run(mod, px, on_all)
        q = _orig_qs(px["SPY"].dropna(), px["DBC"].dropna()) if mod is engine else _orig_qs(px["VFINX"].dropna(), px["GSCI"].dropna())
        spx = sig["spx"]
        rows = []
        for st in q.index:
            if q.loc[st] not in (S, D) or st not in sig.index:
                continue
            nxt = st + pd.offsets.MonthEnd(1)
            a = tdb["AGG"]; b = tdo["AGG"]
            ra = (1 + a.loc[(a.index > st) & (a.index <= nxt)]).prod() - 1
            rb = (1 + b.loc[(b.index > st) & (b.index <= nxt)]).prod() - 1
            if nxt not in spx.index or len(a.loc[(a.index > st) & (a.index <= nxt)]) == 0:
                continue
            rows.append((st, "intact" if both_above.loc[st] else "broken", spx.loc[nxt] / spx.loc[st] - 1, ra, rb, sig.loc[st, "cyc_q4"]))
        d = pd.DataFrame(rows, columns=["stamp", "qb", "spx", "defensive", "stay_in", "cyc_q4"]).set_index("stamp")
        for lab in ("intact", "broken"):
            s = d[d["qb"] == lab]
            print(f"   {era}  monthly QB {lab:6s} (n={len(s):3d}): S&P {s['spx'].mean():+.2%} (up {(s['spx']>0).mean():.0%}, worst {s['spx'].min():+.1%}) | "
                  f"AGG defensive {s['defensive'].mean():+.2%} (worst {s['defensive'].min():+.1%}) | AGG stay-in {s['stay_in'].mean():+.2%} (worst {s['stay_in'].min():+.1%}) | "
                  f"stay-in better in {(s['stay_in'] > s['defensive']).mean():.0%} of months")
        first = d[(d["qb"] == "intact")]
        # first month of each growth-off spell with QB intact
        spell_start = [st for st in first.index if (q.shift(1).get(st) not in (S, D))]
        s = d.loc[spell_start]
        print(f"   {era}  FIRST month of a growth-off spell with QB intact (n={len(s)}): S&P {s['spx'].mean():+.2%} (up {(s['spx']>0).mean():.0%}, worst {s['spx'].min():+.1%}) | "
              f"defensive {s['defensive'].mean():+.2%} | stay-in {s['stay_in'].mean():+.2%} (worst {s['stay_in'].min():+.1%}) | stay-in better {(s['stay_in'] > s['defensive']).mean():.0%}")
        if era == "2007-2026":
            print("      modern list:", ", ".join(f"{st.strftime('%Y-%m')} S&P {r.spx:+.0%}" for st, r in s.iterrows()))


if __name__ == "__main__":
    main()
