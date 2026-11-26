"""Entry 93: price-target and stop exits on the entry 92 events (see PREREGISTRATION_93.md).

    python3 -m research.stock_reversal.price_exits
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit
from scipy.stats import norm

from research.stock_reversal.data import membership
from research.stock_reversal.events import DEV_END, START, prices
from research.stock_reversal.run import clustered_t, holm
from research.swing.data import ohlc

TARGETS = (0.01, 0.02, 0.03, 0.05)
STOPS = (0.03, 0.06, 0.10)
CAP = 20
COST, STOP_SLIP = 0.0010, 0.0010
N_CTRL = 20
ERA_SPLIT = pd.Timestamp("2015-01-01")
HERE = "research/stock_reversal"


@njit(cache=True)
def simulate(o, h, l, c, entries, open_entry, sign, T, S, cap, cost, slip):
    n = len(entries)
    ret = np.full(n, np.nan); held = np.zeros(n); hit = np.zeros(n, np.int8)   # 1 target, -1 stop, 0 time
    last = len(c) - 1
    for k in range(n):
        i = entries[k]
        P = o[i] if open_entry else c[i]
        if not (P > 0):
            continue
        s = sign[k]
        tgt = P * (1 + s * T); stp = P * (1 - s * S)
        first = i if open_entry else i + 1
        end = min(i + cap, last)
        x = np.nan; kind = 0; j = first
        if first > last:
            continue
        for j in range(first, end + 1):
            if not (j == i and open_entry):
                if (s > 0 and o[j] >= tgt) or (s < 0 and o[j] <= tgt):
                    x = o[j]; kind = 1; break
                if (s > 0 and o[j] <= stp) or (s < 0 and o[j] >= stp):
                    x = o[j]; kind = -1; break
            if (s > 0 and l[j] <= stp) or (s < 0 and h[j] >= stp):
                x = stp; kind = -1; break
            if (s > 0 and h[j] >= tgt) or (s < 0 and l[j] <= tgt):
                x = tgt; kind = 1; break
        if kind == 0:
            j = end; x = c[end]
        r = (x / P - 1) if s > 0 else (1 - x / P)
        ret[k] = r - 2 * cost - (slip if kind == -1 else 0.0)
        held[k] = j - i + (1 if open_entry else 0)
        hit[k] = kind
    return ret, held, hit


def main():
    ev = pd.read_parquet("research/cache/stock_reversal_events_dev.parquet")
    ev = ev[ev["size"].isin(["L", "X"])]
    base = pd.concat([ev[(ev.kind == "gap") & (ev.horizon == "H0")], ev[(ev.kind == "day") & (ev.horizon == "H1")]])
    base = base[["ticker", "date", "kind", "bucket", "ex", "dir"]].reset_index(drop=True)
    allbig = ev[["ticker", "date"]].drop_duplicates()
    spy = ohlc("SPY")
    sess = spy.index[spy.index < DEV_END]
    m = membership()
    rng = np.random.default_rng(93)
    out = []
    for t, grp in base.groupby("ticker"):
        px = prices(t)
        if px is None:
            continue
        df = px.reindex(sess)
        o, h, l, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
        raw = df["raw_close"].values
        pos = pd.Series(np.arange(len(sess)), index=sess)
        # control pool: member days, close >= $5, from 2005, not within 5 sessions of a big move of this stock
        mem = np.zeros(len(sess), bool)
        for _, w in m[m.ticker == t].iterrows():
            if px.index[0] > max(w.start_date, pd.Timestamp("2004-06-01")) - pd.Timedelta(days=60):
                continue
            mem |= (sess >= w.start_date) & (sess <= w.end_date)
        near = np.zeros(len(sess), bool)
        for d in allbig[allbig.ticker == t]["date"]:
            p = pos.get(d)
            if p is not None:
                near[max(0, p - 5): p + 6] = True
        prev_raw = np.r_[np.nan, raw[:-1]]
        pool = np.where(mem & ~near & (sess >= START) & (prev_raw >= 5) & np.isfinite(o) & np.isfinite(c))[0]
        if len(pool) < N_CTRL:
            continue
        idx = grp["date"].map(pos).values.astype(np.int64)
        sign = -grp["dir"].values.astype(float)
        ctrl = rng.choice(pool, size=(len(grp), N_CTRL))
        for openA in (True, False):
            sel = (grp["kind"] == ("gap" if openA else "day")).values
            if not sel.any():
                continue
            e_idx, e_sign = idx[sel], sign[sel]
            c_idx = ctrl[sel].ravel(); c_sign = np.repeat(e_sign, N_CTRL)
            g = grp[sel]
            for T in TARGETS:
                for S in STOPS:
                    r, hd, hit = simulate(o, h, l, c, e_idx, openA, e_sign, T, S, CAP, COST, STOP_SLIP)
                    cr, _, _ = simulate(o, h, l, c, c_idx, openA, c_sign, T, S, CAP, COST, STOP_SLIP)
                    cm = np.nanmean(cr.reshape(-1, N_CTRL), axis=1)
                    out.append(pd.DataFrame({"ticker": t, "date": g["date"].values, "bucket": g["bucket"].values,
                                             "ex": g["ex"].values, "dir": g["dir"].values,
                                             "entry": "open" if openA else "close", "T": T, "S": S,
                                             "net": r, "held": hd, "hit": hit, "ctrl": cm}))
    res = pd.concat(out, ignore_index=True)
    res.to_parquet("research/cache/stock_reversal_price_exits_dev.parquet")
    rows = []
    for bucket in ("E", "EX", "F", "N"):
        sb = (res.bucket == "E") & res.ex if bucket == "EX" else res.bucket == bucket
        for d, dn in ((1.0, "up"), (-1.0, "down")):
            for entry in ("open", "close"):
                for T in TARGETS:
                    for S in STOPS:
                        x = res[sb & (res.dir == d) & (res.entry == entry) & (res["T"] == T) & (res.S == S)].dropna(subset=["net"])
                        early = (x.date < ERA_SPLIT).values
                        edge = (x.net - x.ctrl).values
                        rows.append({"trial": f"{bucket}_{dn}_{entry}_T{int(T*100)}_S{int(S*100)}", "bucket": bucket,
                                     "fade": "rise" if d > 0 else "fall", "entry": entry, "target": T, "stop": S,
                                     "n": len(x), "net_bp": x.net.mean() * 1e4, "median_bp": x.net.median() * 1e4,
                                     "win": (x.net > 0).mean(), "target_hit": (x.hit == 1).mean(),
                                     "stop_hit": (x.hit == -1).mean(), "days": x.held.mean(),
                                     "bp_per_day": x.net.mean() / x.held.mean() * 1e4,
                                     "era1_bp": x.net[early].mean() * 1e4, "era2_bp": x.net[~early].mean() * 1e4,
                                     "ctrl_bp": x.ctrl.mean() * 1e4, "edge_bp": edge.mean() * 1e4,
                                     "t": clustered_t(x.net.values, x.date.values),
                                     "edge_t": clustered_t(edge, x.date.values)})
    r = pd.DataFrame(rows)
    r["p"] = 2 * norm.sf(np.abs(r["t"].fillna(0)))
    r["holm_p"] = holm(r["p"].values)
    r["passes"] = ((r.n >= 300) & (r.net_bp > 0) & (r.era1_bp > 0) & (r.era2_bp > 0) & (r.t >= 3)
                   & (r.holm_p < 0.05) & (r.edge_bp > 0) & (r.edge_t >= 2))
    r.to_csv(f"{HERE}/results_93_dev.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 260)
    cols = ["trial", "n", "net_bp", "median_bp", "win", "target_hit", "stop_hit", "days", "bp_per_day",
            "era1_bp", "era2_bp", "ctrl_bp", "edge_bp", "t", "edge_t", "holm_p", "passes"]
    print(r[cols].round(2).to_string(index=False))
    print(f"\ntrials passing every gate: {int(r.passes.sum())} of {len(r)}")


if __name__ == "__main__":
    main()
