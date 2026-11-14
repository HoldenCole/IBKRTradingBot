"""Entry 81 — swing-trading the model's own assets when they get over-stretched
or sold off hard (mean reversion), daily bars, 1999-2026.

Stretch measure: z5 = 5-day return / (sigma x sqrt 5), sigma = daily vol over
the 60 days ending 5 days ago (so the move itself does not inflate it).
  sold off hard  : z5 crosses below -2   (first day)
  over-stretched : z5 crosses above +2   (first day)
Model dial: ext = close / 210-day SMA - 1 (the daily twin of the 10-month
line), ranked against its own trailing 5 years (percentile, ex-ante).

Never short broad US equity (standing rule): for SPY/QQQ the over-stretch side
is reported as forward returns only.

    python3 -m research.swing.study_stretch
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load
from research.swing.lib import ERAS, daily_features, era_of, rsi, simulate, sma, tstats

GROUPS = {"S&P / Nasdaq": ["SPY", "QQQ"], "energy equities": ["XLE"], "oil": ["USO"], "broad commodities": ["DBC"],
          "gold": ["GLD"], "gold miners / silver": ["GDX", "SLV"], "long bonds": ["TLT"],
          "sectors ex-energy": ["XLF", "XLK", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "SMH", "XBI", "KRE", "XHB", "XRT"]}
ALIGNED = {"S&P / Nasdaq": "GR", "sectors ex-energy": "GR", "energy equities": "R", "oil": "R", "broad commodities": "R",
           "gold": "RD", "gold miners / silver": "RD", "long bonds": "D"}
NO_SHORT = {"S&P / Nasdaq"}
HZ = (1, 3, 5, 10, 20)


def z5(c: pd.Series) -> pd.Series:
    r = np.log(c).diff()
    sig = r.rolling(60).std().shift(5)
    return np.log(c / c.shift(5)) / (sig * np.sqrt(5))


def ext_pct(c: pd.Series) -> pd.Series:
    ext = c / sma(c, 210) - 1
    return ext.rolling(1260, min_periods=500).rank(pct=True)


def events(data, feats):
    rows = []
    for g, syms in GROUPS.items():
        for s in syms:
            c = data[s]["close"]; z = z5(c); ep = ext_pct(c)
            fwd = {h: c.shift(-h) / c - 1 for h in HZ}
            q = feats["quad"].reindex(c.index)
            for kind, mask in (("sold", (z <= -2) & (z.shift(1) > -2)), ("stretched", (z >= 2) & (z.shift(1) < 2))):
                for d in c.index[mask.fillna(False)]:
                    rows.append({"group": g, "sym": s, "date": d, "kind": kind, "z": z.loc[d], "ext_pct": ep.loc[d], "quad": q.loc[d],
                                 **{f"f{h}": fwd[h].loc[d] for h in HZ}})
    e = pd.DataFrame(rows)
    e["era"] = e["date"].map(era_of); e = e[e["era"].isin(ERAS)]
    e["aligned"] = [isinstance(q, str) and q in ALIGNED[g] for q, g in zip(e["quad"], e["group"])]
    return e


def base(data, syms, h):
    """Unconditional h-day mean return per era for the group."""
    out = {}
    for era, (a, b) in ERAS.items():
        out[era] = np.nanmean([(data[s]["close"].shift(-h) / data[s]["close"] - 1).loc[a:b].mean() for s in syms])
    return out


def fwd_table(e, data, kind):
    print(f"\n=== B{'1' if kind == 'sold' else '2'} forward EXCESS return (bp, vs the asset's own unconditional mean) after "
          f"{'a HARD SELL-OFF (z5 < -2)' if kind == 'sold' else 'an OVER-STRETCH (z5 > +2)'} ===")
    print(f"{'group':22s} {'n':>5s}  " + "  ".join(f"{h:>3d}d" for h in HZ) + "   | 5d excess by era (A/B/C)      | 5d hit | aligned 5d / not aligned 5d")
    for g, syms in GROUPS.items():
        s = e[(e["group"] == g) & (e["kind"] == kind)]
        if s.empty:
            continue
        cells = []
        for h in HZ:
            b = base(data, syms, h)
            cells.append(np.nanmean(s[f"f{h}"] - s["era"].map(b)) * 1e4)
        b5 = base(data, syms, 5)
        xs5 = s["f5"] - s["era"].map(b5)
        eras = " ".join(f"{xs5[s['era']==k].mean()*1e4:+5.0f}/{(s['era']==k).sum():<3d}" for k in ERAS)
        al, na = xs5[s["aligned"]], xs5[~s["aligned"]]
        print(f"{g:22s} {len(s):5d}  " + "  ".join(f"{c:+4.0f}" for c in cells) + f"   | {eras} | {(s['f5']>0).mean():4.0%}  | {al.mean()*1e4:+5.0f}/{len(al):<3d}  {na.mean()*1e4:+5.0f}/{len(na):<3d}")


def rules(data, feats):
    print("\n=== B3 tradable rules, net 5bp/side (shorts +2bp borrow) ===")
    print("LONG the sell-off: buy the close when z5 crosses below -2; sell on first close above the 5d SMA or after 10 days")
    print("SHORT the stretch: short the close when z5 crosses above +2; cover on first close below the 5d SMA or after 10 days")
    out = {}
    for g, syms in GROUPS.items():
        for side in ("long", "short"):
            if side == "short" and g in NO_SHORT:
                continue
            parts = []
            for s in syms:
                df = data[s]; c = df["close"]; z = z5(c)
                if side == "long":
                    e, x = (z <= -2) & (z.shift(1) > -2), c > sma(c, 5)
                else:
                    e, x = (z >= 2) & (z.shift(1) < 2), c < sma(c, 5)
                tr, _ = simulate(df, e.fillna(False), x, 10)
                if side == "short":
                    tr["ret"] = -(tr["ret"] + 10 / 1e4) - 12 / 1e4
                tr["sym"] = s; parts.append(tr)
            t = pd.concat(parts); t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
            q = feats["quad"].reindex(t["signal"].values).values
            t["aligned"] = [isinstance(v, str) and v in ALIGNED[g] for v in q]
            out[(g, side)] = t
            st = tstats(t["ret"])
            al, na = t[t["aligned"]], t[~t["aligned"]]
            print(f"   {side.upper():5s} {g:22s} n={st['n']:4d} mean {st['mean_bps']:+6.1f}bp win {st['win']:.0%} t {st['t']:+.2f} worst {t['ret'].min():+.1%} | by era "
                  + " ".join(f"{t[t['era']==k]['ret'].mean()*1e4:+5.0f}/{(t['era']==k).sum():<3d}" for k in ERAS)
                  + f" | regime-long {al['ret'].mean()*1e4:+5.0f}/{len(al):<3d} not {na['ret'].mean()*1e4:+5.0f}/{len(na):<3d} | hold {t['days'].mean():.1f}d")
    return out


def dial(data, feats):
    print("\n=== B4 the model's own dial: distance above the 210-day line, as a percentile of its own last 5 years -> forward 10-day return (bp) ===")
    print(f"{'group':22s} " + "  ".join(f"{b:>14s}" for b in ("<=10th pct", "10-50th", "50-90th", "90-97th", ">=97th pct")) + "   | >=97th by era (A/B/C)")
    for g, syms in GROUPS.items():
        cells = {k: [] for k in range(5)}; era_hi = {k: [] for k in ERAS}
        for s in syms:
            c = data[s]["close"]; ep = ext_pct(c); f = c.shift(-10) / c - 1
            b = pd.cut(ep, [0, .10, .50, .90, .97, 1.0], labels=False, include_lowest=True)
            for k in range(5):
                cells[k].append(f[b == k])
            for era, (a, z) in ERAS.items():
                era_hi[era].append(f.loc[a:z][b.loc[a:z] == 4])
        row = "  ".join(f"{pd.concat(cells[k]).mean()*1e4:+7.0f} ({len(pd.concat(cells[k]).dropna())//1:5d})"[:14].rjust(14) for k in range(5))
        print(f"{g:22s} {row}   | " + " ".join(f"{pd.concat(era_hi[k]).mean()*1e4:+5.0f}" for k in ERAS))


def combos(data, feats):
    print("\n=== B5 stretch + dial combined (non-broad assets): short when z5 > +1.5 AND the dial is in its top 10%; cover < 5d SMA or 10d ===")
    for g, syms in GROUPS.items():
        if g in NO_SHORT:
            continue
        parts = []
        for s in syms:
            df = data[s]; c = df["close"]; z = z5(c); ep = ext_pct(c)
            e = (z >= 1.5) & (z.shift(1) < 1.5) & (ep >= 0.90)
            tr, _ = simulate(df, e.fillna(False), c < sma(c, 5), 10)
            tr["ret"] = -(tr["ret"] + 10 / 1e4) - 12 / 1e4; parts.append(tr)
        t = pd.concat(parts); t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
        if len(t):
            print(f"   SHORT {g:22s} n={len(t):4d} mean {t['ret'].mean()*1e4:+6.1f}bp win {(t['ret']>0).mean():.0%} worst {t['ret'].min():+.1%} | by era "
                  + " ".join(f"{t[t['era']==k]['ret'].mean()*1e4:+5.0f}/{(t['era']==k).sum():<3d}" for k in ERAS))
    print("\n=== B6 sold-off + dial: buy z5 < -2 only when the asset is still ABOVE its 210-day line (pullback in an uptrend) vs below it ===")
    for g, syms in GROUPS.items():
        rows = {"above": [], "below": []}
        for s in syms:
            df = data[s]; c = df["close"]; z = z5(c); up = c > sma(c, 210)
            for lab, m in (("above", up), ("below", ~up)):
                e = (z <= -2) & (z.shift(1) > -2) & m
                tr, _ = simulate(df, e.fillna(False), c > sma(c, 5), 10); rows[lab].append(tr)
        line = f"   {g:22s}"
        for lab in ("above", "below"):
            t = pd.concat(rows[lab]); t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
            line += f" | {lab} line: n={len(t):4d} mean {t['ret'].mean()*1e4:+6.1f}bp win {(t['ret']>0).mean():.0%} eras " \
                    + " ".join(f"{t[t['era']==k]['ret'].mean()*1e4:+5.0f}" for k in ERAS)
        print(line)


def case(data):
    print("\n=== B7 case study: energy, Oct-Nov 2026 ===")
    for s in ("XLE", "USO", "SPY"):
        c = data[s]["close"]; z = z5(c); ep = ext_pct(c); r2 = rsi(c, 2)
        d = pd.DataFrame({"close": c, "z5": z, "dial_pct": ep, "rsi2": r2, "1d": c.pct_change()}).loc["2026-10-26":]
        print(f"{s}:"); print(d.round(3).to_string())


def main():
    data = load(); feats = daily_features(data)
    e = events(data, feats)
    fwd_table(e, data, "sold"); fwd_table(e, data, "stretched")
    rules(data, feats); dial(data, feats); combos(data, feats); case(data)


if __name__ == "__main__":
    main()
