"""Entry 92 runner: the 64 pre-registered trials, gates, and the coverage table.

    python3 -m research.stock_reversal.run            # development sample only
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from research.stock_reversal.events import build

COST = 0.0010          # per side
STRESS = 0.0020
ERA_SPLIT = pd.Timestamp("2015-01-01")
HERE = "research/stock_reversal"


def clustered_t(x: np.ndarray, groups: np.ndarray) -> float:
    n = len(x)
    if n < 3:
        return np.nan
    m = x.mean()
    s = pd.Series(x - m).groupby(groups).sum().values
    G = len(s)
    if G < 2:
        return np.nan
    se = np.sqrt((s ** 2).sum() * G / (G - 1)) / n
    return m / se if se > 0 else np.nan


def trial_rows(ev: pd.DataFrame) -> list[dict]:
    out = []
    for bucket in ("E", "EX", "F", "N"):
        sel_b = (ev["bucket"] == "E") & ev["ex"] if bucket == "EX" else ev["bucket"] == bucket
        for hz in ("H0", "H1", "H2", "H3"):
            for direction, dname in ((1.0, "fade a rise"), (-1.0, "fade a fall")):
                for size in ("L", "X"):
                    sel = sel_b & (ev["horizon"] == hz) & (ev["dir"] == direction)
                    if size == "X":
                        sel &= ev["size"] == "X"
                    e = ev[sel]
                    gross = (-direction * e["xret"]).values
                    net = gross - 2 * COST
                    raw = (-direction * e["ret"]).values - 2 * COST
                    early = (e["date"] < ERA_SPLIT).values
                    t = clustered_t(net, e["date"].values) if len(e) else np.nan
                    out.append({
                        "trial": f"{bucket}_{hz}_{'up' if direction > 0 else 'down'}_{size}",
                        "bucket": bucket, "horizon": hz, "direction": dname, "size": size, "n": len(e),
                        "gross_bp": gross.mean() * 1e4 if len(e) else np.nan,
                        "net_bp": net.mean() * 1e4 if len(e) else np.nan,
                        "stress_net_bp": (gross.mean() - 2 * STRESS) * 1e4 if len(e) else np.nan,
                        "median_net_bp": np.median(net) * 1e4 if len(e) else np.nan,
                        "win": (net > 0).mean() if len(e) else np.nan,
                        "era1_net_bp": net[early].mean() * 1e4 if early.any() else np.nan,
                        "era2_net_bp": net[~early].mean() * 1e4 if (~early).any() else np.nan,
                        "n_era1": int(early.sum()), "n_era2": int((~early).sum()),
                        "raw_net_bp": raw.mean() * 1e4 if len(e) else np.nan,
                        "t": t,
                    })
    return out


def holm(p: np.ndarray) -> np.ndarray:
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * p[i])
        adj[i] = min(run, 1.0)
    return adj


def main():
    ev, cov = build()
    ev.to_parquet("research/cache/stock_reversal_events_dev.parquet")
    print("coverage of S&P 500 member-days with prices and filings, by year")
    print((cov["share"] * 100).round(0).astype(int).to_frame("pct").T.to_string())
    r = pd.DataFrame(trial_rows(ev))
    p = 2 * norm.sf(np.abs(r["t"].fillna(0).values))
    r["p"] = p
    r["holm_p"] = holm(p)
    r["g1_n"] = r["n"] >= 300
    r["g2_net"] = r["net_bp"] > 0
    r["g3_eras"] = (r["era1_net_bp"] > 0) & (r["era2_net_bp"] > 0)
    r["g4_t"] = r["t"] >= 3
    r["g5_holm"] = (r["holm_p"] < 0.05) & (r["t"] > 0)
    r["g6_cost"] = r["gross_bp"] >= 2 * 2 * COST * 1e4
    gates = ["g1_n", "g2_net", "g3_eras", "g4_t", "g5_holm", "g6_cost"]
    r["passes"] = r[gates].all(axis=1)
    r.to_csv(f"{HERE}/results_dev.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 250)
    show = ["trial", "n", "gross_bp", "net_bp", "median_net_bp", "win", "era1_net_bp", "era2_net_bp", "raw_net_bp", "t",
            "holm_p", "passes"]
    print(r[show].round(2).to_string(index=False))
    print(f"\nevents: {len(ev):,} rows, {ev.ticker.nunique()} stocks; trials passing every gate: {int(r.passes.sum())}")
    gp = r.groupby("bucket")[["gross_bp"]].mean()
    print(gp.round(1).T.to_string())


if __name__ == "__main__":
    main()
