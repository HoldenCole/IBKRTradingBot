"""Crypto C2 — the Donchian trend ensemble of Zarattini, Pagani and Barbon (2025). See PREREGISTRATION_C2.md.

    python3 -m research.crypto.trend
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

LOOKBACKS = (5, 10, 20, 30, 60, 90, 150, 250, 360)
ANN = 365.0
PAPER_END = pd.Timestamp("2025-03-19")


@njit(cache=True)
def _positions(close, up, mid):
    """Binary position per day for one lookback: enter when close >= Up, exit when close <= trailing stop."""
    n = len(close)
    pos = np.zeros(n)
    p, stop = 0.0, np.nan
    for t in range(n):
        if not np.isfinite(up[t]):
            continue
        if p == 0.0:
            if close[t] >= up[t]:
                p, stop = 1.0, mid[t]
        else:
            if close[t] <= stop:
                p, stop = 0.0, np.nan
            else:
                stop = max(stop, mid[t])
        pos[t] = p
    return pos


def combo(close: pd.Series, target: float = 0.25, cap: float = 2.0) -> tuple[pd.Series, pd.Series]:
    """Target Combo weight at each close, and a flag for days on which any lookback's signal changed."""
    c = close.values.astype(float)
    r = close.pct_change()
    sigma = (r.rolling(90, min_periods=60).std() * np.sqrt(ANN)).values
    size = np.minimum(target / sigma, cap)
    ws, chg = [], np.zeros(len(c), bool)
    for n in LOOKBACKS:
        up = close.rolling(n, min_periods=n).max().values
        lo = close.rolling(n, min_periods=n).min().values
        pos = _positions(c, up, 0.5 * (up + lo))
        chg |= np.r_[False, np.diff(pos) != 0]
        ws.append(np.where(np.isfinite(size), size, 0.0) * pos)
    w = np.mean(ws, axis=0)
    return pd.Series(w, index=close.index), pd.Series(chg, index=close.index)


@njit(cache=True)
def _sleeve(ret, target, chg, cost, thr):
    """One coin's sleeve, equity starting at 1. Position value drifts with the price; at each close the position
    is reset to target on a signal change, or when it is off target by more than thr (relative)."""
    n = len(ret)
    eq = np.ones(n); held = np.zeros(n)
    e, p = 1.0, 0.0
    for t in range(n):
        r = ret[t] if np.isfinite(ret[t]) else 0.0
        e += p * r
        p *= 1.0 + r
        cur = p / e if e > 0 else 0.0
        tgt = target[t]
        if chg[t] or (tgt == 0.0 and cur != 0.0) or (cur == 0.0 and tgt > 0.0) or \
                (cur > 0 and abs(tgt - cur) / cur > thr):
            trade = abs(tgt - cur) * e
            e -= trade * cost
            p = tgt * e
        eq[t] = e; held[t] = p / e if e > 0 else 0.0
    return eq, held


def sleeve(close: pd.Series, target=0.25, cap=2.0, cost=0.001, thr=0.20) -> pd.DataFrame:
    w, chg = combo(close, target, cap)
    eq, held = _sleeve(close.pct_change().values, w.values, chg.values, cost, thr)
    return pd.DataFrame({"eq": eq, "weight": held, "target": w.values}, index=close.index)


def stats(eq: pd.Series) -> dict:
    eq = eq.dropna()
    eq = eq / eq.iloc[0]
    r = eq.pct_change().dropna()
    days = (eq.index[-1] - eq.index[0]).days
    if days < 30 or r.std() == 0:
        return {"CAGR": np.nan, "vol": np.nan, "Sharpe": np.nan, "maxDD": np.nan}
    return {"CAGR": eq.iloc[-1] ** (365.25 / days) - 1, "vol": r.std() * np.sqrt(ANN),
            "Sharpe": r.mean() / r.std() * np.sqrt(ANN), "maxDD": (eq / eq.cummax() - 1).min()}


def part_a():
    from research.crypto.data import coinbase_btc_daily
    btc = coinbase_btc_daily()
    btc = btc[~btc.index.duplicated()].asfreq("D").ffill()
    print("Part A: bitcoin only, Coinbase BTC-USD, no costs, through 2025-03-19 (paper: CAGR 30%, vol 17%, Sharpe 1.58, maxDD 19%)")
    s = sleeve(btc, cost=0.0, thr=0.0)
    for start in ("2015-07-20", "2016-07-20"):
        d = stats(s["eq"].loc[start:PAPER_END])
        print(f"   from {start}: CAGR {d['CAGR']:+.1%} vol {d['vol']:.1%} Sharpe {d['Sharpe']:.2f} maxDD {d['maxDD']:+.1%} "
              f"(average exposure {s['weight'].loc[start:PAPER_END].mean():.0%})")
    rows = []
    for n in LOOKBACKS:
        up = btc.rolling(n, min_periods=n).max().values; lo = btc.rolling(n, min_periods=n).min().values
        pos = _positions(btc.values.astype(float), up, 0.5 * (up + lo))
        sig = (btc.pct_change().rolling(90, min_periods=60).std() * np.sqrt(ANN))
        w = pd.Series(np.minimum(0.25 / sig.values, 2.0) * pos, index=btc.index).fillna(0)
        eq = (1 + w.shift(1).fillna(0) * btc.pct_change().fillna(0)).cumprod()
        d = stats(eq.loc["2015-07-20":PAPER_END])
        rows.append(f"{n}d {d['CAGR']:+.0%}/{d['Sharpe']:.2f}/{d['maxDD']:+.0%}")
    print("   single lookbacks, CAGR/Sharpe/maxDD:", "; ".join(rows))
    print("   paper Table 1: 5d 36%/1.66/25%, 10d 32%/1.55/27%, 20d 34%/1.60/26%, 30d 34%/1.61/24%, 60d 28%/1.30/19%, "
          "90d 27%/1.20/24%, 150d 21%/0.99/29%, 250d 25%/1.13/33%, 360d 29%/1.28/34%")
    post = stats(sleeve(btc, cost=0.001)["eq"].loc[PAPER_END:])
    print(f"   after publication (2025-03-20 on), 10 bp + 20% threshold: CAGR {post['CAGR']:+.1%} Sharpe {post['Sharpe']:.2f} "
          f"maxDD {post['maxDD']:+.1%}; BTC buy and hold {stats(btc.loc[PAPER_END:])['CAGR']:+.1%}")


if __name__ == "__main__":
    part_a()


# ---------------------------------------------------------------- Part B: the portfolio on Binance spot
SIZINGS = {"paper (25% target, cap 200%)": (0.25, 2.0), "spot 50% target": (0.50, 1.0), "spot 100% target": (1.00, 1.0)}
COSTS = (0.0010, 0.0025, 0.0050)
UNIVERSES = (5, 10, 20)
REPL = ("2018-09-01", "2025-03-19")
HALVES = (("2018-09-01", "2021-12-31"), ("2022-01-01", "2025-03-19"))
POST = ("2025-03-20", "2026-12-31")


def panel():
    from research.crypto.data import CACHE, usdt_symbols
    C, V = {}, {}
    for s in usdt_symbols():
        f = CACHE / "spot1d" / f"{s}.parquet"
        if not f.exists():
            continue
        d = pd.read_parquet(f)
        if d.empty or len(d) < 400:
            continue
        d = d[~d.index.duplicated()]
        C[s], V[s] = d["close"], d["qvol"]
    C, V = pd.DataFrame(C).sort_index(), pd.DataFrame(V).sort_index()
    idx = pd.date_range(C.index[0], C.index[-1], freq="D")
    return C.reindex(idx), V.reindex(idx)


def universes(C, V, B):
    """Month end -> list of the top-B eligible pairs for the next month."""
    first = C.apply(lambda s: s.first_valid_index())
    medv = V.rolling(30, min_periods=20).median()
    out = {}
    for d in pd.date_range(C.index[0], C.index[-1], freq="ME"):
        if d not in C.index:
            continue
        ok = (d - first).dt.days >= 365
        mv = medv.loc[d].where(ok & C.loc[d].notna())
        mv = mv[mv >= 2e6].sort_values(ascending=False)
        out[d] = list(mv.index[:B])
    return out


def portfolio(C, V, B, target, cap, cost, thr=0.20, uni=None, weights=None):
    uni = uni or universes(C, V, B)
    R = C.pct_change()
    medv = V.rolling(30, min_periods=20).median()
    medr = R.abs().rolling(30, min_periods=20).median()
    removed = (medv < 1e6) | (medr < 0.005)
    W, CHG = weights
    days = C.index
    month_ends = set(uni)
    E = 1.0; cash = 1.0; sl = {}          # coin -> [equity, position value, removed_flag]
    eq = np.full(len(days), np.nan)
    started = False
    for k, d in enumerate(days):
        # daily mark to market and signal handling
        for coin, s in list(sl.items()):
            r = R.at[d, coin]
            alive = np.isfinite(C.at[d, coin])
            if not alive:                     # delisted or no data: position goes to cash at the last close
                s[1] = 0.0
                continue
            r = 0.0 if not np.isfinite(r) else r
            s[0] += s[1] * r; s[1] *= 1 + r
            if removed.at[d, coin]:
                s[2] = True
            tgt = 0.0 if s[2] else W[coin].at[d]
            cur = s[1] / s[0] if s[0] > 0 else 0.0
            if CHG[coin].at[d] or (tgt == 0 and cur != 0) or (cur == 0 and tgt > 0) or (cur > 0 and abs(tgt - cur) / cur > thr):
                s[0] -= abs(tgt - cur) * s[0] * cost
                s[1] = tgt * s[0]
        if started:
            E = cash + sum(s[0] for s in sl.values())
        # month-end rebalance into next month's universe
        if d in month_ends:
            started = True
            E = cash + sum(s[0] for s in sl.values())
            new = uni[d]
            share = E / B
            nsl = {}
            tc = 0.0
            for coin in set(sl) | set(new):
                old_p = sl[coin][1] if coin in sl else 0.0
                if coin in new:
                    tgt = 0.0 if removed.at[d, coin] else W[coin].at[d]
                    new_p = tgt * share
                    nsl[coin] = [share, new_p, bool(removed.at[d, coin])]
                else:
                    new_p = 0.0
                tc += abs(new_p - old_p) * cost
            cash = E - share * len(new)
            sl = nsl
            if sl:
                per = tc / len(sl)
                for s in sl.values():
                    s[0] -= per
            else:
                cash -= tc
            E = cash + sum(s[0] for s in sl.values())
        eq[k] = E if started else np.nan
    return pd.Series(eq, index=days)


def ew_hold(C, uni, B):
    R = C.pct_change().fillna(0)
    days = C.index; me = sorted(uni)
    eq = pd.Series(np.nan, index=days); E = 1.0; members = []
    for k, d in enumerate(days):
        if members:
            E *= 1 + R.loc[d, members].mean() * len(members) / B
        if d in uni:
            members = uni[d]
        eq.iloc[k] = E if d >= me[0] else np.nan
    return eq


def part_b():
    C, V = panel()
    print(f"panel: {C.shape[1]} pairs, {C.index[0].date()} to {C.index[-1].date()}")
    needed = set()
    unis = {B: universes(C, V, B) for B in UNIVERSES}
    for B in UNIVERSES:
        for v in unis[B].values():
            needed |= set(v)
    rows = []
    btc = C["BTCUSDT"]
    for lab, (tg, cp) in SIZINGS.items():
        W, CHG = {}, {}
        for coin in needed:
            w, chg = combo(C[coin].dropna(), tg, cp)
            W[coin] = w.reindex(C.index).fillna(0.0); CHG[coin] = chg.reindex(C.index).fillna(False)
        for B in UNIVERSES:
            for cost in COSTS:
                eq = portfolio(C, V, B, tg, cp, cost, uni=unis[B], weights=(W, CHG))
                row = {"sizing": lab, "B": B, "cost_bp": cost * 1e4}
                for name, (s, e) in (("repl", REPL), ("h1", HALVES[0]), ("h2", HALVES[1]), ("post", POST)):
                    d = stats(eq.loc[s:e])
                    for m, v in d.items():
                        row[f"{name}_{m}"] = v
                rows.append(row)
                print(f"{lab:30s} B={B:2d} {cost*1e4:3.0f}bp | repl CAGR {row['repl_CAGR']:+6.1%} Sharpe {row['repl_Sharpe']:.2f} "
                      f"maxDD {row['repl_maxDD']:+.0%} | halves Sharpe {row['h1_Sharpe']:.2f} / {row['h2_Sharpe']:.2f} | "
                      f"post CAGR {row['post_CAGR']:+6.1%} Sharpe {row['post_Sharpe']:.2f} maxDD {row['post_maxDD']:+.0%}", flush=True)
    for B in UNIVERSES:
        eh = ew_hold(C, unis[B], B)
        for name, (s, e) in (("repl", REPL), ("post", POST)):
            d = stats(eh.loc[s:e]); b = stats(btc.loc[s:e])
            print(f"benchmark {name}: equal-weight top-{B} held CAGR {d['CAGR']:+.1%} Sharpe {d['Sharpe']:.2f} maxDD {d['maxDD']:+.0%} | "
                  f"BTC held CAGR {b['CAGR']:+.1%} Sharpe {b['Sharpe']:.2f} maxDD {b['maxDD']:+.0%}")
    df = pd.DataFrame(rows)
    df.to_csv("research/crypto/trend_results.csv", index=False, float_format="%.4f")
    g = df[(df.sizing.str.startswith("paper")) & (df.B == 20) & (df.cost_bp == 25)].iloc[0]
    gates = {"1 replication Sharpe >= 1.0": g.repl_Sharpe >= 1.0,
             "2 both halves Sharpe > 0.5": g.h1_Sharpe > 0.5 and g.h2_Sharpe > 0.5,
             "3 post-publication return > 0 and Sharpe >= 0.5": g.post_CAGR > 0 and g.post_Sharpe >= 0.5}
    print("\nGates (paper sizing, B=20, 25 bp):", gates, "-> PASS" if all(gates.values()) else "-> FAIL")
    sample = {d.date(): v[:5] for d, v in list(unis[20].items())[::12]}
    print("universe samples (first five of the top 20, yearly):", sample)
