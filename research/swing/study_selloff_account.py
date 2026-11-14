"""Entry 81b — the sell-off bounce as a standalone account: which assets,
with or without the trend-line filter, leverage, and (again) stops.

Entry: z5 crosses below -2 at the close (see study_stretch). Exit: first close
above the 5d SMA or 10 trading days. Optional stop on the underlying, checked
against the day's low and filled at min(open, stop). Two or three slots.

    python3 -m research.swing.study_selloff_account
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load
from research.swing.lib import ERAS, bollinger, daily_features, perf, rsi, sma
from research.swing.study_stretch import z5

START = "1999-06-01"
EQUITY = ["SPY", "QQQ"]
MODEL = ["SPY", "QQQ", "XLE", "GLD", "GDX", "TLT", "DBC", "USO"]
SECT = ["XLF", "XLK", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "SMH"]


def entries(data, sym, kind):
    df = data[sym]; c = df["close"]
    z = z5(c); above = c > sma(c, 210)
    sold = (z <= -2) & (z.shift(1) > -2)
    mid, up, lo, pctb, bw = bollinger(c); r2 = rsi(c, 2)
    union = (r2 < 10) & ((c < lo) | (c > sma(c, 200)))
    if kind == "z5":
        e = sold
    elif kind == "z5+line":
        e = sold & above
    elif kind == "z5+line(non-eq)":
        e = sold if sym in EQUITY else sold & above
    elif kind == "e79":
        e = union
    elif kind == "e79+z5line":
        e = (union | sold) if sym in EQUITY else sold & above
    else:
        raise ValueError(kind)
    return e.fillna(False), c > sma(c, 5), z


def run(data, feats, universe, kind, slots=2, gate=None, stop=None, cost=5 / 1e4):
    days = feats.index[feats.index >= START]; n = len(days)
    O, L, C, R, E, X, P = {}, {}, {}, {}, {}, {}, {}
    for s in universe:
        df = data[s].reindex(days)
        O[s], L[s], C[s] = df["open"].values, df["low"].values, df["close"].values
        R[s] = df["close"].pct_change().fillna(0.0).values
        e, x, z = entries(data, s, kind)
        E[s] = e.reindex(days).fillna(False).values; X[s] = x.reindex(days).fillna(False).values
        P[s] = z.reindex(days).values
    quad = feats["quad"].reindex(days).values
    frag = ((feats["spy_ext200"].between(0, 0.03)) & (feats["rvol20"] > 0.16)).reindex(days).fillna(False).values
    held = {}; pos = np.zeros(n); expo = np.zeros(n); trades = []
    for i in range(n):
        expo[i] = len(held) / slots
        for s in list(held):
            ei, epx = held[s]
            if stop is not None and L[s][i] <= epx * (1 - stop):
                xpx = min(O[s][i], epx * (1 - stop))
                pos[i] += (xpx / C[s][i - 1] - 1 - cost) / slots
                trades.append((days[ei], days[i], s, xpx / epx - 1 - 2 * cost, "stop")); del held[s]; continue
            pos[i] += R[s][i] / slots
            if X[s][i] or i - ei >= 10:
                pos[i] -= cost / slots
                trades.append((days[ei], days[i], s, C[s][i] / epx - 1 - 2 * cost, "rule" if X[s][i] else "time")); del held[s]
        free = slots - len(held)
        if free > 0:
            cands = []
            for s in universe:
                if not E[s][i] or s in held or np.isnan(C[s][i]):
                    continue
                if gate and s in EQUITY and not (isinstance(quad[i], str) and quad[i] in "GR" and not frag[i]):
                    continue
                cands.append(s)
            for s in sorted(cands, key=lambda s: P[s][i] if not np.isnan(P[s][i]) else 0)[:free]:
                held[s] = (i, C[s][i]); pos[i] -= cost / slots
    out = pd.DataFrame({"pos": pos, "expo": expo}, index=days)
    return out, pd.DataFrame(trades, columns=["entry", "exit", "sym", "ret", "why"])


def account(out, rf, lev=1):
    r = rf.reindex(out.index).fillna(0.0)
    return lev * out["pos"] - out["expo"] * ((lev - 1) * (r + 0.01 / 252) + (0.0095 / 252 if lev > 1 else 0.0)) + (1 - out["expo"]) * r


def row(lab, out, tr, rf, lev=1):
    a = account(out, rf, lev); p = perf(a)
    yr = (1 + a).groupby(a.index.year).prod() - 1
    eras = "  ".join(f"{k[:1]} {perf(a.loc[x:y])['CAGR']:+5.1%}/{perf(a.loc[x:y])['maxDD']:+4.0%}" for k, (x, y) in ERAS.items())
    print(f"{lab:58s} CAGR {p['CAGR']:+5.1%} Sh {p['Sharpe']:.2f} DD {p['maxDD']:+4.0%} worst yr {yr.min():+4.0%} +yrs {(yr>0).mean():3.0%} "
          f"expo {out['expo'].mean():3.0%} tr/yr {len(tr)/(len(out)/252):3.0f} mean {tr['ret'].mean()*1e4:+4.0f}bp win {(tr['ret']>0).mean():.0%} worst {tr['ret'].min():+.0%} | {eras}")


def main():
    data = load(); feats = daily_features(data)
    rf = (data["^IRX"]["close"] / 100 / 252).reindex(feats.index).ffill().fillna(0.0)
    print("era cells = CAGR/maxDD (A 1999-06, B 2007-16, C 2017-26); 1x unless stated; T-bills on idle cash\n")
    print("=== A1 which assets and filters (2 slots, no stop) ===")
    cfgs = [("entry 79 baseline: SPY+QQQ RSI2/band, regime gate", EQUITY, "e79", 2, True),
            ("sell-off z5<-2: SPY+QQQ, no gate", EQUITY, "z5", 2, False),
            ("sell-off z5<-2: SPY+QQQ, regime gate", EQUITY, "z5", 2, True),
            ("sell-off z5<-2: 8 model assets, no filter", MODEL, "z5", 2, False),
            ("sell-off z5<-2: 8 model assets, above trend line", MODEL, "z5+line", 2, False),
            ("sell-off: model assets, line filter on non-equity only", MODEL, "z5+line(non-eq)", 2, False),
            ("sell-off: model assets + 9 sectors, above trend line", MODEL + SECT, "z5+line", 2, False),
            ("COMBINED: entry-79 on SPY/QQQ (gated) + sell-offs above line on energy/gold/bonds/oil/commod", MODEL, "e79+z5line", 2, True),
            ("COMBINED, 3 slots", MODEL, "e79+z5line", 3, True)]
    res = {}
    for lab, u, kind, slots, gate in cfgs:
        out, tr = run(data, feats, u, kind, slots, gate)
        res[lab] = (out, tr); row(lab[:58], out, tr, rf)

    print("\n=== A2 leverage (2x / 3x instruments) on three designs ===")
    for lab in (cfgs[0][0], cfgs[2][0], cfgs[7][0]):
        for lev in (1, 2, 3):
            row(f"{lev}x  {lab[:52]}", *res[lab], rf, lev)

    print("\n=== A3 stops on the underlying (sell-off SPY+QQQ regime gate; and COMBINED), 1x and 3x ===")
    for lab, u, kind, slots, gate in (cfgs[2], cfgs[7]):
        for stop in (None, 0.10, 0.07, 0.05, 0.03, 0.02, 0.01):
            out, tr = run(data, feats, u, kind, slots, gate, stop=stop)
            stopped = (tr["why"] == "stop").mean()
            a1, a3 = perf(account(out, rf, 1)), perf(account(out, rf, 3))
            print(f"   {lab[:34]:34s} stop {str(stop):5s}: stopped {stopped:4.0%} mean {tr['ret'].mean()*1e4:+4.0f}bp win {(tr['ret']>0).mean():.0%} "
                  f"| 1x CAGR {a1['CAGR']:+5.1%} DD {a1['maxDD']:+4.0%} | 3x CAGR {a3['CAGR']:+5.1%} DD {a3['maxDD']:+4.0%}")

    print("\n=== A4 per-asset trades inside COMBINED (2 slots) ===")
    out, tr = res[cfgs[7][0]]
    tr["era"] = [next((k for k, (x, y) in ERAS.items() if pd.Timestamp(x) <= d <= pd.Timestamp(y)), None) for d in tr["entry"]]
    for s, g in tr.groupby("sym"):
        print(f"   {s:4s} n={len(g):4d} mean {g['ret'].mean()*1e4:+5.0f}bp win {(g['ret']>0).mean():.0%} worst {g['ret'].min():+.1%} | by era "
              + " ".join(f"{g[g['era']==k]['ret'].mean()*1e4:+5.0f}/{(g['era']==k).sum():<3d}" for k in ERAS))


if __name__ == "__main__":
    main()
