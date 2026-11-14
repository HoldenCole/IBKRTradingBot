"""Entry 76 — week-over-week swing: cross-sectional sector reversal/momentum,
weekly Bollinger, and what follows a crash week. Friday-close to Friday-close.

    python3 -m research.swing.study_weekly
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import BROAD, MACRO, SECTORS, SUBSECTORS, load
from research.swing.lib import ERAS, bollinger, daily_features, perf, tstats

COST = 5 / 1e4
ALIGNED = {**{s: "GR" for s in BROAD + SECTORS + SUBSECTORS}, "XLE": "R", "GLD": "RD", "GDX": "RD",
           "SLV": "RD", "TLT": "D", "IEF": "D", "DBC": "R", "USO": "R"}


def weekly(data, syms):
    return pd.DataFrame({s: data[s]["close"].resample("W-FRI").last() for s in syms})


def ann(r, per=52):
    r = r.dropna()
    if len(r) < 20:
        return "n/a"
    c = (1 + r).prod() ** (per / len(r)) - 1
    sh = r.mean() / r.std() * np.sqrt(per) if r.std() else np.nan
    eq = (1 + r).cumprod()
    return f"{c:+6.1%} Sh {sh:.2f} DD {float((eq/eq.cummax()-1).min()):+.0%}"


def xs_rotation(W, quad_w, look, k, pick, gate=None):
    """Each Friday rank by `look`-week return; hold top/bottom k for one week."""
    R = W.pct_change()
    sig = W.pct_change(look)
    out, prev = [], set()
    for i in range(look + 1, len(W) - 1):
        row = sig.iloc[i].dropna()
        if len(row) < max(2 * k, 4):
            out.append(np.nan); continue
        names = set((row.nsmallest(k) if pick == "losers" else row.nlargest(k)).index)
        if gate is not None and quad_w.iloc[i] not in gate:
            names = set()
        turn = len(names ^ prev) / (2 * k) if (names or prev) else 0.0
        nxt = R.iloc[i + 1][list(names)].mean() if names else 0.0
        out.append(nxt - turn * 2 * COST)
        prev = names
    return pd.Series(out, index=W.index[look + 2: len(W)])


def main():
    data = load(); feats = daily_features(data)
    quad_w = feats["quad"].resample("W-FRI").last()
    secs = weekly(data, SECTORS)
    wide = weekly(data, SECTORS + SUBSECTORS)
    quad_s = quad_w.reindex(secs.index).ffill()
    ew = secs.pct_change().mean(axis=1)

    print("=== W1 cross-sectional sector rotation, 9 SPDR sectors, weekly rebalance, long top/bottom 2, net 5bp/side ===")
    print(f"{'rule':34s} " + " | ".join(f"{e:22s}" for e in ERAS))
    print(f"{'equal-weight 9 sectors (baseline)':34s} " + " | ".join(ann(ew.loc[a:b]) for a, b in ERAS.values()))
    for lab, look, pick in (("1w reversal (buy 2 worst)", 1, "losers"), ("1w momentum (buy 2 best)", 1, "winners"),
                            ("4w momentum", 4, "winners"), ("13w momentum", 13, "winners"),
                            ("26w momentum", 26, "winners"), ("4w reversal", 4, "losers")):
        r = xs_rotation(secs, quad_s, look, 2, pick)
        x = (r - ew.reindex(r.index))
        print(f"{lab:34s} " + " | ".join(ann(r.loc[a:b]) for a, b in ERAS.values())
              + "   excess/yr vs EW: " + " ".join(f"{x.loc[a:b].mean()*52:+.1%}" for a, b in ERAS.values())
              + f"  t {x.mean()/x.std()*np.sqrt(len(x.dropna())):+.2f}")
    print("\n   with the regime gate (hold only in G/R, cash otherwise):")
    for lab, look, pick in (("1w reversal", 1, "losers"), ("13w momentum", 13, "winners")):
        r = xs_rotation(secs, quad_s, look, 2, pick, gate="GR")
        g = ew.where(quad_s.shift(1).isin(["G", "R"]), 0.0).reindex(r.index)
        print(f"   {lab:31s} " + " | ".join(ann(r.loc[a:b]) for a, b in ERAS.values())
              + "   vs gated EW: " + " ".join(f"{(r-g).loc[a:b].mean()*52:+.1%}" for a, b in ERAS.values()))
    print("\n   16-ETF set (sectors + subsectors), 2007+, long 3:")
    quad_x = quad_w.reindex(wide.index).ffill(); ew2 = wide.pct_change().mean(axis=1)
    for lab, look, pick in (("1w reversal", 1, "losers"), ("4w momentum", 4, "winners"), ("13w momentum", 13, "winners")):
        r = xs_rotation(wide.loc["2006-06-01":], quad_x.loc["2006-06-01":], look, 3, pick)
        x = r - ew2.reindex(r.index)
        print(f"   {lab:31s} " + " | ".join(ann(r.loc[a:b]) for a, b in list(ERAS.values())[1:])
              + "   excess/yr: " + " ".join(f"{x.loc[a:b].mean()*52:+.1%}" for a, b in list(ERAS.values())[1:]))

    print("\n=== W2 weekly Bollinger (20w, 2sd) per asset: lower-band buy -> exit above mid (max 8w); and upper-band breakout ===")
    allw = weekly(data, BROAD + SECTORS + SUBSECTORS + MACRO)
    rows = {"MR": [], "BO": []}
    for s in allw:
        c = allw[s].dropna()
        mid, up, lo, pctb, bw = bollinger(c, 20, 2.0)
        q = quad_w.reindex(c.index).ffill()
        for kind, ent, ex, mh in (("MR", c < lo, c > mid, 8), ("BO", (c > up) & (c.shift(1) <= up.shift(1)), c < mid, 26)):
            i = 20
            while i < len(c) - 1:
                if not ent.iloc[i]:
                    i += 1; continue
                j = i + 1
                while j < len(c) - 1 and not ex.iloc[j] and j - i < mh:
                    j += 1
                rows[kind].append((s, c.index[i], j - i, c.iloc[j] / c.iloc[i] - 1 - 2 * COST, q.iloc[i]))
                i = j + 1
    for kind, lab in (("MR", "weekly lower-band buy"), ("BO", "weekly upper-band breakout")):
        t = pd.DataFrame(rows[kind], columns=["sym", "entry", "weeks", "ret", "quad"])
        t["era"] = [next((k for k, (a, b) in ERAS.items() if pd.Timestamp(a) <= d <= pd.Timestamp(b)), None) for d in t["entry"]]
        t = t.dropna(subset=["era"])
        t["al"] = [isinstance(q, str) and q in ALIGNED.get(s, "") for s, q in zip(t["sym"], t["quad"])]
        print(f"\n{lab}: n={len(t)} avg hold {t['weeks'].mean():.1f}w")
        for era in ERAS:
            e = t[t["era"] == era]
            print(f"   {era}: all {tstats(e['ret'])['mean_bps']:+7.1f}bp/{len(e):4d} win {(e['ret']>0).mean():.0%} | "
                  f"aligned {tstats(e[e['al']]['ret'])['mean_bps']:+7.1f}bp/{e['al'].sum():4d} | "
                  f"not aligned {tstats(e[~e['al']]['ret'])['mean_bps']:+7.1f}bp/{(~e['al']).sum():4d}")

    print("\n=== W3 after a crash week (ETF down >= 8% Friday-to-Friday): forward returns, bp ===")
    rows = []
    for s in allw:
        c = allw[s].dropna(); r = c.pct_change()
        q = quad_w.reindex(c.index).ffill()
        for i in np.where(r.values <= -0.08)[0]:
            if i + 4 < len(c):
                rows.append((s, c.index[i], q.iloc[i], c.iloc[i+1]/c.iloc[i]-1, c.iloc[i+2]/c.iloc[i]-1, c.iloc[i+4]/c.iloc[i]-1))
    t = pd.DataFrame(rows, columns=["sym", "week", "quad", "f1", "f2", "f4"])
    t["era"] = [next((k for k, (a, b) in ERAS.items() if pd.Timestamp(a) <= d <= pd.Timestamp(b)), None) for d in t["week"]]
    t = t.dropna(subset=["era"])
    t["al"] = [isinstance(q, str) and q in ALIGNED.get(s, "") for s, q in zip(t["sym"], t["quad"])]
    base4 = allw.pct_change(4).stack().mean() * 1e4
    print(f"   unconditional 4w mean, all ETFs: {base4:+.0f}bp")
    for lab, m in (("all crash weeks", t["al"] | ~t["al"]), ("aligned with the regime book", t["al"]), ("not aligned", ~t["al"]),
                   ("energy (XLE) only", t["sym"] == "XLE"), ("XLE in Reflation", (t["sym"] == "XLE") & (t["quad"] == "R"))):
        s = t[m]
        nev = s["week"].nunique()
        print(f"   {lab:30s} n={len(s):4d} ({nev} distinct weeks)  1w {s['f1'].mean()*1e4:+6.0f}  2w {s['f2'].mean()*1e4:+6.0f}  "
              f"4w {s['f4'].mean()*1e4:+6.0f}  4w hit {(s['f4']>0).mean():.0%}   by era 4w: "
              + " ".join(f"{s[s['era']==e]['f4'].mean()*1e4:+.0f}/{(s['era']==e).sum()}" for e in ERAS))


if __name__ == "__main__":
    main()
