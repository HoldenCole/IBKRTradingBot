"""Entry 107 — the leads tested on data they were not built from. See PREREGISTRATION_107.md.

    python3 -m research.crypto.independent_tests
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.crypto.data import binance_spot_daily, coinbase_btc_daily
from research.swing.data import ohlc
from research.swing.study_concentrated import lev_ret, snap, trades_from_bars
from research.swing.study_trailing_stop import simulate
from research.trend_cycle.study_signals import states
from src.portfolio import trend_cycle as tc

SWITCH = 0.0025
HALF = pd.Timestamp("2021-01-01")


def perf(eq: pd.Series) -> tuple[float, float]:
    eq = eq.dropna()
    eq = eq / eq.iloc[0]
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return eq.iloc[-1] ** (1 / yrs) - 1, (eq / eq.cummax() - 1).min()


def rule_equity(close: pd.Series, n: int = 10, day: int | None = None) -> tuple[pd.Series, pd.Series, pd.Timestamp]:
    """Equity of the n-sample average rule and of holding, from the first date the rule is defined.
    day=None samples month-end closes; day=10 or 20 samples the last close on or before that day of each month."""
    close = close[~close.index.duplicated()].asfreq("D").ffill().dropna()
    if day is None:
        samp = close.groupby(close.index.to_period("M")).last()
        dates = close.groupby(close.index.to_period("M")).apply(lambda s: s.index[-1])
    else:
        months = pd.period_range(close.index[0].to_period("M"), close.index[-1].to_period("M"), freq="M")
        targets = [pd.Timestamp(m.year, m.month, day) for m in months]
        targets = [t for t in targets if close.index[0] <= t <= close.index[-1]]
        dates = pd.Series(targets)
        samp = pd.Series(close.reindex(targets).values, index=range(len(targets)))
    samp = pd.Series(np.asarray(samp, float), index=pd.DatetimeIndex(np.asarray(dates)))
    on = (samp > samp.rolling(n).mean()).astype(float)
    on[samp.rolling(n).mean().isna()] = np.nan
    first = on.first_valid_index()
    sig = on.copy(); sig.index = sig.index + pd.Timedelta(days=1)
    pos = sig.reindex(close.index, method="ffill")
    r = close.pct_change().fillna(0)
    pos = pos.loc[first + pd.Timedelta(days=1):].fillna(0)
    r = r.loc[pos.index]
    turn = pos.diff().abs().fillna(pos.iloc[0])
    eq = (1 + pos.shift(1).fillna(pos.iloc[0]) * r - turn * SWITCH).cumprod()
    hold = (1 + r).cumprod()
    return eq, hold, first


def part_a():
    print("A1  the 10-month rule on other coins (Binance spot), rule vs holding: CAGR / max drawdown")
    wins = 0
    rows = []
    for c in ["ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "LINK", "AVAX", "LTC"]:
        eq, hold, first = rule_equity(binance_spot_daily(c)["close"])
        (rc, rd), (hc, hd) = perf(eq), perf(hold)
        ok = rc > hc and rd > hd
        wins += ok
        rows.append({"test": "A1", "case": c, "from": first.date(), "rule_CAGR": rc, "rule_maxDD": rd, "hold_CAGR": hc,
                     "hold_maxDD": hd, "beats": ok})
        print(f"    {c:5s} from {first:%Y-%m}: rule {rc:+7.1%} / {rd:+.0%}   hold {hc:+7.1%} / {hd:+.0%}   {'beats' if ok else 'no'}")
    a1 = wins >= 6
    print(f"    {wins} of 9 beat holding on both -> A1 {'PASS' if a1 else 'FAIL'}")

    btc = coinbase_btc_daily()
    print("A2  bitcoin, neighbouring averages (Coinbase, 2016-06 on); each half: rule vs holding")
    a2 = True
    for n in (6, 8, 9, 10, 11, 12):
        eq, hold, _ = rule_equity(btc, n)
        cells, ok_n = [], True
        for lab, (a, b) in (("2016-20", ("2016-06-01", "2020-12-31")), ("2021-26", ("2021-01-01", None))):
            (rc, rd), (hc, hd) = perf(eq.loc[a:b]), perf(hold.loc[a:b])
            ok = rc > hc and rd > hd
            ok_n &= ok
            cells.append(f"{lab} rule {rc:+.0%}/{rd:+.0%} hold {hc:+.0%}/{hd:+.0%}")
            rows.append({"test": "A2", "case": f"{n} months {lab}", "rule_CAGR": rc, "rule_maxDD": rd, "hold_CAGR": hc,
                         "hold_maxDD": hd, "beats": ok})
        if n != 10:
            a2 &= ok_n
        print(f"    {n:2d} months: " + " | ".join(cells) + ("" if n == 10 else f"  {'ok' if ok_n else 'FAILS'}"))
    print(f"    -> A2 {'PASS' if a2 else 'FAIL'} (10 months shown for reference, not part of the test)")

    print("A3  bitcoin, checked on the 10th or the 20th instead of month end (2016-06 on)")
    a3 = True
    for day in (10, 20):
        eq, hold, _ = rule_equity(btc, 10, day)
        (rc, rd), (hc, hd) = perf(eq.loc["2016-06-01":]), perf(hold.loc["2016-06-01":])
        ok = rc > hc and rd > hd
        a3 &= ok
        rows.append({"test": "A3", "case": f"day {day}", "rule_CAGR": rc, "rule_maxDD": rd, "hold_CAGR": hc, "hold_maxDD": hd, "beats": ok})
        print(f"    day {day}: rule {rc:+.0%} / {rd:+.0%}   hold {hc:+.0%} / {hd:+.0%}   {'beats' if ok else 'no'}")
    print(f"    -> A3 {'PASS' if a3 else 'FAIL'}")
    print(f"A: the 10-month rule is {'CONFIRMED' if (a1 and a2 and a3) else 'NOT confirmed'}")
    return rows, a1 and a2 and a3


def part_b():
    print("\nB   the 30% stop monthly bet on indices it never saw (3x, price return): CAGR / max drawdown")
    irx = ohlc("^IRX")["close"] / 100
    rows, wins = [], 0
    for sym, name in (("^NDX", "Nasdaq-100"), ("^RUT", "Russell 2000"), ("^DJI", "Dow"), ("^N225", "Nikkei 225"),
                      ("^GDAXI", "DAX"), ("^FTSE", "FTSE 100")):
        close = ohlc(sym)["close"].dropna()
        close = close[~close.index.duplicated()]
        days = close.index
        r = close.pct_change().fillna(0)
        rf = irx.reindex(days, method="ffill").fillna(0.03)
        r3 = lev_ret(r, rf)
        mb = tc.to_bars(close, "M")
        m = states(mb)
        ent = lambda o, q: (m[o] == q) & (m[o + "_prev"] != q)  # noqa: E731
        w = trades_from_bars(ent("tq", 1), m.index, None, ent("tq", 4) & m["tq_prev"].isin([2, 3]), days)
        a10 = mb > mb.rolling(10).mean()
        me = pd.Series(False, index=days)
        me.loc[snap(a10.index[a10.values], days)] = True
        start = m.index[0]
        eq_s, nstops = simulate(days, r3, w, 0.30, True, me.values)
        eq_n, _ = simulate(days, r3, w, 9.0, False, me.values)
        bh = (1 + r3).cumprod()
        (sc, sd), (nc, nd), (bc, bd) = perf(eq_s.loc[start:]), perf(eq_n.loc[start:]), perf(bh.loc[start:])
        ok = sc > bc and sd > bd and sd > nd
        wins += ok
        rows.append({"test": "B", "case": name, "from": start.date(), "stop_CAGR": sc, "stop_maxDD": sd, "nostop_CAGR": nc,
                     "nostop_maxDD": nd, "bh3x_CAGR": bc, "bh3x_maxDD": bd, "beats": ok, "stops": nstops, "windows": len(w)})
        print(f"    {name:12s} from {start:%Y-%m}: 30% stop {sc:+6.1%} / {sd:+.0%} ({nstops} stops) | no stop {nc:+6.1%} / {nd:+.0%} | "
              f"3x held {bc:+6.1%} / {bd:+.0%}   {'beats' if ok else 'no'}")
    b = wins >= 4
    print(f"    {wins} of 6 pass -> B {'PASS' if b else 'FAIL'}")
    return rows, b


def main():
    ra, a = part_a()
    rb, b = part_b()
    pd.DataFrame(ra + rb).to_csv("research/crypto/independent_tests.csv", index=False, float_format="%.4f")
    print(f"\nC   the half-and-half account (entry 105): {'confirmed with A' if a else 'not confirmed, since A is not'}")


if __name__ == "__main__":
    main()
