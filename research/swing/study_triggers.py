"""Entry 83 — BUY TRIGGERS ONLY on SPY and QQQ. No exit rule: every trigger is
scored by what the price does afterwards at fixed horizons (same-day close,
next day, 3 days, 5 days), how much heat it takes first (worst low in the next
5 days), and how far it runs (best high in the next 5 days).

Trigger families
  %  sell-off at the close : 1-day, 3-day, 5-day drops; drop from the 5-day high
  %  sell-off intraday     : X% below yesterday's close / below today's open /
                             gap-down at the open (filled at the level, or at
                             the open if it gaps through)
  Bollinger                : close below the lower band (several widths),
                             depth below the band, intraday touch of the band,
                             band + other conditions
  other                    : RSI2, consecutive down days, vol-scaled moves
Daily OHLC 1993/1999-2026; hourly bars (2 years) for hourly-band triggers.

    python3 -m research.swing.study_triggers
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load
from research.swing.intraday_data import bars
from research.swing.lib import bollinger, daily_features, ibs, rsi, sma

ERAS = {"93-98": ("1993-01-01", "1998-12-31"), "99-06": ("1999-01-01", "2006-12-31"),
        "07-16": ("2007-01-01", "2016-12-31"), "17-26": ("2017-01-01", "2026-12-31")}


def forward(df, fill: pd.Series, intraday: bool):
    """fill = price paid on trigger days (NaN elsewhere). Returns a frame of forward stats."""
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    f = pd.DataFrame(index=df.index)
    f["fill"] = fill
    f["d0"] = (c / fill - 1) if intraday else np.nan            # to the same day's close
    for k in (1, 3, 5):
        f[f"d{k}"] = c.shift(-k) / fill - 1
    lows = pd.concat([l.shift(-k) for k in range(0 if intraday else 1, 6)], axis=1).min(axis=1)
    highs = pd.concat([h.shift(-k) for k in range(1, 6)], axis=1).max(axis=1)
    if intraday:
        highs = pd.concat([highs, c], axis=1).max(axis=1)
    f["mae"] = lows / fill - 1
    f["mfe"] = highs / fill - 1
    return f.dropna(subset=["fill", "d5"])


def cluster_t(x: pd.Series) -> float:
    wk = x.groupby(x.index.to_period("W")).mean()
    return float(wk.mean() / (wk.std(ddof=1) / np.sqrt(len(wk)))) if len(wk) > 3 and wk.std(ddof=1) > 0 else np.nan


def triggers(df):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    pc = c.shift(1)
    r1 = c / pc - 1
    sig = np.log(c).diff().rolling(60).std()
    T = {}

    def close(name, mask):
        T[name] = (c.where(mask.fillna(False)), False)

    def level(name, lvl, cond=None):
        """Intraday buy at `lvl` if the day's low reaches it; filled at the open if it gaps below."""
        hit = (l <= lvl) if cond is None else ((l <= lvl) & cond)
        T[name] = (pd.concat([o, lvl], axis=1).min(axis=1).where(hit.fillna(False)), True)

    # --- % sell-off at the close
    for x in (1, 1.5, 2, 3, 4):
        close(f"close: 1-day drop >= {x}%", r1 <= -x / 100)
    for x in (3, 4, 5, 7):
        close(f"close: 3-day drop >= {x}%", c / c.shift(3) - 1 <= -x / 100)
    for x in (3, 5, 7, 10):
        close(f"close: 5-day drop >= {x}%", c / c.shift(5) - 1 <= -x / 100)
    hi5 = h.rolling(5).max()
    for x in (3, 5, 7, 10):
        close(f"close: {x}% off the 5-day high", c / hi5 - 1 <= -x / 100)
    # --- vol-scaled
    for z in (2, 3):
        close(f"close: 1-day drop >= {z} sigma", np.log(c / pc) / sig.shift(1) <= -z)
    for z in (2, 3):
        close(f"close: 5-day drop >= {z} sigma", np.log(c / c.shift(5)) / (sig.shift(5) * np.sqrt(5)) <= -z)
    # --- intraday % levels
    for x in (1, 1.5, 2, 3, 4):
        level(f"intraday: {x}% below yesterday's close", pc * (1 - x / 100))
    for x in (1, 1.5, 2, 3):
        level(f"intraday: {x}% below today's open", o * (1 - x / 100))
    for x in (0.5, 1, 2):
        T[f"open: gap down >= {x}%"] = (o.where(o / pc - 1 <= -x / 100), True)
    # --- Bollinger
    for n, k in ((20, 2), (20, 2.5), (20, 3), (10, 2), (10, 2.5), (5, 2)):
        mid, up, lo, pctb, bw = bollinger(c, n, k)
        close(f"BB({n},{k}): close below lower band", c < lo)
        level(f"BB({n},{k}): intraday touch of lower band", lo.shift(1))
    mid, up, lo, pctb, bw = bollinger(c, 20, 2)
    below = c < lo
    prev = below.shift(1, fill_value=False)
    close("BB(20,2): FIRST close below band", below & ~prev)
    close("BB(20,2): 2nd+ straight close below band", below & prev)
    for x in (0.5, 1, 2):
        close(f"BB(20,2): close >= {x}% below the band", c / lo - 1 <= -x / 100)
    close("BB(20,2) below band + 1-day drop >= 1.5%", below & (r1 <= -0.015))
    close("BB(20,2) below band + RSI2 < 10", below & (rsi(c, 2) < 10))
    close("BB(20,2) below band + close in bottom 20% of day's range", below & (ibs(df) < 0.2))
    close("BB(20,2) below band, above 200-day avg", below & (c > sma(c, 200)))
    close("BB(20,2) below band, below 200-day avg", below & (c < sma(c, 200)))
    close("BB(20,2): close back above band after being below", (~below) & prev)
    # --- other
    for x in (10, 5, 2):
        close(f"RSI2 < {x}", rsi(c, 2) < x)
    dn = (r1 < 0).astype(int)
    for k in (3, 4, 5):
        close(f"{k} down closes in a row", dn.rolling(k).sum() == k)
    close("close in bottom 10% of day's range", ibs(df) < 0.1)
    return T


def table(sym, df, feats):
    T = triggers(df)
    c = df["close"]
    yrs = (df.index[-1] - df.index[0]).days / 365.25
    base = {k: (c.shift(-k) / c - 1).mean() for k in (1, 3, 5)}
    gate = (feats["quad"].isin(["G", "R"]) & ~((feats["spy_ext200"].between(0, 0.03)) & (feats["rvol20"] > 0.16))).reindex(df.index).fillna(False)
    print(f"\n{'='*150}\n{sym}  {df.index[0].date()} to {df.index[-1].date()}   baseline any day: 1d {base[1]*1e4:+.0f}bp, 3d {base[3]*1e4:+.0f}bp, 5d {base[5]*1e4:+.0f}bp\n{'='*150}")
    print(f"{'trigger':52s} {'days/yr':>7s} | {'->close':>7s} {'1d':>6s} {'3d':>6s} {'5d':>6s} | {'5d win':>6s} {'5d t':>5s} | {'avg heat':>8s} {'bad heat':>8s} {'avg run':>7s} | 5d by era (93-98/99-06/07-16/17-26) | 5d: regime gate open / closed")
    rows = []
    for name, (fill, intraday) in T.items():
        f = forward(df, fill, intraday)
        if len(f) < 15:
            continue
        eras = " ".join(f"{f.loc[a:b]['d5'].mean()*1e2:+5.2f}" if len(f.loc[a:b]) >= 5 else "  n/a" for a, b in ERAS.values())
        g = gate.reindex(f.index)
        go, gc = f[g]["d5"], f[~g]["d5"]
        rows.append((name, len(f) / yrs, f["d0"].mean(), f["d1"].mean(), f["d3"].mean(), f["d5"].mean(), (f["d5"] > 0).mean(),
                     cluster_t(f["d5"] - base[5]), f["mae"].mean(), f["mae"].quantile(0.05), f["mfe"].mean(), eras,
                     f"{go.mean()*1e2:+5.2f}% ({len(go)}) / {gc.mean()*1e2:+5.2f}% ({len(gc)})"))
    for r in rows:
        d0 = f"{r[2]*1e2:+6.2f}%" if not np.isnan(r[2]) else "      -"
        print(f"{r[0]:52s} {r[1]:7.1f} | {d0} {r[3]*1e2:+5.2f}% {r[4]*1e2:+5.2f}% {r[5]*1e2:+5.2f}% | {r[6]:6.0%} {r[7]:+5.1f} | {r[8]*1e2:+7.2f}% {r[9]*1e2:+7.2f}% {r[10]*1e2:+6.2f}% | {r[11]} | {r[12]}")
    return rows


def dose(sym, df):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    print(f"\n--- {sym}: how the bounce scales with the size of the sell-off (mean forward return; n) ---")
    f1, f3, f5 = c.shift(-1) / c - 1, c.shift(-3) / c - 1, c.shift(-5) / c - 1
    def show(lab, x, bins, labels):
        b = pd.cut(x, bins, labels=labels)
        print(f"   {lab}")
        for lb in labels:
            m = b == lb
            if m.sum() >= 8:
                print(f"      {lb:22s} n={int(m.sum()):5d}  1d {f1[m].mean()*1e2:+5.2f}%  3d {f3[m].mean()*1e2:+5.2f}%  5d {f5[m].mean()*1e2:+5.2f}%  5d win {(f5[m]>0).mean():.0%}  5d worst {f5[m].min()*1e2:+6.1f}%")
    show("1-day change at the close", c / c.shift(1) - 1, [-1, -.04, -.03, -.02, -.015, -.01, -.005, 0, .01, 1],
         ["down 4%+", "down 3-4%", "down 2-3%", "down 1.5-2%", "down 1-1.5%", "down 0.5-1%", "down 0-0.5%", "up 0-1%", "up 1%+"])
    show("5-day change at the close", c / c.shift(5) - 1, [-1, -.10, -.07, -.05, -.03, -.02, -.01, 0, .02, 1],
         ["down 10%+", "down 7-10%", "down 5-7%", "down 3-5%", "down 2-3%", "down 1-2%", "down 0-1%", "up 0-2%", "up 2%+"])
    mid, up, lo, pctb, bw = bollinger(c, 20, 2)
    show("close relative to the lower Bollinger band (20,2)", c / lo - 1, [-1, -.03, -.02, -.01, -.005, 0, .005, .01, .02, 1],
         ["3%+ below band", "2-3% below", "1-2% below", "0.5-1% below", "0-0.5% below", "0-0.5% above", "0.5-1% above", "1-2% above", "2%+ above band"])
    show("%B (0 = on lower band, 1 = on upper band)", pctb, [-5, -.25, -.1, 0, .1, .2, .5, .8, 1, 5],
         ["below -0.25", "-0.25 to -0.10", "-0.10 to 0", "0 to 0.10", "0.10 to 0.20", "0.20 to 0.50", "0.50 to 0.80", "0.80 to 1", "above 1"])


def hourly(sym, data):
    H = bars(sym, "60m")
    c, o, h, l = H["close"], H["open"], H["high"], H["low"]
    day = H.index.normalize()
    dclose = c.groupby(day).last()
    dpos = pd.Series(np.arange(len(dclose)), index=dclose.index)
    def fwd(fill):           # fill: Series on hourly index (NaN = no trigger); only the first trigger per day counts
        f = fill.dropna()
        f = f[~f.index.normalize().duplicated(keep="first")]
        out = []
        for ts, px in f.items():
            i = dpos[ts.normalize()]
            if i + 5 >= len(dclose):
                continue
            out.append((dclose.iloc[i] / px - 1, dclose.iloc[i + 1] / px - 1, dclose.iloc[i + 3] / px - 1, dclose.iloc[i + 5] / px - 1))
        return pd.DataFrame(out, columns=["d0", "d1", "d3", "d5"])
    mid, up, lo, pctb, bw = bollinger(c, 20, 2)
    lo1 = lo.shift(1)
    T = {"hourly BB(20,2): touch of lower band": pd.concat([o, lo1], axis=1).min(axis=1).where(l <= lo1)}
    mid, up, lo25, _, _ = bollinger(c, 20, 2.5)
    T["hourly BB(20,2.5): touch of lower band"] = pd.concat([o, lo25.shift(1)], axis=1).min(axis=1).where(l <= lo25.shift(1))
    T["hourly BB(20,2): bar CLOSES below band"] = c.where(c < lo)
    dhigh = h.groupby(day).cummax()
    for x in (1, 1.5, 2, 3):
        lvl = dhigh.shift(1) * (1 - x / 100)
        same = pd.Series(day, index=H.index) == pd.Series(day, index=H.index).shift(1)
        T[f"intraday: {x}% off the day's high"] = pd.concat([o, lvl], axis=1).min(axis=1).where((l <= lvl) & same)
    pcl = dclose.shift(1).reindex(day).values
    for x in (1, 2, 3):
        lvl = pd.Series(pcl * (1 - x / 100), index=H.index)
        T[f"intraday: {x}% below yesterday's close (hourly check)"] = pd.concat([o, lvl], axis=1).min(axis=1).where(l <= lvl)
    first = ~pd.Series(day, index=H.index).duplicated()
    for x in (0.5, 1):
        T[f"first hour closes down >= {x}% from the open"] = c.where(first & (c / o - 1 <= -x / 100))
    base = {k: (dclose.shift(-k) / dclose - 1).mean() for k in (1, 3, 5)}
    print(f"\n--- {sym} hourly bars, {H.index[0].date()} to {H.index[-1].date()} (2 years, indicative); baseline 1d {base[1]*1e2:+.2f}% 5d {base[5]*1e2:+.2f}% ---")
    for name, fill in T.items():
        f = fwd(fill)
        if len(f) < 8:
            continue
        print(f"   {name:52s} days={len(f):4d} | ->close {f['d0'].mean()*1e2:+5.2f}% (win {(f['d0']>0).mean():.0%})  1d {f['d1'].mean()*1e2:+5.2f}%  3d {f['d3'].mean()*1e2:+5.2f}%  5d {f['d5'].mean()*1e2:+5.2f}% (win {(f['d5']>0).mean():.0%})")


def main():
    data = load(); feats = daily_features(data)
    for sym in ("SPY", "QQQ"):
        table(sym, data[sym], feats)
        dose(sym, data[sym])
        hourly(sym, data)


if __name__ == "__main__":
    main()
