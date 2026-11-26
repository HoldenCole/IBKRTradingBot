"""Crypto C4 — do this project's existing signals predict bitcoin? See PREREGISTRATION_C4.md.

    python3 -m research.crypto.predict_btc
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st

from research.crypto.data import coinbase_btc_daily
from research.crypto.trend import combo
from research.swing.data import load
from research.swing.lib import daily_features
from research.trend_cycle.study_signals import states
from src.portfolio import trend_cycle as tc

HALF = pd.Timestamp("2021-01-01")
START = pd.Timestamp("2015-07-20")


def asof(s: pd.Series, labels: pd.DatetimeIndex) -> pd.Series:
    """Value of a daily series at the last date on or before each label."""
    s = s.dropna().sort_index()
    pos = s.index.searchsorted(labels, side="right") - 1
    out = pd.Series(np.where(pos >= 0, s.values[np.clip(pos, 0, None)], np.nan), index=labels)
    return out


def score(name: str, on: pd.Series, fwd: pd.Series) -> dict:
    d = pd.DataFrame({"on": on, "fwd": fwd}).dropna()
    d = d[d.index >= START]
    d["on"] = d["on"].astype(bool)
    row = {"signal": name, "n_on": int(d.on.sum()), "n_off": int((~d.on).sum())}
    for lab, x in (("all", d), ("2015-20", d[d.index < HALF]), ("2021-26", d[d.index >= HALF])):
        a, b = x.fwd[x.on], x.fwd[~x.on]
        row[f"{lab} on"] = a.mean(); row[f"{lab} off"] = b.mean(); row[f"{lab} diff"] = a.mean() - b.mean()
        if lab == "all":
            row["t"] = st.ttest_ind(a, b, equal_var=False).statistic if len(a) > 2 and len(b) > 2 else np.nan
    row["helps"] = (np.sign(row["2015-20 diff"]) == np.sign(row["2021-26 diff"])) and abs(row["t"]) >= 2
    return row


def run_strategy(pos: pd.Series, r: pd.Series, L: float, cost=0.001) -> pd.Series:
    p = pos.reindex(r.index).fillna(0).shift(1).fillna(0)
    turn = p.diff().abs().fillna(p.iloc[0])
    return (1 + L * p * r - L * turn * cost).cumprod()


def perf(eq: pd.Series) -> tuple[float, float]:
    eq = eq / eq.iloc[0]
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return eq.iloc[-1] ** (1 / yrs) - 1, (eq / eq.cummax() - 1).min()


def main():
    btc = coinbase_btc_daily()
    btc = btc[~btc.index.duplicated()].asfreq("D").ffill()
    data = load()
    feats = daily_features(data)
    spx = data["^GSPC"]["close"]

    # ---- monthly
    mlab = tc.to_bars(spx, "M").index
    mlab = mlab[mlab >= START]
    b_m = asof(btc, mlab)
    fwd_m = b_m.shift(-1) / b_m - 1
    sm = states(tc.to_bars(spx, "M"))
    bm = states(tc.to_bars(btc, "M"))
    quad_next = asof(feats["quad"].astype("object").map({"G": 1, "R": 2, "S": 3, "D": 4}).astype(float),
                     mlab + pd.offsets.MonthBegin(1) + pd.Timedelta(days=5)).set_axis(mlab)
    btc_m_close = tc.to_bars(btc, "M")
    rows = [
        score("M1 regime Growth or Reflation", quad_next.isin([1, 2]) & quad_next.notna(), fwd_m),
        score("M2 S&P monthly flag INTACT", (sm.cq.isin([2, 3]) & sm.tq.isin([2, 3])).reindex(mlab), fwd_m),
        score("M3 S&P monthly trend rising", sm.tq.isin([1, 2]).reindex(mlab), fwd_m),
        score("M4 BTC monthly trend rising", bm.tq.isin([1, 2]).reindex(mlab), fwd_m),
        score("M5 BTC monthly cycle rising", bm.cq.isin([1, 2]).reindex(mlab), fwd_m),
        score("M6 BTC above 10-month average", (btc_m_close > btc_m_close.rolling(10).mean()).reindex(mlab), fwd_m),
    ]
    per_quad = {q: fwd_m[(quad_next == i).values].mean() for i, q in enumerate(["Growth", "Reflation", "Inflation", "Deflation"], 1)}
    n_quad = {q: int((quad_next == i).sum()) for i, q in enumerate(["Growth", "Reflation", "Inflation", "Deflation"], 1)}

    # ---- weekly
    wlab = tc.to_bars(spx, "W").index
    wlab = wlab[wlab >= START]
    b_w = asof(btc, wlab)
    fwd_w = b_w.shift(-1) / b_w - 1
    sw = states(tc.to_bars(spx, "W"))
    bw = states(tc.to_bars(btc, "W"))
    vix = asof(feats["vix"], wlab)
    frag = asof(((feats["spy_ext200"] >= 0) & (feats["spy_ext200"] <= 0.03) & (feats["rvol20"] > 0.16)).astype(float), wlab)
    rows += [
        score("W1 S&P weekly trend rising", sw.tq.isin([1, 2]).reindex(wlab), fwd_w),
        score("W2 BTC weekly trend rising", bw.tq.isin([1, 2]).reindex(wlab), fwd_w),
        score("W3 BTC weekly cycle rising", bw.cq.isin([1, 2]).reindex(wlab), fwd_w),
        score("W4 VIX above 25", vix > 25, fwd_w),
        score("W5 equity fragile state", frag > 0.5, fwd_w),
    ]

    # ---- daily reference: the entry-103 trend
    w, _ = combo(btc)
    trend_on = w > 0
    fwd5 = btc.shift(-5) / btc - 1
    rows.append(score("D1 BTC daily trend on (entry 103)", trend_on, fwd5))
    res = pd.DataFrame(rows)
    res.to_csv("research/crypto/predict_btc_results.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 250)
    show = res.copy()
    for c in show.columns:
        if c.endswith((" on", " off", " diff")):
            show[c] = (show[c] * 100).round(1)
    print("Bitcoin forward return (%) when each signal is on vs off; monthly = next month, weekly = next week, daily = next 5 days")
    print(show.round(2).to_string(index=False))
    print("\nBTC next month by regime quadrant in force (mean %, months):",
          {q: (round(per_quad[q] * 100, 1), n_quad[q]) for q in per_quad})

    # ---- filters on the bitcoin trend
    r = btc.pct_change().fillna(0)
    spx_above10 = (tc.to_bars(spx, "M") > tc.to_bars(spx, "M").rolling(10).mean())
    def monthly_to_daily(flag: pd.Series) -> pd.Series:      # known at the month-end close, applies after it
        f = flag.astype(float).copy(); f.index = f.index + pd.Timedelta(days=1)
        return f.reindex(btc.index, method="ffill").fillna(0) > 0.5
    def weekly_to_daily(flag: pd.Series) -> pd.Series:
        f = flag.astype(float).copy(); f.index = f.index + pd.Timedelta(days=1)
        return f.reindex(btc.index, method="ffill").fillna(0) > 0.5
    not_broken = ~(sm.cq.isin([1, 4]) & sm.tq.isin([1, 4]))
    filt = {"trend alone": trend_on,
            "F1 + S&P above 10-month average": trend_on & monthly_to_daily(spx_above10),
            "F2 + S&P monthly flag not BROKEN": trend_on & monthly_to_daily(not_broken),
            "F3 + BTC weekly trend rising": trend_on & weekly_to_daily(bw.tq.isin([1, 2])),
            "hold bitcoin": pd.Series(True, index=btc.index)}
    print("\nBitcoin trend with and without filters (spot, 10 bp a switch, no funding): CAGR / max drawdown")
    out = []
    for lab, pos in filt.items():
        row = {"design": lab}
        for L in (1, 2):
            for per, (a, b) in (("all", (START, None)), ("2015-20", (START, HALF - pd.Timedelta(days=1))), ("2021-26", (HALF, None))):
                eq = run_strategy(pos.loc[a:b], r.loc[a:b], L)
                c, d = perf(eq)
                row[f"{L}x {per} CAGR"], row[f"{L}x {per} maxDD"] = c, d
        row["time in"] = pos.loc[START:].mean()
        out.append(row)
        print(f"   {lab:36s} in {row['time in']:.0%} | 1x all {row['1x all CAGR']:+.0%}/{row['1x all maxDD']:+.0%} "
              f"2015-20 {row['1x 2015-20 CAGR']:+.0%}/{row['1x 2015-20 maxDD']:+.0%} 2021-26 {row['1x 2021-26 CAGR']:+.0%}/{row['1x 2021-26 maxDD']:+.0%} "
              f"| 2x all {row['2x all CAGR']:+.0%}/{row['2x all maxDD']:+.0%}")
    o = pd.DataFrame(out)
    base = o.iloc[0]
    for _, x in o.iloc[1:4].iterrows():
        better = all(x[f"1x {p} CAGR"] > base[f"1x {p} CAGR"] and x[f"1x {p} maxDD"] > base[f"1x {p} maxDD"] for p in ("2015-20", "2021-26"))
        print(f"   {x['design']}: improves the trend in both halves? {better}")
    o.to_csv("research/crypto/predict_btc_filters.csv", index=False, float_format="%.4f")

    # ---- today's reading
    print(f"\nToday's reading (bitcoin close {btc.index[-1].date()}: ${btc.iloc[-1]:,.0f})")
    lookbacks = (5, 10, 20, 30, 60, 90, 150, 250, 360)
    from research.crypto.trend import _positions
    on_n = []
    for n in lookbacks:
        up = btc.rolling(n).max().values; lo = btc.rolling(n).min().values
        on_n.append(int(_positions(btc.values.astype(float), up, 0.5 * (up + lo))[-1]))
    print(f"   bitcoin daily trend: {'ON' if trend_on.iloc[-1] else 'OFF'} (lookbacks long: "
          + ", ".join(f"{n}d" for n, p in zip(lookbacks, on_n) if p) + ")")
    print(f"   bitcoin monthly QB: cycle Q{int(bm.cq.iloc[-1])}, trend Q{int(bm.tq.iloc[-1])}; weekly: cycle Q{int(bw.cq.iloc[-1])}, "
          f"trend Q{int(bw.tq.iloc[-1])}; 10-month average ${btc_m_close.rolling(10).mean().iloc[-1]:,.0f}")
    print(f"   S&P monthly QB: cycle Q{int(sm.cq.iloc[-1])}, trend Q{int(sm.tq.iloc[-1])}; weekly trend Q{int(sw.tq.iloc[-1])}; "
          f"regime in force {feats['quad'].iloc[-1]}; VIX {feats['vix'].iloc[-1]:.1f}")


if __name__ == "__main__":
    main()
