"""Crypto C5 — the swing plan and the bitcoin 10-month rule in one account. See PREREGISTRATION_C5.md.

    python3 -m research.crypto.combo_account
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.crypto.data import coinbase_btc_daily
from research.swing.data import load
from research.swing.lib import daily_features
from research.swing.study_standalone import run
from src.portfolio import trend_cycle as tc

LEV, SW_COST, BTC_COST, FIN, FEE = 3, 0.0009, 0.0025, 0.01, 0.0095
START, HALF = pd.Timestamp("2016-06-01"), pd.Timestamp("2021-01-01")


def components():
    data = load(); feats = daily_features(data)
    out, _ = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=SW_COST * 1e4 / LEV)
    rf = (data["^IRX"]["close"] / 100).reindex(out.index).ffill().fillna(0) / 252
    swing = LEV * out["pos"] - out["expo"] * ((LEV - 1) * (rf + FIN / 252) + FEE / 252)
    expo = out["expo"]
    btc = coinbase_btc_daily()
    btc = btc[~btc.index.duplicated()].asfreq("D").ffill()
    m = tc.to_bars(btc, "M")
    on_m = (m > m.rolling(10).mean()).astype(float)
    on_m.index = on_m.index + pd.Timedelta(days=1)            # known at the month-end close, applies after it
    days = out.index
    rule = on_m.reindex(btc.index, method="ffill").fillna(0).reindex(days, method="ffill").fillna(0)
    b = btc.reindex(days, method="ffill")
    rbtc = b.pct_change().fillna(0)
    return days, swing, expo, rule, rbtc


def with_btc(days, swing, expo, rbtc, share_btc):
    """Account return: swing component plus bitcoin on `share_btc` (decided at the prior close)."""
    s = share_btc.reindex(days).fillna(0)
    held = s.shift(1).fillna(0)
    trade = s.diff().abs().fillna(s.iloc[0])
    return swing + held * rbtc - trade * BTC_COST


def halves(days, swing, rule, rbtc):
    """V4: half swing plan, half bitcoin rule, back to 50/50 at each month end."""
    btc_sleeve = rule.shift(1).fillna(0) * rbtc - rule.diff().abs().fillna(0) * BTC_COST
    out, ws, wb = [], 0.5, 0.5
    month = None
    for d in days:
        if month is not None and d.month != month:            # first session of a new month: rebalance to 50/50
            tot = ws + wb
            out_cost = abs(wb - tot / 2) * BTC_COST
            ws, wb = tot / 2, tot / 2 - out_cost
        month = d.month
        prev = ws + wb
        ws *= 1 + swing.loc[d]; wb *= 1 + btc_sleeve.loc[d]
        out.append((ws + wb) / prev - 1)
    return pd.Series(out, index=days)


def measures(a: pd.Series) -> dict:
    a = a.loc[START:]
    eq = (1 + a).cumprod()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    yr = (1 + a).groupby(a.index.year).prod() - 1
    d = {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "maxDD": (eq / eq.cummax() - 1).min(), "worst year": yr.min(),
         "best year": yr.max()}
    for lab, (x, y) in (("2016-20", (START, HALF - pd.Timedelta(days=1))), ("2021-26", (HALF, None))):
        e = (1 + a.loc[x:y]).cumprod()
        yy = (e.index[-1] - e.index[0]).days / 365.25
        d[f"{lab} CAGR"] = e.iloc[-1] ** (1 / yy) - 1
        d[f"{lab} maxDD"] = (e / e.cummax() - 1).min()
    bal, dep = 1000.0, 1000.0
    month = None
    for dt, r in a.items():
        if month is not None and dt.month != month:
            bal += 150; dep += 150
        month = dt.month
        bal *= 1 + r
    d["$1,000 + $150/mo"] = bal; d["deposited"] = dep
    return d


def main():
    days, swing, expo, rule, rbtc = components()
    idle = 1 - expo.shift(-1).fillna(expo.iloc[-1])           # idle share for tomorrow, set by today's close
    designs = {
        "V0 swing plan alone": swing,
        "V1 bitcoin rule alone": with_btc(days, swing * 0, expo * 0, rbtc, rule),
        "V2 swing + bitcoin rule on idle cash": with_btc(days, swing, expo, rbtc, rule * idle),
        "V3 swing + bitcoin always on idle cash": with_btc(days, swing, expo, rbtc, idle),
        "V4 half swing, half bitcoin rule": halves(days, swing, rule, rbtc),
        "bitcoin held": rbtc,
    }
    rows = [{"design": k, **measures(v)} for k, v in designs.items()]
    df = pd.DataFrame(rows)
    df.to_csv("research/crypto/combo_account_results.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 250)
    show = df.copy()
    for c in show.columns:
        if c not in ("design", "$1,000 + $150/mo", "deposited"):
            show[c] = (show[c] * 100).round(1)
    print(show.round(0).to_string(index=False))
    v0, v1, v2 = df.iloc[0], df.iloc[1], df.iloc[2]
    gate = all(v2[f"{h} CAGR"] > max(v0[f"{h} CAGR"], v1[f"{h} CAGR"]) for h in ("2016-20", "2021-26")) and v2.maxDD > v1.maxDD
    print(f"\nGate (V2 above V0 and V1 in both halves, shallower drawdown than V1): {'PASS' if gate else 'FAIL'}")
    print(f"swing exposure: in a position {(expo.loc[START:] > 0).mean():.0%} of days; bitcoin rule ON {rule.loc[START:].mean():.0%} of days; "
          f"correlation of daily returns swing vs bitcoin {swing.loc[START:].corr(rbtc.loc[START:]):.2f}")


if __name__ == "__main__":
    main()
