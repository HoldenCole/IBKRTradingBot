"""Entry 75b — is the dip-buy edge more than regime-matched drift, and what
does a swing sleeve add to the live AGG book (carve-out vs margin overlay)?

    python3 -m research.swing.study_sleeve
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.swing.data import BROAD, SECTORS, SUBSECTORS, load
from research.swing.lib import ERAS, bollinger, daily_features, ibs, perf, rsi, sma, tstats
from research.swing.study_daily import ALIGNED, cluster_t

EQ = BROAD + SECTORS + SUBSECTORS
COST = 5 / 1e4
MARGIN_SPREAD = 0.015          # IBKR Pro: benchmark + 1.5% under $100k


def matched_excess():
    """Trade return minus (days held x the asset's mean daily return in the
    same era and same quadrant-at-signal): edge beyond regime-conditional beta."""
    t = pd.read_pickle("research/cache/swing_trades_close.pkl")
    data = load(); feats = daily_features(data)
    mu = {}
    for sym in t["sym"].unique():
        r = data[sym]["close"].pct_change()
        q = feats["quad"].reindex(r.index)
        for era, (a, b) in ERAS.items():
            for quad in "GRSD":
                m = r.loc[a:b][q.loc[a:b] == quad]
                mu[(sym, era, quad)] = m.mean() if len(m) > 20 else np.nan
    t["base"] = [mu.get((s, e, q), np.nan) * d for s, e, q, d in zip(t["sym"], t["era"], t["quad"], t["days"])]
    t["xs"] = t["ret"] - t["base"]
    t["aligned"] = [isinstance(q, str) and q in ALIGNED[g] for q, g in zip(t["quad"], t["group"])]
    print("=== Edge beyond regime-matched drift (aligned equity trades; bp per trade, bp per day held) ===")
    eq = t[t["group"].isin(["broad", "sectors", "subsectors"]) & t["aligned"]].dropna(subset=["xs"])
    for name in t["strat"].unique():
        s = eq[eq["strat"] == name]
        if s.empty:
            continue
        cells = []
        for era in ERAS:
            e = s[s["era"] == era]
            cells.append(f"{era[:1]} raw {e['ret'].mean()*1e4:+6.1f} drift {e['base'].mean()*1e4:+6.1f} xs {e['xs'].mean()*1e4:+6.1f}")
        x = s.assign(ret=s["xs"])
        print(f"{name:26s} n={len(s):5d}  " + " | ".join(cells) +
              f" | ALL xs {s['xs'].mean()*1e4:+6.1f}bp ({s['xs'].mean()*1e4/s['days'].mean():+.1f}/day) clus-t {cluster_t(x):+.2f}")
    return t


def signals(df: pd.DataFrame, kind: str):
    c = df["close"]
    mid, up, lo, pctb, bw = bollinger(c, 20, 2.0)
    r2 = rsi(c, 2)
    if kind == "BB+RSI2":
        return (c < lo) & (r2 < 10), c > sma(c, 5), 10, pctb
    if kind == "BB+trend":
        return (c < lo) & (c > sma(c, 200)), c > mid, 10, pctb
    if kind == "BB":
        return c < lo, c > mid, 10, pctb
    if kind == "RSI2+trend":
        return (r2 < 10) & (c > sma(c, 200)), c > sma(c, 5), 10, r2 / 100
    if kind == "IBS":
        return ibs(df) < 0.2, c > df["high"].shift(1), 5, ibs(df)
    raise ValueError(kind)


def sleeve(data, feats, kind, universe=EQ, gate="GR", slots=4, start="1999-06-01", vix_min=None):
    """Daily sleeve: up to `slots` positions at 1/slots each, most-oversold first.
    Returns (gross position return incl. costs, exposure fraction, n trades)."""
    days = feats.index[feats.index >= start]
    R = pd.DataFrame({s: data[s]["close"].pct_change() for s in universe}).reindex(days)
    E, X, P, H = {}, {}, {}, {}
    for s in universe:
        e, x, h, pr = signals(data[s], kind)
        E[s] = e.reindex(days).fillna(False).values; X[s] = x.reindex(days).fillna(False).values
        P[s] = pr.reindex(days).values; H[s] = h
    quad = feats["quad"].reindex(days).values
    vix = feats["vix"].reindex(days).values
    Rv = {s: R[s].fillna(0.0).values for s in universe}
    held: dict[str, int] = {}
    ret = np.zeros(len(days)); expo = np.zeros(len(days)); ntr = 0
    for i in range(len(days)):
        # accrue today's return on positions opened before today
        for s in held:
            ret[i] += Rv[s][i] / slots
        expo[i] = len(held) / slots
        # exits at today's close
        for s in list(held):
            if X[s][i] or i - held[s] >= H[s]:
                ret[i] -= COST / slots; del held[s]
        # entries at today's close
        ok = (gate is None or (isinstance(quad[i], str) and quad[i] in gate)) and (vix_min is None or vix[i] >= vix_min)
        if ok and len(held) < slots:
            cands = sorted((s for s in universe if E[s][i] and s not in held and not np.isnan(P[s][i])),
                           key=lambda s: P[s][i])
            for s in cands[: slots - len(held)]:
                held[s] = i; ret[i] -= COST / slots; ntr += 1
    return pd.Series(ret, index=days), pd.Series(expo, index=days), ntr


def core_agg():
    sys.path.insert(0, "research")
    import engine  # noqa
    px = engine.load_all()
    rets, q, tier_daily, months = engine.build(px)
    rf = (px["^IRX"] / 100 / 252).reindex(rets.index).ffill().fillna(0.0)
    return tier_daily, rf


def show(lab, r):
    p = perf(r)
    print(f"   {lab:44s} CAGR {p['CAGR']:+6.1%}  vol {p['vol']:5.1%}  Sharpe {p['Sharpe']:.2f}  Sortino {p['Sortino']:.2f}  maxDD {p['maxDD']:+.1%}")
    return p


def main():
    matched_excess()
    data = load(); feats = daily_features(data)
    tier_daily, rf = core_agg()
    rf_all = (data["^IRX"]["close"] / 100 / 252).reindex(feats.index).ffill().fillna(0.0)

    print("\n=== Sleeve standalone (4 slots, most-oversold first, 5bp/side; idle cash earns T-bill) ===")
    sleeves = {}
    for kind in ("BB+RSI2", "BB+trend", "BB", "RSI2+trend", "IBS"):
        for gate in ("GR", None):
            r, x, n = sleeve(data, feats, kind, gate=gate)
            sleeves[(kind, gate)] = (r, x)
            tot = r + (1 - x) * rf_all.reindex(r.index)
            print(f"\n{kind}  gate={'aligned G/R' if gate else 'none'}  trades/yr {n/ (len(r)/252):.0f}  avg exposure {x.mean():.0%}")
            for era, (a, b) in ERAS.items():
                seg = tot.loc[a:b]; xs = r.loc[a:b]
                p = perf(seg)
                dayret = xs[x.loc[a:b] > 0].mean() * 1e4 if (x.loc[a:b] > 0).any() else np.nan
                print(f"   {era}: CAGR {p['CAGR']:+6.1%} Sharpe {p['Sharpe']:.2f} maxDD {p['maxDD']:+.1%}  "
                      f"position-only ann. return {xs.mean()*252:+.1%} on {x.loc[a:b].mean():.0%} exposure")

    print("\n=== Combined with the live AGG book, 2007-2026 (core = research/engine v9 AGG daily) ===")
    core = tier_daily["AGG"].dropna()
    core = core[core.index >= "2007-01-01"]
    base = show("AGG core alone", core)
    for kind in ("BB+RSI2", "BB+trend", "RSI2+trend", "IBS"):
        r, x = sleeves[(kind, "GR")]
        r, x = r.reindex(core.index).fillna(0.0), x.reindex(core.index).fillna(0.0)
        rfc = rf.reindex(core.index).fillna(0.0)
        print(f"\n{kind} (aligned G/R)   corr(sleeve, core) daily {np.corrcoef(r, core)[0,1]:+.2f}; "
              f"on core's worst 5% days sleeve avg {r[core <= core.quantile(.05)].mean()*1e4:+.0f}bp vs all-days {r.mean()*1e4:+.1f}bp")
        for w in (0.25, 0.50, 1.00):
            fin = x * w * (rfc + MARGIN_SPREAD / 252)
            ov = core + w * r - fin
            show(f"margin overlay {w:.0%} of equity", ov)
        for w in (0.20,):
            co = (1 - w) * core + w * (r + (1 - x) * rfc)
            show(f"carve-out {w:.0%} (rest of sleeve in T-bills)", co)
        # half-era split of the overlay increment
        for a, b in (("2007-01-01", "2016-12-31"), ("2017-01-01", "2026-12-31")):
            c = core.loc[a:b]; o = (core + 0.5 * r - x * 0.5 * (rfc + MARGIN_SPREAD / 252)).loc[a:b]
            pc, po = perf(c), perf(o)
            print(f"      {a[:4]}-{b[:4]} 50% overlay: CAGR {pc['CAGR']:+.1%} -> {po['CAGR']:+.1%}, "
                  f"Sortino {pc['Sortino']:.2f} -> {po['Sortino']:.2f}, maxDD {pc['maxDD']:+.1%} -> {po['maxDD']:+.1%}")


if __name__ == "__main__":
    main()
