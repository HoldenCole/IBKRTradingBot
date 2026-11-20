"""Monthly quadrant-balance signal history (ex-ante: each row uses closes
through that month-end only).

Columns
  idx_{cycle,trend}_{q,cc,nn}   S&P 500 index state on monthly bars
  {cyc,trd}_q1..q4, *_q1q2      % of (today's) S&P members per quadrant
  n                             members with enough history that month
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.trend_cycle.data import index_daily, member_monthly
from src.portfolio.trend_cycle import cycle, quadrants, state_history, trend

ERAS = {"1987-2006": ("1987-01-01", "2006-12-31"), "2007-2026": ("2007-01-01", "2026-12-31")}


def monthly_signals(include_partial: bool = True) -> pd.DataFrame:
    idx_m = index_daily().resample("ME").last().dropna()
    out = pd.DataFrame(index=idx_m.index)
    for name, fn in (("cycle", cycle), ("trend", trend)):
        h = state_history(fn(idx_m))
        out[f"idx_{name}_q"] = h["quadrant"]; out[f"idx_{name}_cc"] = h["in_quadrant"]; out[f"idx_{name}_nn"] = h["on_side"]
    members = member_monthly()
    for short, fn in (("cyc", cycle), ("trd", trend)):
        Q = pd.DataFrame({k: quadrants(fn(v)) for k, v in members.items()}).reindex(out.index)
        n = Q.notna().sum(axis=1)
        for q in (1, 2, 3, 4):
            out[f"{short}_q{q}"] = (Q == q).sum(axis=1) / n * 100
        out[f"{short}_q1q2"] = out[f"{short}_q1"] + out[f"{short}_q2"]
        out[f"{short}_n"] = n
    out["spx"] = idx_m
    out = out[out["cyc_n"] >= 100]
    return out


def table(sig: pd.DataFrame, mask_fn, label: str, horizons=(1, 3, 6, 12, 24)):
    spx = sig["spx"]
    fwd = {h: spx.shift(-h) / spx - 1 for h in horizons}
    cells = []
    for era, (a, b) in ERAS.items():
        m = mask_fn(sig).fillna(False)
        idx = sig.index[m]; idx = idx[(idx >= a) & (idx <= b)]
        if len(idx) < 5:
            cells.append(f"{era} n={len(idx):3d}: thin"); continue
        cells.append(f"{era} n={len(idx):3d}: " + " ".join(f"{h}m {fwd[h].reindex(idx).mean():+6.1%}" for h in horizons)
                     + f" | 12m up {(fwd[12].reindex(idx) > 0).mean():4.0%} worst12m {fwd[12].reindex(idx).min():+5.0%}")
    print(f"   {label:46s} " + " || ".join(cells))


def main():
    sig = monthly_signals()
    sig.to_pickle("research/cache/qb_monthly_signals.pkl")
    spx = sig["spx"]
    print(f"monthly signal history {sig.index[0].date()} -> {sig.index[-1].date()}  members/month: {int(sig['cyc_n'].iloc[0])} -> {int(sig['cyc_n'].iloc[-1])}")
    print("baseline S&P forward return, any month:")
    table(sig, lambda s: s["spx"] > 0, "all months")

    print("\n=== 1) INDEX monthly state -> forward S&P return ===")
    for name in ("cycle", "trend"):
        for q, lab in ((1, "Q1 below/rising"), (2, "Q2 above/rising"), (3, "Q3 above/falling"), (4, "Q4 below/falling")):
            table(sig, lambda s, name=name, q=q: s[f"idx_{name}_q"] == q, f"index {name} {lab}")
    table(sig, lambda s: (s["idx_cycle_q"].isin([1, 4])) & (s["idx_trend_q"].isin([1, 4])), "index cycle AND trend both below zero")
    table(sig, lambda s: (s["idx_cycle_q"] == 4) & (s["idx_trend_q"] == 4), "index cycle Q4 AND trend Q4")
    table(sig, lambda s: (s["idx_trend_q"] == 4) & (s["idx_trend_cc"] <= 2), "index trend Q4, months 01-02")
    table(sig, lambda s: (s["idx_trend_q"] == 4) & (s["idx_trend_cc"] >= 3), "index trend Q4, month 03+")
    table(sig, lambda s: (s["idx_trend_q"] == 1) & (s["idx_trend_cc"] == 1), "index trend turns up below zero (Q1, month 01)")
    table(sig, lambda s: (s["idx_cycle_q"] == 1) & (s["idx_cycle_cc"] == 1) & (s["idx_trend_q"].isin([1, 4])), "index cycle turns up (Q1 01), trend below zero")

    print("\n=== 2) MEMBER monthly balances -> forward S&P return ===")
    for col, lab in (("cyc_q4", "cycle: % of members in Q4"), ("trd_q4", "trend: % of members in Q4")):
        for lo, hi in ((0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 101)):
            table(sig, lambda s, col=col, lo=lo, hi=hi: s[col].between(lo, hi, inclusive="left"), f"{lab} {lo}-{hi}%")
    for lo, hi in ((0, 25), (25, 40), (40, 60), (60, 75), (75, 101)):
        table(sig, lambda s, lo=lo, hi=hi: s["cyc_q1q2"].between(lo, hi, inclusive="left"), f"cycle: % rising (Q1+Q2) {lo}-{hi}%")
    pct = {c: sig[c].expanding(60).rank(pct=True) for c in ("cyc_q4", "trd_q4")}
    table(sig, lambda s: pct["cyc_q4"] >= 0.95, "cycle Q4 share in its own top 5% to date")
    table(sig, lambda s: pct["trd_q4"] >= 0.95, "trend Q4 share in its own top 5% to date")
    table(sig, lambda s: (pct["trd_q4"].shift(1) >= 0.90) & (s["trd_q4"] < s["trd_q4"].shift(1)), "trend Q4 share was top 10%, now falling (washout turning)")

    print("\n=== 3) Washout episodes: first month member trend-Q4 share >= 45% (new episode after 12 quiet months) ===")
    ev = sig.index[(sig["trd_q4"] >= 45)]
    keep, last = [], None
    for d in ev:
        if last is None or (d - last).days > 370:
            keep.append(d)
        last = d
    rows = []
    for d in keep:
        i = sig.index.get_loc(d)
        f = lambda h: spx.iloc[i + h] / spx.iloc[i] - 1 if i + h < len(spx) else np.nan
        peak = sig["trd_q4"].iloc[i:i + 13].max()
        low = spx.iloc[i:i + 13].min() / spx.iloc[i] - 1
        rows.append((d.date(), sig["trd_q4"].iloc[i], sig["cyc_q4"].iloc[i], peak, f(3), f(6), f(12), f(24), f(36), low))
    e = pd.DataFrame(rows, columns=["month", "trend_Q4%", "cycle_Q4%", "peak_trend_Q4%_next12m", "3m", "6m", "12m", "24m", "36m", "further_low_12m"]).set_index("month")
    pd.set_option("display.width", 220)
    print(e.assign(**{c: (e[c] * 100).round(1) for c in ("3m", "6m", "12m", "24m", "36m", "further_low_12m")}).round(1).to_string())
    print("\n=== 4) Now ===")
    print(sig.tail(4)[["idx_cycle_q", "idx_cycle_cc", "idx_cycle_nn", "idx_trend_q", "idx_trend_cc", "idx_trend_nn", "cyc_q1", "cyc_q2", "cyc_q3", "cyc_q4", "trd_q1", "trd_q2", "trd_q3", "trd_q4"]].round(1).to_string())
    print("trend Q4 share percentile vs all history:", round(float((sig["trd_q4"] <= sig["trd_q4"].iloc[-1]).mean()), 2),
          "| cycle Q4 share percentile:", round(float((sig["cyc_q4"] <= sig["cyc_q4"].iloc[-1]).mean()), 2))
    print("history: trend Q4 share median", round(sig["trd_q4"].median(), 1), "90th pct", round(sig["trd_q4"].quantile(.9), 1), "max", round(sig["trd_q4"].max(), 1),
          "| cycle Q4 share median", round(sig["cyc_q4"].median(), 1), "90th", round(sig["cyc_q4"].quantile(.9), 1), "max", round(sig["cyc_q4"].max(), 1))


if __name__ == "__main__":
    main()
