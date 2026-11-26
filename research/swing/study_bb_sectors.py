"""Entry 96 — Bollinger bands on the nine sector SPDRs, played through 3x sector funds, as sleeves
or as two slots. See PREREGISTRATION_96.md.

    python3 -m research.swing.study_bb_sectors
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load, ohlc
from research.swing.lib import daily_features
from research.swing.study_bb_index import FEE, FIN, RULES, bands, perf, state_machine
from research.swing.study_standalone import run

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
START = "2000-09-01"
ERAS = {"2000-2006": ("2000-09-01", "2006-12-31"), "2007-2016": ("2007-01-01", "2016-12-31"),
        "2017-2026": ("2017-01-01", "2026-12-31")}
LEV = 3
COST_SLEEVE = 0.35 / (1000 / 9) + 0.0005
COST_SLOT = 0.35 / 500 + 0.0005


def held_flags(px: pd.Series, rule: str, tf: str, n=20, k=2.0, combo=None) -> pd.Series:
    """Rule state decided at each day's close (not yet shifted)."""
    allow = None
    if combo:
        hb = bands(px, combo, n, k)
        allow = (hb.c > hb.mid).reindex(px.index).ffill().fillna(False)
    b = bands(px, tf, n, k)
    return state_machine(b, rule, allow).reindex(px.index).ffill().fillna(0)


def lev_ret(r: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    f = rf.reindex(r.index).ffill().fillna(0) / 252
    return r.mul(LEV).sub((LEV - 1) * (f + FIN / 252) + FEE / 252, axis=0)


def sleeves(H: pd.DataFrame, R3: pd.DataFrame, cost: float) -> pd.Series:
    w = H.shift(1).fillna(0) / len(H.columns)
    turn = w.diff().abs().sum(axis=1).fillna(w.iloc[0].abs().sum())
    return (w * R3).sum(axis=1) - turn * cost


def slots(H: pd.DataFrame, pctb: pd.DataFrame, R3: pd.DataFrame, cost: float, dip: bool, K: int = 2) -> pd.Series:
    cols = list(H.columns)
    held: set[str] = set()
    W = np.zeros(H.shape)
    Hv, Pv = H.values, pctb.values
    for t in range(len(H)):
        on = {c for j, c in enumerate(cols) if Hv[t, j] > 0}
        held &= on                                   # exits
        cand = [j for j, c in enumerate(cols) if c in on and c not in held]
        if cand and len(held) < K:
            score = np.array([Pv[t, j] if np.isfinite(Pv[t, j]) else (np.inf if dip else -np.inf) for j in cand])
            order = np.argsort(score if dip else -score)
            for j in np.array(cand)[order][: K - len(held)]:
                held.add(cols[j])
        for c in held:
            W[t, cols.index(c)] = 1.0 / K
    w = pd.DataFrame(W, index=H.index, columns=cols).shift(1).fillna(0)
    turn = w.diff().abs().sum(axis=1).fillna(w.iloc[0].abs().sum())
    return (w * R3).sum(axis=1) - turn * cost


def main():
    data = load()
    rf = data["^IRX"]["close"] / 100
    px = pd.DataFrame({s: data[s]["close"] for s in SECTORS}).dropna()
    R = px.pct_change().fillna(0)
    R3 = lev_ret(R, rf)
    mid = px.rolling(20).mean(); sd = px.rolling(20).std(ddof=0)
    pctb = (px - (mid - 2 * sd)) / (4 * sd)

    for fund, sec in (("TECL", "XLK"), ("FAS", "XLF"), ("CURE", "XLV")):
        act = ohlc(fund)["close"].pct_change().dropna()
        syn = R3[sec].reindex(act.index).dropna(); act = act.reindex(syn.index)
        print(f"model check {fund}: actual CAGR {perf(act)['CAGR']:+.1%} model {perf(syn)['CAGR']:+.1%} daily corr {act.corr(syn):.3f}")

    def run_rule(rule, tf, combo, how, n=20, k=2.0):
        H = pd.DataFrame({s: held_flags(px[s], rule, tf, n, k, combo) for s in SECTORS})
        if how == "sleeves":
            return sleeves(H, R3, COST_SLEEVE), H
        return slots(H, pctb, R3, COST_SLOT, dip=rule.startswith("dip")), H

    bh3 = R3.mean(axis=1).loc[START:]
    bh1 = R.mean(axis=1).loc[START:]
    feats = daily_features(data)
    out, _ = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=9 / 3)
    f = rf.reindex(out.index).ffill().fillna(0) / 252
    sw = (3 * out["pos"] - out["expo"] * (2 * (f + FIN / 252) + FEE / 252)).loc[START:]

    def eras(a):
        return {e: perf(a.loc[s:x]) for e, (s, x) in ERAS.items()} | {"all": perf(a)}

    ref = {"3x equal-weight buy and hold": eras(bh3), "1x equal-weight buy and hold": eras(bh1),
           "swing plan at 3x (test 79)": eras(sw)}
    rows = []
    for lab, p in ref.items():
        for e, d in p.items():
            rows.append({"rule": lab, "account": "-", "era": e, **d})
    verdicts = []
    for lab, rule, tf, combo in RULES:
        for how in ("sleeves", "slots"):
            a, H = run_rule(rule, tf, combo, how)
            a = a.loc[START:]
            pe = eras(a)
            for e, d in pe.items():
                rows.append({"rule": lab, "account": how, "era": e, **d,
                             "in_market": (H.shift(1).loc[START:].sum(axis=1) > 0).mean()})

            def ok(pp):
                return all(pp[e]["CAGR"] > ref["3x equal-weight buy and hold"][e]["CAGR"]
                           and pp[e]["Sharpe"] > ref["3x equal-weight buy and hold"][e]["Sharpe"]
                           and pp[e]["maxDD"] > ref["3x equal-weight buy and hold"][e]["maxDD"] for e in ERAS)
            base = ok(pe)
            nb = [ok(eras(run_rule(rule, tf, combo, how, n)[0].loc[START:])) for n in (10, 30)] if base else []
            verdicts.append({"rule": lab, "account": how, "beats_3x_bh_all_eras": base,
                             "neighbours": f"{sum(nb)}/2" if base else "-", "passes": base and all(nb),
                             "corr_with_swing": a.corr(sw.reindex(a.index).fillna(0)),
                             "CAGR_all": pe["all"]["CAGR"], "maxDD_all": pe["all"]["maxDD"]})
    res = pd.DataFrame(rows)
    v = pd.DataFrame(verdicts)
    res.to_csv("research/swing/bb_sectors_results.csv", index=False, float_format="%.4f")
    v.to_csv("research/swing/bb_sectors_verdicts.csv", index=False, float_format="%.3f")
    pd.set_option("display.width", 250)
    t = res.pivot_table(index=["rule", "account"], columns="era", values=["CAGR", "maxDD"], sort=False)
    print(t.round(3).to_string())
    print("\n", v.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
