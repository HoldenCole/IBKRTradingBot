"""Swing-study library: indicators, daily regime labels, trade simulator, stats.

Conventions (pre-registered, see TESTS.md entry 75):
  * signals use information through the close of day t only
  * entry 'close' = fill at close t (MOC; signal measured at ~15:50 is a
    close proxy); entry 'open' = fill at open t+1 (conservative check)
  * exits fill at the close of the day the exit rule is true, or at the
    time-stop close; one position per asset, no stacking
  * cost = COST_BPS per side (commission + half-spread)
  * eras: A 1999-2006, B 2007-2016, C 2017-2026 (ETF data); index-only
    history 1987-1998 is reported separately where an index suffices
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.regime.quadrant import Quadrant, quadrant_series  # noqa: E402
from research.swing.data import load  # noqa: E402

COST_BPS = 5.0
ERAS = {"A 99-06": ("1999-01-01", "2006-12-31"),
        "B 07-16": ("2007-01-01", "2016-12-31"),
        "C 17-26": ("2017-01-01", "2026-12-31")}
QMAP = {Quadrant.GROWTH: "G", Quadrant.REFLATION: "R",
        Quadrant.STAGFLATION: "S", Quadrant.DEFLATION: "D"}


# ---------- indicators ----------
def sma(s, n): return s.rolling(n).mean()


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    up, lo = mid + k * sd, mid - k * sd
    pctb = (close - lo) / (up - lo)
    bw = (up - lo) / mid
    return mid, up, lo, pctb, bw


def rsi(close: pd.Series, n: int = 2) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def ibs(df: pd.DataFrame) -> pd.Series:
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return (df["close"] - df["low"]) / rng


# ---------- regime labels ----------
def daily_quadrant(data: dict) -> pd.Series:
    """Quadrant in force on each trading day (G/R/S/D), ex-ante monthly.
    Dials: ^GSPC/^SPGSCI through 2006, SPY/DBC from 2007 (the two engines)."""
    old = quadrant_series(data["^GSPC"]["close"], data["^SPGSCI"]["close"])
    new = quadrant_series(data["SPY"]["close"], data["DBC"]["close"])
    q = pd.concat([old[old.index < "2006-12-31"], new[new.index >= "2006-12-31"]])
    q = q.map(QMAP)
    q.index = q.index.to_period("M") + 1          # stamp at end of M-1 governs month M
    days = data["^GSPC"].index
    lab = pd.Series(days.to_period("M").map(q.to_dict()), index=days, name="quad")
    return lab


def daily_features(data: dict) -> pd.DataFrame:
    spy = data["^GSPC"]["close"]
    f = pd.DataFrame(index=spy.index)
    f["quad"] = daily_quadrant(data)
    f["spy_above_200"] = spy > sma(spy, 200)
    f["spy_ext200"] = spy / sma(spy, 200) - 1
    f["rvol20"] = spy.pct_change().rolling(20).std() * np.sqrt(252)
    f["vix"] = data["^VIX"]["close"].reindex(spy.index).ffill()
    secs = ["XLE", "XLF", "XLK", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB"]
    above = pd.DataFrame({s: (data[s]["close"] > sma(data[s]["close"], 200)) for s in secs}).reindex(spy.index)
    valid = pd.DataFrame({s: sma(data[s]["close"], 200).notna() for s in secs}).reindex(spy.index).fillna(False)
    f["breadth200"] = (above.where(valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan))
    return f


# ---------- trade simulator ----------
def simulate(df: pd.DataFrame, entry: pd.Series, exit_: pd.Series, max_hold: int,
             mode: str = "close", cost_bps: float = COST_BPS, stop: float | None = None):
    """Returns (trades DataFrame, daily strategy return Series incl. costs)."""
    o, c, lo = df["open"].values, df["close"].values, df["low"].values
    e = entry.reindex(df.index).fillna(False).values
    x = exit_.reindex(df.index).fillna(False).values
    n = len(df); cost = cost_bps / 1e4
    daily = np.zeros(n); rows = []
    i = 0
    while i < n - 1:
        if not e[i]:
            i += 1; continue
        if mode == "close":
            ei, epx = i, c[i]
            first = i + 1
        else:
            ei, epx = i + 1, o[i + 1]
            daily[i + 1] += c[i + 1] / o[i + 1] - 1
            first = i + 2
        daily[ei if mode == "close" else i + 1] -= cost
        j = first; xpx = None; why = None
        if mode == "open" and x[i + 1]:
            j = i + 1; xpx = c[j]; why = "rule"
        while xpx is None:
            if j >= n:
                j = n - 1; xpx = c[j]; why = "eod"; break
            if stop is not None and lo[j] <= epx * (1 - stop):
                spx = min(o[j], epx * (1 - stop))
                daily[j] += spx / c[j - 1] - 1; xpx = spx; why = "stop"; break
            daily[j] += c[j] / c[j - 1] - 1
            if x[j]:
                xpx = c[j]; why = "rule"
            elif j - ei >= max_hold:
                xpx = c[j]; why = "time"
            else:
                j += 1
        daily[j] -= cost
        rows.append((df.index[i], df.index[ei], df.index[j], j - ei, xpx / epx - 1 - 2 * cost, why))
        i = j + 1
    tr = pd.DataFrame(rows, columns=["signal", "entry", "exit", "days", "ret", "why"])
    return tr, pd.Series(daily, index=df.index)


# ---------- stats ----------
def tstats(r: pd.Series | np.ndarray) -> dict:
    r = np.asarray(r, dtype=float)
    if len(r) == 0:
        return {"n": 0, "mean_bps": np.nan, "win": np.nan, "t": np.nan, "pf": np.nan}
    g, l = r[r > 0].sum(), -r[r < 0].sum()
    t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 and r.std(ddof=1) > 0 else np.nan
    return {"n": len(r), "mean_bps": r.mean() * 1e4, "win": (r > 0).mean(), "t": t,
            "pf": g / l if l > 0 else np.inf}


def era_of(ts: pd.Timestamp) -> str | None:
    for k, (a, b) in ERAS.items():
        if pd.Timestamp(a) <= ts <= pd.Timestamp(b):
            return k
    return "pre-99" if ts < pd.Timestamp("1999-01-01") else None


def perf(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 60:
        return {}
    yrs = len(r) / 252
    eq = (1 + r).cumprod()
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    dn = r[r < 0].std() * np.sqrt(252)
    return {"CAGR": cagr, "vol": vol, "Sharpe": (r.mean() * 252) / vol if vol else np.nan,
            "Sortino": cagr / dn if dn else np.nan, "maxDD": float((eq / eq.cummax() - 1).min())}


def fmt(d: dict) -> str:
    if not d or d.get("n", 1) == 0:
        return "n=0"
    return (f"n={d['n']:5d} mean {d['mean_bps']:+6.1f}bp win {d['win']:.0%} "
            f"t={d['t']:+.2f} pf={d['pf']:.2f}")


if __name__ == "__main__":
    data = load()
    f = daily_features(data)
    print(f.dropna().tail(3))
    print(f["quad"].value_counts(dropna=False))
    print(f.loc["2026-09-01":, "quad"].resample("ME").last())
