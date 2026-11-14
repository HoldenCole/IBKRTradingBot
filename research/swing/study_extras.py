"""Entry 78 — side tests: sector short fades, fragile-state dip-buys, levered
expression, VIX-conditioned overlay, contribution timing, option t-stats, and
the live signal snapshot.

    python3 -m research.swing.study_extras
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import BROAD, ETFS, SECTORS, SUBSECTORS, load
from research.swing.lib import ERAS, bollinger, daily_features, era_of, ibs, perf, rsi, simulate, sma, tstats
from research.swing.study_daily import cluster_t
from research.swing.study_sleeve import MARGIN_SPREAD, core_agg, show, sleeve
from research.swing import study_options as so

EQ = BROAD + SECTORS + SUBSECTORS


def short_fades(data, feats):
    print("=== X1 sector/sub-sector SHORT fades (never broad indices): close > upper BB(20,2) & RSI2>90 -> short, cover < SMA5, max 10d ===")
    rows = []
    for s in SECTORS + SUBSECTORS:
        df = data[s]; c = df["close"]
        mid, up, lo, pctb, bw = bollinger(c)
        e = (c > up) & (rsi(c, 2) > 90)
        tr, _ = simulate(df, e, c < sma(c, 5), 10)
        # simulate() returns long P&L net of 10bp; short P&L = -(gross) - 10bp cost - 2bp borrow
        gross = tr["ret"] + 10 / 1e4
        tr["ret"] = -gross - 10 / 1e4 - 2 / 1e4
        tr["sym"] = s; rows.append(tr)
    t = pd.concat(rows); t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
    t["quad"] = feats["quad"].reindex(t["signal"].values).values
    for lab, m in (("all", t["quad"].notna()), ("growth-off quadrants (S/D)", t["quad"].isin(["S", "D"])), ("growth-on (G/R)", t["quad"].isin(["G", "R"]))):
        s = t[m]
        print(f"   {lab:28s} n={len(s):5d} mean {s['ret'].mean()*1e4:+6.1f}bp win {(s['ret']>0).mean():.0%} clus-t {cluster_t(s):+.2f}  by era "
              + " ".join(f"{s[s['era']==e]['ret'].mean()*1e4:+.0f}/{(s['era']==e).sum()}" for e in ERAS))


def fragile(data, feats):
    print("\n=== X2 dip-buys by S&P state at signal (equity ETFs, BB(20,2) and BB+RSI2), distinct signal weeks in brackets ===")
    t = pd.read_pickle("research/cache/swing_trades_close.pkl")
    t = t[t["group"].isin(["broad", "sectors", "subsectors"])]
    states = {"healthy: >3% above 200d": t["spy_ext200"] > 0.03,
              "thin cushion 0-3% above, vol<=16%": t["spy_ext200"].between(0, 0.03) & (t["rvol20"] <= 0.16),
              "FRAGILE 0-3% above, vol>16%": t["spy_ext200"].between(0, 0.03) & (t["rvol20"] > 0.16),
              "just below 200d (0 to -5%)": t["spy_ext200"].between(-0.05, 0),
              "deep below 200d (<-5%)": t["spy_ext200"] < -0.05}
    for name in ("BB(20,2) lower -> mid", "BB + RSI2<10", "RSI2<10 + 200d trend"):
        print(f"\n{name}")
        for lab, m in states.items():
            s = t[m & (t["strat"] == name)]
            wk = s["entry"].dt.to_period("W").nunique()
            print(f"   {lab:36s} n={len(s):5d} [{wk:3d} wks] mean {s['ret'].mean()*1e4:+7.1f}bp win {(s['ret']>0).mean():.0%} clus-t {cluster_t(s):+.2f}  by era "
                  + " ".join(f"{s[s['era']==e]['ret'].mean()*1e4:+.0f}/{(s['era']==e).sum()}" for e in ERAS))


def levered(data, feats):
    print("\n=== X3 levered expression: signal on the underlying, position in the levered ETF (real data), aligned G/R, BB+RSI2 ===")
    for und, lev in (("QQQ", "QLD"), ("QQQ", "TQQQ"), ("XLE", "ERX")):
        c = data[und]["close"]; mid, up, lo, pctb, bw = bollinger(c)
        gate = "GR" if und == "QQQ" else "R"
        e = (c < lo) & (rsi(c, 2) < 10) & feats["quad"].reindex(c.index).isin(list(gate))
        x = c > sma(c, 5)
        idx = data[lev].index
        for sym in (und, lev):
            tr, _ = simulate(data[sym].loc[idx[0]:], e.reindex(idx).fillna(False), x.reindex(idx).fillna(False), 10)
            print(f"   signal {und} -> hold {sym:5s} since {idx[0].year}: n={len(tr):3d} mean {tr['ret'].mean()*1e4:+7.1f}bp win {(tr['ret']>0).mean():.0%} "
                  f"worst {tr['ret'].min():+.1%} t {tstats(tr['ret'])['t']:+.2f}")


def vix_overlay(data, feats):
    print("\n=== X4 overlay restricted to high-VIX dips (secondary, conditioned on T5), BB+RSI2 aligned, on AGG 2007-2026 ===")
    tier_daily, rf = core_agg()
    core = tier_daily["AGG"].dropna(); core = core[core.index >= "2007-01-01"]
    show("AGG core alone", core)
    for vmin in (None, 20, 25):
        r, x, n = sleeve(data, feats, "BB+RSI2", gate="GR", vix_min=vmin)
        r, x = r.reindex(core.index).fillna(0.0), x.reindex(core.index).fillna(0.0)
        rfc = rf.reindex(core.index).fillna(0.0)
        for w in (0.5,):
            ov = core + w * r - x * w * (rfc + MARGIN_SPREAD / 252)
            p = show(f"VIX>={vmin}: 50% overlay ({n/ (len(r)/252):.0f} trades/yr, expo {x.mean():.0%})", ov)
            for a, b in (("2007-01-01", "2016-12-31"), ("2017-01-01", "2026-12-31")):
                pc, po = perf(core.loc[a:b]), perf(ov.loc[a:b])
                print(f"         {a[:4]}-{b[:4]}: CAGR {pc['CAGR']:+.1%}->{po['CAGR']:+.1%}  Sortino {pc['Sortino']:.2f}->{po['Sortino']:.2f}  maxDD {pc['maxDD']:+.1%}->{po['maxDD']:+.1%}")


def contribution_timing(data):
    print("\n=== X5 contribution timing: cash arrives on a random day; buy at once vs wait (<=10 trading days) for a dip close ===")
    print("    value = average purchase-price advantage vs buying immediately, bp (+ = cheaper); every start day 1999-2026")
    for sym in ("SPY", "QQQ", "XLE", "GLD"):
        df = data[sym]; c = df["close"].values; n = len(c)
        r2 = rsi(df["close"], 2).values; ib = ibs(df).values
        mid, up, lo, pctb, bw = bollinger(df["close"]); lo = lo.values
        rules = {"first down close": lambda i: c[i] < c[i - 1], "IBS<0.2": lambda i: ib[i] < 0.2,
                 "RSI2<10": lambda i: r2[i] < 10, "below lower BB": lambda i: c[i] < lo[i]}
        out = []
        for lab, f in rules.items():
            adv = np.full(n, np.nan)
            for i in range(250, n - 11):
                px = None
                for j in range(i, i + 11):
                    if f(j):
                        px = c[j]; break
                adv[i] = c[i] / (px if px is not None else c[i + 10]) - 1
            a = pd.Series(adv, index=df.index)
            out.append(f"{lab}: " + " ".join(f"{a.loc[x:y].mean()*1e4:+.0f}" for x, y in ERAS.values()))
        print(f"   {sym}: " + " | ".join(out))


def option_t(data, feats):
    print("\n=== X6 option structures on SPY+QQQ, BB+RSI2 aligned G/R: t-stats on return-on-risk ===")
    rf = data["^IRX"]["close"] / 100
    ivs = {"SPY": 0.90 * (data["^VIX"]["close"] / 100).reindex(data["SPY"].index).ffill(),
           "QQQ": 0.90 * (data["^VXN"]["close"] / 100).reindex(data["QQQ"].index)}
    t = pd.concat([so.run(s, data[s], ivs[s], feats, rf, "BB+RSI2", "GR") for s in ivs])
    t["era"] = t["entry"].map(era_of); t = t[t["era"].isin(ERAS)]
    yrs = (t["entry"].max() - t["entry"].min()).days / 365
    print(f"   n={len(t)} trades over {yrs:.0f} years ({len(t)/yrs:.1f}/yr)")
    for name in so.STRUCTS:
        r = t[name + "|ror"].dropna()
        print(f"   {name:30s} mean {r.mean():+.1%}  sd {r.std():.0%}  t {r.mean()/(r.std()/np.sqrt(len(r))):+.2f}  "
              f"lose>50% of risk in {(r < -0.5).mean():.0%} of trades")


def snapshot(data, feats):
    print(f"\n=== X7 live snapshot, close of {data['SPY'].index[-1].date()} — quadrant in force {feats['quad'].iloc[-1]} ===")
    f = feats.iloc[-1]
    print(f"   S&P vs 200d {f['spy_ext200']:+.1%}, 20d vol {f['rvol20']:.0%}, VIX {f['vix']:.1f}, sectors above 200d {f['breadth200']:.0%}")
    rows = []
    for s in ETFS + ["ERX", "TQQQ"]:
        df = data[s]; c = df["close"]
        mid, up, lo, pctb, bw = bollinger(c)
        rows.append((s, pctb.iloc[-1], rsi(c, 2).iloc[-1], ibs(df).iloc[-1], c.iloc[-1] / sma(c, 200).iloc[-1] - 1,
                     c.iloc[-1] / c.iloc[-6] - 1, c.iloc[-1] / c.iloc[-11] - 1))
    t = pd.DataFrame(rows, columns=["sym", "pctB", "RSI2", "IBS", "vs200d", "5d", "10d"]).set_index("sym").sort_values("pctB")
    pd.set_option("display.width", 200)
    print(t.round(3).to_string())


def main():
    data = load(); feats = daily_features(data)
    short_fades(data, feats); fragile(data, feats); levered(data, feats)
    vix_overlay(data, feats); contribution_timing(data); option_t(data, feats); snapshot(data, feats)


if __name__ == "__main__":
    main()
