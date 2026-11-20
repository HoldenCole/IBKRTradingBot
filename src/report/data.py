"""Data layer for the weekly PDF report. Everything the charts and tables
need, gathered once. Network: Yahoo chart API (no key). Member sweeps are
cached under research/cache/ for 12 hours so a rebuild is fast.
"""
from __future__ import annotations

import pickle
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.yahoo import fetch_yahoo_daily
from src.portfolio import trend_cycle as tc

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "research" / "cache"
MAX_AGE_S = 12 * 3600

INDICES = [("S&P 500", "^GSPC"), ("Nasdaq-100", "^NDX"), ("Russell 2000", "^RUT"),
           ("Dow Industrials", "^DJI"), ("S&P 500 equal weight", "RSP")]
SECTORS = [("Technology", "XLK"), ("Communication", "XLC"), ("Discretionary", "XLY"), ("Financials", "XLF"),
           ("Industrials", "XLI"), ("Materials", "XLB"), ("Energy", "XLE"), ("Health care", "XLV"),
           ("Staples", "XLP"), ("Utilities", "XLU"), ("Real estate", "XLRE")]
MACRO = [("US 10-year yield", "^TNX", "yield"), ("US 30-year yield", "^TYX", "yield"), ("US 5-year yield", "^FVX", "yield"),
         ("US 3-month bill", "^IRX", "yield"), ("Dollar index", "DX-Y.NYB", "price"), ("EUR/USD", "EURUSD=X", "fx"),
         ("USD/JPY", "JPY=X", "price"), ("VIX", "^VIX", "level"), ("MOVE (bond vol)", "^MOVE", "level"),
         ("High-yield bonds (HYG)", "HYG", "price"), ("Long Treasuries (TLT)", "TLT", "price")]
COMMODITIES = [("WTI crude", "CL=F"), ("Brent crude", "BZ=F"), ("Natural gas", "NG=F"), ("Gold", "GC=F"),
               ("Silver", "SI=F"), ("Copper", "HG=F"), ("Commodity index (DBC)", "DBC"),
               ("Energy equities (XLE)", "XLE"), ("Gold miners (GDX)", "GDX")]
EXTRA = ["SPY", "QQQ", "DBC", "XLE", "GDX", "TLT"]


def _cached(name: str, builder):
    f = CACHE / name
    if f.exists() and time.time() - f.stat().st_mtime < MAX_AGE_S:
        return pickle.load(open(f, "rb"))
    out = builder()
    CACHE.mkdir(parents=True, exist_ok=True)
    pickle.dump(out, open(f, "wb"))
    return out


def _ret(s: pd.Series, asof_prev: pd.Timestamp) -> float:
    base = s[s.index <= asof_prev]
    return float(s.iloc[-1] / base.iloc[-1] - 1) if len(base) else float("nan")


def perf_row(name: str, sym: str, s: pd.Series, anchors: dict, kind: str = "price") -> dict:
    last = float(s.iloc[-1])
    row = {"name": name, "sym": sym, "last": last, "kind": kind}
    for k, a in anchors.items():
        base = s[s.index <= a]
        if not len(base):
            row[k] = float("nan"); continue
        row[k] = (last - float(base.iloc[-1])) * 100 if kind == "yield" else last / float(base.iloc[-1]) - 1
    year = s.tail(252)
    row["off_high"] = last / float(year.max()) - 1
    row["vs200"] = last / float(s.tail(200).mean()) - 1 if len(s) >= 200 else float("nan")
    return row


def z5(s: pd.Series) -> float:
    r = np.log(s).diff()
    sig = r.rolling(60).std().shift(5)
    return float(np.log(s.iloc[-1] / s.iloc[-6]) / (sig.iloc[-1] * np.sqrt(5)))


def balance_history(member_daily: dict[str, pd.Series], member_monthly: dict[str, pd.Series]) -> dict[str, pd.DataFrame]:
    """% of members per quadrant through time, per bar size, for both oscillators."""
    out = {}
    for tf in ("D", "W", "M"):
        src = member_monthly if tf == "M" else member_daily
        cols = {}
        for short, fn in (("cyc", tc.cycle), ("trd", tc.trend)):
            Q = pd.DataFrame({k: tc.quadrants(fn(v if tf == "M" else tc.to_bars(v, tf))) for k, v in src.items()})
            n = Q.notna().sum(axis=1)
            for q in (1, 2, 3, 4):
                cols[f"{short}_q{q}"] = (Q == q).sum(axis=1) / n * 100
            cols[f"{short}_n"] = n
        df = pd.DataFrame(cols)
        out[tf] = df[df["cyc_n"] >= 100]
    return out


def classifier_history(spy: pd.Series, dbc: pd.Series) -> pd.DataFrame:
    """Daily distance of SPY and DBC from the 10-month rule's boundary (mean of the prior 9 completed month-end closes)."""
    out = {}
    for name, s in (("spy", spy), ("dbc", dbc)):
        m = s.resample("ME").last()
        thr_m = m.shift(1).rolling(9).mean()          # threshold in force during each month
        thr = thr_m.reindex(s.index, method="bfill")  # month-end stamp governs that month's days
        out[name] = s / thr - 1
    return pd.DataFrame(out).dropna()


def gather(verbose: bool = True) -> dict:
    def say(x):
        if verbose:
            print(x, flush=True)

    d: dict = {}
    syms = sorted({s for _, s in INDICES} | {s for _, s in SECTORS} | {s for _, s, _ in MACRO}
                  | {s for _, s in COMMODITIES} | set(EXTRA))
    say(f"prices: {len(syms)} series")
    px = {}
    for s in syms:
        try:
            px[s] = fetch_yahoo_daily(s, rng="2y")
        except Exception as exc:  # noqa: BLE001
            say(f"  {s}: failed ({exc})")
    d["px"] = px
    asof = px["SPY"].index[-1]
    d["asof"] = asof
    wk_prev = px["SPY"].index[-6]
    anchors = {"wk": wk_prev, "mtd": asof.replace(day=1) - pd.Timedelta(days=1),
               "ytd": pd.Timestamp(asof.year, 1, 1) - pd.Timedelta(days=1)}
    d["anchors"] = anchors
    d["week_start"] = px["SPY"].index[-5]

    d["indices"] = [perf_row(n, s, px[s], anchors) for n, s in INDICES if s in px]
    d["sectors"] = [perf_row(n, s, px[s], anchors) for n, s in SECTORS if s in px]
    d["macro"] = [perf_row(n, s, px[s], anchors, k) for n, s, k in MACRO if s in px]
    d["commodities"] = [perf_row(n, s, px[s], anchors) for n, s in COMMODITIES if s in px]
    for r in d["commodities"]:
        s = px[r["sym"]]
        r["z5"] = z5(s); r["vs210"] = float(s.iloc[-1] / s.tail(210).mean() - 1)

    # --- quadrant balances: index states (long unadjusted closes) and member balances
    say("quadrant balances: index states")
    d["idx_close"] = {name: tc.fetch_close(sym, rng="10y") for name, sym in (("S&P 500", "^GSPC"), ("Nasdaq-100", "^NDX"))}
    d["states"] = {name: tc.index_states(c) for name, c in d["idx_close"].items()}
    d["idx_monthly"] = {name: tc.fetch_bars(sym, "1mo", "1995-01-01") for name, sym in (("S&P 500", "^GSPC"), ("Nasdaq-100", "^NDX"))}
    d["sector_states"] = {}
    for n, s in SECTORS:
        try:
            d["sector_states"][s] = tc.index_states(tc.fetch_close(s, rng="10y"))
        except Exception:  # noqa: BLE001
            pass
    say("quadrant balances: member sweep (cached 12h)")
    member_daily = _cached("report_members_1d.pkl", lambda: tc.fetch_member_closes(tc.fetch_sp500_members()))
    fetch_bars = tc.fetch_bars

    def monthly():
        out = {}
        for sym in member_daily:
            try:
                out[sym] = fetch_bars(sym, "1mo", start="2000-01-01")
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)
        return out
    member_monthly = _cached("report_members_1mo.pkl", monthly)
    d["balances"] = tc.quadrant_balances(member_daily)
    d["balance_hist"] = balance_history(member_daily, member_monthly)
    d["flag"] = tc.market_flag(d["states"]["S&P 500"], d["balances"])
    d["n_members"] = len(member_daily)

    # --- regime model: the two dials only. The report is shareable research, so it reads no ledger,
    # no allocations, no paper accounts and no overrides.
    say("regime model")
    d["classifier"] = classifier_history(px["SPY"], px["DBC"])
    cl = d["classifier"]
    names = {(True, True): "REFLATION", (True, False): "GROWTH", (False, True): "STAGFLATION", (False, False): "DEFLATION"}
    me = cl.groupby(cl.index.to_period("M")).last()
    this_m = asof.to_period("M")
    prior = me.loc[me.index < this_m].iloc[-1]
    d["month"] = str(this_m)
    d["in_force"] = names[(bool(prior["spy"] > 0), bool(prior["dbc"] > 0))]
    d["prov_month"] = str(this_m + 1)
    d["prov_quadrant"] = names[(bool(cl["spy"].iloc[-1] > 0), bool(cl["dbc"].iloc[-1] > 0))]
    d["to_boundary"] = {}
    for k, sym in (("spy", "SPY"), ("dbc", "DBC")):
        mclose = px[sym].resample("ME").last().dropna()
        d["to_boundary"][k] = float(mclose.iloc[-10:-1].mean() / px[sym].iloc[-1] - 1)
    return d


if __name__ == "__main__":
    data = gather()
    print("asof", data["asof"].date(), "| flag", data["flag"], "| prov", data["prov_quadrant"])
    for tf, df in data["balance_hist"].items():
        print(tf, df.index[0].date(), "->", df.index[-1].date(), len(df), df.iloc[-1][["cyc_q4", "trd_q4"]].round(1).to_dict())
    pickle.dump(data, open(CACHE / "report_data.pkl", "wb"))
