"""Entry 87, portfolio check — the monthly Quadrant Balances sell/buy signal as the growth dial.

The index study found one usable monthly signal: OUT while the S&P 500's
monthly trend is in Q4 (below zero and falling), IN otherwise. Here it
replaces or vetoes the classifier's growth dial and the unchanged matrix
resolves the book. Both engines, all four tiers.

    python3 -m research.trend_cycle.study_integration3
"""
from __future__ import annotations

import pandas as pd

from research.trend_cycle.study_integration import ON, OFF, TIERS, engine, fmt, pre, run  # noqa: F401


def mk(sig, off=None, on=None, only=None):
    def f(q: pd.Series) -> pd.Series:
        out = q.copy(); n = 0
        for st in q.index:
            if st not in sig.index:
                continue
            cur = q.loc[st]; new = cur
            if only is not None:
                new = ON.get(cur, cur) if bool(only.loc[st]) else OFF.get(cur, cur)
            else:
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
    t4 = sig["idx_trend_q"].eq(4)
    early = t4 | (sig["idx_trend_q"].eq(3) & sig["idx_cycle_q"].eq(4))
    rules = {
        "H1 growth dial = NOT monthly trend Q4 (replaces the classifier)": mk(sig, only=~t4),
        "H2 growth dial = NOT (trend Q4, or trend Q3 with cycle Q4)": mk(sig, only=~early),
        "H3 classifier, but stay growth-on unless monthly trend Q4": mk(sig, on=~t4),
        "H4 classifier, and also growth-off whenever monthly trend Q4": mk(sig, off=t4),
        "H5 classifier, and also growth-off on the earlier exit (H2 state)": mk(sig, off=early),
    }
    eras = (("2007-2026", engine, engine.load_all(), {}), ("1987-2006", pre, pre.load_all(), {}))
    base = {era: run(mod, px, None, **kw)[0] for era, mod, px, kw in eras}
    print("cells = CAGR/Sortino/maxDD (change in CAGR vs baseline; ✓ = all three at least as good)\n")
    for era, *_ in eras:
        print(f"{'BASELINE v9':66s} {era:10s} {'':>5s} | " + " | ".join(f"{fmt(base[era][t]):30s}" for t in TIERS))
    for name, fn in rules.items():
        passes = 0
        for era, mod, px, kw in eras:
            h, _ = run(mod, px, fn, **kw)
            passes += sum(h[t]["CAGR"] >= base[era][t]["CAGR"] and h[t]["Sortino"] >= base[era][t]["Sortino"] and h[t]["maxDD"] >= base[era][t]["maxDD"] for t in TIERS)
            print(f"{name:66s} {era:10s} {fn.changed:5d} | " + " | ".join(f"{fmt(h[t], base[era][t]):30s}" for t in TIERS))
        print(f"{'':66s} -> improves all three metrics in {passes} of 8 tier-era cells")


if __name__ == "__main__":
    main()
