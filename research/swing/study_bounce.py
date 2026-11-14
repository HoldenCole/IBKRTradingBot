"""Entry 80 — the band bounce: buy the touch of the lower Bollinger band, sell
at the upper band ("the top"), tight stop, short holding period.

Bar sizes: 5m and 15m (Yahoo allows ~60 days), 60m (~2 years), daily (27
years), and 3-day bars (the other reading of "3-day view"). One simulator:

  * bands BB(n, 2) are known from bars through t-1
  * LONG entry: bar t trades down to the prior lower band -> filled at
    min(open_t, band). The stop is live from the entry bar on (if the entry
    bar's low is below the stop, the trade is stopped in that bar).
  * exit, in priority: stop (filled at min(open, stop) — gaps hurt), then
    target = prior upper band or mid band (filled at max(open, target)),
    then time stop at the close.
  * cost 3bp/side intraday bars, 5bp/side daily bars.

    python3 -m research.swing.study_bounce
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.swing.data import BROAD, SECTORS, SUBSECTORS, load
from research.swing.intraday_data import SYMS, bars
from research.swing.lib import ERAS, daily_features, era_of, sma, tstats

ALIGNED = {**{s: "GR" for s in BROAD + SECTORS + SUBSECTORS + ["TQQQ"]}, "XLE": "R", "ERX": "R", "GLD": "RD",
           "GDX": "RD", "TLT": "D", "USO": "R"}
EQ_INTRA = ["SPY", "QQQ", "IWM", "XLF", "XLK", "SMH"]


def bounce(df, n=20, k=2.0, target="upper", stop=0.01, max_bars=21, side=1, cost=3 / 1e4, allow=None):
    o, h, l, c = (df[x].values for x in ("open", "high", "low", "close"))
    cs = pd.Series(c)
    mid = cs.rolling(n).mean().values
    sd = cs.rolling(n).std(ddof=0).values
    up, lo = mid + k * sd, mid - k * sd
    ok = np.ones(len(c), bool) if allow is None else np.asarray(allow, bool)
    rows = []; i = n + 1; N = len(c)
    while i < N:
        band = lo[i - 1] if side == 1 else up[i - 1]
        hit = (l[i] <= band) if side == 1 else (h[i] >= band)
        if not (hit and ok[i]) or np.isnan(band):
            i += 1; continue
        epx = min(o[i], band) if side == 1 else max(o[i], band)
        spx = epx * (1 - stop) if (side == 1 and stop) else epx * (1 + stop) if stop else None
        j = i; xpx = None; why = None
        # stop inside the entry bar
        if spx is not None and ((side == 1 and l[i] <= spx) or (side == -1 and h[i] >= spx)):
            xpx, why = spx, "stop"
        while xpx is None:
            j += 1
            if j >= N:
                j = N - 1; xpx, why = c[j], "eod"; break
            tgt = (up[j - 1] if side == 1 else lo[j - 1]) if target == "upper" else mid[j - 1]
            if spx is not None and ((side == 1 and l[j] <= spx) or (side == -1 and h[j] >= spx)):
                xpx = min(o[j], spx) if side == 1 else max(o[j], spx); why = "stop"
            elif (side == 1 and h[j] >= tgt) or (side == -1 and l[j] <= tgt):
                xpx = max(o[j], tgt) if side == 1 else min(o[j], tgt); why = "target"
            elif j - i >= max_bars:
                xpx, why = c[j], "time"
        rows.append((df.index[i], df.index[j], j - i, side * (xpx / epx - 1) - 2 * cost, why))
        i = j + 1
    return pd.DataFrame(rows, columns=["entry", "exit", "bars", "ret", "why"])


def line(t):
    if len(t) == 0:
        return "n=0"
    s = tstats(t["ret"])
    why = t["why"].value_counts(normalize=True)
    return (f"n={s['n']:5d} mean {s['mean_bps']:+6.1f}bp win {s['win']:.0%} t {s['t']:+.2f} sum {t['ret'].sum():+7.1%} "
            f"| target {why.get('target', 0):.0%} stop {why.get('stop', 0):.0%} time {why.get('time', 0):.0%} | hold {t['bars'].mean():.0f} bars")


def daily_masks(data, feats, sym, index_dates):
    """Per-bar permissions from the PRIOR trading day's daily state."""
    base = {"TQQQ": "QQQ", "ERX": "XLE"}.get(sym, sym)
    c = data[base]["close"]
    trend = (c > sma(c, 200)).shift(1)
    quad = feats["quad"]
    d = pd.DatetimeIndex(index_dates)
    tr = trend.reindex(d).ffill().fillna(False).values
    al = np.array([isinstance(q, str) and q in ALIGNED.get(sym, "") for q in quad.reindex(d).ffill().values])
    return tr.astype(bool), al


def intraday(data, feats, interval, bars_per_day):
    print(f"\n########## {interval} bars — Bollinger(20,2) on the {interval} chart; time stop 3 trading days ##########")
    B = {s: bars(s, interval) for s in SYMS}
    span = f"{B['SPY'].index[0].date()} to {B['SPY'].index[-1].date()} ({B['SPY'].index.normalize().nunique()} days)"
    print(f"window: {span}")
    mb = 3 * bars_per_day
    masks = {s: daily_masks(data, feats, s, B[s].index.tz_localize(None).normalize()) for s in SYMS}
    half = B["SPY"].index[len(B["SPY"]) // 2]

    def pooled(syms, side=1, filt=None, **kw):
        out = []
        for s in syms:
            allow = None if filt is None else masks[s][0] if filt == "trend" else masks[s][1]
            if side == -1 and filt == "trend":
                allow = ~masks[s][0]
            t = bounce(B[s], max_bars=mb, side=side, allow=allow, **kw); t["sym"] = s; out.append(t)
        return pd.concat(out, ignore_index=True)

    print(f"\n-- LONG bounce, index + big sector ETFs pooled ({'+'.join(EQ_INTRA)}), 1x, net 3bp/side --")
    for target in ("upper", "mid"):
        for stop in (0.005, 0.01, 0.02, None):
            t = pooled(EQ_INTRA, target=target, stop=stop)
            h1, h2 = t[t["entry"] < half], t[t["entry"] >= half]
            print(f"   target {target:5s} stop {str(stop):5s}: {line(t)} | halves {h1['ret'].mean()*1e4:+.0f}/{h2['ret'].mean()*1e4:+.0f}bp")
    print("\n-- same, only when the ETF's prior daily close is above its 200d SMA --")
    for target, stop in (("upper", 0.01), ("upper", None), ("mid", 0.01), ("mid", None)):
        t = pooled(EQ_INTRA, filt="trend", target=target, stop=stop)
        print(f"   target {target:5s} stop {str(stop):5s}: {line(t)}")
    print("\n-- per symbol, target upper band, 1% stop / no stop (mean bp, n) --")
    for s in SYMS:
        a = bounce(B[s], max_bars=mb, target="upper", stop=0.01); b = bounce(B[s], max_bars=mb, target="upper", stop=None)
        m = bounce(B[s], max_bars=mb, target="mid", stop=None)
        print(f"   {s:5s} upper/1%: {a['ret'].mean()*1e4:+6.1f}bp n={len(a):3d} win {(a['ret']>0).mean():.0%} sum {a['ret'].sum():+6.1%} | "
              f"upper/none: {b['ret'].mean()*1e4:+6.1f}bp n={len(b):3d} win {(b['ret']>0).mean():.0%} sum {b['ret'].sum():+6.1%} | "
              f"mid/none: {m['ret'].mean()*1e4:+6.1f}bp n={len(m):3d} win {(m['ret']>0).mean():.0%} sum {m['ret'].sum():+6.1%}")
    print("\n-- SHORT the upper-band touch, cover at the lower band (sectors / gold / oil / bonds only — never broad indices) --")
    shorts = ["XLE", "XLF", "XLK", "SMH", "GLD", "GDX", "USO", "TLT"]
    for stop in (0.01, None):
        t = pooled(shorts, side=-1, target="upper", stop=stop)
        print(f"   stop {str(stop):5s}: {line(t)}")
        t = pooled(shorts, side=-1, filt="trend", target="upper", stop=stop)
        print(f"   stop {str(stop):5s} (only below 200d): {line(t)}")


def daily(data, feats):
    print("\n########## DAILY bars, 1999-2026 — the same touch/target/stop trade, 20 equity ETFs, net 5bp/side ##########")
    EQ = BROAD + SECTORS + SUBSECTORS
    for n in (5, 10, 20):
        for target in ("upper", "mid"):
            for stop in (0.01, 0.02, 0.03, 0.05, None):
                out = []
                for s in EQ:
                    t = bounce(data[s], n=n, target=target, stop=stop, max_bars=10, cost=5 / 1e4); t["sym"] = s; out.append(t)
                t = pd.concat(out); t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
                why = t["why"].value_counts(normalize=True)
                print(f"   BB({n:2d},2) target {target:5s} stop {str(stop):5s}: n={len(t):5d} mean {t['ret'].mean()*1e4:+6.1f}bp win {(t['ret']>0).mean():.0%} "
                      f"stopped {why.get('stop', 0):.0%} | by era " + " ".join(f"{t[t['era']==e]['ret'].mean()*1e4:+6.1f}" for e in ERAS)
                      + f" | hold {t['bars'].mean():.1f}d")
    print("\n-- with the regime gate (quadrant G/R at entry), BB(20,2) and BB(10,2), target upper --")
    quad = feats["quad"]
    for n in (10, 20):
        for stop in (0.02, None):
            out = []
            for s in EQ:
                allow = quad.reindex(data[s].index).isin(["G", "R"]).values
                t = bounce(data[s], n=n, target="upper", stop=stop, max_bars=10, cost=5 / 1e4, allow=allow); out.append(t)
            t = pd.concat(out); t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
            print(f"   BB({n},2) stop {str(stop):5s} gated: n={len(t):5d} mean {t['ret'].mean()*1e4:+6.1f}bp win {(t['ret']>0).mean():.0%} | by era "
                  + " ".join(f"{t[t['era']==e]['ret'].mean()*1e4:+6.1f}" for e in ERAS))

    print("\n########## 3-DAY bars (each bar = 3 trading days), BB(20,2), 1999-2026 ##########")
    for target in ("upper", "mid"):
        for stop in (0.03, 0.05, None):
            out = []
            for s in EQ:
                d = data[s]
                g = np.arange(len(d)) // 3
                b3 = d.groupby(g).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
                b3.index = d.index[::3][: len(b3)]
                t = bounce(b3, target=target, stop=stop, max_bars=7, cost=5 / 1e4); out.append(t)
            t = pd.concat(out); t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
            why = t["why"].value_counts(normalize=True)
            print(f"   target {target:5s} stop {str(stop):5s}: n={len(t):5d} mean {t['ret'].mean()*1e4:+7.1f}bp win {(t['ret']>0).mean():.0%} stopped {why.get('stop', 0):.0%} "
                  f"| by era " + " ".join(f"{t[t['era']==e]['ret'].mean()*1e4:+7.1f}" for e in ERAS) + f" | hold {t['bars'].mean()*3:.0f}d")


def main():
    data = load(); feats = daily_features(data)
    intraday(data, feats, "5m", 78)
    intraday(data, feats, "15m", 26)
    intraday(data, feats, "60m", 7)
    daily(data, feats)


if __name__ == "__main__":
    main()
