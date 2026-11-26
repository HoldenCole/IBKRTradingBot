"""Entry 91 — short-dated (weekly) options on the 3x funds for the swing dip-buy (MODEL-BASED).

User follow-up to entry 90: 30 days to expiry is too far out for a trade held a
few days; use a near expiry and account for the bid/ask spread and time decay.

Trades are the same as entry 90 (test-79 signals, 2011-2026, 295 trades; median
hold 5 calendar days, longest 14). Expiry rule: the first Friday at least N
calendar days after entry, N in {3, 7, 14}; 30 days is kept as the reference.
If the option expires before the signal exits, it is sold at the close of the
last trading day on or before that Friday (intrinsic value less the spread).
Everything else is as entry 90: Black-Scholes on the fund's actual price path,
ATM IV = 3 x 0.90 x VIX (UPRO) or VXN (TQQQ) with the same skew, half-spread
max(1%, $0.01) on TQQQ and max(2.5%, $0.025) on UPRO plus $0.65 a contract,
and a stress run with the spread doubled. The VIX is a 30-day measure; the
model applies it unchanged to a one-week option. The test assumes a Friday
expiry existed every week, which the early years may not have had.

    python3 -m research.swing.study_options_3x_weekly
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load, ohlc
from research.swing.lib import daily_features
from research.swing.study_options_3x import COMM, FUND, opt_price
from research.swing.study_standalone import run

START = "2011-01-01"
STRUCTS = {
    "long ATM call": [(True, 1.00, +1)],
    "long ITM call (0.95)": [(True, 0.95, +1)],
    "long ITM call (0.90)": [(True, 0.90, +1)],
    "call debit spread 1.00/1.05": [(True, 1.00, +1), (True, 1.05, -1)],
    "call debit spread 0.95/1.05": [(True, 0.95, +1), (True, 1.05, -1)],
}
RULES = {"Friday 3+ days out": 3, "Friday 7+ days out": 7, "Friday 14+ days out": 14, "30 days (entry 90)": None}


def expiry(entry: pd.Timestamp, min_days: int | None) -> pd.Timestamp:
    if min_days is None:
        return entry + pd.Timedelta(days=30)
    d = entry + pd.Timedelta(days=min_days)
    return d + pd.Timedelta(days=(4 - d.day_of_week) % 7)


def fill(px, buy, pct, floor, mult):
    hs = max(pct * px, floor) * mult
    return px + hs + COMM if buy else max(px - hs - COMM, 0.0)


def build(data, tr, funds, rf, min_days, mult):
    rows = []
    for _, t in tr.iterrows():
        f, vix, pct, floor = FUND[t["sym"]]
        fd = funds[f]
        if t["entry"] not in fd.index or t["exit"] not in fd.index:
            continue
        exp = expiry(t["entry"], min_days)
        x = t["exit"] if t["exit"] <= exp else fd.index[fd.index <= exp][-1]
        S0 = float(fd["raw_close"].loc[t["entry"]])
        S1 = S0 * float(fd["close"].loc[x] / fd["close"].loc[t["entry"]])
        iv = (3 * 0.90 * data[vix]["close"] / 100).reindex(fd.index).ffill()
        v0, v1 = float(iv.loc[t["entry"]]), float(iv.loc[x])
        r = float(rf.reindex(fd.index).ffill().loc[t["entry"]])
        T0, T1 = (exp - t["entry"]).days, (exp - x).days
        row = {"entry": t["entry"], "exit": t["exit"], "opt_exit": x, "early": x < t["exit"], "sym": t["sym"],
               "fund": f, "S0": S0, "fund_ret": float(fd["close"].loc[t["exit"]] / fd["close"].loc[t["entry"]]) - 1,
               "dte": T0}
        for name, legs in STRUCTS.items():
            mid0 = sum(sg * opt_price(S0, S0 * k, T0, v0, r, c) for c, k, sg in legs)
            c0 = sum(sg * fill(opt_price(S0, S0 * k, T0, v0, r, c), sg > 0, pct, floor, mult) for c, k, sg in legs)
            mid1d = sum(sg * opt_price(S0, S0 * k, T0 - 1, v0, r, c) for c, k, sg in legs)  # one day, price unchanged
            c1 = sum(sg * fill(opt_price(S1, S0 * k, T1, v1, r, c), sg < 0, pct, floor, mult) for c, k, sg in legs)
            c1 = max(c1, 0.0)
            row[f"{name}|cost"] = c0 * 100
            row[f"{name}|pnl"] = (c1 - c0) * 100
            row[f"{name}|spread"] = 2 * (c0 - mid0) / c0 if c0 > 0 else np.nan     # round trip, share of premium
            row[f"{name}|theta"] = (mid0 - mid1d) / c0 if c0 > 0 else np.nan        # first day's decay, share of premium
        rows.append(row)
    return pd.DataFrame(rows)


def account(t, name, start, frac, contrib):
    """Whole contracts, `frac` of equity in premium per trade; name=None holds the fund (half per slot)."""
    ex = "exit" if name is None else "opt_exit"
    ev = sorted([(r.entry, 1, i) for i, r in t.iterrows()] + [(r[ex], 0, i) for i, r in t.iterrows()],
                key=lambda e: (e[0], e[1]))
    cash, open_, path, last = start, {}, [], None
    for d, kind, i in ev:
        m = (d.year, d.month)
        if last is not None and m != last:
            cash += contrib
        last = m
        r = t.loc[i]
        if kind == 0 and i in open_:
            n, _ = open_.pop(i)
            cash += n * r.S0 * (1 + r.fund_ret) - 0.35 if name is None else n * (r[f"{name}|cost"] + r[f"{name}|pnl"])
        elif kind == 1:
            eq = cash + sum(c for _, c in open_.values())
            if name is None:
                n = int(min(eq / 2, cash) // r.S0); cost = n * r.S0 + 0.35
            else:
                unit = r[f"{name}|cost"]
                n = int(min(frac * eq, cash) // unit) if unit > 0 else 0; cost = n * unit
            if n >= 1:
                cash -= cost; open_[i] = (n, cost)
        path.append((d, cash + sum(c for _, c in open_.values())))
    s = pd.Series([e for _, e in path], index=[d for d, _ in path])
    s = s[~s.index.duplicated(keep="last")]
    return s.iloc[-1], (s / s.cummax() - 1).min()


def main():
    data = load()
    feats = daily_features(data)
    rf = data["^IRX"]["close"] / 100
    _, tr = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=0.0)
    tr = tr[tr["entry"] >= START].reset_index(drop=True)
    funds = {f: ohlc(f) for f, *_ in FUND.values()}
    res = []
    for mult in (1.0, 2.0):
        for rule, nd in RULES.items():
            t = build(data, tr, funds, rf, nd, mult)
            t["era"] = np.where(t["entry"] < "2017-01-01", "2011-16", "2017-26")
            if mult == 1.0 and rule == "Friday 3+ days out":
                fe, fd_ = account(t, None, 1000.0, 0.5, 150)
                print(f"trades {len(t)}; 3x fund per trade mean {t.fund_ret.mean():+.1%} win {(t.fund_ret>0).mean():.0%}; "
                      f"account $1,000 + $150/mo -> ${fe:,.0f}, worst drop {fd_:+.0%}")
            print(f"\n=== {rule}, spread x{mult:.0f} | days to expiry median {t.dte.median():.0f}, "
                  f"closed at expiry before the signal exit {t.early.mean():.0%} ===")
            for name in STRUCTS:
                ror = t[f"{name}|pnl"] / t[f"{name}|cost"]
                line = {"rule": rule, "spread": mult, "struct": name, "mean": ror.mean(), "median": ror.median(),
                        "win": (ror > 0).mean(), "e1": ror[t.era == "2011-16"].mean(), "e2": ror[t.era == "2017-26"].mean(),
                        "rt_spread": t[f"{name}|spread"].median(), "theta1d": t[f"{name}|theta"].median(),
                        "upro": t[t.fund == "UPRO"][f"{name}|cost"].median(), "tqqq": t[t.fund == "TQQQ"][f"{name}|cost"].median()}
                for frac in (0.10, 0.25):
                    line[f"end{int(frac*100)}"], line[f"dd{int(frac*100)}"] = account(t, name, 1000.0, frac, 150)
                res.append(line)
                print(f"   {name:28s} mean {line['mean']:+6.1%} med {line['median']:+6.1%} win {line['win']:.0%} "
                      f"| 2011-16 {line['e1']:+6.1%} 2017-26 {line['e2']:+6.1%} | spread r/t {line['rt_spread']:.0%} "
                      f"decay day1 {line['theta1d']:.1%} | cost UPRO ${line['upro']:,.0f} TQQQ ${line['tqqq']:,.0f} "
                      f"| acct 10% ${line['end10']:>8,.0f} ({line['dd10']:+.0%}) 25% ${line['end25']:>8,.0f} ({line['dd25']:+.0%})")
    pd.DataFrame(res).to_csv("research/swing/options_3x_weekly_results.csv", index=False)


if __name__ == "__main__":
    main()
