"""Entries 86-87, second pass.

1. Crash weeks: what state were the Quadrant Balances in the week BEFORE each
   large weekly fall, and how does that compare with the mix of all weeks?
2. Base rates of the exact pre-crash state of 13 Nov 2026.
3. The fragile state (S&P 0-3% above its 200-day average, 20-day vol above 16%).
4. Weekly buy signals split by the monthly state (the two-level reading).
5. Trade list for the monthly sell/buy rule, and the index levels that would
   flip the monthly readings from here.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.trend_cycle.study_signals import ERAS, load, states  # noqa: E402
from src.portfolio import trend_cycle as tc  # noqa: E402

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)


def main():
    close, vf, irx = load()
    w = states(tc.to_bars(close, "W"))
    mb = tc.to_bars(close, "M")
    m = states(mb)
    # monthly state known during each week = last COMPLETED month
    mc = m[["cq", "tq"]].shift(1).reindex(w.index, method="ffill")
    w["m_cq"], w["m_tq"] = mc["cq"], mc["tq"]
    w["m_state"] = np.select([w["m_cq"].isin([2, 3]) & w["m_tq"].isin([2, 3]), w["m_cq"].isin([1, 4]) & w["m_tq"].isin([1, 4])], ["intact", "broken"], "mixed")
    w["ret"] = w["px"].pct_change()
    w["next1"] = w["ret"].shift(-1)
    w["next4"] = w["px"].shift(-4) / w["px"] - 1
    w["next13"] = w["px"].shift(-13) / w["px"] - 1
    w["next26"] = w["px"].shift(-26) / w["px"] - 1
    w["min4"] = pd.Series([w["px"].iloc[i + 1:i + 5].min() / w["px"].iloc[i] - 1 if i + 1 < len(w) else np.nan for i in range(len(w))], index=w.index)
    w["hi52"] = w["px"] / w["px"].rolling(52).max() - 1
    w["wstate"] = "c" + w["cq"].astype(int).astype(str) + " t" + w["tq"].astype(int).astype(str)

    print("=== 1. CRASH WEEKS: weekly falls of 6% or more since 1950, and the state at the PRIOR Friday ===")
    cw = w[w["next1"] <= -0.06]
    t = cw[["px", "next1", "cq", "cc", "tq", "tcn", "tn", "m_state", "hi52"]].copy()
    t.index = [f"{(d + pd.Timedelta(days=7)).date()}" for d in t.index]
    t["next1"] = (t["next1"] * 100).round(1); t["hi52"] = (t["hi52"] * 100).round(1); t["px"] = t["px"].round(0)
    print(t.rename(columns={"next1": "week_%", "cq": "W_cyc", "cc": "cyc_wks", "tq": "W_trd", "tcn": "trd_wks", "tn": "trd_side", "hi52": "from_52w_high_%"}).to_string())
    print("\n  share of weeks by prior state: all weeks vs the weeks before a fall of 5%+ / 6%+")
    for lab, col in (("weekly trend quadrant", "tq"), ("weekly cycle quadrant", "cq"), ("monthly state", "m_state")):
        base = w[col].value_counts(normalize=True).sort_index()
        c5 = w[w["next1"] <= -0.05][col].value_counts(normalize=True).reindex(base.index).fillna(0)
        c6 = w[w["next1"] <= -0.06][col].value_counts(normalize=True).reindex(base.index).fillna(0)
        print(f"  {lab}: " + " | ".join(f"{k}: all {base[k]:.0%}, before -5% {c5[k]:.0%}, before -6% {c6[k]:.0%}" for k in base.index))
    print(f"  n: all {len(w)}, -5% weeks {(w['next1'] <= -0.05).sum()}, -6% weeks {(w['next1'] <= -0.06).sum()}, -8% weeks {(w['next1'] <= -0.08).sum()}")
    near = w["hi52"] >= -0.05
    print(f"  crash weeks (-6%) that started within 5% of a 52-week high: {(cw['hi52'] >= -0.05).sum()} of {len(cw)}: "
          + ", ".join(f"{(d + pd.Timedelta(days=7)).date()}" for d in cw.index[cw["hi52"] >= -0.05]))

    print("\n=== 2. BASE RATES for the state on Friday 13 Nov 2026 (weekly cycle Q4, weekly trend Q3, monthly both Q3, 3% off the high) ===")
    both3_m = w["m_cq"].eq(3) & w["m_tq"].eq(3)
    conds = {
        "any week": pd.Series(True, index=w.index),
        "weekly trend Q3": w["tq"].eq(3),
        "weekly trend Q3 for 4+ weeks": w["tq"].eq(3) & (w["tcn"] >= 4),
        "weekly cycle Q4 and weekly trend Q3": w["cq"].eq(4) & w["tq"].eq(3),
        "monthly both rolling over (Q3 and Q3)": both3_m,
        "... and weekly trend Q3": both3_m & w["tq"].eq(3),
        "... and weekly cycle Q4, weekly trend Q3 (13 Nov)": both3_m & w["cq"].eq(4) & w["tq"].eq(3),
        "... same, and within 5% of the 52-week high": both3_m & w["cq"].eq(4) & w["tq"].eq(3) & near,
        "weekly trend falling 12+ weeks above zero, within 3% of high": w["tq"].eq(3) & (w["tcn"] >= 12) & (w["hi52"] >= -0.03),
    }
    for lab, mk in conds.items():
        cells = []
        for era, (a, b) in ERAS.items():
            s = w[mk.fillna(False)].loc[a:b]
            if len(s) < 8:
                cells.append(f"{era} n={len(s):4d}: thin" + " " * 50); continue
            cells.append(f"{era} n={len(s):4d}: 1w {s['next1'].mean():+5.2%} 4w {s['next4'].mean():+5.1%} 13w {s['next13'].mean():+5.1%} | "
                         f"P(-5% wk next) {(s['next1'] <= -0.05).mean():4.1%} P(-7% in 4w) {(s['min4'] <= -0.07).mean():4.1%}")
        print(f"  {lab:62s} " + " || ".join(cells))

    print("\n=== 3. THE FRAGILE STATE on daily closes (S&P 0-3% above its 200-day average and 20-day realised vol above 16%) ===")
    d = pd.DataFrame({"px": close})
    d["ext"] = d["px"] / d["px"].rolling(200).mean() - 1
    d["rv"] = d["px"].pct_change().rolling(20).std() * np.sqrt(252)
    d["frag"] = d["ext"].between(0, 0.03) & (d["rv"] > 0.16)
    d["n5"] = d["px"].shift(-5) / d["px"] - 1; d["n21"] = d["px"].shift(-21) / d["px"] - 1
    d["min10"] = pd.Series(d["px"].values[::-1]).rolling(10).min().values[::-1] if False else d["px"].shift(-1).iloc[::-1].rolling(10, min_periods=1).min().iloc[::-1] / d["px"] - 1
    for lab, mk in {"any day": pd.Series(True, index=d.index), "fragile": d["frag"], "0-3% above 200d, vol below 16%": d["ext"].between(0, 0.03) & (d["rv"] <= 0.16),
                    "above 200d by 3%+": d["ext"] > 0.03, "below the 200d": d["ext"] < 0}.items():
        cells = []
        for era, (a, b) in ERAS.items():
            s = d[mk.fillna(False)].loc[a:b]
            cells.append(f"{era} n={len(s):5d}: 5d {s['n5'].mean():+5.2%} 21d {s['n21'].mean():+5.2%} | P(5d <= -5%) {(s['n5'] <= -0.05).mean():4.1%} P(-7% low in 10d) {(s['min10'] <= -0.07).mean():4.1%}")
        print(f"  {lab:34s} " + " || ".join(cells))
    print("  recent days:")
    print((d.loc["2026-10-26":, ["px", "ext", "rv", "frag"]].assign(ext=lambda x: (x.ext * 100).round(2), rv=lambda x: (x.rv * 100).round(1), px=lambda x: x.px.round(0))).to_string())

    print("\n=== 4. WEEKLY BUY SIGNALS split by the monthly state (monthly = last completed month) ===")
    ent = lambda col, q: (w[col] == q) & (w[col].shift(1) != q)  # noqa: E731
    buys = {
        "weekly trend turns up below zero (->Q1)": ent("tq", 1),
        "weekly trend ->Q1 after 6+ weeks declining": ent("tq", 1) & (w["tcn_prev"] >= 6),
        "weekly cycle turns up (->Q1) while weekly trend Q4, week 4+": ent("cq", 1) & w["tq"].eq(4) & (w["tcn"] >= 4),
        "weekly cycle turns up (->Q1) while weekly trend Q4, weeks 1-3": ent("cq", 1) & w["tq"].eq(4) & (w["tcn"] <= 3),
        "weekly trend Q4, week 4+ (every such week)": w["tq"].eq(4) & (w["tcn"] >= 4),
        "weekly trend Q4, weeks 1-3 (every such week)": w["tq"].eq(4) & (w["tcn"] <= 3),
        "weekly both Q4 (every such week)": w["tq"].eq(4) & w["cq"].eq(4),
        "weekly cycle crosses above zero (->Q2)": ent("cq", 2) & w["cq"].shift(1).isin([1, 4]),
    }
    for ms in ("intact", "mixed", "broken"):
        print(f"  --- monthly {ms} ---")
        for lab, mk in buys.items():
            cells = []
            for era, (a, b) in ERAS.items():
                s = w[mk.fillna(False) & w["m_state"].eq(ms)].loc[a:b]
                if len(s) < 6:
                    cells.append(f"{era} n={len(s):3d}: thin" + " " * 44); continue
                cells.append(f"{era} n={len(s):3d}: 4w {s['next4'].mean():+5.1%} 13w {s['next13'].mean():+5.1%} 26w {s['next26'].mean():+5.1%} up13 {(s['next13'].dropna() > 0).mean():4.0%} worst13 {s['next13'].min():+4.0%}")
            print(f"  {lab:62s} " + " || ".join(cells))

    print("\n=== 5a. MONTHLY RULE TRADE LIST: out when the monthly trend is in Q4, back in when it leaves Q4 (signal at month-end close) ===")
    mm = m.copy(); out = mm["tq"].eq(4)
    start = None; rows = []
    for dte, o in out.items():
        if o and start is None:
            start = dte
        if not o and start is not None:
            px_out, px_in = mm.loc[start, "px"], mm.loc[dte, "px"]
            low = mb.loc[start:dte].min(); hi_before = mb.loc[:start].iloc[-24:].max()
            rows.append((start.strftime("%Y-%m"), dte.strftime("%Y-%m"), round(px_out, 0), round(px_in, 0), f"{px_in / px_out - 1:+.1%}",
                         f"{px_out / hi_before - 1:+.1%}", f"{low / px_out - 1:+.1%}"))
            start = None
    print(pd.DataFrame(rows, columns=["sell (month-end)", "buy back", "sell level", "buy level", "re-entry vs exit", "exit vs prior 2y high", "lowest month-end while out"]).to_string(index=False))
    r = pd.DataFrame(rows); better = (r[4].str.rstrip("%").astype(float) < 0)
    print(f"  re-entered LOWER than the exit in {better.sum()} of {len(r)} round trips (1950-2026); since 1987: {better[r[0] >= '1987'].sum()} of {(r[0] >= '1987').sum()}")

    print("\n=== 5b. WHERE WOULD THE MONTHLY READINGS FLIP? (index level at a month-end close, holding that level afterwards) ===")
    done = mb.copy()
    last_full = done.index[-1]
    def flips(fn, target_q: set, months_ahead: int) -> float | None:
        lo, hi = 2000.0, float(done.iloc[-1]) * 1.3
        def ok(level):
            s = done.copy()
            s.iloc[-1] = level                                   # the month in progress closes at `level`
            for k in range(1, months_ahead + 1):
                s.loc[s.index[-1] + pd.offsets.MonthEnd(1)] = level
            return fn(s).iloc[-1] <= 0
        if not ok(lo):
            return None
        if ok(hi):
            return hi
        for _ in range(40):
            mid = (lo + hi) / 2
            if ok(mid):
                lo = mid
            else:
                hi = mid
        return lo
    for k, lab in ((0, "Nov close"), (1, "Dec close"), (2, "Jan close"), (3, "Feb close"), (5, "Apr close")):
        c0, t0 = flips(tc.cycle, set(), k), flips(tc.trend, set(), k)
        last = float(close.iloc[-1])
        f = lambda v: "not reachable above 2,000" if v is None else f"at or under {v:,.0f} ({v / last - 1:+.0%} from here)"  # noqa: E731
        print(f"  by the {lab}: monthly cycle below zero if the S&P sits {f(c0)}; monthly trend below zero {f(t0)}")
    print(f"  current monthly oscillator values: cycle {tc.cycle(mb).iloc[-1]:+.1f}, trend {tc.trend(mb).iloc[-1]:+.1f}; "
          f"weekly: cycle {tc.cycle(tc.to_bars(close, 'W')).iloc[-1]:+.1f}, trend {tc.trend(tc.to_bars(close, 'W')).iloc[-1]:+.2f}")


if __name__ == "__main__":
    main()
