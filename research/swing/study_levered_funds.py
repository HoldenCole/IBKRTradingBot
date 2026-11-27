"""Entry 116 — the swing rules through real 3x sector funds, and a mirror short through inverse 3x funds.
See PREREGISTRATION_116.md.

    python3 -m research.swing.study_levered_funds
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.data import CACHE, load  # noqa: E402
from research.swing.lib import bollinger, daily_features, perf, rsi, sma  # noqa: E402
from research.swing.study_dissect import account, engine, entry_rule, exit_rule, line, tstat  # noqa: E402

# fund -> (underlying 1x ETF, +1 bull / -1 bear)
FUNDS = {"SOXL": ("SMH", 1), "SOXS": ("SMH", -1), "TECL": ("XLK", 1), "TECS": ("XLK", -1), "FAS": ("XLF", 1),
         "FAZ": ("XLF", -1), "ERX": ("XLE", 1), "ERY": ("XLE", -1), "EDC": ("EEM", 1), "EDZ": ("EEM", -1),
         "WANT": ("XLY", 1), "DUSL": ("XLI", 1), "CURE": ("XLV", 1), "UTSL": ("XLU", 1), "DRN": ("IYR", 1),
         "DRV": ("IYR", -1), "NAIL": ("XHB", 1), "LABU": ("XBI", 1), "LABD": ("XBI", -1), "DPST": ("KRE", 1),
         "RETL": ("XRT", 1), "NUGT": ("GDX", 1), "DUST": ("GDX", -1), "GUSH": ("XOP", 1), "DRIP": ("XOP", -1),
         "YINN": ("FXI", 1), "YANG": ("FXI", -1)}
REF = {"UPRO": ("SPY", 1), "TQQQ": ("QQQ", 1)}
SIDE = 0.0009


def read(s):
    return pd.read_csv(CACHE / f"ohlc_{s}.csv", index_col=0, parse_dates=True)


def trend_on(close, up=True):
    m = close.resample("ME").last()
    g = (m > m.rolling(10).mean()) if up else (m < m.rolling(10).mean())
    g = g.shift(1)
    g.index = g.index.to_period("M")
    return pd.Series(close.index.to_period("M").map(g.to_dict()), index=close.index).fillna(False).astype(bool)


def short_trades(close, gate, cost=0.0005, inv=None, inv_cost=SIDE):
    """Mirror rule: RSI(2) > 90 and (above upper band or below 200-day); cover below the 5-day average or after 10 days."""
    c = close.dropna()
    _, up, _, _, _ = bollinger(c, 20, 2.0)
    e = (rsi(c, 2) > 90) & ((c > up) | (c < sma(c, 200)))
    x = c < sma(c, 5)
    if gate:
        e = e & trend_on(c, up=False)
    c2 = c[c.index >= "1999-01-01"]
    e, x = e.reindex(c2.index).fillna(False).values, x.reindex(c2.index).fillna(False).values
    r = c2.pct_change().fillna(0.0).values
    ri = inv["close"].reindex(c2.index).pct_change().values if inv is not None else None
    out, i0 = [], None
    for i in range(len(c2)):
        if i0 is not None and (x[i] or i - i0 >= 10):
            und = np.prod(1 + r[i0 + 1:i + 1]) - 1
            fund = np.nan
            if ri is not None and c2.index[i0] >= inv.index[0] + pd.Timedelta(days=5):
                fund = np.prod(1 + ri[i0 + 1:i + 1]) - 1 - 2 * inv_cost
            out.append((c2.index[i0], -und - 2 * cost, fund)); i0 = None
        if i0 is None and e[i]:
            i0 = i
    return pd.DataFrame(out, columns=["entry", "ret", "fund"])


def main():
    data = load()
    for s in list(FUNDS) + list(REF) + ["XBI", "XOP", "FXI", "GDX", "KRE", "XRT", "XHB", "IYR", "XLV", "XLU"]:
        data[s] = read(s)
    feats = daily_features(data)
    rf = (data["^IRX"]["close"] / 100 / 252).reindex(feats.index).ffill().fillna(0.0)
    pd.set_option("display.width", 220)

    print("=== Part A. Inventory ===")
    rows, usable = [], {}
    for f, (u, sign) in {**REF, **FUNDS}.items():
        d = data[f]
        last = d[d.index >= "2026-05-27"]
        dv = float((last.raw_close * last.volume).median() / 1e6)
        yrs = (d.index[-1] - d.index[0]).days / 365.25
        fr = d["close"].pct_change()
        ur = data[u]["close"].pct_change().reindex(fr.index)
        both = pd.concat([fr, ur], axis=1).dropna()
        gap = (both.iloc[:, 0] - 3 * sign * both.iloc[:, 1]).mean() * 252
        corr = both.iloc[:, 0].corr(both.iloc[:, 1]) * sign
        ok = yrs >= 5 and dv >= 5
        usable[f] = ok
        rows.append({"fund": f, "underlying": u, "side": "bull" if sign > 0 else "bear", "since": d.index[0].date(),
                     "median $ vol 6m ($M)": round(dv, 1), "years": round(yrs, 1),
                     "gap vs 3x underlying (%/yr)": round(gap * 100, 1), "corr": round(corr, 3), "usable": ok})
    inv = pd.DataFrame(rows)
    print(inv.to_string(index=False))

    print("\n=== Part B1. Long swing rules through each real bull fund (one position, whole account, 9 bp a side) ===")
    b1 = []
    for f, (u, sign) in {**REF, **FUNDS}.items():
        if sign < 0 or not usable[f]:
            continue
        st = str((data[f].index[0] + pd.Timedelta(days=300)).date())     # 200-day average needs history; fund live
        for gate in ("none", "full"):
            res = engine(data, feats, universe=(u,), slots=1, gate=gate, ret_from={u: f}, start=max(st, "1999-06-01"))
            a = account(res, rf, lev_override=1)
            tr = res["trades"]
            p = perf(a)
            fr = [np.prod(1 + np.array(x)) - 1 - 2 * SIDE for x in tr.rets]
            b1.append({"fund": f, "signal on": u, "gate": gate, "from": st[:4], "trades": len(tr),
                       "mean per trade": np.mean(fr) * 100, "win": np.mean(np.array(fr) > 0), "t": tstat(fr),
                       "CAGR": p["CAGR"] * 100, "maxDD": p["maxDD"] * 100,
                       "fund buy-hold CAGR": perf(data[f]["close"].pct_change().loc[st:].dropna())["CAGR"] * 100})
    b1 = pd.DataFrame(b1)
    print(b1.round(2).to_string(index=False))

    print("\n=== Part B2. The live plan with a wider universe (synthetic 3x, eras A/B/C, idle cash 0) ===")
    print("    (XLY dropped: its 3x fund WANT fails the liquidity test in part A; XLP has no 3x fund)")
    base = engine(data, feats)
    eb = line("baseline SPY, QQQ", account(base, rf), base)
    wide = engine(data, feats, universe=("SPY", "QQQ", "SMH", "XLK", "EEM"))
    ew = line("wide SPY, QQQ, SMH, XLK, EEM", account(wide, rf), wide)
    ok = all(ew[k][0] > eb[k][0] and ew[k][1] >= eb[k][1] for k in "ABC")
    print(f"B2 verdict: {'LEAD (passes; paper-log, in-sample universe)' if ok else 'no'}")
    print("\n   same two universes through the ACTUAL funds (UPRO, TQQQ, SOXL, TECL, EDC), 2011-2026, descriptive:")
    m = {"SPY": "UPRO", "QQQ": "TQQQ", "SMH": "SOXL", "XLK": "TECL", "EEM": "EDC"}
    for lab, u in (("baseline, actual funds", ("SPY", "QQQ")), ("wide, actual funds", tuple(m))):
        res = engine(data, feats, universe=u, ret_from=m, start="2011-01-01")
        a = account(res, rf, lev_override=1)
        p = perf(a)
        h1, h2 = perf(a.loc[:"2018-12-31"]), perf(a.loc["2019-01-01":])
        print(f"   {lab:26s} CAGR {p['CAGR']:+6.1%} maxDD {p['maxDD']:+5.0%} | 2011-18 {h1['CAGR']:+6.1%} {h1['maxDD']:+5.0%}"
              f" | 2019-26 {h2['CAGR']:+6.1%} {h2['maxDD']:+5.0%} | {len(res['trades']) / (len(a) / 252):.0f} tr/yr")

    print("\n=== Part C. Mirror short (RSI(2) > 90), underlying at 1x short, 5 bp a side ===")
    c_rows = []
    for f, (u, sign) in FUNDS.items():
        if sign > 0 or not usable[f]:
            continue
        cut = "2013-01-01"
        for ver, g in (("no gate", False), ("own downtrend", True)):
            t = short_trades(data[u]["close"], g, inv=data[f])
            h1, h2 = t[t.entry < cut].ret, t[t.entry >= cut].ret
            ok = t.ret.mean() > 0 and tstat(t.ret) >= 2 and h1.mean() > 0 and h2.mean() > 0
            fd = t.fund.dropna()
            c_rows.append({"bear fund": f, "underlying": u, "version": ver, "trades": len(t),
                           "mean bp": t.ret.mean() * 1e4, "win": (t.ret > 0).mean(), "t": tstat(t.ret),
                           "1st half bp": h1.mean() * 1e4, "2nd half bp": h2.mean() * 1e4, "passes": bool(ok),
                           "via fund: trades": len(fd), "via fund: mean %": fd.mean() * 100 if len(fd) else np.nan})
    c = pd.DataFrame(c_rows)
    print(c.round(2).to_string(index=False))
    print(f"\npassers: {sorted(set(c[c.passes]['bear fund']))}")
    inv.to_csv(ROOT / "research" / "swing" / "levered_funds_inventory.csv", index=False)
    b1.to_csv(ROOT / "research" / "swing" / "levered_funds_long.csv", index=False, float_format="%.4f")
    c.to_csv(ROOT / "research" / "swing" / "levered_funds_short.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
