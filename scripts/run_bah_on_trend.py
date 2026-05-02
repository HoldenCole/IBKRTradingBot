"""Out-of-sample validation: BAH-on-trend-ON-days candidate strategy.

Tests "hold QQQ when SMA(50) > SMA(200) AND close > SMA(50); cash otherwise"
across three non-overlapping periods to validate whether the 2018-2026
result was a real edge or a sample-specific artifact.

Periods:
  - 2018-2026 (the original sample) — re-run as sanity check with the
    fixed (standard) Sortino formula.
  - 2010-2017 (held-out 8-year window we have not analyzed).
  - 2000-2009 (completely different macro regime — dot-com bust, GFC).

Decision criteria (locked before run, per user):
  - If lift over QQQ buy-and-hold is comparable in BOTH 2010-2017 and
    2000-2009 (within 50% of the 2018-2026 lift) → real candidate,
    investigate further as the buy-and-hold-lift component.
  - If lift is much weaker or absent in either → 2018-2026 was sample-
    specific, do not deploy.

Methodology:
  - Filter checked on each trading day's close.
  - Rule: hold QQQ when (close > SMA50) AND (SMA50 > SMA200); else 0%
    return for the day (cash).
  - Sortino fixed (standard formula: dd² = sum-of-squares of negative
    returns / N_total, target = 0).
  - Per-year breakdown.
  - No MA window tuning. 50/200 because that's what the prior result used.

Data sources:
  - FMP for QQQ 2010+ (already integrated, has full history).
  - yfinance for QQQ 2000-2009 (FMP doesn't have pre-2010).
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics
from src.data.fmp import FMPHistorical
from src.data import yahoo


def fetch_qqq(start: str, end: str, fmp_key: str) -> pd.DataFrame:
    """Fetch QQQ daily bars. FMP if start >= 2010-01-01 else yfinance."""
    start_date = date.fromisoformat(start)
    if start_date >= date(2010, 1, 1):
        fmp = FMPHistorical(api_key=fmp_key)
        df = fmp.daily("QQQ", start, end)
        return df
    # yfinance for older data
    return yahoo.daily("QQQ", start, end)


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    """Compute filter ON/OFF flag for each bar in `close`.
    ON when close > SMA(fast) > SMA(slow)."""
    sma_fast = close.rolling(fast, min_periods=fast).mean()
    sma_slow = close.rolling(slow, min_periods=slow).mean()
    flags = (close > sma_fast) & (sma_fast > sma_slow)
    return flags.fillna(False)


def run_bah_on_trend(close: pd.Series, start_capital: float = 8000.0) -> dict:
    """Compute equity curve for: hold QQQ when filter ON, cash (0% return) when OFF.
    Returns metrics dict + equity curve.
    """
    rets = close.pct_change().fillna(0.0)
    flags = filter_on_flags(close)
    masked = rets.where(flags, 0.0)
    equity = (1 + masked).cumprod() * start_capital
    m = equity_metrics(equity, start_capital)
    m["n_on_days"] = int(flags.sum())
    m["n_total_days"] = int(len(flags))
    m["pct_on"] = m["n_on_days"] / max(1, m["n_total_days"])
    m["equity"] = equity
    return m


def per_year_breakdown(close: pd.Series, equity: pd.Series, label: str) -> str:
    """Per-year return for both QQQ BAH and the trend-gated strategy."""
    by_year_strat: dict[int, list[float]] = defaultdict(list)
    by_year_bah: dict[int, list[float]] = defaultdict(list)
    bah_eq = (close / close.iloc[0]) * float(equity.iloc[0])

    for d in equity.index:
        y = d.year if hasattr(d, "year") else None
        if y is not None:
            by_year_strat[y].append(equity.loc[d])
            by_year_bah[y].append(bah_eq.loc[d])

    lines = [f"\n[{label}] Per-year breakdown"]
    lines.append(f"  {'Year':>4s}  {'BAH ret':>8s}  {'Strat ret':>9s}  {'Lift':>7s}")
    prev_strat = float(equity.iloc[0])
    prev_bah = float(bah_eq.iloc[0])
    for y in sorted(by_year_strat):
        end_strat = by_year_strat[y][-1]
        end_bah = by_year_bah[y][-1]
        strat_ret = (end_strat - prev_strat) / prev_strat
        bah_ret = (end_bah - prev_bah) / prev_bah
        lines.append(f"  {y:>4d}  {bah_ret:>+7.1%}  {strat_ret:>+8.1%}  "
                     f"{(strat_ret - bah_ret)*100:>+5.1f}pp")
        prev_strat = end_strat
        prev_bah = end_bah
    return "\n".join(lines)


def report_period(label: str, start: date, end: date, fmp_key: str,
                  prev_capital: float = 8000.0) -> dict:
    print(f"\n{'='*88}")
    print(f"PERIOD: {label} ({start} to {end})")
    print(f"{'='*88}")

    df = fetch_qqq(start.isoformat(), end.isoformat(), fmp_key)
    if df.empty:
        print(f"ERROR: no QQQ data returned for {label}")
        return {}
    close = df["close"]
    print(f"  {len(close)} trading days, range ${close.min():.2f}-${close.max():.2f}")

    bah = buy_and_hold_metrics(close, prev_capital, "QQQ")
    strat = run_bah_on_trend(close, prev_capital)

    print(f"\n  {'Metric':18s}  {'QQQ BAH':>10s}  {'Trend gate':>11s}  {'Lift':>9s}")
    print(f"  {'Total return':18s}  {bah.total_return:>+9.1%}  "
          f"{strat['total_return']:>+10.1%}  "
          f"{(strat['total_return']-bah.total_return)*100:>+7.1f}pp")
    print(f"  {'CAGR':18s}  {bah.cagr:>+9.1%}  "
          f"{strat['cagr']:>+10.1%}  "
          f"{(strat['cagr']-bah.cagr)*100:>+7.1f}pp")
    print(f"  {'Sortino':18s}  {bah.sortino:>10.2f}  "
          f"{strat['sortino']:>11.2f}  "
          f"{strat['sortino']-bah.sortino:>+9.2f}")
    print(f"  {'Sharpe':18s}  {bah.sharpe:>10.2f}  "
          f"{strat['sharpe']:>11.2f}  "
          f"{strat['sharpe']-bah.sharpe:>+9.2f}")
    print(f"  {'Max drawdown':18s}  {bah.max_drawdown:>+9.1%}  "
          f"{strat['max_drawdown']:>+10.1%}  "
          f"{(strat['max_drawdown']-bah.max_drawdown)*100:>+7.1f}pp")
    print(f"  {'Final equity ($)':18s}  ${bah.final_equity:>9,.0f}  "
          f"${strat['final_equity']:>10,.0f}  "
          f"${strat['final_equity']-bah.final_equity:>+8,.0f}")
    print(f"  {'Filter-ON days':18s}  {'-':>10s}  "
          f"{strat['n_on_days']}/{strat['n_total_days']} ({strat['pct_on']:.0%})")

    print(per_year_breakdown(close, strat["equity"], label))

    return {
        "bah": bah, "strat": strat, "label": label,
        "sortino_lift": strat["sortino"] - bah.sortino,
        "return_lift_pp": (strat["total_return"] - bah.total_return) * 100,
        "dd_lift_pp": (strat["max_drawdown"] - bah.max_drawdown) * 100,
    }


def main() -> int:
    api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        print("ERROR: FMP_API_KEY not set", file=sys.stderr)
        return 1

    print("# BAH-on-trend-ON-days — out-of-sample validation")
    print("# Strategy: hold QQQ when (close > SMA50) AND (SMA50 > SMA200);")
    print("#           0% return (cash) otherwise. Daily flag.")
    print("# Sortino formula: standard (downside dev = sqrt(sum_neg² / N_total),")
    print("#   target = 0). Updated from prior non-standard convention.")

    in_sample = report_period(
        "2018-2026 (in-sample)", date(2018, 1, 1), date(2026, 4, 15), api_key,
    )
    held_out_a = report_period(
        "2010-2017 (held-out)", date(2010, 1, 1), date(2017, 12, 31), api_key,
    )
    held_out_b = report_period(
        "2000-2009 (different regime)", date(2000, 1, 1), date(2009, 12, 31), api_key,
    )

    # Decision rule application
    print(f"\n{'='*88}")
    print("DECISION RULE — locked criteria")
    print(f"{'='*88}\n")
    base_lift = in_sample["sortino_lift"]
    print(f"In-sample (2018-2026) Sortino lift: {base_lift:+.2f}")
    print(f"Held-out (2010-2017)  Sortino lift: {held_out_a['sortino_lift']:+.2f}")
    print(f"Held-out (2000-2009)  Sortino lift: {held_out_b['sortino_lift']:+.2f}")

    threshold = abs(base_lift) * 0.50  # within 50% of in-sample lift

    print(f"\nRule: each held-out lift within 50% of in-sample (within ±{threshold:.2f})")
    crit_a = abs(held_out_a["sortino_lift"]) >= threshold and \
             (held_out_a["sortino_lift"] * base_lift > 0)  # same sign as in-sample
    crit_b = abs(held_out_b["sortino_lift"]) >= threshold and \
             (held_out_b["sortino_lift"] * base_lift > 0)

    print(f"  2010-2017: |{held_out_a['sortino_lift']:+.2f}| >= {threshold:.2f}? "
          f"{'PASS' if crit_a else 'FAIL'}")
    print(f"  2000-2009: |{held_out_b['sortino_lift']:+.2f}| >= {threshold:.2f}? "
          f"{'PASS' if crit_b else 'FAIL'}")

    print(f"\n--- VERDICT ---")
    if crit_a and crit_b:
        print(f"  REAL CANDIDATE: BAH-on-trend-ON-days lifts comparably across "
              f"all three periods. Worth scoping as the portfolio's "
              f"buy-and-hold-lift component.")
    else:
        print(f"  SAMPLE-SPECIFIC: 2018-2026 lift is not robust across held-out "
              f"periods. Do NOT deploy this rule. The result was an artifact "
              f"of the 2018-2026 sample.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
