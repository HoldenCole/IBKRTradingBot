"""Backtest engine for the quadrant rotation — reproduces the official
tier numbers (evidence used in TESTS.md / PORTFOLIOS.md / the workbook).

Rebuilt in-repo 2026-09-23 after the scratchpad copy was lost. Data is
fetched from Yahoo (adjusted closes, granularity-asserted) and cached
under research/cache/ (gitignored). Conventions are unchanged:
  * classifier: quadrant_series (SPY/DBC vs 10m SMA, completed months)
  * levered ETFs simulated as N*daily - (N-1)*(rf+100bp)/252 - 0.95%/252
    (ERX modeled 2x; SCO real from Nov 2008, synthetic -2x USO before)
  * aux signals monthly: TLT 10m trend, 6m momentum tilt, breadth washout
  * stats: CAGR; Sortino = CAGR/ann downside dev; maxDD on daily series
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.yahoo import fetch_yahoo_daily_window  # noqa: E402
from src.portfolio.matrix import R_TILT, TIERS, resolve_allocation  # noqa: E402
from src.regime.quadrant import Quadrant, quadrant_series  # noqa: E402

CACHE = ROOT / "research" / "cache"
START, END = "2005-06-01", "2026-12-31"
BREADTH = ["XLE", "XLY", "XLF", "XLK", "XLI", "XLB", "XLV", "XLU", "XLP", "IYR",
           "XRT", "XHB", "ITB", "KRE", "IYT", "SMH", "GDX", "XBI"]
CORE = ["SPY", "QQQ", "TLT", "GLD", "DBC", "USO", "SHY", "IEF", "XLE", "GDX", "XLP", "SCO", "^IRX"]
QMAP = {Quadrant.GROWTH: "G", Quadrant.REFLATION: "R",
        Quadrant.STAGFLATION: "S", Quadrant.DEFLATION: "D"}


def price(symbol: str) -> pd.Series:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{symbol.replace('^', '')}.csv"
    if f.exists():
        return pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
    s = fetch_yahoo_daily_window(symbol, START, END)
    s.to_frame(symbol).to_csv(f)
    time.sleep(0.3)
    return s


def load_all() -> pd.DataFrame:
    cols = {}
    for sym in sorted(set(CORE) | set(BREADTH)):
        try:
            cols[sym] = price(sym)
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: fetch failed ({exc})", file=sys.stderr)
    return pd.DataFrame(cols).sort_index()


def build(px: pd.DataFrame, first_stamp: str = "2006-12-01"):
    rets = px.drop(columns=["^IRX"]).pct_change()
    rf = (px["^IRX"] / 100 / 252).reindex(rets.index).ffill().fillna(0.0)

    def lev(base, n):
        return n * rets[base] - (n - 1) * (rf + 0.01 / 252) - 0.0095 / 252

    rets["QLD"] = lev("QQQ", 2); rets["TQQQ"] = lev("QQQ", 3)
    rets["TMF"] = lev("TLT", 3); rets["ERX"] = lev("XLE", 2)
    sco_synth = -2 * rets["USO"] + rf - 0.0095 / 252
    rets["SCO"] = sco_synth.where(rets["SCO"].isna(), rets["SCO"])
    rets["ERY"] = -2 * rets["XLE"] + rf - 0.0095 / 252

    flags = {s: (px[s].resample("ME").last().dropna() > px[s].resample("ME").last().dropna().rolling(10).mean())
             for s in BREADTH if s in px}
    fdf = pd.DataFrame(flags)
    washout = (fdf.sum(axis=1) / fdf.notna().sum(axis=1)) < 0.25

    q = quadrant_series(px["SPY"].dropna(), px["DBC"].dropna())
    tlt_m = px["TLT"].resample("ME").last()
    mm = {a: px[a].resample("ME").last() for a in sorted({x for t in R_TILT.values() for x in t}) if a in px}
    stamps = q.index
    tier_daily, months = {}, []
    for tier in TIERS:
        parts = []
        for i, st in enumerate(stamps):
            if st < pd.Timestamp(first_stamp):
                continue
            quad = q.loc[st]
            h = tlt_m.loc[:st].dropna()
            tlt_up = bool(h.iloc[-1] > h.tail(10).mean()) if len(h) >= 10 else None
            mom = {a: float(s.loc[:st].dropna().iloc[-1] / s.loc[:st].dropna().iloc[-7] - 1)
                   for a, s in mm.items() if len(s.loc[:st].dropna()) > 6}
            pw = washout.index[washout.index <= st]
            wo = bool(washout.loc[pw[-1]]) if len(pw) else None
            w = resolve_allocation(tier, quad, tlt_up, mom, include_shorts=True, breadth_washout=wo)
            nxt = stamps[i + 1] if i + 1 < len(stamps) else rets.index[-1]
            win = rets.loc[(rets.index > st) & (rets.index <= nxt)]
            if win.empty:
                continue
            parts.append(sum(win[a].fillna(0.0) * wt for a, wt in w.items()))
            if tier == TIERS[0]:
                months.append((st, QMAP[quad], w))
        tier_daily[tier] = pd.concat(parts)
    return rets, q, tier_daily, months


def headline(r: pd.Series) -> dict:
    r = r.dropna(); yrs = len(r) / 252
    cagr = (1 + r).prod() ** (1 / yrs) - 1
    dn = r[r < 0].std() * np.sqrt(252)
    eq = (1 + r).cumprod()
    return {"CAGR": cagr, "Sortino": cagr / dn, "maxDD": float((eq / eq.cummax() - 1).min())}


def drawdown_episodes(r: pd.Series, n: int = 4) -> list[dict]:
    eq = (1 + r.dropna()).cumprod()
    dd = eq / eq.cummax() - 1
    episodes, in_dd, start = [], False, None
    for t, v in dd.items():
        if not in_dd and v < 0:
            in_dd, start = True, t
        elif in_dd and v == 0:
            seg = dd.loc[start:t]
            episodes.append({"peak": start, "trough": seg.idxmin(), "depth": float(seg.min()), "recovered": t})
            in_dd = False
    if in_dd:
        seg = dd.loc[start:]
        episodes.append({"peak": start, "trough": seg.idxmin(), "depth": float(seg.min()), "recovered": None})
    return sorted(episodes, key=lambda e: e["depth"])[:n]


if __name__ == "__main__":
    px = load_all()
    rets, q, tier_daily, months = build(px)
    print("window:", tier_daily["MOD"].index[0].date(), "->", tier_daily["MOD"].index[-1].date())
    official = {"CONS": (0.097, 1.60, -0.102), "MOD": (0.153, 1.72, -0.143),
                "AGG": (0.246, 1.26, -0.342), "VAGG": (0.324, 1.11, -0.470)}
    for t in TIERS:
        h = headline(tier_daily[t]); o = official[t]
        print(f"  {t:>4}: CAGR {h['CAGR']:+.1%} (official {o[0]:+.1%})  Sortino {h['Sortino']:.2f} ({o[1]:.2f})  "
              f"maxDD {h['maxDD']:.1%} ({o[2]:.1%})")
