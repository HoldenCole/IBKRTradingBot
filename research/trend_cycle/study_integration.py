"""Entry 85 — tying Quadrant Balances into the regime switch.

The classifier's growth dial is SPY vs its 10-month SMA. Each rule below
overrides that dial from the MONTHLY quadrant-balance state (ex-ante, at the
same month-end stamp), then the unchanged matrix resolves the book. Both
engines (modern 2007-2026, pre-2007 1987-2006), all four tiers.

  A  QB-OUT       in Growth/Reflation months, growth -> OFF when the index's
                  monthly cycle AND trend are both below zero
  C  QB-STAY-IN   in Stagflation/Deflation months, growth -> ON while the
                  index's monthly cycle AND trend are both still above zero
  A+C             both (growth dial = classifier, vetoed either way by QB)
  G  QB-ONLY      growth ON iff the index's monthly trend is above zero
  D  WASHOUT-BUY  in S/D months, growth -> ON when >= 50% of members are in
                  monthly cycle Q4 (the user's "monthly washout" thesis)
  D2 WASHOUT-BUY  same, trigger = <= 25% of members rising (Q1+Q2)
  D3 WASHOUT-HOLD D, and stay ON for the 5 following months
  T  TURN-BUY     in S/D months, growth -> ON when the index's monthly cycle
                  is in Q1 (below zero but rising)

    python3 -m research.trend_cycle.study_integration
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import engine  # noqa: E402
import engine_pre2007 as pre  # noqa: E402
from src.regime.quadrant import Quadrant, quadrant_series as _orig_qs  # noqa: E402

G, R, S, D = Quadrant.GROWTH, Quadrant.REFLATION, Quadrant.STAGFLATION, Quadrant.DEFLATION
ON = {S: R, D: G}
OFF = {G: D, R: S}
TIERS = ("CONS", "MOD", "AGG", "VAGG")


def rules(sig: pd.DataFrame) -> dict:
    both_below = sig["idx_cycle_q"].isin([1, 4]) & sig["idx_trend_q"].isin([1, 4])
    both_above = sig["idx_cycle_q"].isin([2, 3]) & sig["idx_trend_q"].isin([2, 3])
    trend_above = sig["idx_trend_q"].isin([2, 3])
    wash = sig["cyc_q4"] >= 50
    wash2 = sig["cyc_q1q2"] <= 25
    wash_hold = wash.rolling(6, min_periods=1).max().astype(bool)
    turn = sig["idx_cycle_q"] == 1

    def mk(off=None, on=None, only=None):
        def f(q: pd.Series) -> pd.Series:
            out = q.copy(); n = 0
            for st in q.index:
                if st not in sig.index:
                    continue
                cur = q.loc[st]
                if only is not None:
                    want_on = bool(only.loc[st])
                    new = ON.get(cur, cur) if want_on else OFF.get(cur, cur)
                else:
                    new = cur
                    if off is not None and bool(off.loc[st]) and cur in OFF:
                        new = OFF[cur]
                    if on is not None and bool(on.loc[st]) and cur in ON:
                        new = ON[cur]
                if new is not cur:
                    out.loc[st] = new; n += 1
            f.changed = n
            return out
        return f

    return {"A  QB-OUT (both monthly below zero -> growth off)": mk(off=both_below),
            "C  QB-STAY-IN (both monthly above zero -> growth on)": mk(on=both_above),
            "A+C both vetoes": mk(off=both_below, on=both_above),
            "G  QB-ONLY (growth = monthly trend above zero)": mk(only=trend_above),
            "D  WASHOUT-BUY (>=50% members in monthly cycle Q4)": mk(on=wash),
            "D2 WASHOUT-BUY (<=25% members rising)": mk(on=wash2),
            "D3 WASHOUT-HOLD (D, held 6 months)": mk(on=wash_hold),
            "T  TURN-BUY (index monthly cycle Q1)": mk(on=turn)}


def run(mod, px, override=None, **kw):
    if override is None:
        mod.quadrant_series = _orig_qs
    else:
        mod.quadrant_series = lambda a, b: override(_orig_qs(a, b))
    try:
        rets, q, td, months = mod.build(px, **kw)
    finally:
        mod.quadrant_series = _orig_qs
    return {t: engine.headline(td[t]) for t in TIERS}, td


def fmt(h, b=None):
    s = f"{h['CAGR']:+6.1%}/{h['Sortino']:.2f}/{h['maxDD']:+4.0%}"
    if b is not None:
        ok = h["CAGR"] >= b["CAGR"] and h["Sortino"] >= b["Sortino"] and h["maxDD"] >= b["maxDD"]
        s += f" ({h['CAGR']-b['CAGR']:+.1%}{' ✓' if ok else ''})"
    return s


def main():
    sig = pd.read_pickle("research/cache/qb_monthly_signals.pkl")
    R_ = rules(sig)
    eras = (("2007-2026", engine, engine.load_all(), {}), ("1987-2006", pre, pre.load_all(), {}))
    base, results = {}, {}
    for era, mod, px, kw in eras:
        base[era], _ = run(mod, px, None, **kw)
    print("cells = CAGR/Sortino/maxDD (change in CAGR vs baseline; ✓ = CAGR, Sortino and maxDD all at least as good)\n")
    print(f"{'rule':54s} {'era':10s} {'months changed':>14s} | " + " | ".join(f"{t:^30s}" for t in TIERS))
    for era, mod, px, kw in eras:
        print(f"{'BASELINE v9':54s} {era:10s} {'':>14s} | " + " | ".join(f"{fmt(base[era][t]):30s}" for t in TIERS))
    for name, fn in R_.items():
        passes = 0
        for era, mod, px, kw in eras:
            h, td = run(mod, px, fn, **kw)
            results[(name, era)] = (h, td)
            ok = sum(h[t]["CAGR"] >= base[era][t]["CAGR"] and h[t]["Sortino"] >= base[era][t]["Sortino"] and h[t]["maxDD"] >= base[era][t]["maxDD"] for t in TIERS)
            passes += ok
            print(f"{name:54s} {era:10s} {fn.changed:14d} | " + " | ".join(f"{fmt(h[t], base[era][t]):30s}" for t in TIERS))
        print(f"{'':54s} -> improves all three metrics in {passes} of 8 tier-era cells")
    pd.to_pickle({k: v[0] for k, v in results.items()}, "research/cache/qb_integration_results.pkl")


if __name__ == "__main__":
    main()
