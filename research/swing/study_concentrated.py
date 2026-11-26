"""Entry 98 — few, large, all-in bets in a 3x S&P 500 fund. See PREREGISTRATION_98.md.

    python3 -m research.swing.study_concentrated
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from research.swing.data import load, ohlc
from research.swing.lib import daily_features
from research.swing.study_standalone import run
from research.trend_cycle.study_signals import load as qb_load, states
from src.data.yahoo import _ssl_context
from src.portfolio import trend_cycle as tc

LEV, COST, FIN, FEE = 3, 0.0009, 0.01, 0.0095
ERAS = {"1950-1986": ("1950-01-01", "1986-12-31"), "1987-2006": ("1987-01-01", "2006-12-31"),
        "2007-2026": ("2007-01-01", "2026-12-31")}
SW_ERAS = {"1999-2006": ("1999-06-01", "2006-12-31"), "2007-2026": ("2007-01-01", "2026-12-31")}


def series():
    close, _, _ = qb_load()
    close = close[~close.index.duplicated()].sort_index()
    r = close.pct_change()
    dy = pd.Series(np.where(close.index < "1987-01-01", 0.040, 0.032), index=close.index) / 252
    r = r + dy
    spy = ohlc("SPY")["close"].pct_change().dropna()
    common = spy.index.intersection(r.index)
    r.loc[common] = spy.loc[common]
    f = Path("research/cache/fred_TB3MS.csv")
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=TB3MS", timeout=30,
                                    context=_ssl_context()) as resp:
            f.write_bytes(resp.read())
    tb = pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0] / 100
    rf = tb.reindex(close.index, method="ffill")
    irx = ohlc("^IRX")["close"] / 100
    rf.loc[irx.index.intersection(rf.index)] = irx.reindex(rf.index).dropna()
    return close, r.fillna(0), rf.ffill().fillna(0)


def lev_ret(r, rf, lev=LEV):
    return lev * r - (lev - 1) * (rf / 252 + FIN / 252) - (FEE / 252 if lev > 1 else 0)


def snap(dates: pd.Index, days: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Map bar-end labels to the last trading day on or before them."""
    pos = days.searchsorted(pd.DatetimeIndex(dates), side="right") - 1
    return days[np.clip(pos, 0, len(days) - 1)]


def trades_from_bars(sig: pd.Series, bars_idx: pd.DatetimeIndex, hold: int | None, sell: pd.Series | None, days):
    """Sequential non-overlapping trades: enter at a signal bar, exit `hold` bars later or at the first sell bar."""
    out, i, n = [], 0, len(bars_idx)
    s = sig.values; sl = sell.values if sell is not None else None
    while i < n:
        if s[i]:
            j = i + 1
            if hold is not None:
                j = min(i + hold, n - 1)
            else:
                while j < n - 1 and not sl[j]:
                    j += 1
            out.append((bars_idx[i], bars_idx[j]))
            i = j + 1 if hold is None else j
            continue
        i += 1
    ent = snap([a for a, _ in out], days); ex = snap([b for _, b in out], days)
    return [(a, b) for a, b in zip(ent, ex) if b > a]


def held_from_trades(trades, days):
    h = pd.Series(0.0, index=days)
    for a, b in trades:
        h.loc[(days > a) & (days <= b)] = 1.0
    return h


def account(held, r3):
    turn = held.diff().abs().fillna(held.iloc[0])
    return held * r3 - turn * COST


def deep_dip_trades(close):
    mid = close.rolling(20).mean(); lo = mid - 2 * close.rolling(20).std(ddof=0)
    sma5 = close.rolling(5).mean()
    sig = (close / lo - 1) <= -0.01
    out, i, idx, c = [], 0, close.index, close.values
    s, m5 = sig.values, sma5.values
    while i < len(idx) - 1:
        if s[i]:
            j = i + 1
            while j < len(idx) - 1 and not (c[j] > m5[j]) and j - i < 10:
                j += 1
            out.append((idx[i], idx[j])); i = j + 1
            continue
        i += 1
    return out


def stats(a: pd.Series, held: pd.Series, trades, eras) -> dict:
    eq = (1 + a).cumprod()
    yrs = len(a) / 252
    d = {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "maxDD": (eq / eq.cummax() - 1).min(),
         "invested": held.reindex(a.index).mean(), "trades_yr": len(trades) / yrs}
    tr = [eq.loc[b] / eq.loc[eq.index[max(eq.index.searchsorted(a_) - 0, 0)]] - 1 for a_, b in trades
          if a_ in eq.index and b in eq.index]
    if tr:
        d["mean_trade"] = float(np.mean(tr)); d["worst_trade"] = float(np.min(tr)); d["win"] = float(np.mean(np.array(tr) > 0))
    m3 = (eq.shift(-756) / eq).dropna()
    d.update({"3y_p10": m3.quantile(0.10), "3y_median": m3.median(), "3y_p90": m3.quantile(0.90),
              "3y_below_half": (m3 < 0.5).mean()})
    for e, (s, x) in eras.items():
        sub = a.loc[s:x]
        if len(sub) > 252:
            q = (1 + sub).cumprod()
            d[f"{e} CAGR"] = q.iloc[-1] ** (252 / len(sub)) - 1
            d[f"{e} maxDD"] = (q / q.cummax() - 1).min()
    return d


def main():
    close, r, rf = series()
    days = close.index
    r3 = lev_ret(r, rf)
    mb = tc.to_bars(close, "M"); m = states(mb)
    wb = tc.to_bars(close, "W"); w = states(wb)
    ent = lambda df, o, q: (df[o] == q) & (df[o + "_prev"] != q)  # noqa: E731
    m_trend_up = ent(m, "tq", 1)
    m_cycle_up = ent(m, "cq", 2) & m["cq_prev"].isin([1, 4])
    m_sell = ent(m, "tq", 4) & m["tq_prev"].isin([2, 3])
    mc = m[["cq", "tq"]].shift(1).reindex(w.index, method="ffill")
    intact = mc["cq"].isin([2, 3]) & mc["tq"].isin([2, 3])
    w_buy = ent(w, "cq", 1) & w["tq"].eq(4) & (w["tcn"] >= 4) & intact
    designs = {
        "1 M-trend-up, 12 months": trades_from_bars(m_trend_up, m.index, 12, None, days),
        "2 M-trend-up, until sell": trades_from_bars(m_trend_up, m.index, None, m_sell, days),
        "3 M-cycle-confirm, 12 months": trades_from_bars(m_cycle_up, m.index, 12, None, days),
        "4 M-cycle-confirm, until sell": trades_from_bars(m_cycle_up, m.index, None, m_sell, days),
        "5 W-mature-turn, 13 weeks": trades_from_bars(w_buy, w.index, 13, None, days),
        "6 Deep dip (1% below lower band)": deep_dip_trades(close),
    }
    rows, tl = [], []
    bh = pd.Series(1.0, index=days)
    start = m.index[0]
    for lab, held, ret, er in (("3x buy and hold", bh, r3, ERAS), ("1x buy and hold", bh, r, ERAS)):
        a = account(held, ret).loc[start:]
        rows.append({"design": lab, **stats(a, held, [], er)})
    for lab, trades in designs.items():
        held = held_from_trades(trades, days)
        a = account(held, r3).loc[start:]
        rows.append({"design": lab, **stats(a, held, trades, ERAS)})
        for a_, b in trades:
            tl.append({"design": lab, "entry": a_.date(), "exit": b.date(),
                       "fund_return": float((1 + r3.loc[a_:b].iloc[1:]).prod() - 1),
                       "index_return": float(close.loc[b] / close.loc[a_] - 1)})
    # swing plan, one and two slots (1999 on)
    data = load(); feats = daily_features(data)
    for slots_n in (1, 2):
        out, tr = run(data, feats, "UNION", ["SPY", "QQQ"], slots_n, "aligned+nofragile", cost_bps=COST * 1e4 / LEV)
        f = rf.reindex(out.index).ffill().fillna(0) / 252
        a = (LEV * out["pos"] - out["expo"] * ((LEV - 1) * (f + FIN / 252) + FEE / 252)).loc["1999-06-01":]
        trs = [(pd.Timestamp(x.entry), pd.Timestamp(x.exit)) for x in tr.itertuples()]
        rows.append({"design": f"{6 + slots_n} Swing plan, {'one slot (all in)' if slots_n == 1 else 'two slots (live)'}",
                     **stats(a, out["expo"], trs, SW_ERAS)})
    for lab, held, ret in (("3x buy and hold, 1999 on", bh, r3),):
        a = account(held, ret).loc["1999-06-01":]
        rows.append({"design": lab, **stats(a, held, [], SW_ERAS)})
    df = pd.DataFrame(rows)
    df.to_csv("research/swing/concentrated_results.csv", index=False, float_format="%.4f")
    pd.DataFrame(tl).to_csv("research/swing/concentrated_trades.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
    print(df.round(3).to_string(index=False))
    t = pd.DataFrame(tl)
    for lab in designs:
        x = t[t.design == lab]
        print(f"\n{lab}: {len(x)} trades; fund return per trade: mean {x.fund_return.mean():+.1%}, "
              f"median {x.fund_return.median():+.1%}, worst {x.fund_return.min():+.1%}, best {x.fund_return.max():+.1%}, "
              f"win {(x.fund_return > 0).mean():.0%}")
        if len(x) <= 30:
            print("   " + "; ".join(f"{e.entry} {e.fund_return:+.0%}" for e in x.itertuples()))


if __name__ == "__main__":
    main()


def combo():
    """Post-hoc lead (not a pre-registered design): the swing plan as usual, but all in at 3x for 12 months
    whenever the monthly trend turns up below zero (design 1 overrides the swing plan)."""
    close, r, rf = series()
    days = close.index
    r3 = lev_ret(r, rf)
    mb = tc.to_bars(close, "M"); m = states(mb)
    sig = (m["tq"] == 1) & (m["tq_prev"] != 1)
    held = held_from_trades(trades_from_bars(sig, m.index, 12, None, days), days)
    big = account(held, r3)
    data = load(); feats = daily_features(data)
    out, _ = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=COST * 1e4 / LEV)
    f = rf.reindex(out.index).ffill().fillna(0) / 252
    sw = LEV * out["pos"] - out["expo"] * ((LEV - 1) * (f + FIN / 252) + FEE / 252)
    idx = sw.loc["1999-06-01":].index.intersection(r3.index)
    h = held.reindex(idx).fillna(0)
    a = (h * big.reindex(idx).fillna(0) + (1 - h) * sw.reindex(idx).fillna(0))
    for lab, x in (("swing plan alone", sw.loc[idx]), ("swing plan + all in at 3x on monthly bottoms", a),
                   ("3x buy and hold", r3.loc[idx])):
        eq = (1 + x).cumprod()
        yr = (1 + x).groupby(x.index.year).prod() - 1
        print(f"{lab:46s} CAGR {eq.iloc[-1] ** (252 / len(x)) - 1:+.1%}  max drawdown {(eq / eq.cummax() - 1).min():+.0%}  "
              f"$1,000 -> ${1000 * eq.iloc[-1]:,.0f}  best year {yr.max():+.0%}  worst year {yr.min():+.0%}")
