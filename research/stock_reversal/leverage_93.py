"""Entry 94: the entry-93 no-filing gap-up short (3% target, 6% or 10% stop) run as an account with leverage.

User: 70% win is good; lever it up. Account: at most 2 positions at once, each sized
leverage x equity / 2 at entry; a signal is skipped when both slots are full; P&L booked
at exit; equity floored at zero (ruin). Development sample 2005-2023 only.

    python3 -m research.stock_reversal.leverage_93
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import ohlc
from research.stock_reversal.events import DEV_END


def account(x: pd.DataFrame, lev: float, slots: int = 2):
    x = x.sort_values(["date", "ticker"])
    ev = sorted([(r.entry_d, 1, i) for i, r in x.iterrows()] + [(r.exit_d, 0, i) for i, r in x.iterrows()],
                key=lambda e: (e[0], -e[1]))  # same day: enter first (intraday exits close the same day)
    eq, open_, path, taken = 1.0, {}, [], []
    for d, kind, i in ev:
        if kind == 1:
            if len(open_) >= slots or eq <= 0:
                continue
            open_[i] = lev * eq / slots
        elif i in open_:
            pnl = open_.pop(i) * x.at[i, "net"]
            eq = max(eq + pnl, 0.0)
            taken.append((d, x.at[i, "net"] * lev / slots / 1.0, eq))
            path.append((d, eq))
    s = pd.Series([e for _, e in path], index=[d for d, _ in path])
    s = s[~s.index.duplicated(keep="last")]
    return s, len(taken)


def main():
    res = pd.read_parquet("research/cache/stock_reversal_price_exits_dev.parquet")
    sess = ohlc("SPY").index
    sess = sess[sess < DEV_END]
    pos = pd.Series(np.arange(len(sess)), index=sess)
    years = (sess[-1] - pd.Timestamp("2005-01-01")).days / 365.25
    print("no-filing gap-up, short at the open, 2005-2023; account with 2 slots, leverage = total short / equity")
    for S in (0.06, 0.10):
        x = res[(res.bucket == "N") & (res.dir == 1) & (res.entry == "open") & (res["T"] == 0.03) & (res.S == S)].dropna(subset=["net"]).copy()
        x["entry_d"] = x["date"]
        x["exit_d"] = sess[np.minimum(x["date"].map(pos).values + x["held"].values.astype(int) - 1, len(sess) - 1)]
        x = x.reset_index(drop=True)
        wins, losses = x.net[x.net > 0], x.net[x.net <= 0]
        print(f"\n3% target, {S:.0%} stop: {len(x)} trades, win {(x.net>0).mean():.0%}, average win {wins.mean():+.2%}, "
              f"average loss {losses.mean():+.2%}, worst {x.net.min():+.1%}, mean {x.net.mean():+.2%} "
              f"(2005-14 {x[x.date<'2015'].net.mean():+.2%}, 2015-23 {x[x.date>='2015'].net.mean():+.2%})")
        for lev in (1, 2, 3, 4, 6, 8):
            eq, n = account(x, lev)
            dd = (eq / eq.cummax() - 1).min()
            cagr = eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 else -1
            e14 = eq[eq.index < "2015-01-01"].iloc[-1]
            e23 = eq.iloc[-1] / e14 if e14 > 0 else 0
            worst = (x.net.min() * lev / 2)
            print(f"   {lev}x: $1,000 -> ${1000*eq.iloc[-1]:>9,.0f}  CAGR {cagr:+6.1%}  max drawdown {dd:+5.0%}  "
                  f"2005-14 x{e14:.2f}  2015-23 x{e23:.2f}  worst single trade {worst:+.0%} of equity  trades {n}")


if __name__ == "__main__":
    main()
