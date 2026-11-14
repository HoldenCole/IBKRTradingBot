"""Entry 79 — the swing strategy as its OWN account (not an overlay).

Assessed standalone: capital sits in T-bills until a dip signal fires, then
goes into up to `slots` equity ETFs. Design axes: signal, regime gate,
number of slots (concentration), universe, leverage of the position
instrument (1x ETF / 2x / 3x daily-reset ETF, modelled as in research/engine:
N x daily - (N-1) x (rf+1%) - 0.95% expense), entry at the signal close or
next open. Benchmarks: SPY buy-and-hold and T-bills over the same windows.

    python3 -m research.swing.study_standalone
"""
from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

from research.swing.data import BROAD, SECTORS, SUBSECTORS, load
from research.swing.lib import ERAS, bollinger, daily_features, perf, rsi, sma

EQ = BROAD + SECTORS + SUBSECTORS
START = "1999-06-01"


def sig(df, kind):
    c = df["close"]
    mid, up, lo, pctb, bw = bollinger(c, 20, 2.0)
    r2 = rsi(c, 2)
    if kind == "BB+RSI2":
        return (c < lo) & (r2 < 10), c > sma(c, 5), 10, r2
    if kind == "RSI2+trend":
        return (r2 < 10) & (c > sma(c, 200)), c > sma(c, 5), 10, r2
    if kind == "UNION":
        return (r2 < 10) & ((c < lo) | (c > sma(c, 200))), c > sma(c, 5), 10, r2
    if kind == "BB+trend":
        return (c < lo) & (c > sma(c, 200)), c > mid, 10, pctb
    raise ValueError(kind)


def run(data, feats, kind, universe, slots, gate, cost_bps=5.0, entry="close"):
    """Returns DataFrame[pos (position return on account, pre-leverage, incl. costs), expo] and a trade list."""
    days = feats.index[feats.index >= START]
    n = len(days)
    cost = cost_bps / 1e4
    cc, oc, E, X, P = {}, {}, {}, {}, {}
    for s in universe:
        df = data[s].reindex(days)
        cc[s] = df["close"].pct_change().fillna(0.0).values
        oc[s] = (df["close"] / df["open"] - 1).fillna(0.0).values
        e, x, h, pr = sig(data[s], kind)
        E[s] = e.reindex(days).fillna(False).values; X[s] = x.reindex(days).fillna(False).values
        P[s] = pr.reindex(days).values
    quad = feats["quad"].reindex(days).values
    frag = ((feats["spy_ext200"].between(0, 0.03)) & (feats["rvol20"] > 0.16)).reindex(days).fillna(False).values
    held, pend = {}, []           # held: sym -> (entry idx, cum return)
    pos = np.zeros(n); expo = np.zeros(n); trades = []
    for i in range(n):
        for s in pend:            # next-open entries from yesterday's signals
            held[s] = [i, 0.0, True]
        pend = []
        for s, st in held.items():
            r = oc[s][i] if (entry == "open" and st[2]) else cc[s][i]
            st[2] = False
            pos[i] += r / slots; st[1] = (1 + st[1]) * (1 + r) - 1
        expo[i] = len(held) / slots
        for s in list(held):
            if X[s][i] or i - held[s][0] >= 10:
                pos[i] -= cost / slots
                trades.append((days[held[s][0]], days[i], s, held[s][1] - 2 * cost)); del held[s]
        ok = True
        if gate in ("aligned", "aligned+nofragile"):
            ok = isinstance(quad[i], str) and quad[i] in "GR"
        if gate == "aligned+nofragile" and frag[i]:
            ok = False
        free = slots - len(held) - len(pend)
        if ok and free > 0:
            cands = sorted((s for s in universe if E[s][i] and s not in held and not np.isnan(P[s][i])), key=lambda s: P[s][i])
            for s in cands[:free]:
                pos[i] -= cost / slots
                if entry == "close":
                    held[s] = [i, 0.0, False]
                else:
                    pend.append(s)
    out = pd.DataFrame({"pos": pos, "expo": expo}, index=days)
    tr = pd.DataFrame(trades, columns=["entry", "exit", "sym", "ret"])
    return out, tr


def account(out, rf, lev=1):
    """Daily account return: levered position + T-bill on idle cash."""
    r = rf.reindex(out.index).fillna(0.0)
    p = lev * out["pos"] - out["expo"] * ((lev - 1) * (r + 0.01 / 252) + (0.0095 / 252 if lev > 1 else 0.0))
    return p + (1 - out["expo"]) * r


def stats(a):
    p = perf(a)
    yr = (1 + a).groupby(a.index.year).prod() - 1
    return p, yr


def row(lab, a, out=None, tr=None):
    p, yr = stats(a)
    eras = "  ".join(f"{k[:1]} {perf(a.loc[x:y])['CAGR']:+5.1%}/{perf(a.loc[x:y])['Sharpe']:.2f}/{perf(a.loc[x:y])['maxDD']:+4.0%}" for k, (x, y) in ERAS.items())
    extra = ""
    if out is not None:
        extra = f"  expo {out['expo'].mean():3.0%} tr/yr {len(tr)/(len(out)/252):3.0f}"
    print(f"{lab:46s} CAGR {p['CAGR']:+5.1%} Sh {p['Sharpe']:.2f} So {p['Sortino']:.2f} DD {p['maxDD']:+4.0%} "
          f"worst yr {yr.min():+4.0%} +yrs {(yr>0).mean():3.0%}{extra} | {eras}")
    return p


def main():
    data = load(); feats = daily_features(data)
    rf = (data["^IRX"]["close"] / 100 / 252).reindex(feats.index).ffill().fillna(0.0)
    days = feats.index[feats.index >= START]
    print("era cells = CAGR/Sharpe/maxDD;  A 1999-2006, B 2007-2016, C 2017-2026\n")
    print("=== Benchmarks ===")
    spy = data["SPY"]["close"].pct_change().reindex(days).fillna(0.0)
    qqq = data["QQQ"]["close"].pct_change().reindex(days).fillna(0.0)
    row("SPY buy & hold", spy); row("QQQ buy & hold", qqq); row("T-bills", rf.reindex(days))

    print("\n=== S1 design grid at 1x (5bp/side, entry at signal close) ===")
    res = {}
    for kind, uni, slots, gate in itertools.product(("BB+RSI2", "RSI2+trend", "UNION"), ("SPY+QQQ", "20 ETFs"),
                                                    (1, 2, 4), ("none", "aligned", "aligned+nofragile")):
        if uni == "SPY+QQQ" and slots == 4:
            continue
        u = ["SPY", "QQQ"] if uni == "SPY+QQQ" else EQ
        out, tr = run(data, feats, kind, u, slots, gate)
        res[(kind, uni, slots, gate)] = (out, tr)
        row(f"{kind:10s} {uni:8s} slots {slots} {gate}", account(out, rf), out, tr)

    # choose by robustness: best worst-era Sharpe among configs positive in all eras
    def worst_sh(k):
        a = account(res[k][0], rf)
        return min(perf(a.loc[x:y])["Sharpe"] for x, y in ERAS.values())
    ranked = sorted(res, key=worst_sh, reverse=True)
    print("\n=== S2 top 6 by WORST-era Sharpe (robustness ranking, not best-fit) ===")
    for k in ranked[:6]:
        row(f"{k[0]:10s} {k[1]:8s} slots {k[2]} {k[3]}", account(res[k][0], rf), *res[k])
    best = ranked[0]
    print(f"\nselected for detail: {best}")
    out, tr = res[best]
    u = ["SPY", "QQQ"] if best[1] == "SPY+QQQ" else EQ

    print("\n=== S3 leverage on the selected design (position held in a 2x/3x daily-reset ETF or on margin) ===")
    for lev in (1, 2, 3):
        row(f"selected at {lev}x", account(out, rf, lev), out, tr)
    print("\n=== S4 realism checks on the selected design ===")
    o2, t2 = run(data, feats, best[0], u, best[2], best[3], entry="open")
    for lev in (1, 2):
        row(f"entry at NEXT OPEN, {lev}x", account(o2, rf, lev), o2, t2)
    for bps in (10, 20):
        o3, t3 = run(data, feats, best[0], u, best[2], best[3], cost_bps=bps)
        row(f"{bps}bp per side, 1x", account(o3, rf, 1), o3, t3)
        row(f"{bps}bp per side, 2x", account(o3, rf, 2), o3, t3)

    print("\n=== S5 trade statistics, selected design (unlevered, per trade) ===")
    tr["era"] = [next((k for k, (x, y) in ERAS.items() if pd.Timestamp(x) <= d <= pd.Timestamp(y)), None) for d in tr["entry"]]
    w, l = tr[tr["ret"] > 0]["ret"], tr[tr["ret"] <= 0]["ret"]
    print(f"   n={len(tr)}  win {len(w)/len(tr):.0%}  avg win {w.mean():+.2%}  avg loss {l.mean():+.2%}  mean {tr['ret'].mean()*1e4:+.0f}bp  "
          f"worst {tr['ret'].min():+.1%}  best {tr['ret'].max():+.1%}  avg hold {(tr['exit']-tr['entry']).dt.days.mean():.1f} cal days")
    for e in ERAS:
        s = tr[tr["era"] == e]
        print(f"   {e}: n={len(s):4d} mean {s['ret'].mean()*1e4:+5.0f}bp win {(s['ret']>0).mean():.0%} worst {s['ret'].min():+.1%}")
    streak = mx = 0
    for r in tr.sort_values("exit")["ret"]:
        streak = streak + 1 if r <= 0 else 0; mx = max(mx, streak)
    print(f"   longest losing streak: {mx} trades;  top-5 symbols by trade count: {tr['sym'].value_counts().head(5).to_dict()}")

    print("\n=== S6 year by year, selected design vs SPY (1x and 2x) ===")
    a1, a2 = account(out, rf, 1), account(out, rf, 2)
    y = pd.DataFrame({"1x": (1 + a1).groupby(a1.index.year).prod() - 1, "2x": (1 + a2).groupby(a2.index.year).prod() - 1,
                      "SPY": (1 + spy).groupby(spy.index.year).prod() - 1, "expo": out["expo"].groupby(out.index.year).mean()})
    print((y * 100).round(1).to_string())
    print(f"   corr of yearly returns with SPY: 1x {y['1x'].corr(y['SPY']):+.2f};  daily corr {a1.corr(spy):+.2f};  "
          f"years beating T-bills (1x): {(y['1x'] > ((1+rf.reindex(days)).groupby(days.year).prod()-1)).mean():.0%}")
    out.to_pickle("research/cache/swing_standalone_selected.pkl")


if __name__ == "__main__":
    main()
