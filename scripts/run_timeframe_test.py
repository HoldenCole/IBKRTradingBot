"""Timeframe variation test — four signal frequencies on the trend rule.

Tests whether a different signal timeframe should replace daily 50/200 as the
deployment baseline. Four variations, on both the equity sleeve (^GSPC, 98yr,
the deployment's long-history proxy) and the BTC sleeve (BTC-USD, 11.6yr):

  1. Daily 50/200            — current baseline (validated)
  2. Weekly 10/40            — ~calendar-equivalent to daily 50/200
  3. Weekly 50/200           — much slower (~1yr vs ~4yr trend)
  4. Daily 50/200 acted wkly — daily signal, position changes only on wk close

Same framework conventions as the prior research:
  - Trend rule: ON iff close>SMA_fast AND SMA_fast>SMA_slow
  - Convention 2 (no look-ahead): signal at close[t-1] governs return[t].
    For weekly-acted variants: signal at week-end governs the FOLLOWING week.
  - T-bill OFF: FRED TB3MS, monthly -> daily compounding factor.
  - Costs on: per-transition bps (equity 5, BTC 10) + BTC IBIT 0.25%/yr expense.
  - Metrics: CAGR, Sortino (LPM2, target 0), Calmar (CAGR/|maxDD|), max DD.
  - Whipsaw rate: state transitions per year (the key metric).
  - After-tax CAGR: annual-realization ST/LT model (ST 37%, LT 20%, T-bill
    interest ordinary), losses carried forward. Captures turnover tax drag.

Data is read from data/cache/*.csv (pulled once via httpx from Yahoo v8 +
FRED; see the cache-pull in the session log). ^GSPC and BTC-USD are
price-only/settlement closes — same caveat as the long-history study.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
CACHE = REPO / "data" / "cache"

# ---- tax + cost assumptions (stated, not tuned) ----
ST_RATE = 0.37       # short-term / ordinary (top bracket, matches deploy tax note)
LT_RATE = 0.20       # long-term cap gains (top bracket)
EQUITY_TRANSITION_BPS = 5.0
BTC_TRANSITION_BPS = 10.0
BTC_EXPENSE_ANNUAL = 0.0025   # IBIT ~0.25%/yr while held (crypto engine convention)


# =====================================================================
# Data — cached CSVs; auto-pull from Yahoo v8 + FRED if missing.
# (Yahoo rate-limits shared IPs; a cookie warm-up + pacing makes it reliable.
#  yfinance's curl_cffi backend does NOT honor the agent-proxy CA bundle, so
#  we hit the v8 chart API directly over httpx.)
# =====================================================================
_YF_TARGETS = {
    "^GSPC":   ("1927-12-01", "2026-04-14"),
    "QQQ":     ("1999-03-01", "2026-04-14"),
    "BTC-USD": ("2014-09-01", "2026-04-14"),
}
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/121.0 Safari/537.36")


def _pull_yahoo(symbol: str, start: str, end: str) -> None:
    import time, httpx
    from datetime import datetime, timezone

    def ts(d):
        return int(datetime.strptime(d, "%Y-%m-%d")
                   .replace(tzinfo=timezone.utc).timestamp())
    with httpx.Client(headers={"User-Agent": _UA}, timeout=60.0,
                      follow_redirects=True) as c:
        c.get("https://fc.yahoo.com"); time.sleep(3)   # warm cookie
        last = None
        for i in range(6):
            host = "query2" if i % 2 else "query1"
            url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
                   f"?period1={ts(start)}&period2={ts(end)}&interval=1d")
            try:
                r = c.get(url)
                if r.status_code == 429 or "Too Many" in r.text[:40]:
                    last = "429"; time.sleep(10 * (i + 1)); continue
                r.raise_for_status()
                res = r.json()["chart"]["result"][0]
                q = res["indicators"]["quote"][0]
                from datetime import datetime as dt
                idx = pd.to_datetime([dt.fromtimestamp(t, tz=timezone.utc).date()
                                      for t in res["timestamp"]])
                df = pd.DataFrame({"open": q["open"], "high": q["high"],
                                   "low": q["low"], "close": q["close"],
                                   "volume": q["volume"]}, index=idx)
                df.index.name = "date"
                df.dropna(subset=["close"]).to_csv(
                    CACHE / f"{symbol.replace('^', '_')}.csv")
                return
            except Exception as e:
                last = repr(e)[:150]; time.sleep(8 * (i + 1))
        raise RuntimeError(f"Yahoo pull {symbol} failed: {last}")


def _pull_tb3ms() -> None:
    import io, httpx
    r = httpx.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=TB3MS",
                  timeout=30.0)
    r.raise_for_status()
    tb = pd.read_csv(io.StringIO(r.text))
    tb.columns = ["date", "tb3ms"]
    tb = tb[tb["tb3ms"] != "."].copy()
    tb.to_csv(CACHE / "TB3MS.csv", index=False)


def ensure_cached() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    import time
    for sym, (s, e) in _YF_TARGETS.items():
        if not (CACHE / f"{sym.replace('^', '_')}.csv").exists():
            print(f"  pulling {sym} from Yahoo...")
            _pull_yahoo(sym, s, e); time.sleep(6)
    if not (CACHE / "TB3MS.csv").exists():
        print("  pulling TB3MS from FRED...")
        _pull_tb3ms()


def load_close(symbol: str) -> pd.Series:
    fn = CACHE / f"{symbol.replace('^', '_')}.csv"
    df = pd.read_csv(fn, parse_dates=["date"]).set_index("date")
    return df["close"].astype(float).dropna()


def load_tbill_daily(idx: pd.DatetimeIndex) -> pd.Series:
    tb = pd.read_csv(CACHE / "TB3MS.csv", parse_dates=["date"]).set_index("date")["tb3ms"]
    rate = tb.reindex(idx, method="ffill").bfill().fillna(0.0)   # % annual
    return (1.0 + rate / 100.0) ** (1.0 / 252.0) - 1.0            # daily factor


# =====================================================================
# Signals -> daily no-lookahead position
# =====================================================================
def _on_flags(close: pd.Series, fast: int, slow: int) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def position_daily(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    """Var 1: daily signal, acted daily. Convention 2 -> shift(1)."""
    return _on_flags(close, fast, slow).shift(1).fillna(False).astype(bool)


def position_weekly_ma(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """Vars 2/3: SMA on WEEKLY closes. Weekly signal at Friday close governs the
    FOLLOWING week (no look-ahead): ffill weekly flag onto daily grid, then
    shift one trading day so the new signal first applies next session."""
    wclose = close.resample("W-FRI").last().dropna()
    wflag = _on_flags(wclose, fast, slow)
    daily = wflag.reindex(close.index, method="ffill")
    return daily.shift(1).fillna(False).astype(bool)


def position_daily_acted_weekly(close: pd.Series, fast: int = 50,
                                slow: int = 200) -> pd.Series:
    """Var 4: daily 50/200 signal, but position only changes on the weekly
    close. Sample the daily flag at each week-end, then apply to the following
    week (same no-look-ahead mapping as the weekly-MA variants)."""
    daily_flag = _on_flags(close, fast, slow)
    week_end_flag = daily_flag.resample("W-FRI").last()
    daily = week_end_flag.reindex(close.index, method="ffill")
    return daily.shift(1).fillna(False).astype(bool)


VARIATIONS = {
    "daily_50_200":        lambda c: position_daily(c, 50, 200),
    "weekly_10_40":        lambda c: position_weekly_ma(c, 10, 40),
    "weekly_50_200":       lambda c: position_weekly_ma(c, 50, 200),
    "daily_50_200_wkly":   lambda c: position_daily_acted_weekly(c, 50, 200),
}
VAR_LABELS = {
    "daily_50_200":      "1. Daily 50/200 (baseline)",
    "weekly_10_40":      "2. Weekly 10/40",
    "weekly_50_200":     "3. Weekly 50/200",
    "daily_50_200_wkly": "4. Daily 50/200 acted weekly",
}


# =====================================================================
# Backtest (pre-tax) + metrics
# =====================================================================
@dataclass
class BTResult:
    equity: pd.Series
    daily_ret: pd.Series
    pos: pd.Series
    n_transitions: int
    years: float
    transitions_per_year: float


def run_backtest(close: pd.Series, pos: pd.Series, tbill_daily: pd.Series,
                 asset: str) -> BTResult:
    """Pre-tax equity with costs + T-bill OFF. `pos` is already lagged."""
    r = close.pct_change().fillna(0.0)
    pos = pos.reindex(close.index).fillna(False).astype(bool)
    trans_bps = EQUITY_TRANSITION_BPS if asset == "equity" else BTC_TRANSITION_BPS
    expense_daily = (BTC_EXPENSE_ANNUAL / 252.0) if asset == "btc" else 0.0

    on_ret = r - expense_daily
    daily = on_ret.where(pos, tbill_daily.reindex(close.index).fillna(0.0))
    flips = pos.ne(pos.shift(1)).fillna(False)
    # First bar isn't a real transition (no prior position); exclude it.
    if len(flips):
        flips.iloc[0] = False
    daily = daily - flips.astype(float) * (trans_bps / 1e4)

    equity = (1.0 + daily).cumprod()
    years = (close.index[-1] - close.index[0]).days / 365.25
    n_trans = int(flips.sum())
    tpy = n_trans / years if years > 0 else 0.0
    return BTResult(equity=equity, daily_ret=daily, pos=pos,
                    n_transitions=n_trans, years=years, transitions_per_year=tpy)


def metrics(equity: pd.Series, daily_ret: pd.Series, ann: int) -> dict:
    """CAGR (calendar), Sortino (LPM2, target 0), Calmar, max DD."""
    r = daily_ret.dropna()
    if len(r) < 2 or equity.empty:
        return {"cagr": 0.0, "sortino": 0.0, "calmar": 0.0, "max_dd": 0.0}
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    final_mult = float(equity.iloc[-1] / equity.iloc[0])
    cagr = final_mult ** (1.0 / max(years, 1e-9)) - 1.0
    downside = np.minimum(r.values, 0.0)
    dd_dev = np.sqrt(np.sum(downside ** 2) / len(r))
    sortino = float(r.mean() / dd_dev * np.sqrt(ann)) if dd_dev > 0 else 0.0
    rmax = equity.cummax()
    max_dd = float(((equity - rmax) / rmax).min())    # negative
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    return {"cagr": cagr, "sortino": sortino, "calmar": calmar, "max_dd": max_dd}


# =====================================================================
# After-tax: annual-realization ST/LT model
# =====================================================================
def after_tax_cagr(close: pd.Series, pos: pd.Series, tbill_daily: pd.Series,
                   asset: str) -> tuple[float, float]:
    """Simulate taxes paid annually. Risk-asset gains realized on EXIT (ST if
    held <=365 days, else LT); T-bill interest is ordinary income realized in
    the year earned. Net capital losses carry forward. Taxes are paid from the
    account at each year-end (drag on compounding). Returns (after_tax_cagr,
    pretax_cagr) — pretax must match run_backtest for reconciliation."""
    idx = close.index
    r = close.pct_change().fillna(0.0).values
    pos_a = pos.reindex(idx).fillna(False).astype(bool).values
    tb = tbill_daily.reindex(idx).fillna(0.0).values
    trans = (EQUITY_TRANSITION_BPS if asset == "equity" else BTC_TRANSITION_BPS) / 1e4
    expense_daily = (BTC_EXPENSE_ANNUAL / 252.0) if asset == "btc" else 0.0
    dates = [d.date() if hasattr(d, "date") else d for d in idx]

    C = 1.0             # after-tax account
    P = 1.0             # pretax account (reconciliation)
    basis = None        # entry after-tax capital of current risk holding
    basis_p = None
    entry_date = None
    st_gain = 0.0       # realized short-term capital gain/loss this year (after-tax $)
    lt_gain = 0.0
    interest = 0.0
    loss_carry = 0.0    # net capital-loss carryforward (positive number)
    prev_pos = False
    year = dates[0].year

    def settle(cap: float) -> float:
        nonlocal st_gain, lt_gain, interest, loss_carry
        # Offset net capital losses (carryforward + this year) against gains.
        net_cap = st_gain + lt_gain
        st_taxable, lt_taxable = st_gain, lt_gain
        if net_cap < 0:
            loss_carry += -net_cap
            st_taxable = lt_taxable = 0.0
        else:
            # apply carryforward, ST first (worst rate) then LT
            use = min(loss_carry, st_taxable)
            st_taxable -= use; loss_carry -= use
            use = min(loss_carry, lt_taxable)
            lt_taxable -= use; loss_carry -= use
        tax = max(0.0, st_taxable) * ST_RATE + max(0.0, lt_taxable) * LT_RATE
        tax += interest * ST_RATE           # ordinary income on T-bill
        st_gain = lt_gain = interest = 0.0
        return cap - tax

    for i in range(len(idx)):
        if dates[i].year != year:
            C = settle(C)
            year = dates[i].year
        flip = (pos_a[i] != prev_pos) and i > 0
        if pos_a[i]:
            if basis is None:
                basis, basis_p, entry_date = C, P, dates[i]
            C *= (1.0 + r[i] - expense_daily)
            P *= (1.0 + r[i] - expense_daily)
        else:
            if basis is not None:      # just exited -> realize
                gain = C - basis
                held = (dates[i] - entry_date).days
                if held > 365:
                    lt_gain += gain
                else:
                    st_gain += gain
                basis = basis_p = entry_date = None
            C *= (1.0 + tb[i]); P *= (1.0 + tb[i])
            interest += C * tb[i] / (1.0 + tb[i])   # interest portion earned today
        if flip:
            C *= (1.0 - trans); P *= (1.0 - trans)
        prev_pos = pos_a[i]

    # Final settle: realize any open position's unrealized gain? No — unrealized
    # is not taxed. Just settle the accrued realized items.
    C = settle(C)
    years = (idx[-1] - idx[0]).days / 365.25
    at_cagr = C ** (1.0 / max(years, 1e-9)) - 1.0
    pretax_cagr = P ** (1.0 / max(years, 1e-9)) - 1.0
    return at_cagr, pretax_cagr


# =====================================================================
# Period / stress slicing
# =====================================================================
def slice_by_dates(s: pd.Series, ps: date, pe: date) -> pd.Series:
    d = pd.Series([ps <= (x.date() if hasattr(x, "date") else x) <= pe
                   for x in s.index], index=s.index)
    return s.loc[d]


def event_dd(equity: pd.Series, ps: date, pe: date) -> float:
    sub = slice_by_dates(equity, ps, pe)
    if sub.empty:
        return 0.0
    return float(((sub.cummax() - sub) / sub.cummax()).max())


EQUITY_PERIODS = [
    ("1928-1949 Depression+WWII", date(1928, 12, 30), date(1949, 12, 31)),
    ("1950-1965 Post-war bull",   date(1950, 1, 3),   date(1965, 12, 31)),
    ("1966-1982 Secular bear",    date(1966, 1, 3),   date(1982, 12, 31)),
    ("1983-1999 Disinflationary", date(1983, 1, 3),   date(1999, 12, 31)),
    ("2000-2009 Dotcom+GFC",      date(2000, 1, 3),   date(2009, 12, 31)),
    ("2010-2017 Post-GFC",        date(2010, 1, 4),   date(2017, 12, 31)),
    ("2018-2026 Modern",          date(2018, 1, 2),   date(2026, 4, 14)),
]
EQUITY_STRESS = [
    ("1929 Crash",        date(1929, 9, 16), date(1932, 6, 1)),
    ("1973-74 oil bear",  date(1973, 1, 11), date(1974, 12, 6)),
    ("1987 Black Monday", date(1987, 8, 25), date(1987, 12, 4)),
    ("2000-2002 dotcom",  date(2000, 3, 24), date(2002, 10, 9)),
    ("2008-2009 GFC",     date(2008, 9, 1),  date(2009, 3, 9)),
    ("2020 COVID",        date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation",    date(2022, 1, 3),  date(2022, 10, 13)),
]
BTC_PERIODS = [
    ("2015-2016 recovery",  date(2015, 1, 1),  date(2016, 12, 31)),
    ("2017 ICO boom",       date(2017, 1, 1),  date(2017, 12, 31)),
    ("2018 bear",           date(2018, 1, 1),  date(2018, 12, 31)),
    ("2019-2020 chop",      date(2019, 1, 1),  date(2020, 9, 30)),
    ("2020-21 retail boom", date(2020, 10, 1), date(2021, 11, 30)),
    ("2022 contagion",      date(2022, 1, 1),  date(2022, 12, 31)),
    ("2023+ ETF era",       date(2023, 1, 1),  date(2026, 4, 14)),
]
BTC_STRESS = [
    ("2018 bear",         date(2018, 1, 6),  date(2018, 12, 15)),
    ("2020 COVID",        date(2020, 2, 12), date(2020, 3, 13)),
    ("2021 May crash",    date(2021, 4, 14), date(2021, 7, 20)),
    ("2022 LUNA/3AC",     date(2022, 3, 28), date(2022, 6, 18)),
    ("2022 FTX collapse", date(2022, 11, 5), date(2022, 11, 21)),
]


def period_metrics(daily_ret: pd.Series, pos: pd.Series, ps: date, pe: date,
                   ann: int) -> dict:
    """Metrics on a period slice: rebuild equity within the slice, count
    transitions within the slice."""
    sub_r = slice_by_dates(daily_ret, ps, pe)
    sub_pos = slice_by_dates(pos, ps, pe)
    if len(sub_r) < 60:
        return {"cagr": None, "sortino": None, "calmar": None, "max_dd": None,
                "tpy": None, "n": len(sub_r)}
    eq = (1.0 + sub_r).cumprod()
    m = metrics(eq, sub_r, ann)
    flips = sub_pos.ne(sub_pos.shift(1)).fillna(False)
    if len(flips):
        flips.iloc[0] = False
    yrs = (sub_r.index[-1] - sub_r.index[0]).days / 365.25
    m["tpy"] = int(flips.sum()) / yrs if yrs > 0 else 0.0
    m["n"] = len(sub_r)
    return m


def bah_metrics(close: pd.Series, ann: int) -> dict:
    r = close.pct_change().fillna(0.0)
    eq = (1.0 + r).cumprod()
    return metrics(eq, r, ann)


def run_asset(name: str, symbol: str, ann: int, periods, stress) -> dict:
    close = load_close(symbol)
    tbill = load_tbill_daily(close.index)
    print("\n" + "=" * 100)
    print(f"ASSET: {name}  ({symbol})   {close.index[0].date()} -> {close.index[-1].date()}"
          f"   ({(close.index[-1]-close.index[0]).days/365.25:.1f} yr, {len(close):,} bars)")
    print("=" * 100)

    bah = bah_metrics(close, ann)
    print(f"  Buy&hold reference: CAGR={bah['cagr']:+.1%} Sortino={bah['sortino']:.2f} "
          f"Calmar={bah['calmar']:.2f} maxDD={bah['max_dd']:.0%}")

    results = {}
    for key, fn in VARIATIONS.items():
        pos = fn(close)
        res = run_backtest(close, pos, tbill, name)
        m = metrics(res.equity, res.daily_ret, ann)
        at, _ = after_tax_cagr(close, pos, tbill, name)
        results[key] = {"res": res, "m": m, "at": at, "pos": pos}

    # ---- FULL headline table ----
    print(f"\n  {'Variation':<30}{'CAGR':>7}{'Sortino':>9}{'Calmar':>8}"
          f"{'maxDD':>7}{'Whip/yr':>9}{'AT-CAGR':>9}")
    base = results["daily_50_200"]
    for key in VARIATIONS:
        m = results[key]["m"]; res = results[key]["res"]; at = results[key]["at"]
        print(f"  {VAR_LABELS[key]:<30}{m['cagr']:>+6.1%} {m['sortino']:>8.2f} "
              f"{m['calmar']:>7.2f} {m['max_dd']:>6.0%} {res.transitions_per_year:>8.2f} "
              f"{at:>+8.1%}")

    # ---- vs-baseline deltas + locked criteria ----
    print(f"\n  Locked criteria vs daily 50/200 baseline "
          f"(need: ΔSortino≥+0.30 OR ΔCalmar≥+0.15; whipsaw ≥30% fewer; "
          f"AT-CAGR comparable/better):")
    bm, bres, bat = base["m"], base["res"], base["at"]
    for key in VARIATIONS:
        if key == "daily_50_200":
            continue
        m, res, at = results[key]["m"], results[key]["res"], results[key]["at"]
        d_sortino = m["sortino"] - bm["sortino"]
        d_calmar = m["calmar"] - bm["calmar"]
        whip_red = (1 - res.transitions_per_year / bres.transitions_per_year
                    if bres.transitions_per_year else 0.0)
        d_at = at - bat
        perf_ok = (d_sortino >= 0.30) or (d_calmar >= 0.15)
        whip_ok = whip_red >= 0.30
        at_ok = d_at >= -0.005            # within 0.5pp = "comparable"
        print(f"  {VAR_LABELS[key]:<30} ΔSortino={d_sortino:+.2f} "
              f"ΔCalmar={d_calmar:+.2f} whip-red={whip_red:+.0%} ΔAT-CAGR={d_at:+.1%}  "
              f"[{'PASS' if (perf_ok and whip_ok and at_ok) else 'fail'}: "
              f"perf={'Y' if perf_ok else 'n'} whip={'Y' if whip_ok else 'n'} "
              f"at={'Y' if at_ok else 'n'}]")

    # ---- per-period Sortino / whipsaw ----
    print(f"\n  Per-period Sortino  (robustness — must not depend on one regime):")
    header = "  " + f"{'Period':<28}" + "".join(f"{VAR_LABELS[k].split('.')[0]:>8}"
                                                 for k in VARIATIONS)
    print(header)
    for plabel, ps, pe in periods:
        row = f"  {plabel:<28}"
        for key in VARIATIONS:
            pm = period_metrics(results[key]["res"].daily_ret, results[key]["pos"],
                                ps, pe, ann)
            row += (f"{pm['sortino']:>8.2f}" if pm['sortino'] is not None else f"{'—':>8}")
        print(row)

    print(f"\n  Per-period whipsaw (transitions/yr):")
    print(header)
    for plabel, ps, pe in periods:
        row = f"  {plabel:<28}"
        for key in VARIATIONS:
            pm = period_metrics(results[key]["res"].daily_ret, results[key]["pos"],
                                ps, pe, ann)
            row += (f"{pm['tpy']:>8.1f}" if pm['tpy'] is not None else f"{'—':>8}")
        print(row)

    print(f"\n  Per-period Calmar:")
    print(header)
    for plabel, ps, pe in periods:
        row = f"  {plabel:<28}"
        for key in VARIATIONS:
            pm = period_metrics(results[key]["res"].daily_ret, results[key]["pos"],
                                ps, pe, ann)
            row += (f"{pm['calmar']:>8.2f}" if pm['calmar'] is not None else f"{'—':>8}")
        print(row)

    # ---- stress windows: max DD ----
    print(f"\n  Stress-window max drawdown (lower=better; B&H shown for context):")
    print("  " + f"{'Event':<20}{'B&H':>7}" +
          "".join(f"{VAR_LABELS[k].split('.')[0]:>8}" for k in VARIATIONS))
    bah_eq = (1.0 + close.pct_change().fillna(0.0)).cumprod()
    for elabel, ps, pe in stress:
        row = f"  {elabel:<20}{event_dd(bah_eq, ps, pe)*100:>6.0f}%"
        for key in VARIATIONS:
            dd = event_dd(results[key]["res"].equity, ps, pe)
            row += f"{dd*100:>7.0f}%"
        print(row)

    return results


def main() -> int:
    print("#" * 100)
    print("# TIMEFRAME VARIATION TEST — 4 signal frequencies on the trend rule")
    print("# Convention 2 (no look-ahead), T-bill OFF (TB3MS), costs on.")
    print(f"# Tax: ST {ST_RATE:.0%} / LT {LT_RATE:.0%}. "
          f"Costs: equity {EQUITY_TRANSITION_BPS:.0f}bps/flip, "
          f"BTC {BTC_TRANSITION_BPS:.0f}bps/flip + {BTC_EXPENSE_ANNUAL:.2%}/yr expense.")
    print("#" * 100)
    ensure_cached()
    run_asset("equity", "^GSPC", 252, EQUITY_PERIODS, EQUITY_STRESS)
    run_asset("btc", "BTC-USD", 365, BTC_PERIODS, BTC_STRESS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
