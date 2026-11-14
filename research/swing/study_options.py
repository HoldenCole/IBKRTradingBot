"""Entry 77 — expressing the daily dip-buy with ETF options (MODEL-BASED).

No historical option chains are available, so prices are Black-Scholes with
the listed implied-vol index as input: SPY<-VIX, QQQ<-VXN. Sector ETFs use a
proxy IV = VIX x (sector 60d realized vol / SPY 60d realized vol). Mapping:
ATM IV = 0.90 x index (the index includes wing premium); skew
IV(K) = ATM x (1 + a ln(S/K)), a = 4 below spot, 1.5 above. Costs: half-spread
0.75% of option price per leg per side (min $0.01) + $0.0065/share commission.
These are approximations — the study answers a DIRECTIONAL question (does the
option wrapper keep, amplify or surrender the stock edge?), not a P&L forecast.

    python3 -m research.swing.study_options
"""
from __future__ import annotations

from math import erf, exp, log, sqrt

import numpy as np
import pandas as pd

from research.swing.data import SECTORS, load
from research.swing.lib import ERAS, bollinger, daily_features, era_of, rsi, simulate, sma

DTE = 30


def ncdf(x): return 0.5 * (1 + erf(x / sqrt(2)))


def bs(S, K, T, v, r, call):
    if T <= 0 or v <= 0:
        return max(S - K, 0.0) if call else max(K - S, 0.0)
    d1 = (log(S / K) + (r + 0.5 * v * v) * T) / (v * sqrt(T)); d2 = d1 - v * sqrt(T)
    return S * ncdf(d1) - K * exp(-r * T) * ncdf(d2) if call else K * exp(-r * T) * ncdf(-d2) - S * ncdf(-d1)


def iv_at(atm, S, K):
    m = log(S / K)
    return atm * (1 + (4.0 if m > 0 else 1.5) * m)


def fill(px, buy):
    hs = max(0.0075 * px, 0.01)
    return px + hs + 0.0065 if buy else max(px - hs - 0.0065, 0.0)


def price(S, K, days_left, atm, r, call):
    return bs(S, K, max(days_left, 0) / 365, max(iv_at(atm, S, K), 0.03), r, call)


STRUCTS = {
    # name: list of (call?, strike multiple of spot, +1 long / -1 short)
    "long ATM call": [(True, 1.00, +1)],
    "long ITM call (0.96)": [(True, 0.96, +1)],
    "deep ITM call (0.90)": [(True, 0.90, +1)],
    "call debit spread 1.00/1.04": [(True, 1.00, +1), (True, 1.04, -1)],
    "put credit spread 1.00/0.95": [(False, 1.00, -1), (False, 0.95, +1)],
    "put credit spread 0.97/0.92": [(False, 0.97, -1), (False, 0.92, +1)],
}


def run(sym, df, atm_iv, feats, rf, kind, gate):
    c = df["close"]
    mid, up, lo, pctb, bw = bollinger(c, 20, 2.0)
    if kind == "BB+RSI2":
        e, x, h = (c < lo) & (rsi(c, 2) < 10), c > sma(c, 5), 10
    else:
        e, x, h = (c < lo), c > mid, 10
    if gate:
        e &= feats["quad"].reindex(c.index).isin(list(gate))
    e &= atm_iv.reindex(c.index).notna()
    tr, _ = simulate(df, e, x, h, mode="close", cost_bps=5)
    rows = []
    for _, t in tr.iterrows():
        # price options off the RAW (traded) price so fixed-cent spreads are scaled correctly;
        # the adjusted-close ratio carries the underlying move (incl. any dividend)
        S0 = float(df["raw_close"].loc[t["entry"]]); S1 = S0 * c.loc[t["exit"]] / c.loc[t["entry"]]
        v0, v1 = atm_iv.loc[t["entry"]], atm_iv.reindex(c.index).ffill().loc[t["exit"]]
        r = float(rf.reindex(c.index).ffill().loc[t["entry"]])
        cal = (t["exit"] - t["entry"]).days
        row = {"sym": sym, "entry": t["entry"], "stock": t["ret"], "iv0": v0, "iv1": v1, "kind": kind}
        for name, legs in STRUCTS.items():
            cost0 = sum(sgn * fill(price(S0, S0 * k, DTE, v0, r, call), sgn > 0) for call, k, sgn in legs)
            val1 = sum(sgn * fill(price(S1, S0 * k, DTE - cal, v1, r, call), sgn < 0) for call, k, sgn in legs)
            pnl = val1 - cost0                       # per share
            if cost0 > 0:                            # debit: risk = premium paid
                risk = cost0
            else:                                    # credit spread: risk = width - credit
                ks = [k for _, k, _ in legs]
                risk = (max(ks) - min(ks)) * S0 + cost0
            row[name + "|pnl_notional"] = pnl / S0
            row[name + "|ror"] = pnl / risk if risk > 0.005 * S0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    data = load(); feats = daily_features(data)
    rf = data["^IRX"]["close"] / 100
    spy_rv = data["SPY"]["close"].pct_change().rolling(60).std()
    vix = data["^VIX"]["close"] / 100
    ivs = {"SPY": 0.90 * vix.reindex(data["SPY"].index).ffill(),
           "QQQ": 0.90 * (data["^VXN"]["close"] / 100).reindex(data["QQQ"].index)}
    for s in SECTORS:
        ratio = (data[s]["close"].pct_change().rolling(60).std() / spy_rv.reindex(data[s].index)).clip(0.6, 3.0)
        ivs[s] = 0.90 * vix.reindex(data[s].index).ffill() * ratio
    for kind in ("BB+RSI2", "BB"):
        for gate, glab in (("GR", "aligned G/R"), (None, "ungated")):
            parts = [run(s, data[s], ivs[s], feats, rf, kind, gate) for s in ivs]
            t = pd.concat(parts, ignore_index=True)
            t["era"] = t["entry"].map(era_of)
            t = t[t["era"].isin(ERAS)]
            for uni, m in (("SPY+QQQ (listed vol index)", t["sym"].isin(["SPY", "QQQ"])), ("9 sectors (proxy IV)", ~t["sym"].isin(["SPY", "QQQ"]))):
                s = t[m]
                print(f"\n=== {kind} · {glab} · {uni}: n={len(s)}  IV at entry {s['iv0'].mean():.0%} -> at exit {s['iv1'].mean():.0%} ===")
                print(f"   {'stock (reference)':30s} pnl/notional {s['stock'].mean()*1e4:+6.1f}bp  win {(s['stock']>0).mean():.0%}   by era "
                      + " ".join(f"{s[s['era']==e]['stock'].mean()*1e4:+.0f}" for e in ERAS))
                for name in STRUCTS:
                    pn, ror = s[name + "|pnl_notional"], s[name + "|ror"]
                    print(f"   {name:30s} pnl/notional {pn.mean()*1e4:+6.1f}bp  win {(pn>0).mean():.0%}  "
                          f"return on risk: mean {ror.mean():+6.1%} median {ror.median():+6.1%} worst {ror.min():+.0%}   by era "
                          + " ".join(f"{s[s['era']==e][name+'|ror'].mean():+.1%}" for e in ERAS))
    t.to_pickle("research/cache/swing_options_trades.pkl")


if __name__ == "__main__":
    main()
