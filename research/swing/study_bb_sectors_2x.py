"""Entry 97 — the monthly trend rule on the nine sector SPDRs at 1x, 2x and 3x (user follow-up to
entry 96; chosen after seeing entry 96, so a lead, not a pre-registered test).

Rule: hold a sector while its month-end close is above its 20-month average. Sleeves (a fixed
ninth each) or two slots ranked by %b, as entry 96. Every sector has a listed 2x fund (ProShares
Ultra series; ERX for energy), many of them thin, so the spread is taken at 10 bp for 2x and 3x.

    python3 -m research.swing.study_bb_sectors_2x
"""
from __future__ import annotations

import pandas as pd

from research.swing.data import load
from research.swing.lib import daily_features
from research.swing.study_bb_index import FEE, FIN, perf
from research.swing.study_bb_sectors import ERAS, SECTORS, START, held_flags, sleeves, slots
from research.swing.study_standalone import run


def lev_ret(R, rf, lev):
    f = rf.reindex(R.index).ffill().fillna(0) / 252
    return R.mul(lev).sub((lev - 1) * (f + FIN / 252) + (FEE / 252 if lev > 1 else 0), axis=0)


def main():
    data = load()
    rf = data["^IRX"]["close"] / 100
    px = pd.DataFrame({s: data[s]["close"] for s in SECTORS}).dropna()
    R = px.pct_change().fillna(0)
    mid = px.rolling(20).mean(); sd = px.rolling(20).std(ddof=0)
    pctb = (px - (mid - 2 * sd)) / (4 * sd)
    feats = daily_features(data)
    rows = []

    def add(lab, a):
        a = a.loc[START:]
        d = {"design": lab}
        for e, (s, x) in ERAS.items():
            p = perf(a.loc[s:x]); d[f"{e} CAGR"] = p["CAGR"]; d[f"{e} maxDD"] = p["maxDD"]
        p = perf(a); d.update({"CAGR": p["CAGR"], "Sharpe": p["Sharpe"], "maxDD": p["maxDD"]})
        yr = (1 + a).groupby(a.index.year).prod() - 1
        d["worst year"] = yr.min(); d["years down"] = (yr < 0).mean()
        rows.append(d)
        return a

    for lev in (1, 2, 3):
        spread = 0.0002 if lev == 1 else 0.0010
        R3 = lev_ret(R, rf, lev)
        add(f"equal-weight sectors held, {lev}x", R3.mean(axis=1))
        for n in (10, 20, 30):
            H = pd.DataFrame({s: held_flags(px[s], "above", "M", n) for s in SECTORS})
            add(f"monthly trend {n}m, nine sleeves, {lev}x", sleeves(H, R3, 0.35 / (1000 / 9) + spread))
            add(f"monthly trend {n}m, two slots, {lev}x", slots(H, pctb, R3, 0.35 / 500 + spread, dip=False))
        out, _ = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=9 / lev)
        f = rf.reindex(out.index).ffill().fillna(0) / 252
        sw = lev * out["pos"] - out["expo"] * ((lev - 1) * (f + FIN / 252) + (FEE / 252 if lev > 1 else 0))
        add(f"swing plan, {lev}x", sw)
    df = pd.DataFrame(rows)
    df.to_csv("research/swing/bb_sectors_2x_results.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 250)
    show = df.copy()
    for c in show.columns[1:]:
        show[c] = (show[c] * (1 if c == "Sharpe" else 100)).round(2 if c == "Sharpe" else 1)
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()


def blend():
    """Half the account in the swing plan at 3x, half in the 2x sector trend (nine sleeves), rebalanced monthly.
    The sector trend here is costed as a $500 half-account (eighteenths of $1,000), so its stand-alone line
    differs slightly from main()."""
    data = load()
    rf = data["^IRX"]["close"] / 100
    px = pd.DataFrame({s: data[s]["close"] for s in SECTORS}).dropna()
    R = px.pct_change().fillna(0)
    feats = daily_features(data)
    out, _ = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=9 / 3)
    f = rf.reindex(out.index).ffill().fillna(0) / 252
    sw = (3 * out["pos"] - out["expo"] * (2 * (f + FIN / 252) + FEE / 252)).loc[START:]
    print(f"{'design':48s} {'CAGR':>6s} {'maxDD':>6s} {'Sharpe':>6s} " + " ".join(f"{e:>15s}" for e in ERAS))
    for n in (10, 20, 30):
        H = pd.DataFrame({s: held_flags(px[s], "above", "M", n) for s in SECTORS})
        tr = sleeves(H, lev_ret(R, rf, 2), 0.35 / (1000 / 18) + 0.0010).loc[START:]
        for lab, a in ((f"swing 3x alone", sw), (f"sector trend {n}m 2x alone", tr), (f"half and half ({n}m)", None)):
            if a is None:
                both = pd.DataFrame({"s": sw, "t": tr.reindex(sw.index).fillna(0)})
                g = (1 + both).groupby(both.index.to_period("M")).cumprod()
                prev = g.groupby(both.index.to_period("M")).shift(1).fillna(1)
                a = 0.5 * (prev["s"] * both["s"] + prev["t"] * both["t"]) / (0.5 * prev["s"] + 0.5 * prev["t"])
            p = perf(a)
            era = " ".join(f"{perf(a.loc[s:x])['CAGR']:+6.1%}/{perf(a.loc[s:x])['maxDD']:+4.0%}" for s, x in ERAS.values())
            if lab.startswith("swing") and n != 10:
                continue
            print(f"{lab:48s} {p['CAGR']:+6.1%} {p['maxDD']:+6.0%} {p['Sharpe']:6.2f} {era}")
        print(f"   correlation {sw.corr(tr.reindex(sw.index).fillna(0)):.2f}")
