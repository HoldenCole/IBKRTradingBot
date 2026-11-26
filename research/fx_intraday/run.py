"""Run the pre-registered protocol (PREREGISTRATION.md) on the development sample.

    python3 -m research.fx_intraday.run            # EUR/USD development sample, all gates
    python3 -m research.fx_intraday.run --sims 200

Writes research/fx_intraday/results/ (summary tables and the gate verdicts) and
appends every evaluated variant to trials.csv. Opens the hold-out only for a
rule that passes every development gate, once.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.fx_intraday import costs, data, registry, rules, stats
from research.fx_intraday.engine import Bars, simulate

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
TRADES = data.CACHE.parent / "fx_results"
FAMILIES = {"drift": [t for t in rules.trial_ids() if t.startswith("drift")],
            "mr": [t for t in rules.trial_ids() if t.startswith("mr_")],
            "rn": [t for t in rules.trial_ids() if t.startswith("rn_")],
            "london": ["london_breakout"]}


# ------------------------------------------------------------------ random-entry nulls
def _pool(bars: Bars, mask: np.ndarray, margin: int = 600) -> np.ndarray:
    idx = np.flatnonzero(mask)
    return idx[idx < len(bars) - margin]


def null_sims(bars: Bars, t: pd.DataFrame, fam: str, tid: str, sims: int, seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = len(t)
    ny = bars.time.tz_convert(rules.NY)
    ok_spread = costs.spread_ok(bars.spread, bars.pair)
    weekday = np.asarray((ny.day_of_week < 5) | ((ny.day_of_week == 6) & (ny.hour >= 19)))
    not_hol = ~rules.holiday(ny)
    side_a = t["side"].to_numpy()
    mid_a = t["entry_mid"].to_numpy()
    ds = side_a * (mid_a - t["stop"].to_numpy()) / mid_a
    dt = side_a * (t["target"].to_numpy() - mid_a) / mid_a
    if fam == "drift":
        mask = weekday & not_hol & ok_spread
        dur = (t["exit_time"] - t["entry_time"]).to_numpy()
    elif fam in ("mr", "rn"):
        mask = rules.eligible_mr_minutes(bars)
        T = int(tid.split("_T")[1])
    else:
        ldn = bars.time.tz_convert(rules.LDN)
        mask = np.asarray((ldn.hour >= 7) & (ldn.hour < 12) & (ldn.day_of_week < 5)) & not_hol & ok_spread
    pool = _pool(bars, mask)
    out = np.empty(sims)
    for s in range(sims):
        perm = rng.permutation(n)
        side, d_s, d_t = side_a[perm], ds[perm], dt[perm]
        ei = np.sort(rng.choice(pool, size=n, replace=False))
        et = bars.time[ei]
        flat = rules.next_flat(et).asi8
        if fam == "drift":
            d = dur[perm].astype("timedelta64[ns]").astype(np.int64)
            last_t = et.asi8 + d
            bad = last_t > flat                      # would cross 16:45 New York: shift the entry earlier
            last_t = np.where(bad, flat, last_t)
        elif fam in ("mr", "rn"):
            last_t = np.minimum(et.asi8 + T * 3_600_000_000_000, flat)
        else:
            last_t = flat
        li = np.searchsorted(bars.time.asi8, last_t)
        mid = bars.mid_o[ei]
        stop = mid * (1 - side * d_s)
        target = mid * (1 + side * d_t)
        r = simulate(bars, ei, side, stop, target, li)
        out[s] = r["net_bp"].mean()
    return out


# ------------------------------------------------------------------ walk-forward for mean reversion
def walk_forward(trades: dict[str, pd.DataFrame], ids: list[str], min_is: int = 100) -> tuple[pd.DataFrame, list]:
    quarters = pd.date_range("2015-01-01", "2024-12-01", freq="QS")
    picks, oos = [], []
    for q0 in quarters:
        q1 = min(q0 + pd.offsets.QuarterBegin(1), pd.Timestamp("2024-12-01"))
        is0 = q0 - pd.DateOffset(years=3)
        best, best_m = None, -np.inf
        for tid in ids:
            t = trades[tid]
            et = t["entry_time"].dt.tz_convert(None)
            ins = t[(et >= is0) & (et < q0)]
            if len(ins) >= min_is and ins["net_bp"].mean() > best_m:
                best, best_m = tid, ins["net_bp"].mean()
        if best is None:
            continue
        t = trades[best]
        et = t["entry_time"].dt.tz_convert(None)
        oos.append(t[(et >= q0) & (et < q1)].assign(variant=best))
        picks.append((q0.date().isoformat(), best, round(best_m, 3)))
    return (pd.concat(oos) if oos else pd.DataFrame()), picks


def fmt(x, d=2):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="EURUSD")
    ap.add_argument("--sims", type=int, default=200)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    TRADES.mkdir(parents=True, exist_ok=True)
    pair = a.pair
    df = data.load(pair, data.DEV_START, data.HOLDOUT_START)
    bars = Bars.from_frame(pair, df)
    print(f"{pair} development bars: {len(bars):,}  {bars.time[0]} -> {bars.time[-1]}", flush=True)
    hb = rules.hourly(bars)

    # ---- every trial at every stress level
    rows, base = [], {}
    for tid in rules.trial_ids():
        for stress in costs.STRESS_LEVELS:
            t = rules.run_trial(bars, tid, stress, hb=hb)
            s = stats.summarize(t)
            row = {"trial": tid, "family": rules.family(tid), "pair": pair, "sample": "dev", "stress": stress,
                   **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}}
            rows.append(row)
            registry.log_trial({k: row.get(k) for k in ("trial", "family", "pair", "sample", "stress", "n",
                                                        "mean_net_bp", "t", "mean_gross_bp", "mean_cost_bp", "cost_ratio")})
            if stress == 1.0:
                base[tid] = t
                t.to_parquet(TRADES / f"{pair}_{tid}_dev.parquet")
        print(f"  {tid:22s} n={rows[-3]['n']:5d} net={fmt(rows[-3].get('mean_net_bp'))}bp t={fmt(rows[-3].get('t'))} "
              f"gross={fmt(rows[-3].get('mean_gross_bp'))} cost={fmt(rows[-3].get('mean_cost_bp'))}", flush=True)
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / f"{pair}_dev_summary.csv", index=False)

    # ---- snooping: SPA and StepM across all 20 trials, daily net P&L
    cal = pd.bdate_range(data.DEV_START.tz_localize(None), (data.HOLDOUT_START - pd.Timedelta(days=1)).tz_localize(None))
    daily = pd.DataFrame({tid: stats.daily(base[tid], cal) for tid in rules.trial_ids()})
    spa = stats.spa_tests(daily)
    print("SPA", spa, flush=True)

    # ---- per family: best trial, gates
    verdicts = {}
    b = summary[summary["stress"] == 1.0].set_index("trial")
    for fam, ids in FAMILIES.items():
        best = b.loc[ids, "mean_net_bp"].idxmax()
        s = b.loc[best]
        g = {}
        g["1 trades >= 1,000"] = bool(s["n"] >= 1000)
        g["2 mean net > 0"] = bool(s["mean_net_bp"] > 0)
        g["3 cost ratio >= 2"] = bool(s["cost_ratio"] >= 2)
        g["4 both windows > 0"] = bool(s["mean_net_2012-2017"] > 0 and s["mean_net_2018-2024"] > 0)
        g["5 SPA p<0.05, in StepM set, t >= 3"] = bool(spa["spa_p_consistent"] < 0.05 and best in spa["stepm_superior"] and s["t"] >= 3)
        sims = null_sims(bars, base[best], fam, best, a.sims)
        p_null = stats.null_p(s["mean_net_bp"], sims)
        g["6 beats random-entry null (p<0.05)"] = bool(p_null < 0.05)
        extra = {"null_p": p_null, "null_mean_bp": float(sims.mean()), "null_p95_bp": float(np.quantile(sims, 0.95))}
        if fam in ("mr", "rn"):
            wf, picks = walk_forward(base, ids)
            wfs = stats.summarize(wf)
            g["7 walk-forward mean net > 0"] = bool(wfs.get("mean_net_bp", -1) > 0)
            extra["walk_forward"] = {k: wfs.get(k) for k in ("n", "mean_net_bp", "t")}
            extra["walk_forward_picks"] = picks
        if fam == "rn":
            ctrl = {}
            k, m, T = (float(best.split("_")[1][1:]), float(best.split("_")[2][1:]), int(best.split("_")[3][1:]))
            for off in rules.RN_CONTROL_OFFSETS:
                ct = rules.mean_reversion(bars, k, m, T, 1.0, hb=hb, round_offset=off)
                cs = stats.summarize(ct)
                ctrl[off] = cs.get("mean_net_bp")
                registry.log_trial({"trial": f"{best}_ctrl{off}", "family": "round-number control", "pair": pair,
                                    "sample": "dev", "stress": 1.0, "n": cs.get("n"), "mean_net_bp": cs.get("mean_net_bp"),
                                    "t": cs.get("t"), "mean_gross_bp": cs.get("mean_gross_bp"),
                                    "mean_cost_bp": cs.get("mean_cost_bp"), "cost_ratio": cs.get("cost_ratio")})
            g["8 true grid beats all 3 controls"] = bool(all(s["mean_net_bp"] > v for v in ctrl.values()))
            extra["controls"] = ctrl
        ref = stats.summarize(rules.run_trial(bars, best, 1.15, hb=hb))
        extra["cme_micro_reference_stress_1.15"] = {k: ref.get(k) for k in ("n", "mean_net_bp", "t")}
        yearly = stats.by_year(base[best])
        yearly.to_csv(OUT / f"{pair}_{best}_by_year.csv")
        verdicts[fam] = {"best_trial": best, "summary": {k: (None if pd.isna(v) else (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v))
                                                         for k, v in s.items()},
                         "gates": g, "passed_all": all(g.values()), **extra}
        print(fam, best, "PASS" if all(g.values()) else "FAIL", {k: v for k, v in g.items() if not v}, flush=True)

    # ---- hold-out: only for a rule that passed every development gate
    holdout = {}
    for fam, v in verdicts.items():
        if not v["passed_all"]:
            continue
        tid = v["best_trial"]
        token = registry.open_holdout(tid, pair, gates="all development gates passed")
        ho = data.load(pair, data.HOLDOUT_START - pd.Timedelta(days=10), None, holdout_token=token)
        hbars = Bars.from_frame(pair, ho)
        ht = rules.run_trial(hbars, tid, 1.0)
        ht = ht[ht["entry_time"] >= data.HOLDOUT_START]
        hs = stats.summarize(ht)
        from scipy import stats as sps
        p = float(sps.t.sf(hs["t"], hs["n"] - 1)) if hs.get("n", 0) > 1 else 1.0
        holdout[tid] = {**{k: hs.get(k) for k in ("n", "mean_net_bp", "t", "cost_ratio")}, "p_one_sided": p,
                        "passed": bool(hs.get("mean_net_bp", -1) > 0 and p < 0.05)}
        registry.log_trial({"trial": tid, "family": rules.family(tid), "pair": pair, "sample": "holdout", "stress": 1.0,
                            "n": hs.get("n"), "mean_net_bp": hs.get("mean_net_bp"), "t": hs.get("t"),
                            "mean_gross_bp": hs.get("mean_gross_bp"), "mean_cost_bp": hs.get("mean_cost_bp"),
                            "cost_ratio": hs.get("cost_ratio")})

    result = {"pair": pair, "dev_bars": len(bars), "spa": spa, "verdicts": verdicts, "holdout": holdout,
              "power": {"52% at 1:1, t=1.645": stats.trades_needed(0.52, 1.0, 0),
                        "55% at 1:1, t=1.645": stats.trades_needed(0.55, 1.0, 0),
                        "40% at 2:1, t=1.645": stats.trades_needed(0.40, 2.0, 0),
                        "52% at 1:1, t=3": stats.trades_needed(0.52, 1.0, 3.0),
                        "55% at 1:1, t=3": stats.trades_needed(0.55, 1.0, 3.0),
                        "40% at 2:1, t=3": stats.trades_needed(0.40, 2.0, 3.0)}}
    (OUT / f"{pair}_dev_result.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps({f: (v["best_trial"], v["passed_all"]) for f, v in verdicts.items()}), "holdout:", holdout)


if __name__ == "__main__":
    main()
