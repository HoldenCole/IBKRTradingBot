"""Long-history validation of the BAH-on-trend rule on ^GSPC.

Tests the 50/200 SMA + T-bill OFF rule across the full ^GSPC history
(1928-12-30 → 2026-04-14, ~98 years). The key new period is the
1966-1982 secular bear — the regime that's missing from our 26-year
QQQ sample.

Data:
  - ^GSPC (S&P 500 index, price-only, no dividends)
    Yahoo provides ~98 years of daily data.
  - T-bill rate: TB3MS (FRED, monthly 3-month T-bill secondary market,
    since 1934). For 1928-1933 we use the earliest known value (Jan 1934
    = 0.72%) as a placeholder. Documented below.

Caveats (read these before drawing conclusions):
  1. ^GSPC is PRICE-ONLY. Both the strategy and the BAH baseline will
     have similar CAGR understatement (~3-5pp/yr in 1930s-1960s when
     dividend yields were 4-6%; ~2pp/yr in 1980s-2010s; ~1.5pp/yr now).
     The relative comparison (strategy lift over BAH) is valid because
     dividends accrue equally to ON-period and BAH paths. The Sortino
     comparison is also broadly valid.

  2. Both backtest conventions reported (Convention 1 lookahead vs
     Convention 2 honest), as established in Test A.

  3. T-bill rate proxy: TB3MS is monthly secondary-market 3-month bill
     rate; we ffill to daily. Slightly different from DGS3MO (daily
     constant-maturity), but close enough for OFF-period yield modeling.

Periods (non-overlapping):
  1928-1949  Depression + WWII (regime: deflation, war finance)
  1950-1965  Post-war bull (regime: low inflation, Bretton Woods)
  1966-1982  Secular bear (regime: stagflation, oil shocks) ← KEY NEW TEST
  1983-1999  Disinflationary bull (regime: Volcker → Greenspan)
  2000-2009  Dotcom + GFC (already tested via QQQ)
  2010-2017  Post-GFC recovery (already tested)
  2018-2026  Modern in-sample (already tested)

For each period we report:
  - BAH-on-trend Sortino, CAGR, |DD|
  - BAH-only (no strategy) Sortino, CAGR, |DD|
  - Sortino lift, CAGR cost (or lift)
  - DD avoidance vs BAH
"""
from __future__ import annotations

import io
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import httpx
import numpy as np
import pandas as pd

from src.backtest.benchmark import equity_metrics
from src.data import yahoo


def fetch_tb3ms(start: str, end: str, cache_dir: Path | None = None) -> pd.Series:
    """Fetch monthly TB3MS from FRED and return a daily-indexed series of
    annual rates (in percent). Forward-fills weekends/holidays.
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    params = {"id": "TB3MS", "cosd": start, "coed": end}
    cache_path = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"TB3MS_{start}_{end}.csv"
        if cache_path.exists():
            text = cache_path.read_text()
        else:
            r = httpx.get(url, params=params, timeout=30)
            r.raise_for_status()
            text = r.text
            cache_path.write_text(text)
    else:
        r = httpx.get(url, params=params, timeout=30)
        r.raise_for_status()
        text = r.text

    df = pd.read_csv(io.StringIO(text))
    date_col = next(c for c in df.columns if c.lower() in ("observation_date", "date"))
    val_col = next(c for c in df.columns if c != date_col)
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.rename(columns={date_col: "date", val_col: "rate"}).set_index("date")
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    df = df.dropna(subset=["rate"])
    return df["rate"]


def daily_tbill_factor(monthly_rate_pct: pd.Series, target_idx: pd.Index) -> pd.Series:
    """Convert monthly TB3MS to daily compounding factor on target index."""
    rate = monthly_rate_pct.reindex(target_idx, method="ffill")
    # Backfill for any pre-inception dates (uses the earliest known value)
    rate = rate.bfill().fillna(0.0)
    return (1.0 + rate / 100.0) ** (1.0 / 252.0) - 1.0


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def equity_curve(close: pd.Series, on_flags: pd.Series, tbill_daily: pd.Series,
                 start_capital: float = 8000.0, shift_flags: bool = False) -> pd.Series:
    rets = close.pct_change().fillna(0.0)
    flags = (on_flags.shift(1).fillna(False) if shift_flags else on_flags).astype(bool)
    daily = rets.where(flags, tbill_daily.reindex(close.index).fillna(0.0))
    return (1 + daily).cumprod() * start_capital


def slice_series(s: pd.Series, ps: date, pe: date) -> pd.Series:
    idx = [d.date() if hasattr(d, "date") else d for d in s.index]
    mask = pd.Series([ps <= d <= pe for d in idx], index=s.index)
    return s.loc[mask]


PERIODS = [
    ("1928-1949 Depression+WWII",     date(1928, 12, 30), date(1949, 12, 31)),
    ("1950-1965 Post-war bull",       date(1950, 1, 3),   date(1965, 12, 31)),
    ("1966-1982 Secular bear",        date(1966, 1, 3),   date(1982, 12, 31)),
    ("1983-1999 Disinflationary",     date(1983, 1, 3),   date(1999, 12, 31)),
    ("2000-2009 Dotcom+GFC",          date(2000, 1, 3),   date(2009, 12, 31)),
    ("2010-2017 Post-GFC",            date(2010, 1, 4),   date(2017, 12, 31)),
    ("2018-2026 Modern",              date(2018, 1, 2),   date(2026, 4, 14)),
    ("FULL 1928-2026",                date(1928, 12, 30), date(2026, 4, 14)),
]


# Notable bear-window drawdown stress tests
DECLINE_EVENTS = [
    ("1929 Crash",        date(1929, 9, 16), date(1932, 6, 1)),    # peak to trough
    ("1973-74 oil bear",  date(1973, 1, 11), date(1974, 12, 6)),
    ("1987 Black Monday", date(1987, 8, 25), date(1987, 12, 4)),
    ("2000-2002 dotcom",  date(2000, 3, 24), date(2002, 10, 9)),
    ("2008-2009 GFC",     date(2008, 9, 1),  date(2009, 3, 9)),
    ("March 2020 COVID",  date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation",    date(2022, 1, 3),  date(2022, 10, 13)),
]


def event_dd(equity: pd.Series, ps: date, pe: date) -> float:
    sub = slice_series(equity, ps, pe)
    if sub.empty:
        return 0.0
    return float(((sub.cummax() - sub) / sub.cummax()).max())


def main() -> int:
    full_start = date(1928, 12, 30)
    full_end = date(2026, 4, 14)
    cache = REPO / "data" / "fred_cache"

    print("Fetching ^GSPC + TB3MS...")
    df = yahoo.daily("^GSPC", full_start.isoformat(), full_end.isoformat())
    print(f"  ^GSPC: {len(df):,} bars, {df.index[0].date()} → {df.index[-1].date()}")
    tb3ms = fetch_tb3ms(full_start.isoformat(), full_end.isoformat(), cache)
    print(f"  TB3MS: {len(tb3ms)} obs, {tb3ms.index[0].date()} → {tb3ms.index[-1].date()}")
    print(f"  Avg TB3MS over full period: {tb3ms.mean():.2f}% annual")
    print(f"  TB3MS in 1966-1982 (secular bear): {tb3ms.loc['1966':'1982'].mean():.2f}%")

    close = df["close"]
    on_flags = filter_on_flags(close)
    tbill_daily = daily_tbill_factor(tb3ms, close.index)

    # ===================== Per-period table (both conventions) =====================
    for shift_flags, conv_label in (
        (False, "Convention 1: flag[t] → ret[t] (MOC, prior framework)"),
        (True,  "Convention 2: flag[t-1] → ret[t] (no-lookahead, honest)"),
    ):
        print("\n" + "#" * 110)
        print(f"# Long-history validation | ^GSPC (price-only) | {conv_label}")
        print("#" * 110)

        print(f"\n{'Period':30s}  {'Strategy':>20s}  {'BAH-only':>20s}  "
              f"{'Lift':>15s}")
        print(f"{'':30s}  {'Sort  CAGR   |DD|':>20s}  {'Sort  CAGR   |DD|':>20s}  "
              f"{'ΔSort  ΔCAGR':>15s}")

        for plabel, ps, pe in PERIODS:
            sub_close = slice_series(close, ps, pe)
            sub_flags = slice_series(on_flags, ps, pe)
            sub_tbill = slice_series(tbill_daily, ps, pe)
            if sub_close.empty or len(sub_close) < 250:
                print(f"  {plabel:30s}  (insufficient data)")
                continue

            # Strategy
            strat_eq = equity_curve(sub_close, sub_flags, sub_tbill, 8000.0,
                                    shift_flags=shift_flags)
            ms = equity_metrics(strat_eq, 8000.0)

            # BAH (price-only)
            bah_eq = (1 + sub_close.pct_change().fillna(0.0)).cumprod() * 8000.0
            mb = equity_metrics(bah_eq, 8000.0)

            d_sortino = ms["sortino"] - mb["sortino"]
            d_cagr = (ms["cagr"] - mb["cagr"]) * 100

            print(f"  {plabel:30s}  "
                  f"{ms['sortino']:>4.2f} {ms['cagr']:>+5.1%} {abs(ms['max_drawdown']):>4.0%}  "
                  f"{mb['sortino']:>4.2f} {mb['cagr']:>+5.1%} {abs(mb['max_drawdown']):>4.0%}  "
                  f"{d_sortino:>+5.2f} {d_cagr:>+5.1f}pp")

    # ===================== Decline-event stress test =====================
    print("\n" + "#" * 110)
    print(f"# Drawdown avoidance per decline event (Convention 2, honest)")
    print("# BAH max DD over event window vs strategy max DD")
    print("#" * 110)

    full_strat_eq = equity_curve(close, on_flags, tbill_daily, 8000.0,
                                 shift_flags=True)
    full_bah_eq = (1 + close.pct_change().fillna(0.0)).cumprod() * 8000.0

    print(f"\n{'Event':25s}  {'BAH |DD|':>10s}  {'Strat |DD|':>11s}  {'Saved':>8s}")
    for elabel, ps, pe in DECLINE_EVENTS:
        bah_dd = event_dd(full_bah_eq, ps, pe)
        st_dd = event_dd(full_strat_eq, ps, pe)
        saved = bah_dd - st_dd
        print(f"  {elabel:25s}  {bah_dd*100:>8.0f}%   {st_dd*100:>9.0f}%   "
              f"{saved*100:>+5.0f}pp")

    # ===================== Tier-A check on the secular bear =====================
    print("\n" + "#" * 110)
    print("# Secular-bear focus: 1966-1982 vs all other periods")
    print("# Does the BAH-on-trend rule still beat BAH-only on Sortino during stagflation?")
    print("#" * 110)

    sec_close = slice_series(close, date(1966, 1, 3), date(1982, 12, 31))
    sec_flags = slice_series(on_flags, date(1966, 1, 3), date(1982, 12, 31))
    sec_tbill = slice_series(tbill_daily, date(1966, 1, 3), date(1982, 12, 31))

    print(f"\n  {'Convention':22s}  {'Strategy':>20s}  {'BAH-only':>20s}  "
          f"{'Verdict':>20s}")
    for shift_flags, conv_label in ((False, "Conv 1 (lookahead)"),
                                     (True,  "Conv 2 (no-lookahead)")):
        strat_eq = equity_curve(sec_close, sec_flags, sec_tbill, 8000.0,
                                shift_flags=shift_flags)
        ms = equity_metrics(strat_eq, 8000.0)
        bah_eq = (1 + sec_close.pct_change().fillna(0.0)).cumprod() * 8000.0
        mb = equity_metrics(bah_eq, 8000.0)
        d = ms["sortino"] - mb["sortino"]
        verdict = "Lift confirmed" if d > 0 else "FAILS to beat BAH"
        print(f"  {conv_label:22s}  "
              f"{ms['sortino']:>4.2f} {ms['cagr']:>+5.1%} {abs(ms['max_drawdown']):>4.0%}  "
              f"{mb['sortino']:>4.2f} {mb['cagr']:>+5.1%} {abs(mb['max_drawdown']):>4.0%}  "
              f"{verdict:>20s}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
