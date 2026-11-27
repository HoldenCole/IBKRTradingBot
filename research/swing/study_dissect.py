"""Entry 115 — why the 3x swing plan works, whether it transfers, and what could improve it.
See PREREGISTRATION_115.md.

    python3 -m research.swing.study_dissect
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.data import CACHE, load  # noqa: E402
from research.swing.lib import ERAS, bollinger, daily_features, perf, rsi, sma  # noqa: E402

START = "1999-06-01"
SIDE = 0.0009                     # 9 bp a side on the fund bought, at the small account's size
ERA_ROWS = {"A": ("1999-06-01", "2006-12-31"), "B": ("2007-01-01", "2016-12-31"), "C": ("2017-01-01", "2026-12-31")}


# ------------------------------------------------------------------ signals
def entry_rule(df, kind="UNION", rsi_max=10):
    c = df["close"]
    _, _, lo, _, _ = bollinger(c, 20, 2.0)
    r2 = rsi(c, 2)
    base = r2 < rsi_max
    if kind == "UNION":
        e = base & ((c < lo) | (c > sma(c, 200)))
    elif kind == "RSI2":
        e = base
    elif kind == "RSI2+BB":
        e = base & (c < lo)
    elif kind == "RSI2+trend":
        e = base & (c > sma(c, 200))
    else:
        raise ValueError(kind)
    return e, r2


def exit_rule(df, kind="SMA5"):
    c = df["close"]
    if kind == "SMA5":
        return c > sma(c, 5)
    if kind == "UPCLOSE":
        return c > c.shift(1)
    if kind == "NONE":
        return pd.Series(False, index=c.index)
    raise ValueError(kind)


# ------------------------------------------------------------------ engine (same order of events as study_standalone.run)
def engine(data, feats, universe=("SPY", "QQQ"), slots=2, entry="UNION", rsi_max=10, exit_="SMA5", max_hold=10,
           gate="full", lev_fn=None, random_p=None, seed=0):
    days = feats.index[feats.index >= START]
    n = len(days)
    rng = np.random.default_rng(seed)
    cc, on, E, X, P = {}, {}, {}, {}, {}
    for s in universe:
        df = data[s].reindex(days)
        cc[s] = df["close"].pct_change().fillna(0.0).values
        on[s] = (df["open"] / df["close"].shift(1) - 1).fillna(0.0).values
        e, r2 = entry_rule(data[s], entry, rsi_max)
        E[s] = e.reindex(days).fillna(False).values
        if random_p is not None:
            E[s] = rng.random(n) < random_p
        X[s] = exit_rule(data[s], exit_).reindex(days).fillna(False).values
        P[s] = r2.reindex(days).values if random_p is None else rng.random(n)
    quad = feats["quad"].reindex(days).values
    frag = ((feats["spy_ext200"].between(0, 0.03)) & (feats["rvol20"] > 0.16)).reindex(days).fillna(False).values
    vix = feats["vix"].reindex(days).values
    levs = sorted({3} | ({2} if lev_fn else set()))
    pos = {L: np.zeros(n) for L in levs}; expo = {L: np.zeros(n) for L in levs}
    sides = np.zeros(n)
    held, trades = {}, []
    for i in range(n):
        for s, st in held.items():
            r = cc[s][i]
            pos[st["L"]][i] += r / slots
            st["rets"].append(r); st["on"].append(on[s][i])
        for s, st in held.items():
            expo[st["L"]][i] += 1 / slots
        for s in list(held):
            st = held[s]
            if X[s][i] or i - st["i"] >= max_hold:
                sides[i] += 1 / slots
                trades.append({"entry": days[st["i"]], "exit": days[i], "sym": s, "L": st["L"], "rsi": st["rsi"],
                               "vix": st["vix"], "quad": st["quad"], "frag": st["frag"], "rets": st["rets"],
                               "on": st["on"]})
                del held[s]
        ok = True
        if gate in ("full", "nofrag"):
            ok = isinstance(quad[i], str) and quad[i] in "GR"
        if gate == "full" and frag[i]:
            ok = False
        free = slots - len(held)
        if ok and free > 0:
            cands = sorted((s for s in universe if E[s][i] and s not in held and not np.isnan(P[s][i])),
                           key=lambda s: P[s][i])
            for s in cands[:free]:
                sides[i] += 1 / slots
                L = lev_fn(vix[i]) if lev_fn else 3
                held[s] = {"i": i, "L": L, "rsi": P[s][i], "vix": vix[i], "quad": quad[i], "frag": bool(frag[i]),
                           "rets": [], "on": []}
    tr = pd.DataFrame(trades)
    if len(tr):
        tr["ret1x"] = [np.prod(1 + np.array(r)) - 1 for r in tr.rets]
    return {"days": days, "pos": pos, "expo": expo, "sides": sides, "trades": tr}


def account(res, rf, lev_override=None, idle="zero"):
    days = res["days"]
    r = rf.reindex(days).fillna(0.0).values
    a = np.zeros(len(days)); tot_expo = np.zeros(len(days))
    for L in res["pos"]:
        LL = lev_override or L
        a += LL * res["pos"][L] - res["expo"][L] * ((LL - 1) * (r + 0.01 / 252) + (0.0095 / 252 if LL > 1 else 0.0))
        tot_expo += res["expo"][L]
    a -= res["sides"] * SIDE
    if idle == "bills":
        a += (1 - tot_expo) * (r - 0.001 / 252)
        a -= np.abs(np.diff(np.r_[0.0, tot_expo])) * SIDE
    return pd.Series(a, index=days)


def eras(a):
    out = {}
    for k, (x, y) in ERA_ROWS.items():
        p = perf(a.loc[x:y])
        out[k] = (p["CAGR"], p["maxDD"], p["Sharpe"])
    p = perf(a)
    out["all"] = (p["CAGR"], p["maxDD"], p["Sharpe"])
    return out


def line(lab, a, res=None):
    e = eras(a)
    cells = "  ".join(f"{k} {c:+6.1%} {d:+5.0%} {s:4.2f}" for k, (c, d, s) in e.items())
    extra = f"  {len(res['trades']) / (len(a) / 252):4.0f} tr/yr" if res is not None else ""
    print(f"{lab:38s} {cells}{extra}")
    return e


# ------------------------------------------------------------------ part 3 helpers
def trades_single(close, gate_trend=False, cost=0.0005, max_hold=10):
    c = close.dropna()
    c = c[c.index >= "1999-01-01"]
    full = close.dropna()
    e, _ = entry_rule(pd.DataFrame({"close": full}))
    x = exit_rule(pd.DataFrame({"close": full}))
    if gate_trend:
        m = full.resample("ME").last()
        on = (m > m.rolling(10).mean()).shift(1)          # known at the prior month-end
        on.index = on.index.to_period("M")
        g = pd.Series(full.index.to_period("M").map(on.to_dict()), index=full.index).fillna(False).astype(bool)
        e = e & g
    e, x = e.reindex(c.index).fillna(False).values, x.reindex(c.index).fillna(False).values
    r = c.pct_change().fillna(0.0).values
    out, i0, acc = [], None, 1.0
    for i in range(len(c)):
        if i0 is not None:
            acc *= 1 + r[i]
            if x[i] or i - i0 >= max_hold:
                out.append((c.index[i0], acc - 1 - 2 * cost)); i0 = None
        if i0 is None and e[i]:
            i0, acc = i, 1.0
    return pd.DataFrame(out, columns=["entry", "ret"])


def tstat(x):
    x = np.asarray(x)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan


# ------------------------------------------------------------------ main
def main():
    data = load()
    for s in ("^GDAXI", "^FTSE", "^N225"):
        df = pd.read_csv(CACHE / f"ohlc_{s}.csv", index_col=0, parse_dates=True)
        data[s] = df[df.index < "2026-11-27"]
    feats = daily_features(data)
    rf = (data["^IRX"]["close"] / 100 / 252).reindex(feats.index).ffill().fillna(0.0)
    rows = {}
    pd.set_option("display.width", 220)
    print("cells: era CAGR / maxDD / Sharpe; eras A 1999-06..2006, B 2007-2016, C 2017-2026; idle cash earns 0\n")

    print("=== Part 1. One piece at a time, at 3x ===")
    base = engine(data, feats)
    ab = account(base, rf)
    rows["baseline"] = line("baseline (live plan)", ab, base)
    line("baseline at 1x (same trades)", account(base, rf, lev_override=1), base)
    spy = data["SPY"]["close"].pct_change().reindex(base["days"]).fillna(0.0)
    line("SPY buy and hold, 1x", spy)
    r = rf.reindex(base["days"]).fillna(0.0)
    line("SPY buy and hold, 3x daily reset", 3 * spy - 2 * (r + 0.01 / 252) - 0.0095 / 252)
    variants = {
        "no regime gate": dict(gate="none"),
        "regime gate, no fragile veto": dict(gate="nofrag"),
        "entry RSI(2)<10 alone": dict(entry="RSI2"),
        "entry RSI(2) + Bollinger leg only": dict(entry="RSI2+BB"),
        "entry RSI(2) + trend leg only": dict(entry="RSI2+trend"),
        "exit after a fixed 3 days": dict(exit_="NONE", max_hold=3),
        "SPY only (one full slot)": dict(universe=("SPY",), slots=1),
        "QQQ only (one full slot)": dict(universe=("QQQ",), slots=1),
        "one slot (SPY or QQQ)": dict(slots=1),
    }
    p1 = {}
    for lab, kw in variants.items():
        res = engine(data, feats, **kw)
        p1[lab] = line(lab, account(res, rf), res)

    print("\n=== Part 2. Where the return comes from (baseline trades, 1x unless stated) ===")
    tr = base["trades"].copy()
    ex = sum(base["expo"].values())
    print(f"time in the market: {(ex > 0).mean():.0%} of days; average exposure {ex.mean():.0%} of the account")
    print(f"trades {len(tr)}, mean {tr.ret1x.mean() * 1e4:+.0f} bp gross, win {(tr.ret1x > 0).mean():.0%}, "
          f"median hold {np.median([len(x) for x in tr.rets]):.0f} days")
    # by holding day
    hd = {}
    for rets in tr.rets:
        for k, v in enumerate(rets, 1):
            hd.setdefault(k, []).append(v)
    tot = sum(sum(v) for v in hd.values())
    t2 = pd.DataFrame({"open trades": {k: len(v) for k, v in hd.items()},
                       "mean bp": {k: np.mean(v) * 1e4 for k, v in hd.items()},
                       "share of total": {k: sum(v) / tot for k, v in hd.items()}})
    print("\nby holding day:"); print(t2.round(2).to_string())
    # overnight vs intraday (log shares)
    lo = sum(np.log1p(np.array(x)).sum() for x in tr.on)
    lc = sum(np.log1p(np.array(x)).sum() for x in tr.rets)
    print(f"\nlog return while held: total {lc:+.3f}; overnight (close to open) {lo:+.3f} ({lo / lc:.0%}); "
          f"intraday (open to close) {lc - lo:+.3f} ({(lc - lo) / lc:.0%})")
    # unconditional overnight/intraday for SPY+QQQ over the same days
    for s in ("SPY", "QQQ"):
        d = data[s].reindex(base["days"])
        o = np.log(d["open"] / d["close"].shift(1)).sum(); c = np.log(d["close"] / d["close"].shift(1)).sum()
        print(f"   {s} every day, same period: total {c:+.3f}, overnight {o:+.3f}, intraday {c - o:+.3f}")
    # by RSI depth and VIX
    tr["rsi bucket"] = pd.cut(tr.rsi, [-0.01, 2, 5, 10], labels=["<2", "2-5", "5-10"])
    tr["vix bucket"] = pd.cut(tr.vix, [0, 15, 20, 30, 200], labels=["<15", "15-20", "20-30", ">30"])
    for col in ("rsi bucket", "vix bucket"):
        g = tr.groupby(col, observed=True).ret1x
        print(f"\nby {col}:"); print(pd.DataFrame({"trades": g.size(), "mean bp": g.mean() * 1e4, "win": g.apply(lambda x: (x > 0).mean()),
                                                  "t": g.apply(tstat)}).round(2).to_string())
    # what the gate removed
    ug = engine(data, feats, gate="none")["trades"]
    ug["state"] = np.where(ug.quad.isin(["G", "R"]) & ~ug.frag, "G/R, not fragile (kept)",
                           np.where(ug.quad.isin(["G", "R"]), "G/R, fragile (removed)",
                                    "quadrant " + ug.quad.astype(str) + " (removed)"))
    g = ug.groupby("state").ret1x
    print("\nungated signals by regime at entry:")
    print(pd.DataFrame({"trades": g.size(), "mean bp": g.mean() * 1e4, "win": g.apply(lambda x: (x > 0).mean()),
                        "worst": g.min() * 100, "t": g.apply(tstat)}).round(2).to_string())
    # daily reset path effect
    r3 = np.array([np.prod(1 + 3 * np.array(x)) - 1 for x in tr.rets])
    gap = r3 - 3 * tr.ret1x.values
    print(f"\n3x daily reset vs 3 x the 1x trade return (before costs and financing): mean gap {gap.mean() * 1e4:+.1f} bp, "
          f"median {np.median(gap) * 1e4:+.1f} bp, worst {gap.min() * 1e4:+.0f} bp, best {gap.max() * 1e4:+.0f} bp")
    fin = np.mean([len(x) for x in tr.rets]) * (2 * (rf.mean() + 0.01 / 252) + 0.0095 / 252)
    print(f"   financing and fund fees per 3x trade, average: {fin * 1e4:.1f} bp; round-trip cost {2 * SIDE * 1e4:.0f} bp")

    # random-entry control (added; descriptive)
    freq = np.mean([entry_rule(data[s])[0].reindex(base["days"]).fillna(False).mean() for s in ("SPY", "QQQ")])
    cg = []
    for sd in range(200):
        res = engine(data, feats, random_p=freq, seed=sd)
        cg.append(perf(account(res, rf))["CAGR"])
    cg = np.array(cg)
    print(f"\nrandom-entry control (added, descriptive): random entry days at the signal's frequency ({freq:.1%} of days), "
          f"same gate, exits and 3x: CAGR median {np.median(cg):+.1%}, 95th pct {np.percentile(cg, 95):+.1%}, "
          f"best {cg.max():+.1%}; plan {perf(ab)['CAGR']:+.1%}")

    print("\n=== Part 3. Same rules elsewhere (1x, one position, 5 bp a side) ===")
    inst = ["IWM", "DIA", "XLE", "XLF", "XLK", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "SMH", "EFA", "EEM",
            "^GDAXI", "^FTSE", "^N225", "GLD", "TLT", "DBC", "BTC"]
    ref = ["SPY", "QQQ"]
    from research.crypto.data import coinbase_btc_daily
    btc = coinbase_btc_daily()
    btc = btc[btc.index < "2026-11-27"]
    rows3 = []
    for s in ref + inst:
        close = btc if s == "BTC" else data[s]["close"]
        cut = "2021-01-01" if s == "BTC" else "2013-01-01"
        for ver, gt in (("no gate", False), ("own trend", True)):
            t = trades_single(close, gate_trend=gt)
            h1, h2 = t[t.entry < cut].ret, t[t.entry >= cut].ret
            passes = (t.ret.mean() > 0 and tstat(t.ret) >= 2 and h1.mean() > 0 and h2.mean() > 0)
            rows3.append({"instrument": s + (" (built on)" if s in ref else ""), "version": ver, "trades": len(t),
                          "mean bp": t.ret.mean() * 1e4, "win": (t.ret > 0).mean(), "t": tstat(t.ret),
                          "1st half bp": h1.mean() * 1e4, "2nd half bp": h2.mean() * 1e4,
                          "transfers": bool(passes) if s not in ref else "-"})
    t3 = pd.DataFrame(rows3)
    print(t3.round(2).to_string(index=False))
    t3.to_csv(ROOT / "research" / "swing" / "dissect_transfer.csv", index=False, float_format="%.4f")
    inst_pass = sorted({r["instrument"] for r in rows3 if r["transfers"] is True})
    print(f"\ntransfer (either version passes): {len(inst_pass)} of {len(inst)}: {inst_pass}")

    print("\n=== Part 4. Candidate improvements, each alone, at 3x ===")
    line("baseline", ab, base)
    cands = {
        "I1 add IWM": (dict(universe=("SPY", "QQQ", "IWM")), "zero"),
        "I2 exit at first up close": (dict(exit_="UPCLOSE"), "zero"),
        "I3 2x when VIX > 30 at entry": (dict(lev_fn=lambda v: 2 if v > 30 else 3), "zero"),
        "I4 idle cash in T-bill ETF": ({}, "bills"),
        "I5 RSI(2) < 5": (dict(rsi_max=5), "zero"),
    }
    verdict = {}
    for lab, (kw, idle) in cands.items():
        res = base if not kw else engine(data, feats, **kw)
        e = line(lab, account(res, rf, idle=idle), res)
        b = rows["baseline"]
        ok = all(e[k][0] > b[k][0] and e[k][1] >= b[k][1] for k in "ABC")
        better_all = e["all"][0] > b["all"][0]
        verdict[lab] = "IMPROVEMENT" if ok else ("lead only" if better_all else "no")
    print("\nverdicts:", verdict)


if __name__ == "__main__":
    main()
