"""Entry 100 — entry 99's design A (monthly trend turns up below zero, hold until the monthly trend
crosses below zero, re-enter at a month-end above the 10-month average after a stop) at 1x, 2x and
3x, with trailing stops of 20/25/30% and none. User follow-up; chosen after seeing entry 99, so a lead.

    python3 -m research.swing.study_trailing_stop_2x
"""
from __future__ import annotations

import pandas as pd

from research.swing.study_concentrated import lev_ret, series, snap, trades_from_bars
from research.swing.study_trailing_stop import measures, simulate
from research.trend_cycle.study_signals import states
from src.portfolio import trend_cycle as tc


def main():
    close, r, rf = series()
    days = close.index
    m = states(tc.to_bars(close, "M"))
    ent = lambda o, q: (m[o] == q) & (m[o + "_prev"] != q)  # noqa: E731
    w = trades_from_bars(ent("tq", 1), m.index, None, ent("tq", 4) & m["tq_prev"].isin([2, 3]), days)
    mb = tc.to_bars(close, "M")
    a10 = mb > mb.rolling(10).mean()
    me = pd.Series(False, index=days); me.loc[snap(a10.index[a10.values], days)] = True
    start = m.index[0]
    rows = []
    for lev in (1, 2, 3):
        rl = lev_ret(r, rf, lev)
        rows.append({"leverage": f"{lev}x", "design": "buy and hold", "stops": 0, **measures((1 + rl).cumprod(), start)})
        for s in (None, 0.20, 0.25, 0.30):
            eq, n = simulate(days, rl, w, 9.0 if s is None else s, s is not None, me.values)
            yr = eq.loc[start:].resample("YE").last().pct_change().dropna()
            rows.append({"leverage": f"{lev}x", "design": "monthly bet, no stop" if s is None else f"monthly bet, {s:.0%} stop, re-enter",
                         "stops": n, **measures(eq, start), "worst_year": yr.min(), "best_year": yr.max(),
                         "years_down": (yr < 0).mean()})
    df = pd.DataFrame(rows)
    df.to_csv("research/swing/trailing_stop_2x_results.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    cols = ["leverage", "design", "stops", "CAGR", "maxDD", "worst_day", "worst_year", "best_year", "years_down",
            "3y_p10", "3y_median", "1950-1986 CAGR", "1950-1986 maxDD", "1987-2006 CAGR", "1987-2006 maxDD",
            "2007-2026 CAGR", "2007-2026 maxDD", "end_multiple"]
    print(df[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
