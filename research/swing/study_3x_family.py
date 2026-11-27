"""Entry 117 — the whole 3x family: mean reversion (M), trend (T) and trend through LEAPS (L).
See PREREGISTRATION_117.md.

    python3 -m research.swing.study_3x_family
"""
from __future__ import annotations

import sys
from math import log
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.data import CACHE, load  # noqa: E402
from research.swing.lib import bollinger, daily_features, perf, rsi, sma  # noqa: E402
from research.swing.study_options import bs, iv_at  # noqa: E402

ALL = """SPXL SPXS UPRO SPXU TQQQ SQQQ UDOW SDOW URTY SRTY TNA TZA UMDD SMDD MIDU
TECL TECS SOXL SOXS FAS FAZ ERX ERY LABU LABD NUGT DUST JNUG JDST GUSH DRIP DRN DRV CURE NAIL DPST RETL WANT DUSL UTSL
TPOR PILL DFEN WEBL WEBS HIBL HIBS EDC EDZ YINN YANG KORU MEXX EURL TMF TMV TYD TYO TTT
FNGU FNGD BULZ BERZ NRGU NRGD GDXU GDXD BNKU BNKD OILU OILD CARU WTIU WTID SHNY DULL""".split()
DUPES = {"SPXL", "TNA", "MIDU", "TTT"}
BROAD_BEAR = {"SPXS", "SPXU", "SQQQ", "SDOW", "SRTY", "TZA", "SMDD"}
BEAR = BROAD_BEAR | {"TECS", "SOXS", "FAZ", "ERY", "LABD", "DUST", "JDST", "DRIP", "DRV", "WEBS", "HIBS", "EDZ", "YANG",
                     "TMV", "TYO", "TTT", "FNGD", "BERZ", "NRGD", "GDXD", "BNKD", "OILD", "WTID", "DULL"}
SIDE = 0.0009
H1, H2 = ("2010-01-01", "2017-12-31"), ("2018-01-01", "2026-12-31")


def read(s):
    return pd.read_csv(CACHE / f"lev3_{s}.csv", index_col=0, parse_dates=True)


def month_signal(c):
    """Series over days: True if the prior month-end close is above the average of the last 10 month-end closes."""
    m = c.resample("ME").last()
    on = (m > m.rolling(10).mean()).shift(1)
    on.index = on.index.to_period("M")
    return pd.Series(c.index.to_period("M").map(on.to_dict()), index=c.index).fillna(False).astype(bool)


def m_sleeve(c):
    _, _, lo, _, _ = bollinger(c, 20, 2.0)
    e = ((rsi(c, 2) < 10) & ((c < lo) | (c > sma(c, 200)))).values
    x = (c > sma(c, 5)).values
    r = c.pct_change().fillna(0.0).values
    d = np.zeros(len(c)); trades = []; i0 = None
    for i in range(len(c)):
        if i0 is not None:
            d[i] += r[i]
            if x[i] or i - i0 >= 10:
                d[i] -= SIDE
                trades.append((c.index[i0], np.prod(1 + r[i0 + 1:i + 1]) - 1 - 2 * SIDE)); i0 = None
        if i0 is None and e[i]:
            i0 = i; d[i] -= SIDE
    return pd.Series(d, index=c.index), pd.DataFrame(trades, columns=["entry", "ret"])


def t_sleeve(c):
    on = month_signal(c)
    r = c.pct_change().fillna(0.0)
    sw = on.astype(int).diff().abs().fillna(0.0)
    return r.where(on, 0.0) - sw * SIDE


def l_sleeve(c, raw, share, rf, iv_win=60, hs_pct=0.03):
    """Month-end LEAPS: 12-month ATM calls with `share` of equity while T is on; sell when off or after 6 months."""
    lr = np.log(c).diff()
    iv = (lr.rolling(iv_win).std() * np.sqrt(252) * 1.1).values
    # Yahoo closes are split-adjusted, so the pre-registered $0.05 / $0.65 floors cannot be applied in real dollars
    # (they would bind on tiny split-adjusted early prices). At these funds' real prices the 3% term dominates, so
    # the spread is 3% of the option price each side (bug fix, entry 117 write-up).
    mm = c.groupby(c.index.to_period("M")).last()
    sig_now = (mm > mm.rolling(10).mean()).to_dict()       # known at that month's last close
    month_end = set(c.groupby(c.index.to_period("M")).tail(1).index)
    rr = rf.reindex(c.index).ffill().fillna(0.0).values * 252
    S = c.values; idx = c.index
    eq = np.ones(len(c)); cash = 1.0; n = 0.0; K = np.nan; exp_i = None; bought = None
    for i in range(len(c)):
        val = 0.0
        if n:
            days = max((exp_i - idx[i]).days, 0)
            val = n * bs(S[i], K, days / 365, max(iv_at(iv[i], S[i], K), 0.05) if np.isfinite(iv[i]) else 0.5, rr[i], True)
        if idx[i] in month_end and np.isfinite(iv[i]):
            on = bool(sig_now.get(idx[i].to_period("M"), False))
            if n and (not on or (idx[i] - bought).days >= 180):
                px = val / n
                hs = hs_pct * px
                cash += n * max(px - hs, 0.0); n = 0.0; val = 0.0
            if on and not n:
                total = cash
                K = S[i]; exp_i = idx[i] + pd.Timedelta(days=365); bought = idx[i]
                px = bs(S[i], K, 1.0, max(iv[i], 0.05), rr[i], True)
                ask = px * (1 + hs_pct)
                n = share * total / ask; cash -= n * ask
                val = n * px
        eq[i] = cash + val
    e = pd.Series(eq, index=idx)
    return e.pct_change().fillna(0.0)


def portfolio(sleeves: dict, elig: dict):
    """Equal weight across eligible sleeves, reset at each month start, drifting within the month."""
    df = pd.DataFrame(sleeves).sort_index()
    df = df[df.index >= "2010-01-01"]
    out = []
    for per, g in df.groupby(df.index.to_period("M")):
        cols = [s for s in g.columns if elig[s] <= g.index[0] and g[s].notna().all()]
        if not cols:
            out.append(pd.Series(0.0, index=g.index)); continue
        path = (1 + g[cols]).cumprod().mean(axis=1)
        out.append(path.pct_change().fillna(path.iloc[0] - 1))
    return pd.concat(out)


def ctstat(r, g):
    m = r.mean(); s = (r - m).groupby(g).sum(); G = len(s)
    return m / (np.sqrt((s ** 2).sum() * G / max(G - 1, 1)) / len(r))


def halves(a):
    return [perf(a.loc[x:y]) for x, y in (H1, H2)]


def main():
    data = load()
    rf = (data["^IRX"]["close"] / 100 / 252)
    pd.set_option("display.width", 220)
    funds = {}
    print("=== Universe ===")
    skipped = []
    for s in ALL:
        try:
            d = read(s)
        except FileNotFoundError:
            skipped.append((s, "no data")); continue
        last = d[d.index >= "2026-05-27"]
        dv = float((last.raw_close * last.volume).median() / 1e6) if len(last) else 0.0
        yrs = (d.index[-1] - d.index[0]).days / 365.25
        if s in DUPES:
            skipped.append((s, "duplicate")); continue
        if s in BROAD_BEAR:
            skipped.append((s, "broad US bear (rule)")); continue
        if yrs < 3 or dv < 1:
            skipped.append((s, f"{yrs:.1f} yrs, ${dv:.1f}M")); continue
        funds[s] = d
    bulls = [s for s in funds if s not in BEAR]; bears = [s for s in funds if s in BEAR]
    print(f"usable: {len(funds)} ({len(bulls)} bull, {len(bears)} bear)")
    print("bull:", " ".join(bulls)); print("bear:", " ".join(bears))
    print("not used:", "; ".join(f"{s} ({w})" for s, w in skipped))

    M, T, L25, L50, L50y, BH, trades, vol, elig = {}, {}, {}, {}, {}, {}, [], {}, {}
    for s, d in funds.items():
        c = d["close"].dropna(); raw = d["raw_close"].reindex(c.index)
        elig[s] = c.index[min(252, len(c) - 1)]
        M[s], tr = m_sleeve(c); tr["fund"] = s; trades.append(tr)
        T[s] = t_sleeve(c); BH[s] = c.pct_change().fillna(0.0)
        vol[s] = float(np.log(c).diff().std() * np.sqrt(252))
        if s not in BEAR:
            L25[s] = l_sleeve(c, raw, 0.25, rf); L50[s] = l_sleeve(c, raw, 0.50, rf)
            L50y[s] = l_sleeve(c, raw, 0.50, rf, iv_win=252)
    trades = pd.concat(trades, ignore_index=True)
    trades = trades[trades.entry >= trades.fund.map(elig)]

    print("\n=== Test 1. Mean reversion (M), all trades pooled, per trade net of 9 bp a side ===")
    t1 = {}
    for lab, grp in (("bull", bulls), ("bear", bears)):
        t = trades[trades.fund.isin(grp)]
        a, b = t[t.entry <= H1[1]].ret, t[t.entry >= H2[0]].ret
        ts = ctstat(t.ret, t.entry)
        ok = t.ret.mean() > 0 and ts >= 3 and a.mean() > 0 and b.mean() > 0
        t1[lab] = ok
        print(f"{lab}: {len(t)} trades in {t.fund.nunique()} funds, mean {t.ret.mean():+.2%}, win {(t.ret > 0).mean():.0%}, "
              f"t {ts:.2f} | 2010-17 {a.mean():+.2%} ({len(a)}) | 2018-26 {b.mean():+.2%} ({len(b)}) | passes: {ok}")
    per = trades.groupby("fund").ret.agg(["size", "mean"]).join(pd.Series(vol, name="vol"))
    per["t"] = trades.groupby("fund").ret.apply(lambda x: x.mean() / (x.std() / np.sqrt(len(x))) if len(x) > 2 else np.nan)
    per["side"] = ["bear" if s in BEAR else "bull" for s in per.index]
    print("\nper fund (sorted by volatility):")
    print(per.sort_values("vol", ascending=False).assign(mean=lambda x: x["mean"] * 100, vol=lambda x: x.vol * 100).round(2).to_string())

    print("\n=== Test 2. Is mean reversion better on the most volatile funds? (bull funds) ===")
    vb = pd.Series({s: vol[s] for s in bulls})
    terc = pd.qcut(vb, 3, labels=["low", "mid", "high"])
    tb = trades[trades.fund.isin(bulls)].copy(); tb["vol third"] = tb.fund.map(terc)
    rows = []
    for th in ("low", "mid", "high"):
        x = tb[tb["vol third"] == th]
        rows.append({"third": th, "funds": int((terc == th).sum()), "vol range %": f"{vb[terc == th].min() * 100:.0f}-{vb[terc == th].max() * 100:.0f}",
                     "trades": len(x), "mean %": x.ret.mean() * 100, "t": ctstat(x.ret, x.entry),
                     "2010-17 %": x[x.entry <= H1[1]].ret.mean() * 100, "2018-26 %": x[x.entry >= H2[0]].ret.mean() * 100})
    t2 = pd.DataFrame(rows); print(t2.round(2).to_string(index=False))
    hi, lo = t2.iloc[2], t2.iloc[0]
    print(f"supported: {bool(hi['2010-17 %'] > lo['2010-17 %'] and hi['2018-26 %'] > lo['2018-26 %'])}")

    print("\n=== Tests 3-5. Equal-weight portfolios of every usable bull fund, 2010-2026 ===")
    sub = lambda dct: {s: dct[s] for s in bulls}
    ports = {"buy and hold": portfolio(sub(BH), elig), "T trend (10-month)": portfolio(sub(T), elig),
             "L LEAPS 25%": portfolio(L25, elig), "L LEAPS 50%": portfolio(L50, elig),
             "M mean reversion": portfolio(sub(M), elig),
             "L 50%, 1-year vol (check)": portfolio(L50y, elig)}
    res = {}
    for k, a in ports.items():
        p = perf(a); h = halves(a); res[k] = (p, h)
        yr = (1 + a).groupby(a.index.year).prod() - 1
        print(f"{k:22s} CAGR {p['CAGR']:+6.1%} maxDD {p['maxDD']:+5.0%} | 2010-17 {h[0]['CAGR']:+6.1%} {h[0]['maxDD']:+5.0%}"
              f" | 2018-26 {h[1]['CAGR']:+6.1%} {h[1]['maxDD']:+5.0%} | worst year {yr.min():+5.0%}")
    bh, tt = res["buy and hold"][1], res["T trend (10-month)"][1]
    t3 = all(tt[i]["CAGR"] > bh[i]["CAGR"] and tt[i]["maxDD"] > bh[i]["maxDD"] for i in (0, 1))
    print(f"\ntest 3, T beats buy-and-hold on CAGR and drawdown in both halves: {t3}")
    for k in ("L LEAPS 25%", "L LEAPS 50%"):
        lh = res[k][1]
        print(f"test 4, {k} beats T on CAGR in both halves: {all(lh[i]['CAGR'] > tt[i]['CAGR'] for i in (0, 1))}")
    # per-fund T vs buy-and-hold
    pf = []
    for s in bulls:
        a, b = T[s].loc[elig[s]:], BH[s].loc[elig[s]:]
        pt, pb = perf(a), perf(b)
        if pt and pb:
            pf.append({"fund": s, "since": elig[s].year, "B&H CAGR": pb["CAGR"] * 100, "B&H maxDD": pb["maxDD"] * 100,
                       "T CAGR": pt["CAGR"] * 100, "T maxDD": pt["maxDD"] * 100,
                       "L50 CAGR": perf(L50[s].loc[elig[s]:])["CAGR"] * 100,
                       "L50 maxDD": perf(L50[s].loc[elig[s]:])["maxDD"] * 100, "M CAGR": perf(M[s].loc[elig[s]:])["CAGR"] * 100})
    pf = pd.DataFrame(pf).sort_values("T CAGR", ascending=False)
    print("\nper bull fund, from one year after its start:")
    print(pf.round(1).to_string(index=False))
    print(f"\nfunds where T beat buy-and-hold on CAGR: {(pf['T CAGR'] > pf['B&H CAGR']).sum()} of {len(pf)}; "
          f"on drawdown: {(pf['T maxDD'] > pf['B&H maxDD']).sum()} of {len(pf)}; T CAGR > 0: {(pf['T CAGR'] > 0).sum()}")

    # check added after the results and the live-quote calibration (leaps_calibration.py): only the funds with
    # listed 1-year options, at the measured median half-spread of 6.5%
    have = ["UPRO", "TQQQ", "TECL", "SOXL", "FAS", "LABU", "NUGT", "JNUG", "GUSH", "NAIL", "DPST", "YINN", "KORU", "TMF"]
    print("\ncheck: funds with listed LEAPS only (14), LEAPS at a 6.5% half-spread:")
    chk = {"buy and hold": portfolio({s: BH[s] for s in have}, elig), "T trend": portfolio({s: T[s] for s in have}, elig)}
    for sh in (0.25, 0.50):
        chk[f"L {int(sh * 100)}%, 6.5% spread"] = portfolio({s: l_sleeve(funds[s]["close"].dropna(), None, sh, rf, hs_pct=0.065)
                                                            for s in have}, elig)
        chk[f"L {int(sh * 100)}%, 6.5% spread, 1-year vol"] = portfolio(
            {s: l_sleeve(funds[s]["close"].dropna(), None, sh, rf, iv_win=252, hs_pct=0.065) for s in have}, elig)
    for k, a in chk.items():
        p = perf(a); h = halves(a)
        print(f"   {k:32s} CAGR {p['CAGR']:+6.1%} maxDD {p['maxDD']:+5.0%} | 2010-17 {h[0]['CAGR']:+6.1%} {h[0]['maxDD']:+5.0%}"
              f" | 2018-26 {h[1]['CAGR']:+6.1%} {h[1]['maxDD']:+5.0%}")

    # live plan reference through actual UPRO/TQQQ
    from research.swing.study_dissect import account, engine
    for s in ("UPRO", "TQQQ"):
        data[s] = read(s)
    feats = daily_features(data)
    res_lp = engine(data, feats, ret_from={"SPY": "UPRO", "QQQ": "TQQQ"}, start="2010-06-01")
    a = account(res_lp, rf.reindex(feats.index).ffill().fillna(0.0), lev_override=1)
    p, h = perf(a), halves(a)
    print(f"\nreference, live plan via actual UPRO/TQQQ: CAGR {p['CAGR']:+.1%} maxDD {p['maxDD']:+.0%} | 2010-17 "
          f"{h[0]['CAGR']:+.1%} {h[0]['maxDD']:+.0%} | 2018-26 {h[1]['CAGR']:+.1%} {h[1]['maxDD']:+.0%}")
    per.to_csv(ROOT / "research" / "swing" / "family_3x_per_fund_M.csv", float_format="%.4f")
    pf.to_csv(ROOT / "research" / "swing" / "family_3x_per_fund.csv", index=False, float_format="%.2f")


if __name__ == "__main__":
    main()
