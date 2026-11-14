"""Entry 75 — daily swing signals on ETFs: Bollinger / RSI2 / IBS, alone and
combined, by era, by asset group, and conditioned on the quadrant in force.

    python3 -m research.swing.study_daily
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.swing.data import BROAD, ETFS, INTL, MACRO, SECTORS, SUBSECTORS, load
from research.swing.lib import ERAS, daily_features, era_of, simulate, tstats
from research.swing.strategies import PRIMARY, bb_mr

GROUPS = {"broad": BROAD, "sectors": SECTORS, "subsectors": SUBSECTORS,
          "energy": ["XLE"], "gold": ["GLD", "GDX", "SLV"], "bonds": ["TLT", "IEF"],
          "commod": ["DBC", "USO"], "intl": INTL}
# the matrix's own long map: which asset groups the rotation book is LONG per quadrant
ALIGNED = {"broad": "GR", "sectors": "GR", "subsectors": "GR", "intl": "GR", "energy": "R",
           "gold": "RD", "bonds": "D", "commod": "R"}


def cluster_t(tr: pd.DataFrame) -> float:
    """t-stat on entry-week mean returns (trades in one selloff are one bet)."""
    if len(tr) < 5:
        return float("nan")
    wk = tr.groupby(tr["entry"].dt.to_period("W"))["ret"].mean()
    return float(wk.mean() / (wk.std(ddof=1) / np.sqrt(len(wk)))) if len(wk) > 2 else float("nan")


def all_trades(data, feats, mode="close", strategies=PRIMARY, universe=ETFS):
    out = []
    for name, fn in strategies.items():
        for sym in universe:
            df = data[sym]
            e, x, h = fn(df)
            tr, _ = simulate(df, e, x, h, mode=mode)
            if tr.empty:
                continue
            tr["sym"], tr["strat"] = sym, name
            out.append(tr)
    t = pd.concat(out, ignore_index=True)
    t["era"] = t["entry"].map(era_of)
    t = t[t["era"].isin(ERAS)]
    f = feats.reindex(t["signal"].values)
    for col in feats.columns:
        t[col] = f[col].values
    grp = {s: g for g, ss in GROUPS.items() for s in ss if g not in ("energy",)}
    grp["XLE"] = "energy"
    t["group"] = t["sym"].map(grp)
    return t


def line(tr):
    s = tstats(tr["ret"])
    if s["n"] == 0:
        return "n=0"
    return (f"n={s['n']:5d}  {s['mean_bps']:+6.1f}bp  win {s['win']:.0%}  "
            f"pf {s['pf']:.2f}  clus-t {cluster_t(tr):+.2f}  hold {tr['days'].mean():.1f}d")


def baseline(data, universe=ETFS):
    """Unconditional mean daily return per era (the drift a long-only trade gets for free)."""
    rows = {}
    for era, (a, b) in ERAS.items():
        r = pd.concat([data[s]["close"].pct_change().loc[a:b] for s in universe])
        rows[era] = r.mean() * 1e4
    return rows


def main():
    data = load()
    feats = daily_features(data)
    res = {}
    print("Unconditional drift, bp/day, ETF universe:", {k: round(v, 1) for k, v in baseline(data).items()})
    for mode in ("close", "open"):
        t = all_trades(data, feats, mode)
        t.to_pickle(f"research/cache/swing_trades_{mode}.pkl")
        print(f"\n=== T1 primary specs, pooled ETF universe (30 ETFs), entry at {mode}, net of 5bp/side ===")
        for name in PRIMARY:
            s = t[t["strat"] == name]
            print(f"\n{name}")
            print(f"   ALL     {line(s)}")
            for era in ERAS:
                print(f"   {era} {line(s[s['era'] == era])}")
            res[f"{mode}|{name}"] = {era: tstats(s[s["era"] == era]["ret"]) for era in ERAS}
        if mode == "open":
            continue
        print("\n=== T2 by asset group (entry close), per era mean bp / n ===")
        for name in PRIMARY:
            print(f"\n{name}")
            for g in GROUPS:
                s = t[(t["strat"] == name) & (t["group"] == g)]
                cells = "  ".join(f"{era[:1]} {tstats(s[s['era']==era]['ret'])['mean_bps']:+6.1f}/{(s['era']==era).sum():4d}"
                                  for era in ERAS)
                print(f"   {g:10s} {cells}   | all {line(s)}")
        print("\n=== T3 by quadrant in force at signal, pooled eras B+C then era A (entry close) ===")
        for name in PRIMARY:
            print(f"\n{name}")
            for g in GROUPS:
                s = t[(t["strat"] == name) & (t["group"] == g)]
                row = []
                for q in "GRSD":
                    m = s[(s["quad"] == q) & (s["era"] != "A 99-06")]; a = s[(s["quad"] == q) & (s["era"] == "A 99-06")]
                    row.append(f"{q}: {tstats(m['ret'])['mean_bps']:+6.1f}/{len(m):4d} (A {tstats(a['ret'])['mean_bps']:+6.1f}/{len(a):3d})")
                print(f"   {g:10s} " + "  ".join(row))
        print("\n=== T4 matrix-aligned gate: trade a group only in quadrants where the rotation book is long it ===")
        for name in PRIMARY:
            s = t[t["strat"] == name]
            al = s[[q in ALIGNED[g] for q, g in zip(s["quad"].fillna("?"), s["group"])]]
            na = s.drop(al.index)
            print(f"\n{name}\n   aligned     {line(al)}\n   not aligned {line(na)}")
            for era in ERAS:
                print(f"      {era}: aligned {tstats(al[al['era']==era]['ret'])['mean_bps']:+6.1f}bp/{(al['era']==era).sum():4d}"
                      f"   not {tstats(na[na['era']==era]['ret'])['mean_bps']:+6.1f}bp/{(na['era']==era).sum():4d}")
        print("\n=== T5 conditioning features (equity groups only: broad+sectors+subsectors) ===")
        eq = t[t["group"].isin(["broad", "sectors", "subsectors"])]
        for name in ("BB(20,2) lower -> mid", "RSI2<10 + 200d trend", "IBS<0.2"):
            s = eq[eq["strat"] == name]
            print(f"\n{name}")
            conds = {"S&P above 200d": s["spy_above_200"] == True, "S&P below 200d": s["spy_above_200"] == False,
                     "VIX <16": s["vix"] < 16, "VIX 16-25": (s["vix"] >= 16) & (s["vix"] < 25), "VIX >=25": s["vix"] >= 25,
                     "breadth200 >=60%": s["breadth200"] >= 0.6, "breadth200 <30%": s["breadth200"] < 0.3,
                     "fragile (ext200<3% & rvol>16%, growth on)": (s["spy_ext200"].between(0, 0.03)) & (s["rvol20"] > 0.16)}
            for lab, m in conds.items():
                ss = s[m]
                print(f"   {lab:42s} {line(ss)}   by era: " +
                      " ".join(f"{tstats(ss[ss['era']==e]['ret'])['mean_bps']:+.0f}" for e in ERAS))
        print("\n=== T6 Bollinger grid robustness (pooled ETFs, entry close): mean bp by era ===")
        for n in (10, 20, 30):
            for k in (1.5, 2.0, 2.5):
                for ex in ("mid", "sma5"):
                    g = all_trades(data, feats, "close", {"g": lambda df, n=n, k=k, ex=ex: bb_mr(df, n, k, ex)})
                    print(f"   BB({n},{k}) exit {ex:4s} " +
                          "  ".join(f"{e[:1]} {tstats(g[g['era']==e]['ret'])['mean_bps']:+6.1f}/{(g['era']==e).sum():5d}" for e in ERAS)
                          + f"  clus-t {cluster_t(g):+.2f}")
    json.dump(res, open("research/swing_daily_results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
