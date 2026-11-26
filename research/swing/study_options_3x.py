"""Entry 90 — options on the 3x funds (UPRO, TQQQ) as the wrapper for the swing dip-buy (MODEL-BASED).

User question: what about options on 3x ETFs, for the small high-risk account?
Same signals as the live 3x account (test 79: SPY/QQQ RSI(2) dip-buys, two
slots, regime gate, exit above the 5-day average or after 10 days), 2011-2026
when both funds and their options trade. The fund's ACTUAL price path between
entry and exit is used; only the option prices are modelled.

Option model (as test 77, scaled to the funds): Black-Scholes, 30 days to
expiry at entry, ATM implied vol = 3 x 0.90 x the index's vol index (VIX for
UPRO, VXN for TQQQ), skew IV(K) = ATM x (1 + a ln(S/K)), a = 4 below spot and
1.5 above. Costs per leg per side: half-spread max(1% of price, $0.01) on TQQQ
and max(2.5%, $0.025) on UPRO (UPRO's chain is much thinner; both are
assumptions, not measured), plus $0.65 per contract. Directional answer only:
no historical chains were used. Credit spreads are left out: they need a margin
account, and at the model's highest implied vols (3 x a VIX of 80) the risk per
spread shrinks toward zero, which makes the model unreliable for them.

    python3 -m research.swing.study_options_3x
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load, ohlc
from research.swing.lib import daily_features
from research.swing.study_options import bs, iv_at
from research.swing.study_standalone import run

START = "2011-01-01"
DTE = 30
FUND = {"SPY": ("UPRO", "^VIX", 0.025, 0.025), "QQQ": ("TQQQ", "^VXN", 0.01, 0.01)}
STRUCTS = {
    "long ATM call": [(True, 1.00, +1)],
    "long ITM call (0.90)": [(True, 0.90, +1)],
    "call debit spread 1.00/1.05": [(True, 1.00, +1), (True, 1.05, -1)],
    "call debit spread 1.00/1.10": [(True, 1.00, +1), (True, 1.10, -1)],
}
COMM = 0.0065   # $0.65 per contract, per share


def fill(px: float, buy: bool, pct: float, floor: float) -> float:
    hs = max(pct * px, floor)
    return px + hs + COMM if buy else max(px - hs - COMM, 0.0)


def opt_price(S, K, days, atm, r, call):
    return bs(S, K, max(days, 0) / 365, max(iv_at(atm, S, K), 0.05), r, call)


def trades_with_options(data, feats, rf):
    out, tr = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=0.0)
    tr = tr[tr["entry"] >= START].reset_index(drop=True)
    funds = {f: ohlc(f) for f, *_ in FUND.values()}
    rows = []
    for _, t in tr.iterrows():
        f, vix, pct, floor = FUND[t["sym"]]
        fd = funds[f]
        if t["entry"] not in fd.index or t["exit"] not in fd.index:
            continue
        S0 = float(fd["raw_close"].loc[t["entry"]])
        S1 = S0 * float(fd["close"].loc[t["exit"]] / fd["close"].loc[t["entry"]])
        iv = 3 * 0.90 * data[vix]["close"] / 100
        v0, v1 = float(iv.reindex([t["entry"]]).iloc[0]), float(iv.reindex(fd.index).ffill().loc[t["exit"]])
        r = float(rf.reindex(fd.index).ffill().loc[t["entry"]])
        cal = (t["exit"] - t["entry"]).days
        row = {"entry": t["entry"], "exit": t["exit"], "sym": t["sym"], "fund": f, "S0": S0, "iv0": v0, "iv1": v1,
               "fund_ret": S1 / S0 - 1}
        for name, legs in STRUCTS.items():
            c0 = sum(sg * fill(opt_price(S0, S0 * k, DTE, v0, r, call), sg > 0, pct, floor) for call, k, sg in legs)
            c1 = sum(sg * fill(opt_price(S1, S0 * k, DTE - cal, v1, r, call), sg < 0, pct, floor) for call, k, sg in legs)
            c1 = max(c1, 0.0)                       # a nearly worthless debit position is left to expire, not paid to close
            if c0 > 0:
                risk = c0
            else:
                ks = [k for _, k, _ in legs]
                risk = (max(ks) - min(ks)) * S0 + c0
            row[f"{name}|cost"] = c0 * 100          # per contract
            row[f"{name}|risk"] = risk * 100
            row[f"{name}|pnl"] = (c1 - c0) * 100
        rows.append(row)
    return pd.DataFrame(rows)


def account(t: pd.DataFrame, name: str | None, start: float, frac: float, contrib: float = 0.0):
    """Event-driven account: at each entry spend `frac` of equity (premium, or margin at risk for credit
    spreads) in whole contracts; skip if one contract is too big. name=None trades the 3x fund itself
    with half the equity per slot (whole shares, $0.35 per order)."""
    ev = sorted([(r.entry, 1, i) for i, r in t.iterrows()] + [(r.exit, 0, i) for i, r in t.iterrows()],
                key=lambda e: (e[0], e[1]))
    cash, open_, eq_path, taken, skipped = start, {}, [], 0, 0
    last_month = None
    for d, kind, i in ev:
        m = (d.year, d.month)
        if contrib and last_month is not None and m != last_month:
            cash += contrib
        last_month = m
        r = t.loc[i]
        if kind == 0 and i in open_:
            n, cost = open_.pop(i)
            if name is None:
                cash += n * r.S0 * (1 + r.fund_ret) - 0.35
            else:
                cash += n * (r[f"{name}|cost"] + r[f"{name}|pnl"]) if r[f"{name}|cost"] > 0 else n * (r[f"{name}|risk"] + r[f"{name}|pnl"])
        elif kind == 1:
            equity = cash + sum(c for _, c in open_.values())
            if name is None:
                n = int((min(equity / 2, cash)) // r.S0)
                cost = n * r.S0 + 0.35 if n else 0
            else:
                unit = r[f"{name}|cost"] if r[f"{name}|cost"] > 0 else r[f"{name}|risk"]
                n = int(min(frac * equity, cash) // unit) if unit > 0 else 0
                cost = n * unit
            if n < 1:
                skipped += 1
                continue
            cash -= cost
            open_[i] = (n, cost)
            taken += 1
        eq_path.append((d, cash + sum(c for _, c in open_.values())))
    eq = pd.Series([e for _, e in eq_path], index=[d for d, _ in eq_path])
    eq = eq[~eq.index.duplicated(keep="last")]
    return eq, taken, skipped


def main():
    data = load()
    feats = daily_features(data)
    rf = data["^IRX"]["close"] / 100
    t = trades_with_options(data, feats, rf)
    print(f"trades 2011-2026 with prices for both the fund and the model: {len(t)}  "
          f"(UPRO {int((t['fund']=='UPRO').sum())}, TQQQ {int((t['fund']=='TQQQ').sum())})")
    print(f"model IV at entry: UPRO {t[t.fund=='UPRO'].iv0.mean():.0%}, TQQQ {t[t.fund=='TQQQ'].iv0.mean():.0%}; "
          f"at exit {t.iv1.mean():.0%} vs entry {t.iv0.mean():.0%}")
    t["era"] = np.where(t["entry"] < "2017-01-01", "2011-16", "2017-26")
    print("\n=== per trade: return on money at risk (premium, or margin for the credit spread) ===")
    print(f"   {'3x fund itself':48s} mean {t.fund_ret.mean():+6.1%} median {t.fund_ret.median():+6.1%} win {(t.fund_ret>0).mean():.0%} "
          f"worst {t.fund_ret.min():+5.0%} | 2011-16 {t[t.era=='2011-16'].fund_ret.mean():+.1%} 2017-26 {t[t.era=='2017-26'].fund_ret.mean():+.1%}")
    for name in STRUCTS:
        ror = t[f"{name}|pnl"] / t[f"{name}|risk"]
        cost = t[f"{name}|cost"].abs() if name.startswith("put") else t[f"{name}|cost"]
        print(f"   {name:48s} mean {ror.mean():+6.1%} median {ror.median():+6.1%} win {(ror>0).mean():.0%} worst {ror.min():+5.0%} "
              f"| 2011-16 {ror[t.era=='2011-16'].mean():+.1%} 2017-26 {ror[t.era=='2017-26'].mean():+.1%} "
              f"| per contract: UPRO ${t[t.fund=='UPRO'][f'{name}|risk'].median():,.0f}, TQQQ ${t[t.fund=='TQQQ'][f'{name}|risk'].median():,.0f} at risk")

    print("\n=== accounts, 2011-2026: start balance, $150 a month added, whole contracts / shares ===")
    print("   (money-weighted; 'end' is the final balance; 'deposited' = start + contributions)")
    months = (t["exit"].max().to_period("M") - t["entry"].min().to_period("M")).n
    for start in (1000.0, 5000.0):
        dep = start + 150 * months
        eq, n, sk = account(t, None, start, 0.5, 150)
        dd = (eq / eq.cummax() - 1).min()
        print(f"   ${start:,.0f} start | {'3x fund, half the account per slot':52s} end ${eq.iloc[-1]:>9,.0f} (deposited ${dep:,.0f}) "
              f"trades {n} skipped {sk} worst drop {dd:+.0%}")
        for name in ("long ATM call", "long ITM call (0.90)", "call debit spread 1.00/1.10"):
            for frac in (0.10, 0.25):
                eq, n, sk = account(t, name, start, frac, 150)
                dd = (eq / eq.cummax() - 1).min()
                print(f"   ${start:,.0f} start | {name[:36]:36s} {frac:.0%} per trade end ${eq.iloc[-1]:>9,.0f} "
                      f"trades {n:3d} skipped {sk:3d} worst drop {dd:+.0%}")
    t.to_pickle("research/cache/swing_options_3x_trades.pkl")


if __name__ == "__main__":
    main()
