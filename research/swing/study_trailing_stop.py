"""Entry 99 — trailing stops on the monthly Quadrant Balances bets (all in at 3x). See PREREGISTRATION_99.md.

    python3 -m research.swing.study_trailing_stop
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import ohlc
from research.swing.study_concentrated import COST, ERAS, lev_ret, series, snap, trades_from_bars
from research.trend_cycle.study_signals import states
from src.portfolio import trend_cycle as tc

STOPS = (0.15, 0.20, 0.25, 0.30)


def simulate(days, r3, windows, stop, reentry, above10_me, intraday=None):
    """Daily loop. windows: [(entry_close_date, end_date)]. Returns daily equity and the number of stops."""
    n = len(days)
    pos = {d: i for i, d in enumerate(days)}
    starts = {pos[a]: pos[b] for a, b in windows if a in pos and b in pos}
    eq = np.empty(n); e = 1.0; held = False; peak = 1.0; end = -1; in_window = False; stops = 0
    rr = r3.values
    if intraday is not None:
        lo_r, hi_r, op_r = intraday
    for k in range(n):
        if held:
            if intraday is not None and np.isfinite(lo_r[k]):
                prev = e
                lvl = peak * (1 - stop)
                o_val, l_val = prev * (1 + op_r[k]), prev * (1 + lo_r[k])
                if o_val <= lvl or l_val <= lvl:
                    e = (o_val if o_val <= lvl else lvl) * (1 - COST)
                    held = False; stops += 1
                else:
                    e = prev * (1 + rr[k])
                    peak = max(peak, prev * (1 + hi_r[k]), e)
            else:
                e *= 1 + rr[k]
                peak = max(peak, e)
                if e / peak - 1 <= -stop:
                    e *= 1 - COST; held = False; stops += 1
        if in_window and k == end:
            if held:
                e *= 1 - COST; held = False
            in_window = False
        if k in starts and not in_window:
            in_window, end = True, starts[k]
            if not held:
                e *= 1 - COST; held = True; peak = e
        elif in_window and not held and reentry and above10_me[k] and k < end:
            e *= 1 - COST; held = True; peak = e
        eq[k] = e
    return pd.Series(eq, index=days), stops


def measures(eq: pd.Series, start) -> dict:
    eq = eq.loc[start:]
    eq = eq / eq.iloc[0]
    a = eq.pct_change().fillna(0)
    yrs = len(eq) / 252
    dd = eq / eq.cummax() - 1
    m3 = (eq.shift(-756) / eq).dropna()
    d = {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "maxDD": dd.min(), "worst_day": a.min(),
         "days_25pct_down": (dd < -0.25).mean(), "3y_p10": m3.quantile(0.1), "3y_median": m3.median(),
         "end_multiple": eq.iloc[-1]}
    for e, (s, x) in ERAS.items():
        q = eq.loc[s:x]
        if len(q) > 252:
            q = q / q.iloc[0]
            d[f"{e} CAGR"] = q.iloc[-1] ** (252 / len(q)) - 1
            d[f"{e} maxDD"] = (q / q.cummax() - 1).min()
    return d


def main(intraday_check: bool = True, table: bool = True):
    close, r, rf = series()
    days = close.index
    r3 = lev_ret(r, rf)
    m = states(tc.to_bars(close, "M"))
    ent = lambda o, q: (m[o] == q) & (m[o + "_prev"] != q)  # noqa: E731
    trend_up, cycle_up = ent("tq", 1), ent("cq", 2) & m["cq_prev"].isin([1, 4])
    sell = ent("tq", 4) & m["tq_prev"].isin([2, 3])
    base = {"A trend-up, until sell": trades_from_bars(trend_up, m.index, None, sell, days),
            "B cycle-confirm, until sell": trades_from_bars(cycle_up, m.index, None, sell, days),
            "C trend-up, 12 months": trades_from_bars(trend_up, m.index, 12, None, days)}
    mb = tc.to_bars(close, "M")
    a10 = (mb > mb.rolling(10).mean())
    me = pd.Series(False, index=days)
    me.loc[snap(a10.index[a10.values], days)] = True
    above10 = me.values
    start = m.index[0]
    rows = []
    bh = (1 + r3).cumprod()
    rows.append({"design": "3x buy and hold", "stop": "-", "reentry": "-", "stops": 0, **measures(bh, start)})
    for lab, w in base.items():
        eq, _ = simulate(days, r3, w, 9.0, False, above10)
        rows.append({"design": lab, "stop": "none", "reentry": "-", "stops": 0, **measures(eq, start)})
        for s in STOPS:
            for re_ in (False, True):
                eq, ns = simulate(days, r3, w, s, re_, above10)
                rows.append({"design": lab, "stop": f"{s:.0%}", "reentry": "R2 month-end above 10m avg" if re_ else "R1 next signal",
                             "stops": ns, **measures(eq, start)})
    df = pd.DataFrame(rows)
    bhr = df.iloc[0]
    def passes(row):
        if row["stop"] in ("-", "none"):
            return np.nan
        nos = df[(df.design == row["design"]) & (df.stop == "none")].iloc[0]
        return all(row[f"{e} CAGR"] > bhr[f"{e} CAGR"] and row[f"{e} maxDD"] > bhr[f"{e} maxDD"]
                   and row[f"{e} maxDD"] > nos[f"{e} maxDD"] for e in ERAS)
    df["passes"] = df.apply(passes, axis=1)
    df["within_25pct"] = df["maxDD"] >= -0.25
    df.to_csv("research/swing/trailing_stop_results.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 280); pd.set_option("display.max_columns", 40)
    cols = ["design", "stop", "reentry", "stops", "CAGR", "maxDD", "worst_day", "days_25pct_down", "3y_p10", "3y_median",
            "1950-1986 CAGR", "1950-1986 maxDD", "1987-2006 CAGR", "1987-2006 maxDD", "2007-2026 CAGR", "2007-2026 maxDD", "passes"]
    if table:
        print(df[cols].round(3).to_string(index=False))

    if intraday_check:
        g = ohlc("^GSPC")
        g = g[~g.index.duplicated()].reindex(days)
        pc = close.shift(1)
        lo_r = (3 * (g["low"] / pc - 1)).to_numpy(copy=True)
        hi_r = (3 * (g["high"] / pc - 1)).to_numpy(copy=True)
        op_r = (3 * (g["open"] / pc - 1)).to_numpy(copy=True)
        bad = ~(np.isfinite(lo_r)) | (g["low"].values >= g["high"].values)   # early Yahoo rows with no range
        lo_r[bad] = np.nan
        print("\nSensitivity, 1984 on: close-based stop vs a real intraday trailing-stop order")
        for lab, w in base.items():
            for s in STOPS:
                for re_ in (False, True):
                    e1, n1 = simulate(days, r3, w, s, re_, above10)
                    e2, n2 = simulate(days, r3, w, s, re_, above10, (lo_r, hi_r, op_r))
                    p1, p2 = measures(e1, "1985-01-02"), measures(e2, "1985-01-02")
                    print(f"   {lab:28s} {s:.0%} {'R2' if re_ else 'R1'}: close stop {p1['CAGR']:+.1%} / {p1['maxDD']:+.0%} "
                          f"(worst day {p1['worst_day']:+.0%}) | intraday order {p2['CAGR']:+.1%} / {p2['maxDD']:+.0%} "
                          f"(worst day {p2['worst_day']:+.0%})")


if __name__ == "__main__":
    main()
