"""Crypto C3 — bitcoin signals, traded short-term and levered in BTC and altcoins. See PREREGISTRATION_C3.md.

    python3 -m research.crypto.levered            # development sample only
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from research.crypto.data import binance_funding, perp_hourly
from research.crypto.trend import combo

COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
CAP = {"BTC": 10, "ETH": 10, "SOL": 5, "XRP": 5, "DOGE": 4}
DEV_END = pd.Timestamp("2024-01-01", tz="UTC")
ERA_SPLIT = pd.Timestamp("2022-01-01", tz="UTC")
COST, STRESS = 0.0010, 0.0020
LEVERAGES = (1, 2, 3, 5, 10)
HOLDOUT_FLAG = "open the C3 hold-out once for gate passers"


def load():
    px = {c: perp_hourly(c) for c in COINS}
    idx = px["BTC"].index
    px = {c: d.reindex(idx) for c, d in px.items()}
    fund = {}
    for c in COINS:
        f = binance_funding(c).set_index("time")["rate"]
        f.index = f.index.floor("h")
        f = f.groupby(level=0).sum()
        fund[c] = f.reindex(idx, method=None).fillna(0.0)    # funding events land on 00/08/16 UTC open times
    return idx, px, fund


def rsi(s: pd.Series, n: int = 2) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def windows(idx, btc: pd.DataFrame) -> dict[str, list[tuple[int, int, int]]]:
    """Trade windows (entry position, exit position, direction) on the hourly index, from BTC only.
    Position k refers to the hourly bar with open time idx[k]; entry and exit are at that bar's close."""
    c = btc["close"]
    r1 = c.pct_change()
    sig = r1.rolling(720, min_periods=500).std().shift(1)
    n = len(idx)
    out = {}

    def fixed(direction: np.ndarray, hold: int):
        tr, k = [], 0
        while k < n - hold:
            d = direction[k]
            if d != 0 and np.isfinite(d):
                tr.append((k, k + hold, int(d)))
                k += hold
                continue
            k += 1
        return tr

    d1 = np.where(r1 > 2 * sig, 1, np.where(r1 < -2 * sig, -1, 0))
    out["S1 impulse 1h, hold 4h"] = fixed(d1, 4)
    out["S2 impulse 1h, hold 1h"] = fixed(d1, 1)
    r4 = c / c.shift(4) - 1
    d3 = np.where(r4 > 4 * sig, 1, np.where(r4 < -4 * sig, -1, 0))
    out["S3 impulse 4h, hold 24h"] = fixed(d3, 24)

    # 4-hour bars: open times 00, 04, ... UTC; the bar closes at the close of the hourly bar opened 3 hours later
    b4 = btc.resample("4h", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pos = pd.Series(np.arange(n), index=idx)
    b4_pos = pos.reindex(b4.index + pd.Timedelta(hours=3)).values
    ok = np.isfinite(b4_pos)
    b4, b4_pos = b4[ok], b4_pos[ok].astype(int)
    hi20, lo20 = b4["high"].rolling(20).max().shift(1), b4["low"].rolling(20).min().shift(1)
    hi10, lo10 = b4["high"].rolling(10).max().shift(1), b4["low"].rolling(10).min().shift(1)
    cl = b4["close"].values
    tr, j = [], 0
    m = len(b4)
    while j < m:
        if np.isfinite(hi20.iloc[j]) and (cl[j] > hi20.iloc[j] or cl[j] < lo20.iloc[j]):
            d = 1 if cl[j] > hi20.iloc[j] else -1
            k = j + 1
            while k < m and b4_pos[k] - b4_pos[j] < 72:
                if (d > 0 and cl[k] < lo10.iloc[k]) or (d < 0 and cl[k] > hi10.iloc[k]):
                    break
                k += 1
            k = min(k, m - 1)
            exit_pos = min(b4_pos[k], b4_pos[j] + 72)
            tr.append((int(b4_pos[j]), int(exit_pos), d))
            j = k + 1
            continue
        j += 1
    out["S4 4-hour breakout"] = tr

    r2 = rsi(b4["close"], 2).values
    d5 = np.zeros(n)
    d5[b4_pos] = np.where(r2 < 10, 1, np.where(r2 > 90, -1, 0))
    out["S5 4-hour RSI(2) dip and rip"] = fixed(d5, 24)

    # daily trend: daily close = close of the hourly bar opened at 23:00 UTC
    daily = c[idx.hour == 23]
    w, _ = combo(daily.reset_index(drop=True).set_axis(daily.index.normalize()))
    on = (w.values > 0).astype(int)
    dpos = pos.reindex(daily.index).values.astype(int)
    tr, j = [], 0
    while j < len(on):
        if on[j]:
            k = j
            while k + 1 < len(on) and on[k + 1]:
                k += 1
            if k > j:
                tr.append((int(dpos[j]), int(dpos[k] if k < len(on) - 1 else dpos[-1]), 1))
            j = k + 1
            continue
        j += 1
    out["S6 daily trend (long only)"] = tr
    return out


def trade_table(wins, idx, px, fund, coin, holdout=False):
    o = px[coin]
    c, h, l = o["close"].values, o["high"].values, o["low"].values
    f = fund[coin].values
    rows = []
    for a, b, d in wins:
        if not (np.isfinite(c[a]) and np.isfinite(c[b])):
            continue
        if not holdout and idx[b] >= DEV_END:
            continue
        gross = d * (c[b] / c[a] - 1)
        fsum = f[a + 1:b + 1].sum()
        hh, ll = np.nanmax(h[a + 1:b + 1]), np.nanmin(l[a + 1:b + 1])
        adverse = (c[a] - ll) / c[a] if d > 0 else (hh - c[a]) / c[a]
        rows.append({"entry": idx[a], "exit": idx[b], "dir": d, "gross": gross, "funding": -d * fsum,
                     "adverse": max(adverse, 0.0), "hours": b - a})
    t = pd.DataFrame(rows)
    if len(t):
        t["net"] = t.gross + t.funding - 2 * COST
        t["net_stress"] = t.gross + t.funding - 2 * STRESS
    return t


def account(t: pd.DataFrame, L: float):
    e, peak, mdd, liq = 1.0, 1.0, 0.0, 0
    for r in t.itertuples():
        if r.adverse >= 1 / L - 0.005:
            e *= 0.005 * L
            liq += 1
        else:
            e *= max(1 + L * r.net, 0.0)
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    yrs = max((t.exit.iloc[-1] - t.entry.iloc[0]).days / 365.25, 1e-9)
    return {"multiple": e, "CAGR": e ** (1 / yrs) - 1 if e > 0 else -1.0, "maxDD": mdd, "liquidations": liq,
            "ruin": e < 0.1}


def main():
    idx, px, fund = load()
    wins = windows(idx, px["BTC"])
    rows, lev_rows = [], []
    for s, w in wins.items():
        for coin in COINS:
            t = trade_table(w, idx, px, fund, coin)
            if t.empty:
                continue
            e1, e2 = t[t.entry < ERA_SPLIT], t[t.entry >= ERA_SPLIT]
            tstat = t.net.mean() / (t.net.std(ddof=1) / np.sqrt(len(t))) if len(t) > 2 else np.nan
            row = {"signal": s, "coin": coin, "trades": len(t), "mean_bp": t.net.mean() * 1e4, "median_bp": t.net.median() * 1e4,
                   "win": (t.net > 0).mean(), "t": tstat, "era1_bp": e1.net.mean() * 1e4, "era2_bp": e2.net.mean() * 1e4,
                   "stress_bp": t.net_stress.mean() * 1e4, "funding_bp": t.funding.mean() * 1e4,
                   "ratio": t.net.mean() / t.net.std(ddof=1), "avg_hours": t.hours.mean(),
                   "worst_adverse": t.adverse.max()}
            if s.startswith("S6"):
                a1 = account(t, 1)
                row["cagr_1x"] = a1["CAGR"]
                row["era1_cagr"] = account(e1, 1)["CAGR"] if len(e1) else np.nan
                row["era2_cagr"] = account(e2, 1)["CAGR"] if len(e2) else np.nan
            rows.append(row)
            best = (0.0, None)
            for L in [x for x in (0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10) if x <= CAP[coin]]:
                a = account(t, L)
                if L in LEVERAGES:
                    lev_rows.append({"signal": s, "coin": coin, "L": L, **a})
                if a["multiple"] > best[0]:
                    best = (a["multiple"], L)
            row["growth_optimal_L"] = best[1]
    r = pd.DataFrame(rows)
    p = 2 * norm.sf(np.abs(r["t"].fillna(0)))
    order = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * p[i]); adj[i] = min(run, 1.0)
    r["holm_p"] = adj
    is6 = r.signal.str.startswith("S6")
    r["g1"] = np.where(is6, r.trades >= 20, r.trades >= 200)
    r["g2"] = np.where(is6, (r.era1_cagr > 0) & (r.era2_cagr > 0), (r.era1_bp > 0) & (r.era2_bp > 0))
    r["g3"] = np.where(is6, True, (r.t >= 2.5) & (r.holm_p < 0.05))
    r["g4"] = r.stress_bp > 0
    r["passes"] = r[["g1", "g2", "g3", "g4"]].all(axis=1)
    L = pd.DataFrame(lev_rows)
    r.to_csv("research/crypto/levered_dev.csv", index=False, float_format="%.4f")
    L.to_csv("research/crypto/levered_dev_leverage.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    cols = ["signal", "coin", "trades", "mean_bp", "median_bp", "win", "t", "era1_bp", "era2_bp", "stress_bp", "funding_bp",
            "ratio", "avg_hours", "growth_optimal_L", "holm_p", "passes"]
    print(r[cols].round(3).to_string(index=False))
    piv = L.pivot_table(index=["signal", "coin"], columns="L", values="multiple", sort=False)
    print("\nfinal multiple of the starting balance, development 2020-2023, by leverage (liquidations included)")
    print(piv.round(2).to_string())
    liq = L.pivot_table(index=["signal", "coin"], columns="L", values="liquidations", sort=False)
    print("\nliquidations"); print(liq.to_string())
    print(f"\ntrials passing every gate: {int(r.passes.sum())} of {len(r)}")


if __name__ == "__main__":
    main()
