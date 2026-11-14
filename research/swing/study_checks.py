"""Entry 75 robustness: pre-1999 index era, other tiers, cost sensitivity.

    python3 -m research.swing.study_checks
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load
from research.swing.lib import bollinger, daily_features, perf, rsi, simulate, sma, tstats
from research.swing import study_sleeve as ss
from research.swing.strategies import bb_mr, bb_rsi, rsi2


def main():
    data = load(); feats = daily_features(data)
    print("=== C1 index-only history (not tradable as such; evidence on era stability), close entry, 5bp/side ===")
    for sym in ("^GSPC", "^NDX"):
        df = data[sym]
        for name, fn in (("BB(20,2)->mid", bb_mr), ("BB+RSI2<10", bb_rsi), ("RSI2<10+200d", rsi2)):
            e, x, h = fn(df)
            tr, _ = simulate(df, e, x, h)
            cells = []
            for a, b in (("1987-01-01", "1998-12-31"), ("1999-01-01", "2006-12-31"), ("2007-01-01", "2016-12-31"), ("2017-01-01", "2026-12-31")):
                s = tr[(tr["entry"] >= a) & (tr["entry"] <= b)]
                cells.append(f"{a[:4]}-{b[2:4]} {s['ret'].mean()*1e4:+6.1f}bp/{len(s):3d} t{tstats(s['ret'])['t']:+.1f}")
            print(f"   {sym:6s} {name:14s} " + " | ".join(cells))
        r = df["close"].pct_change()
        print(f"   {sym:6s} lag-1 daily autocorrelation: " + " | ".join(
            f"{a[:4]}-{b[2:4]} {r.loc[a:b].autocorr(1):+.3f}" for a, b in (("1987-01-01", "1998-12-31"), ("1999-01-01", "2006-12-31"),
                                                                        ("2007-01-01", "2016-12-31"), ("2017-01-01", "2026-12-31"))))

    print("\n=== C2 the BB+RSI2 aligned overlay on each tier, 2007-2026 (25% and 50% of equity on margin) ===")
    tier_daily, rf = ss.core_agg()
    r, x, n = ss.sleeve(data, feats, "BB+RSI2", gate="GR")
    for tier in ("CONS", "MOD", "AGG", "VAGG"):
        core = tier_daily[tier].dropna(); core = core[core.index >= "2007-01-01"]
        rr, xx, rfc = r.reindex(core.index).fillna(0.0), x.reindex(core.index).fillna(0.0), rf.reindex(core.index).fillna(0.0)
        p0 = perf(core)
        line = f"   {tier:5s} core {p0['CAGR']:+.1%}/{p0['Sortino']:.2f}/{p0['maxDD']:+.1%}"
        for w in (0.25, 0.5):
            p = perf(core + w * rr - xx * w * (rfc + ss.MARGIN_SPREAD / 252))
            line += f"  | +{w:.0%}: {p['CAGR']:+.1%}/{p['Sortino']:.2f}/{p['maxDD']:+.1%}"
        if tier == "CONS":   # CONS holds 30% SHY: fund the sleeve from it (no margin; forgo the bill yield while invested)
            p = perf(core + 0.25 * rr - xx * 0.25 * rfc)
            line += f"  | 25% funded from its SHY: {p['CAGR']:+.1%}/{p['Sortino']:.2f}/{p['maxDD']:+.1%}"
        print(line + f"   corr {np.corrcoef(rr, core)[0,1]:+.2f}")
    print("   (CAGR / Sortino / maxDD)")

    print("\n=== C3 cost sensitivity, BB+RSI2 aligned G/R sleeve standalone position return (ann.) and AGG +50% overlay ===")
    core = tier_daily["AGG"].dropna(); core = core[core.index >= "2007-01-01"]
    for bps in (2, 5, 10, 15):
        ss.COST = bps / 1e4
        r2, x2, n2 = ss.sleeve(data, feats, "BB+RSI2", gate="GR")
        rr, xx, rfc = r2.reindex(core.index).fillna(0.0), x2.reindex(core.index).fillna(0.0), rf.reindex(core.index).fillna(0.0)
        p = perf(core + 0.5 * rr - xx * 0.5 * (rfc + ss.MARGIN_SPREAD / 252))
        print(f"   {bps:2d}bp/side: sleeve position return {r2.mean()*252:+.2%}/yr on {x2.mean():.0%} exposure "
              f"({n2/(len(r2)/252):.0f} trades/yr) | AGG+50%: CAGR {p['CAGR']:+.1%} Sortino {p['Sortino']:.2f} maxDD {p['maxDD']:+.1%}")
    ss.COST = 5 / 1e4


if __name__ == "__main__":
    main()
