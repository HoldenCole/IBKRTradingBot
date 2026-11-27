"""Entry 119 — when did levered funds make sense? Rotation across synthetic 3x funds, with overfitting guards.
See PREREGISTRATION_119.md.

    python3 -m research.swing.study_rotation_3x
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.data import CACHE, load  # noqa: E402
from research.swing.lib import daily_features, perf  # noqa: E402

UNI = ["SPY", "QQQ", "IWM", "XLK", "SMH", "XLF", "XLE", "XLV", "XLU", "IYR", "EEM", "TLT", "GDX", "XBI", "KRE", "XHB", "FXI"]
TECH = ["SMH", "XLK", "QQQ"]
FUND = {"SPY": "UPRO", "QQQ": "TQQQ", "IWM": "TNA", "XLK": "TECL", "SMH": "SOXL", "XLF": "FAS", "XLE": "ERX", "XLV": "CURE",
        "XLU": "UTSL", "IYR": "DRN", "EEM": "EDC", "TLT": "TMF", "GDX": "NUGT", "XBI": "LABU", "KRE": "DPST", "XHB": "NAIL",
        "FXI": "YINN"}
SIDE = 0.0009
HALVES = {"2000-12": ("2000-01-01", "2012-12-31"), "2013-26": ("2013-01-01", "2026-12-31")}
SEED = 20261127


def setup():
    data = load()
    data["FXI"] = pd.read_csv(CACHE / "ohlc_FXI.csv", index_col=0, parse_dates=True)
    days = data["SPY"].index[data["SPY"].index >= "1999-01-01"]
    C = pd.DataFrame({s: data[s]["close"] for s in UNI}).reindex(days)
    rf = (data["^IRX"]["close"] / 100 / 252).reindex(days).ffill().fillna(0.0)
    R1 = C.pct_change()
    R3 = 3 * R1 - (2 * (rf + 0.01 / 252) + 0.0095 / 252).values[:, None]
    first = C.apply(lambda s: s.first_valid_index())
    mend = pd.Series(days, index=days).groupby(days.to_period("M")).last()
    M = C.loc[mend.values]                                    # month-end closes
    trend = M > M.rolling(10, min_periods=10).mean()
    elig = pd.DataFrame({s: M.index >= first[s] + pd.DateOffset(months=12) for s in UNI}, index=M.index)
    vol3 = R1.rolling(63).std().loc[mend.values] * np.sqrt(252)
    feats = daily_features(data)
    return data, days, C, rf, R1, R3, M, trend, elig, vol3, feats


def month_paths(R3, M):
    """For each month after a month-end: (days, cumulative growth matrix days x funds)."""
    out = []
    ends = list(M.index)
    for a, b in zip(ends[:-1], ends[1:]):
        g = R3.loc[(R3.index > a) & (R3.index <= b)].fillna(0.0)
        out.append((a, g.index, (1 + g).cumprod().values))
    return out


def run(paths, weights_fn, cols):
    """weights_fn(month_end) -> np.array of target weights over cols. Returns daily account returns."""
    ci = {c: i for i, c in enumerate(UNI)}
    sel = [ci[c] for c in cols]
    prev = np.zeros(len(cols)); rets = []; idx = []
    for a, d, G in paths:
        w = weights_fn(a)
        cost = np.abs(w - prev).sum() * SIDE
        g = G[:, sel]
        val = (1 - w.sum()) + g @ w
        val = np.r_[1.0 - cost, val - cost]
        rets.append(val[1:] / val[:-1] - 1); idx.append(d)
        last = g[-1] * w
        prev = last / val[-1] if val[-1] > 0 else np.zeros(len(cols))
    return pd.Series(np.concatenate(rets), index=np.concatenate(idx))


def rot_weights(M, trend, elig, cols, L, N):
    ret = M[cols] / M[cols].shift(L) - 1
    def f(a):
        e = elig.loc[a, cols] & ret.loc[a].notna()
        r = ret.loc[a][e].sort_values(ascending=False).head(N)
        w = pd.Series(0.0, index=cols)
        for s in r.index:
            if trend.loc[a, s]:
                w[s] = 1 / N
        return w.values
    return f


def trend_weights(trend, elig, cols):
    def f(a):
        e = elig.loc[a, cols]
        k = int(e.sum())
        w = pd.Series(0.0, index=cols)
        if k:
            w[(e & trend.loc[a, cols]).values] = 1 / k
        return w.values
    return f


def rand_weights(trend, elig, cols, N, rng):
    def f(a):
        ok = [s for s in cols if elig.loc[a, s] and trend.loc[a, s]]
        w = pd.Series(0.0, index=cols)
        for s in (rng.choice(ok, size=min(N, len(ok)), replace=False) if ok else []):
            w[s] = 1 / N
        return w.values
    return f


def summ(a):
    a = a.loc["2000-01-01":]
    p = perf(a); h = {k: perf(a.loc[x:y]) for k, (x, y) in HALVES.items()}
    yr = (1 + a).groupby(a.index.year).prod() - 1
    return {"CAGR": p["CAGR"], "maxDD": p["maxDD"], **{f"{k} CAGR": v["CAGR"] for k, v in h.items()},
            **{f"{k} maxDD": v["maxDD"] for k, v in h.items()}, "worst yr": yr.min(), "best yr": yr.max()}


def show(lab, d):
    print(f"{lab:40s} CAGR {d['CAGR']:+6.1%} maxDD {d['maxDD']:+5.0%} | 2000-12 {d['2000-12 CAGR']:+6.1%} {d['2000-12 maxDD']:+5.0%}"
          f" | 2013-26 {d['2013-26 CAGR']:+6.1%} {d['2013-26 maxDD']:+5.0%} | worst yr {d['worst yr']:+5.0%} best {d['best yr']:+6.0%}")


def main():
    data, days, C, rf, R1, R3, M, trend, elig, vol3, feats = setup()
    pd.set_option("display.width", 220)

    print("=== Part 1. When did 3x make sense? Monthly returns of each synthetic 3x fund, 2000-2026 ===")
    ends = list(M.index)
    rows = []
    ret6 = M / M.shift(6) - 1
    for a, b in zip(ends[:-1], ends[1:]):
        if a < pd.Timestamp("1999-12-31"):
            continue
        g3 = (1 + R3.loc[(R3.index > a) & (R3.index <= b)]).prod() - 1
        g1 = (1 + R1.loc[(R1.index > a) & (R1.index <= b)]).prod() - 1
        e = elig.loc[a] & ret6.loc[a].notna()
        rk = ret6.loc[a][e].rank(ascending=False)
        q = feats["quad"].reindex(R1.index).loc[(R1.index > a)].iloc[0] if (R1.index > a).any() else None
        for s in UNI:
            if not e[s]:
                continue
            rows.append({"fund": s, "month": b, "r3": g3[s], "r1": g1[s], "trend": bool(trend.loc[a, s]),
                         "top3": bool(rk[s] <= 3), "vol": vol3.loc[a, s], "quad": q})
    X = pd.DataFrame(rows)
    X["decay"] = X.r3 - 3 * X.r1
    X["vol bucket"] = pd.cut(X.vol, [0, 0.20, 0.35, 9], labels=["vol < 20%", "20-35%", "> 35%"])

    def tab(df, by):
        g = df.groupby(by, observed=True)
        return pd.DataFrame({"months": g.size(), "mean 3x %/mo": g.r3.mean() * 100, "median %": g.r3.median() * 100,
                             "up months": g.r3.apply(lambda x: (x > 0).mean()), "decay %/mo": g.decay.mean() * 100,
                             "worst %": g.r3.min() * 100}).round(2)
    for lab, df in (("all 17 funds", X), ("SMH (the SOXL proxy)", X[X.fund == "SMH"]),
                    ("all except SMH, XLK, QQQ", X[~X.fund.isin(TECH)])):
        print(f"\n-- {lab} --")
        for by in ("trend", "top3", "vol bucket", "quad"):
            print(tab(df, by).to_string()); print()
        print("trend x vol:"); print(tab(df, ["trend", "vol bucket"]).to_string()); print()
        h1, h2 = df[df.month <= "2012-12-31"], df[df.month >= "2013-01-01"]
        for hl, hd in (("2000-12", h1), ("2013-26", h2)):
            on = hd[hd.trend & (hd["vol bucket"] != "> 35%")]; off = hd[~hd.trend]
            print(f"   {hl}: trend on and vol <= 35%: {on.r3.mean() * 100:+.2f}%/mo ({len(on)}); trend off: {off.r3.mean() * 100:+.2f}%/mo ({len(off)})")

    paths = month_paths(R3, M)
    paths = [p for p in paths if p[0] >= pd.Timestamp("1999-12-31")]
    print("\n=== Part 2. Rotation (synthetic 3x, 2000-2026) ===")
    res = {}
    for lab, cols in (("all 17", UNI), ("without SMH, XLK, QQQ", [c for c in UNI if c not in TECH])):
        print(f"\n-- universe: {lab} --")
        t = summ(run(paths, trend_weights(trend, elig, cols), cols)); show("equal-weight trend rule", t)
        if lab == "all 17":
            spy = summ(run(paths, lambda a: np.array([1.0 if (elig.loc[a, "SPY"] and trend.loc[a, "SPY"]) else 0.0]), ["SPY"]))
            show("SPY 3x while above 10-month average", spy)
        grid = {}
        for L, N in itertools.product((3, 6, 12), (1, 2, 3)):
            d = summ(run(paths, rot_weights(M, trend, elig, cols, L, N), cols)); grid[(L, N)] = d
            show(f"rotation L={L:2d} N={N}" + ("  <- P" if (L, N) == (6, 2) else ""), d)
        med = {k: float(np.median([g[k] for g in grid.values()])) for k in grid[(6, 2)]}
        show("grid median (each column separately)", med)
        res[lab] = {"T": t, "P": grid[(6, 2)], "median": med, "grid": grid}

    print("\n=== Random control: N=2 at random among funds above their 10-month average, 500 draws, all 17 ===")
    rng = np.random.default_rng(SEED)
    rc = [summ(run(paths, rand_weights(trend, elig, UNI, 2, rng), UNI)) for _ in range(500)]
    cg = np.array([r["CAGR"] for r in rc])
    print(f"random CAGR median {np.median(cg):+.1%}, 95th pct {np.percentile(cg, 95):+.1%}, best {cg.max():+.1%}; "
          f"P {res['all 17']['P']['CAGR']:+.1%}; random maxDD median {np.median([r['maxDD'] for r in rc]):+.0%}")
    for k in HALVES:
        x = np.array([r[f"{k} CAGR"] for r in rc])
        print(f"   {k}: random median {np.median(x):+.1%}, 95th {np.percentile(x, 95):+.1%}; P {res['all 17']['P'][f'{k} CAGR']:+.1%}")

    P, T = res["all 17"]["P"], res["all 17"]["T"]
    Px, Tx = res["without SMH, XLK, QQQ"]["P"], res["without SMH, XLK, QQQ"]["T"]
    c1 = all(P[f"{k} CAGR"] > T[f"{k} CAGR"] for k in HALVES)
    c2 = P["CAGR"] > np.percentile(cg, 95)
    c3 = all(Px[f"{k} CAGR"] > Tx[f"{k} CAGR"] for k in HALVES)
    med = res["all 17"]["median"]
    fragile = not all(med[f"{k} CAGR"] > T[f"{k} CAGR"] for k in HALVES)
    print(f"\nP beats trend rule both halves: {c1}; beats random 95th pct: {c2}; ex-tech P beats ex-tech trend both halves: {c3}"
          f" -> PASSES: {c1 and c2 and c3}{' (fragile: grid median does not)' if (c1 and c2 and c3 and fragile) else ''}")

    print("\n=== Today (informational; never trades) ===")
    for a, lab in ((M.index[-2], "last completed month-end"), (M.index[-1], "latest close, provisional")):
        r6 = (M.loc[a] / M.shift(6).loc[a] - 1)
        t = pd.DataFrame({"6-month %": r6 * 100, "above 10-month avg": trend.loc[a], "3-month vol %": vol3.loc[a] * 100,
                          "3x fund": pd.Series(FUND)}).sort_values("6-month %", ascending=False)
        held = [s for s in t.index[:2] if t.loc[s, "above 10-month avg"]]
        print(f"\n{lab} {a.date()}: P would hold {held or 'cash'}; trend on for {int(t['above 10-month avg'].sum())} of 17")
        print(t.round(1).to_string())
    X.to_csv(ROOT / "research" / "swing" / "rotation_3x_months.csv", index=False, float_format="%.5f")


if __name__ == "__main__":
    main()
