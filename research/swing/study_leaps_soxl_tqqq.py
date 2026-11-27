"""Entry 118 — trend-following LEAPS on SOXL and TQQQ only. See PREREGISTRATION_118.md.

    python3 -m research.swing.study_leaps_soxl_tqqq
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.data import load  # noqa: E402
from research.swing.lib import daily_features, perf  # noqa: E402
from research.swing.study_3x_family import l_sleeve, month_signal, portfolio, read, t_sleeve  # noqa: E402
from research.swing.study_options import bs, iv_at  # noqa: E402
from src.data.yahoo import _get_json  # noqa: E402

FUNDS = ("TQQQ", "SOXL")
HS = 0.065
H = {"2011-17": ("2011-01-01", "2017-12-31"), "2018-26": ("2018-01-01", "2026-12-31")}


def splits(sym):
    j = _get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=1262304000&period2=1800000000"
                  f"&interval=1mo&events=split")
    ev = j["chart"]["result"][0].get("events", {}).get("splits", {})
    out = []
    for v in ev.values():
        a, b = v["splitRatio"].split(":")
        out.append((pd.Timestamp(v["date"], unit="s").normalize(), float(a) / float(b)))
    return sorted(out)


def real_price(d, sym):
    """Unsplit traded price: Yahoo's split-adjusted close times every later split ratio."""
    f = pd.Series(1.0, index=d.index)
    for t, r in splits(sym):
        f[f.index < t] *= r
    return d["raw_close"] * f


def row(lab, a):
    p = perf(a); hs = {k: perf(a.loc[x:y]) for k, (x, y) in H.items()}
    yr = (1 + a).groupby(a.index.year).prod() - 1
    print(f"{lab:44s} CAGR {p['CAGR']:+6.1%} maxDD {p['maxDD']:+5.0%} | " +
          " | ".join(f"{k} {v['CAGR']:+6.1%} {v['maxDD']:+5.0%}" for k, v in hs.items()) +
          f" | worst yr {yr.min():+5.0%} best yr {yr.max():+6.0%}")
    return yr


def live_chain():
    import http.cookiejar
    import urllib.request
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]
    try:
        op.open("https://fc.yahoo.com", timeout=20)
    except Exception:
        pass
    for k in range(6):
        try:
            crumb = op.open("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=20).read().decode()
            return op, crumb
        except Exception:
            time.sleep(30 * (k + 1))
    raise RuntimeError("Yahoo crumb unavailable")


def main():
    data = load()
    rf = data["^IRX"]["close"] / 100 / 252
    pd.set_option("display.width", 220)
    f = {s: read(s) for s in FUNDS}
    c = {s: f[s]["close"].dropna() for s in FUNDS}
    elig = {s: c[s].index[252] for s in FUNDS}
    print(f"sleeves eligible from: {', '.join(f'{s} {elig[s].date()}' for s in FUNDS)}\n")

    print("=== Two-fund portfolio (equal weight, monthly reset), 2011-2026 ===")
    bh = portfolio({s: c[s].pct_change().fillna(0.0) for s in FUNDS}, elig)
    tt = portfolio({s: t_sleeve(c[s]) for s in FUNDS}, elig)
    yrs = {"buy and hold": row("buy and hold", bh), "T trend in the funds": row("T trend held in the funds", tt)}
    from research.swing.study_dissect import account, engine
    data["UPRO"], data["TQQQ"] = read("UPRO"), read("TQQQ")
    feats = daily_features(data)
    lp = account(engine(data, feats, ret_from={"SPY": "UPRO", "QQQ": "TQQQ"}, start="2011-03-01"),
                 rf.reindex(feats.index).ffill().fillna(0.0), lev_override=1)
    yrs["live swing plan"] = row("live swing plan (real UPRO/TQQQ)", lp)
    print()
    logs = {}
    print("pre-registered model (entry 77 skew) first, then the corrected flat-vol model\n")
    for skew in (True, False):
      print(f"--- {'skew as pre-registered (overstated; see check 1)' if skew else 'CORRECTED: flat implied vol across strikes'} ---")
      for iv_win in (60, 252):
        for otm in (0.0, 0.2):
            for share in (0.25, 0.5, 1.0):
                lg = {s: [] for s in FUNDS}
                a = portfolio({s: l_sleeve(c[s], None, share, rf, iv_win=iv_win, hs_pct=HS, otm=otm, log=lg[s], skew=skew)
                               for s in FUNDS}, elig)
                lab = (f"LEAPS {int(share * 100):3d}%, {'ATM' if otm == 0 else '20% OTM'}, {'60-day' if iv_win == 60 else '1-year'} vol"
                       + ("" if skew else ", flat"))
                y = row(lab, a)
                if share == 0.5 and iv_win == 252 and not skew:
                    yrs[lab] = y; logs[lab] = lg
        print()
    print("=== Year by year (%) ===")
    print((pd.DataFrame(yrs) * 100).round(0).to_string())

    print("\n=== Each LEAPS purchase, 50% ATM, 1-year vol, flat ===")
    for s in FUNDS:
        t = pd.DataFrame(logs["LEAPS  50%, ATM, 1-year vol, flat"][s])
        print(f"{s}: {len(t)} purchases, won {(t.ret > 0).mean():.0%}, mean {t.ret.mean():+.0%}, median {t.ret.median():+.0%}, "
              f"best {t.ret.max():+.0%}, worst {t.ret.min():+.0%}; months in calls "
              f"{sum((t.sold - t.bought).dt.days) / 30.4:.0f} of {(c[s].index[-1] - elig[s]).days / 30.4:.0f}")
        top = t.sort_values("ret", ascending=False).head(3)
        print("   biggest:", "; ".join(f"{r.bought.date()} to {r.sold.date()} {r.ret:+.0%}" for r in top.itertuples()))

    print("\n=== Check 1. Today's quotes vs the model (12-month calls) ===")
    op, crumb = live_chain()
    for s in FUNDS:
        base = f"https://query2.finance.yahoo.com/v7/finance/options/{s}?crumb={crumb}"
        r = json.load(op.open(base, timeout=20))["optionChain"]["result"][0]
        S = r["quote"]["regularMarketPrice"]; now = time.time()
        e = min([x for x in r["expirationDates"] if (x - now) / 86400 >= 270], key=lambda x: abs((x - now) / 86400 - 365))
        T = (e - now) / 86400 / 365
        time.sleep(0.4)
        calls = json.load(op.open(base + f"&date={e}", timeout=20))["optionChain"]["result"][0]["options"][0]["calls"]
        lr = np.log(c[s]).diff()
        atm = {"1-year": lr.tail(252).std() * np.sqrt(252) * 1.1, "60-day": lr.tail(60).std() * np.sqrt(252) * 1.1}
        r0 = float(rf.dropna().iloc[-1] * 252)
        print(f"{s} at ${S:.2f}, expiry in {T * 365:.0f} days; model ATM vol 1-year {atm['1-year']:.0%}, 60-day {atm['60-day']:.0%}")
        for mny in (1.0, 1.1, 1.2, 1.3, 1.5):
            q = min(calls, key=lambda x: abs(x["strike"] - S * mny))
            K = q["strike"]
            m1 = bs(S, K, T, iv_at(atm["1-year"], S, K), r0, True) * (1 + HS)
            m2 = bs(S, K, T, atm["1-year"], r0, True) * (1 + HS)
            print(f"   strike {K:7.2f} ({K / S:4.0%}): bid {q.get('bid', 0):6.2f} ask {q.get('ask', 0):6.2f} market IV "
                  f"{q.get('impliedVolatility', 0):4.0%} | model ask, skew {m1:6.2f}, flat {m2:6.2f} | one contract ${q.get('ask', 0) * 100:,.0f}")
        time.sleep(0.4)

    print("\n=== Check 2. $1,000 + $150 a month, whole contracts, 1-year flat vol, 50% of the account in calls ===")
    px = {s: f[s]["raw_close"].reindex(c[s].index) for s in FUNDS}             # split-adjusted path
    fac = {s: (real_price(f[s], s) / f[s]["raw_close"]).reindex(c[s].index) for s in FUNDS}   # to real dollars
    for otm in (0.0, 0.2):
        cash, held, contrib, blocked, onm, buys = 1000.0, {}, 1000.0, 0, 0, 0
        days = c["TQQQ"].index.union(c["SOXL"].index)
        days = days[days >= max(elig.values())]
        mends = set(pd.Series(days, index=days).groupby(days.to_period("M")).tail(1))
        sig = {s: month_signal(c[s]) for s in FUNDS}
        vol = {s: (np.log(c[s]).diff().rolling(252).std() * np.sqrt(252) * 1.1) for s in FUNDS}
        eq_path = []
        for d in days:
            val = 0.0
            for s, h in held.items():
                S = px[s].get(d, np.nan); left = max((h["exp"] - d).days, 0) / 365
                h["val"] = bs(S, h["K"], left, max(vol[s].get(d, 0.8), 0.05), float(rf.get(d, 0) * 252), True) * 100 * h["f"]
                val += h["n"] * h["val"]
            if d in mends:
                cash += 150; contrib += 150
                nxt = {s: bool(sig[s].loc[d:].iloc[1]) if len(sig[s].loc[d:]) > 1 else bool(sig[s].loc[d]) for s in FUNDS}
                for s in list(held):
                    h = held[s]
                    if not nxt[s] or (d - h["t"]).days >= 180:
                        cash += h["n"] * h["val"] * (1 - HS); val -= h["n"] * h["val"]; del held[s]
                for s in FUNDS:
                    if nxt[s] and s not in held:
                        onm += 1
                        S = px[s][d]; K = S * (1 + otm)
                        cost = bs(S, K, 1.0, max(vol[s][d], 0.05), float(rf.get(d, 0) * 252), True) * 100 * fac[s][d] * (1 + HS)
                        budget = 0.5 * (cash + val) / 2
                        n = int(budget // cost)
                        if n == 0:
                            blocked += 1; continue
                        buys += 1; cash -= n * cost
                        held[s] = {"n": n, "K": K, "exp": d + pd.Timedelta(days=365), "t": d, "val": cost / (1 + HS), "f": fac[s][d]}
                        val += n * held[s]["val"]
            eq_path.append(cash + val)
        eq = pd.Series(eq_path, index=days)
        print(f"   {'ATM' if otm == 0 else '20% OTM'}: trend-on purchase chances {onm}, could not afford one contract {blocked} "
              f"({blocked / max(onm, 1):.0%}), bought {buys}; contributed ${contrib:,.0f}, ended ${eq.iloc[-1]:,.0f}; "
              f"worst fall {float((eq / eq.cummax() - 1).min()):+.0%}")
    print("   same $1,000 + $150 a month (fractional shares) into the comparisons, from the same start:")
    start = max(elig.values())
    for lab, a in (("buy and hold", bh), ("T trend held in the funds", tt), ("live swing plan", lp)):
        a = a.loc[start:]
        me = set(pd.Series(a.index, index=a.index).groupby(a.index.to_period("M")).tail(1))
        e, path = 1000.0, []
        for d, r in a.items():
            e *= 1 + r
            if d in me:
                e += 150
            path.append(e)
        pth = pd.Series(path, index=a.index)
        print(f"      {lab:28s} ended ${e:,.0f}; worst fall {float((pth / pth.cummax() - 1).min()):+.0%}")


if __name__ == "__main__":
    main()
