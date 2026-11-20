"""Entry 84 — what the Trend & Cycle state codes have meant for the S&P 500.

Index-level only (the member balances need point-in-time constituents to
backfill honestly). ^GSPC weekly and daily bars, two eras: 1987-2006 and
2007-2026. For each oscillator (cycle = SMA5-SMA15, trend = Coppock) and each
quadrant: how long a stay usually lasts, and forward S&P returns by how
mature the stay is (the 01 / 02 / 03 ... count).

    python3 -m research.trend_cycle.study_states
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import fetch_ohlc
from src.portfolio.trend_cycle import OSCILLATORS, state_history, to_bars

ERAS = {"1987-2006": ("1987-01-01", "2006-12-31"), "2007-2026": ("2007-01-01", "2026-12-31")}
QN = {1: "Q1 below/rising", 2: "Q2 above/rising", 3: "Q3 above/falling", 4: "Q4 below/falling"}


def runs(h: pd.DataFrame) -> pd.DataFrame:
    """One row per completed stay in a quadrant: quadrant, length."""
    g = (h["quadrant"] != h["quadrant"].shift()).cumsum()
    r = h.groupby(g).agg(quadrant=("quadrant", "first"), length=("in_quadrant", "max"), start=("in_quadrant", lambda s: s.index[0]))
    return r.iloc[:-1]            # drop the still-open stay


def study(close: pd.Series, tf: str, horizons: tuple, unit: str):
    bars = to_bars(close, tf)
    fwd = {h: bars.shift(-h) / bars - 1 for h in horizons}
    base = {era: {h: fwd[h].loc[a:b].mean() for h in horizons} for era, (a, b) in ERAS.items()}
    print(f"\n################ {unit.upper()} bars ################")
    print("baseline forward return, any bar: " + " | ".join(
        f"{era}: " + ", ".join(f"{h}{unit[0]} {base[era][h]:+.2%}" for h in horizons) for era in ERAS))
    for m, fn in OSCILLATORS.items():
        h = state_history(fn(bars))
        r = runs(h)
        print(f"\n== {m.upper()} ==")
        print("   how long a stay in each quadrant lasts (" + unit + "s): " + " | ".join(
            f"{QN[q]}: median {r[r['quadrant']==q]['length'].median():.0f}, mean {r[r['quadrant']==q]['length'].mean():.1f}, "
            f"90th pct {r[r['quadrant']==q]['length'].quantile(.9):.0f}" for q in (1, 2, 3, 4)))
        print("   forward return by quadrant (mean; share positive) — per era")
        for q in (1, 2, 3, 4):
            cells = []
            for era, (a, b) in ERAS.items():
                idx = h.index[(h["quadrant"] == q)]
                idx = idx[(idx >= a) & (idx <= b)]
                cells.append(f"{era} n={len(idx):4d}: " + ", ".join(
                    f"{hz}{unit[0]} {fwd[hz].reindex(idx).mean():+.2%} ({(fwd[hz].reindex(idx) > 0).mean():.0%})" for hz in horizons))
            print(f"      {QN[q]:18s} " + " | ".join(cells))
        print("   maturity: forward return by bars-in-quadrant (the CC digits), Q4 and Q2")
        for q in (4, 2, 3, 1):
            for lo, hi, lab in ((1, 1, "01"), (2, 2, "02"), (3, 3, "03"), (4, 5, "04-05"), (6, 8, "06-08"), (9, 99, "09+")):
                cells = []
                for era, (a, b) in ERAS.items():
                    idx = h.index[(h["quadrant"] == q) & h["in_quadrant"].between(lo, hi)]
                    idx = idx[(idx >= a) & (idx <= b)]
                    if len(idx) < 8:
                        cells.append(f"{era} n={len(idx):3d}: thin")
                        continue
                    hz = horizons[1]
                    cells.append(f"{era} n={len(idx):3d}: " + ", ".join(
                        f"{z}{unit[0]} {fwd[z].reindex(idx).mean():+.2%}" for z in horizons) + f" ({(fwd[hz].reindex(idx) > 0).mean():.0%} up at {hz}{unit[0]})")
                print(f"      {QN[q][:2]} count {lab:5s} " + " | ".join(cells))
    return bars


def combined(close: pd.Series):
    """Today's exact combination: weekly cycle Q4 and weekly trend Q4 while BOTH monthly oscillators are still above zero."""
    w = to_bars(close, "W"); mth = to_bars(close, "M")
    hc, ht = state_history(OSCILLATORS["cycle"](w)), state_history(OSCILLATORS["trend"](w))
    mc, mt = state_history(OSCILLATORS["cycle"](mth)), state_history(OSCILLATORS["trend"](mth))
    # monthly state known at each week = last COMPLETED month (ex-ante)
    mside = ((mc["quadrant"].isin([2, 3])) & (mt["quadrant"].isin([2, 3]))).shift(1)
    mside_w = mside.reindex(w.index, method="ffill")
    df = pd.DataFrame({"c": hc["quadrant"], "cc": hc["in_quadrant"], "t": ht["quadrant"], "tc": ht["in_quadrant"]}).dropna()
    df["m_up"] = mside_w.reindex(df.index)
    fwd = {h: w.shift(-h) / w - 1 for h in (1, 4, 13, 26)}
    print("\n################ COMBINED STATES (weekly) ################")
    conds = {
        "weekly cycle Q4 AND weekly trend Q4": (df["c"] == 4) & (df["t"] == 4),
        "  ... and monthly cycle+trend both still above zero": (df["c"] == 4) & (df["t"] == 4) & (df["m_up"] == True),
        "  ... and monthly NOT both above zero": (df["c"] == 4) & (df["t"] == 4) & (df["m_up"] == False),
        "  ... trend Q4 just began (count 01-02), monthly above zero": (df["c"] == 4) & (df["t"] == 4) & (df["tc"] <= 2) & (df["m_up"] == True),
        "weekly trend Q4, any cycle": df["t"] == 4,
        "weekly trend Q1 (below zero, turning up)": df["t"] == 1,
        "weekly trend Q1 count 01 (first week turning up)": (df["t"] == 1) & (df["tc"] == 1),
        "weekly cycle Q1 count 01 while trend Q4": (df["c"] == 1) & (df["cc"] == 1) & (df["t"] == 4),
    }
    for lab, m in conds.items():
        cells = []
        for era, (a, b) in ERAS.items():
            idx = df.index[m.fillna(False)]; idx = idx[(idx >= a) & (idx <= b)]
            if len(idx) < 6:
                cells.append(f"{era} n={len(idx)}: thin"); continue
            cells.append(f"{era} n={len(idx):3d}: " + ", ".join(f"{h}w {fwd[h].reindex(idx).mean():+.2%}" for h in fwd)
                         + f" ({(fwd[13].reindex(idx) > 0).mean():.0%} up at 13w, worst 13w {fwd[13].reindex(idx).min():+.0%})")
        print(f"   {lab:62s} " + " | ".join(cells))
    # episodes like now: first week weekly trend enters Q4 with monthly both above zero
    ep = df.index[((df["t"] == 4) & (df["tc"] == 1) & (df["m_up"] == True)).fillna(False)]
    print(f"\n   Episodes like this week — weekly TREND enters Q4 (count 01) while monthly cycle and trend are above zero: {len(ep)} since 1987")
    rows = []
    for d in ep:
        i = w.index.get_loc(d)
        # how long the weekly trend then stayed below zero
        j = i
        while j + 1 < len(df.index) and df["t"].reindex(w.index).iloc[j + 1] in (1, 4):
            j += 1
        low = w.iloc[i:i + 27].min() / w.iloc[i] - 1
        rows.append((d.date(), j - i + 1, fwd[4].get(d, np.nan), fwd[13].get(d, np.nan), fwd[26].get(d, np.nan), low))
    e = pd.DataFrame(rows, columns=["week", "weeks_trend_below_zero", "next_4w", "next_13w", "next_26w", "further_low_26w"]).set_index("week")
    pd.set_option("display.width", 200)
    print((e.assign(**{c: (e[c] * 100).round(1) for c in ("next_4w", "next_13w", "next_26w", "further_low_26w")})).to_string())
    done = e.iloc[:-1]
    print(f"   averages (excluding the current one): weeks below zero median {done['weeks_trend_below_zero'].median():.0f}; "
          f"4w {done['next_4w'].mean():+.1%}, 13w {done['next_13w'].mean():+.1%}, 26w {done['next_26w'].mean():+.1%}; "
          f"positive at 13w {(done['next_13w'] > 0).mean():.0%}; avg further low {done['further_low_26w'].mean():+.1%}")


def main():
    close = fetch_ohlc("^GSPC", start="1984-01-01")["raw_close"]
    study(close, "W", (1, 4, 13), "week")
    study(close, "D", (1, 5, 21), "day")
    combined(close)


if __name__ == "__main__":
    main()
