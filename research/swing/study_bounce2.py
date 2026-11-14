"""Entry 80b — can the band bounce carry a tight stop? Three rescues:

  (1) CONFIRMATION entry: wait for the first close back above the lower band
      after a close below it; buy that close; stop = the low of the excursion
      (a structural, usually tight stop); target = upper or mid band.
  (2) VOL-SCALED stops on the touch entry: stop = m x ATR(14) of the bar size.
  (3) MULTI-TIMEFRAME: hourly lower-band touch taken only when the DAILY chart
      is sold off (prior daily close below its own lower BB(20,2) or daily
      RSI2 < 10) — the proven daily signal with an intraday entry.
Plus an account-level simulation of the hourly no-stop bounce at 1x/2x/3x.

    python3 -m research.swing.study_bounce2
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import BROAD, SECTORS, SUBSECTORS, load
from research.swing.intraday_data import SYMS, bars
from research.swing.lib import ERAS, bollinger, daily_features, era_of, rsi, tstats
from research.swing.study_bounce import EQ_INTRA, bounce, line

EQ = BROAD + SECTORS + SUBSECTORS


def confirm(df, n=20, k=2.0, target="upper", max_bars=21, cost=3 / 1e4, min_risk=0.0, allow=None):
    o, h, l, c = (df[x].values for x in ("open", "high", "low", "close"))
    cs = pd.Series(c); mid = cs.rolling(n).mean().values; sd = cs.rolling(n).std(ddof=0).values
    up, lo = mid + k * sd, mid - k * sd
    ok = np.ones(len(c), bool) if allow is None else np.asarray(allow, bool)
    rows = []; N = len(c); i = n + 1; exc_low = None
    while i < N - 1:
        if c[i] < lo[i]:
            exc_low = l[i] if exc_low is None else min(exc_low, l[i]); i += 1; continue
        if exc_low is None or not ok[i]:
            exc_low = None; i += 1; continue
        # first close back above the band after an excursion
        exc_low = min(exc_low, l[i]); epx = c[i]; spx = exc_low
        risk = epx / spx - 1
        exc_low = None
        if risk < min_risk:
            i += 1; continue
        j = i; xpx = None
        while xpx is None:
            j += 1
            if j >= N:
                j = N - 1; xpx, why = c[j], "eod"; break
            tgt = up[j - 1] if target == "upper" else mid[j - 1]
            if l[j] <= spx:
                xpx, why = min(o[j], spx), "stop"
            elif h[j] >= tgt:
                xpx, why = max(o[j], tgt), "target"
            elif j - i >= max_bars:
                xpx, why = c[j], "time"
        rows.append((df.index[i], df.index[j], j - i, xpx / epx - 1 - 2 * cost, why, risk))
        i = j + 1
    return pd.DataFrame(rows, columns=["entry", "exit", "bars", "ret", "why", "risk"])


def atr_stop_bounce(df, m, target="upper", max_bars=21, cost=3 / 1e4, n=20):
    """Touch entry with stop = m x ATR(14) below entry (ATR as a fraction of price, known at t-1)."""
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = (tr.rolling(14).mean() / c).shift(1)
    out = []
    # bucket bars by ATR level so each trade uses its own stop: run per-quantile approximation exactly by looping stops
    o, hh, ll, cc = (df[x].values for x in ("open", "high", "low", "close"))
    cs = pd.Series(cc); mid = cs.rolling(n).mean().values; sd = cs.rolling(n).std(ddof=0).values
    up, lo = mid + 2 * sd, mid - 2 * sd; a = atr.values
    N = len(cc); i = n + 15
    while i < N:
        if not (ll[i] <= lo[i - 1]) or np.isnan(a[i]):
            i += 1; continue
        epx = min(o[i], lo[i - 1]); spx = epx * (1 - m * a[i]); j = i; xpx = None
        if ll[i] <= spx:
            xpx, why = spx, "stop"
        while xpx is None:
            j += 1
            if j >= N:
                j = N - 1; xpx, why = cc[j], "eod"; break
            tgt = up[j - 1] if target == "upper" else mid[j - 1]
            if ll[j] <= spx:
                xpx, why = min(o[j], spx), "stop"
            elif hh[j] >= tgt:
                xpx, why = max(o[j], tgt), "target"
            elif j - i >= max_bars:
                xpx, why = cc[j], "time"
        out.append((df.index[i], df.index[j], j - i, xpx / epx - 1 - 2 * cost, why))
        i = j + 1
    return pd.DataFrame(out, columns=["entry", "exit", "bars", "ret", "why"])


def pool(fn, syms, src):
    out = []
    for s in syms:
        t = fn(src[s]); t["sym"] = s; out.append(t)
    return pd.concat(out, ignore_index=True)


def era_cells(t):
    t = t.assign(era=t["entry"].map(era_of)); t = t[t["era"].isin(ERAS)]
    return t, " ".join(f"{t[t['era']==e]['ret'].mean()*1e4:+6.1f}" for e in ERAS)


def main():
    data = load(); feats = daily_features(data)
    H = {s: bars(s, "60m") for s in SYMS}

    print("=== (1) CONFIRMATION entry + structural stop under the excursion low ===")
    print("-- hourly, 2 years, 6 equity ETFs pooled, net 3bp/side --")
    for target in ("upper", "mid"):
        t = pool(lambda d, target=target: confirm(d, target=target), EQ_INTRA, H)
        print(f"   target {target:5s}: {line(t)} | median stop distance {t['risk'].median():.2%} | R-multiple mean {(t['ret']/t['risk']).clip(-5,20).mean():+.2f}")
    print("-- daily, 1999-2026, 20 equity ETFs, net 5bp/side --")
    for target in ("upper", "mid"):
        t = pool(lambda d, target=target: confirm(d, target=target, max_bars=10, cost=5 / 1e4), EQ, data)
        t, cells = era_cells(t)
        why = t["why"].value_counts(normalize=True)
        print(f"   target {target:5s}: n={len(t):5d} mean {t['ret'].mean()*1e4:+6.1f}bp win {(t['ret']>0).mean():.0%} stopped {why.get('stop',0):.0%} | by era {cells} "
              f"| median stop distance {t['risk'].median():.2%} | hold {t['bars'].mean():.1f}d")
    quad = feats["quad"]
    for target in ("upper", "mid"):
        t = pd.concat([confirm(data[s], target=target, max_bars=10, cost=5 / 1e4,
                               allow=quad.reindex(data[s].index).isin(["G", "R"]).values) for s in EQ])
        t, cells = era_cells(t)
        print(f"   target {target:5s} + regime gate G/R: n={len(t):5d} mean {t['ret'].mean()*1e4:+6.1f}bp win {(t['ret']>0).mean():.0%} | by era {cells}")

    print("\n=== (2) VOL-SCALED stops on the touch entry (stop = m x ATR14 of the bar) ===")
    for lab, src, syms, mb, cost in (("hourly 2y", H, EQ_INTRA, 21, 3 / 1e4), ("daily 27y", data, EQ, 10, 5 / 1e4)):
        for m in (0.5, 1, 2, 3, 5):
            t = pool(lambda d, m=m: atr_stop_bounce(d, m, max_bars=mb, cost=cost), syms, src)
            extra = ""
            if lab.startswith("daily"):
                t, cells = era_cells(t); extra = f" | by era {cells}"
            why = t["why"].value_counts(normalize=True)
            print(f"   {lab} stop {m:>3} ATR: n={len(t):5d} mean {t['ret'].mean()*1e4:+6.1f}bp win {(t['ret']>0).mean():.0%} stopped {why.get('stop',0):.0%} t {tstats(t['ret'])['t']:+.2f}{extra}")

    print("\n=== (3) MULTI-TIMEFRAME: hourly lower-band touch only when the daily chart is sold off (hourly, 2y) ===")
    for lab, cond in (("prior daily close below daily lower BB(20,2)", "bb"), ("prior daily RSI2 < 10", "rsi"),
                      ("either", "either"), ("neither (control)", "none")):
        for stop in (None, 0.01):
            out = []
            for s in EQ_INTRA:
                c = data[s]["close"]; mid, up, lo, pctb, bw = bollinger(c)
                bb = (c < lo); rs = rsi(c, 2) < 10
                flag = {"bb": bb, "rsi": rs, "either": bb | rs, "none": ~(bb | rs)}[cond].shift(1).fillna(False)
                d = pd.DatetimeIndex(H[s].index.tz_localize(None).normalize())
                allow = flag.reindex(d).ffill().fillna(False).values
                t = bounce(H[s], target="upper", stop=stop, max_bars=21, allow=allow); t["sym"] = s; out.append(t)
            t = pd.concat(out)
            print(f"   {lab:44s} stop {str(stop):5s}: {line(t)}")

    print("\n=== (4) Account simulation, hourly no-stop bounce (touch lower band -> upper band or 3 days), 2 years ===")
    for syms, lab in ((["SPY", "QQQ"], "SPY+QQQ"), (EQ_INTRA, "6 equity ETFs"), (["SPY", "QQQ", "IWM", "GDX", "USO"], "post-hoc best 5 (optimistic)")):
        tr = pd.concat([bounce(H[s], target="upper", stop=None, max_bars=21).assign(sym=s) for s in syms]).sort_values("entry")
        # two slots of 50%: take trades in time order, skip when both slots are busy
        busy = []; taken = []
        for _, t in tr.iterrows():
            busy = [b for b in busy if b > t["entry"]]
            if len(busy) < 2:
                busy.append(t["exit"]); taken.append(t)
        tk = pd.DataFrame(taken).sort_values("exit")
        yrs = (tk["exit"].max() - tk["entry"].min()).days / 365.25
        line_ = f"   {lab:30s} trades {len(tk)} ({len(tk)/yrs:.0f}/yr) mean {tk['ret'].mean()*1e4:+.0f}bp win {(tk['ret']>0).mean():.0%} worst {tk['ret'].min():+.1%}"
        for lev in (1, 2, 3):
            eq = (1 + 0.5 * lev * tk["ret"].values).cumprod()
            dd = (eq / np.maximum.accumulate(eq) - 1).min()
            line_ += f" | {lev}x: {eq[-1]**(1/yrs)-1:+.1%}/yr DD {dd:+.0%}"
        print(line_)
    spy = H["SPY"]["close"]
    print(f"   (SPY buy & hold over the same window: {(spy.iloc[-1]/spy.iloc[0])**(1/yrs)-1:+.1%}/yr; trade-level drawdowns understate intra-trade lows; levered returns ignore financing/decay)")


if __name__ == "__main__":
    main()
