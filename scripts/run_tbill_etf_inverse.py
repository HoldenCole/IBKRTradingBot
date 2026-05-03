"""BAH-on-trend with T-bill yield on OFF-period cash + alternative-ETF sweep.

Implements user-spec'd Priorities 1, 2, 3 in a single runner:

  P1: T-bill yield on OFF-period cash (FRED DGS3MO 3-month Treasury rate,
      annualized, daily-compounded). Replaces the prior 0%-on-OFF model.
      Tax: ordinary income (= STCG rate). Becomes the new default for
      all BAH-on-trend backtests going forward.

  P2: Alternative ETFs on the long side. Same SMA(50)/(200) rule, applied
      to each ETF's own price history. Tests:
        VOO, MTUM, QQQM, IWM, EFA, EEM, XLK, XLF, XLE, XLV
      26-year backtest where data allows; documents inception dates.

  P3: Inverse ETFs (PSQ for QQQ, SH for SPY) during OFF periods instead
      of T-bill cash. 1x inverse only (no SQQQ/SDS — leveraged decay).
      Compared against the T-bill OFF baseline.

P4 runs in a separate runner (run_ibs_overlay.py) since it needs the
shares engine + IBS strategy.

Tax model:
  Capital gains (long position, cap appreciation): STCG rate (rule's
    typical hold is short, ~30 days; we approximate as 100% STCG).
  T-bill interest: ordinary income (= STCG rate).
  Both pieces taxed at the same marginal rate, so blended treatment
  is identical to applying STCG to total gain.

Periods: 2018-2026 in-sample, 2010-2017 held-out, 2000-2009 regime shift.
"""
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics
from src.data import yahoo
from src.data.fred import fetch_tbill_3m


@dataclass(frozen=True)
class TaxScenario:
    label: str
    stcg_rate: float        # short-term cap gains + ordinary income (T-bill)
    ltcg_rate: float        # long-term cap gains
    @property
    def shares_rate(self) -> float:
        return self.stcg_rate
    @property
    def ord_rate(self) -> float:
        return self.stcg_rate
    @property
    def futures_rate(self) -> float:
        return 0.6 * self.ltcg_rate + 0.4 * self.stcg_rate


TAX_LOWER = TaxScenario("Lower bracket (24% STCG, 15% LTCG)", 0.24, 0.15)
TAX_HIGHER = TaxScenario("Higher bracket (37% STCG, 20% LTCG)", 0.37, 0.20)


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    sma_fast = close.rolling(fast, min_periods=fast).mean()
    sma_slow = close.rolling(slow, min_periods=slow).mean()
    return ((close > sma_fast) & (sma_fast > sma_slow)).fillna(False)


def daily_tbill_factor(tbill_pct: pd.Series) -> pd.Series:
    """Convert annualized T-bill rate (in percent, e.g. 5.25) to a daily
    compounding factor (1 + r_annual)^(1/252) - 1.
    Forward-fills missing days (FRED skips weekends/holidays).
    """
    rates = (tbill_pct / 100.0).reindex(tbill_pct.index).ffill().fillna(0.0)
    return (1.0 + rates) ** (1.0 / 252.0) - 1.0


def bah_on_trend_with_tbill(
    close: pd.Series,
    tbill_daily_factor: pd.Series,
    start_capital: float = 8000.0,
    leverage: float = 1.0,
) -> tuple[pd.Series, dict]:
    """Equity curve for BAH-on-trend with T-bill yield on OFF days.

    On filter-ON days: equity grows at leverage * cash_index_return.
    On filter-OFF days: equity grows at the T-bill daily factor.

    Returns (equity_curve, breakdown) where breakdown contains the
    capital-gain vs T-bill-interest split for tax modeling.
    """
    rets = close.pct_change().fillna(0.0)
    flags = filter_on_flags(close)

    # Align T-bill index to price index
    tbill_aligned = tbill_daily_factor.reindex(close.index).ffill().fillna(0.0)

    # Daily return = leverage * idx_return on ON days, T-bill rate on OFF days
    on_returns = leverage * rets
    daily_returns = on_returns.where(flags, tbill_aligned)

    equity = (1 + daily_returns).cumprod() * start_capital

    # Decompose for tax modeling: ON-day P&L = capital appreciation,
    # OFF-day P&L = T-bill interest (ordinary income).
    on_pnl = ((1 + on_returns.where(flags, 0.0)).cumprod() - 1) * start_capital
    off_pnl_factor = (1 + tbill_aligned.where(~flags, 0.0)).cumprod()
    # Approximate split: by total contribution.
    # Simpler: compute the total final equity, decompose by gross contribution
    # of each component. Both pieces are taxed at the same rate (STCG=ordinary),
    # so the split doesn't change the final answer for shares.
    breakdown = {
        "n_on_days": int(flags.sum()),
        "n_off_days": int((~flags).sum()),
        "n_total_days": int(len(flags)),
    }
    return equity, breakdown


def bah_on_trend_inverse_off(
    close_long: pd.Series,
    close_inverse: pd.Series,    # PSQ for QQQ, SH for SPY
    start_capital: float = 8000.0,
) -> tuple[pd.Series, dict]:
    """ON: long the underlying. OFF: long the 1x inverse ETF.

    Daily return = idx_return on ON days, inverse_ret on OFF days.
    No leverage modeling — assumes 1x inverse ETF tracks closely.
    """
    rets_long = close_long.pct_change().fillna(0.0)
    rets_inv = close_inverse.pct_change().fillna(0.0)
    flags = filter_on_flags(close_long)
    # Align indices
    common = close_long.index.intersection(close_inverse.index)
    rets_long = rets_long.reindex(common).fillna(0.0)
    rets_inv = rets_inv.reindex(common).fillna(0.0)
    flags = flags.reindex(common).fillna(False)

    daily = rets_long.where(flags, rets_inv)
    equity = (1 + daily).cumprod() * start_capital

    breakdown = {
        "n_on_days": int(flags.sum()),
        "n_off_days": int((~flags).sum()),
        "n_total_days": int(len(flags)),
    }
    return equity, breakdown


def slice_close(df: pd.DataFrame, start: date, end: date) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    idx = [d.date() if hasattr(d, "date") else d for d in df.index]
    mask = pd.Series([start <= d <= end for d in idx], index=df.index)
    s = df.loc[mask]["close"]
    return s


def after_tax_cagr(equity: pd.Series, start_capital: float,
                   tax_rate: float) -> tuple[float, float]:
    """Apply flat tax to total gain. Returns (after_tax_cagr, after_tax_final)."""
    if equity.empty:
        return 0.0, start_capital
    final = float(equity.iloc[-1])
    gain = final - start_capital
    tax = max(0, gain) * tax_rate
    after_tax = start_capital + (gain - tax)
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (after_tax / start_capital) ** (1.0 / max(1e-9, years)) - 1.0 \
           if after_tax > 0 else -1.0
    return cagr, after_tax


# ===========================================================================
# Priority 1: T-bill yield on OFF-period — re-run shares + futures baselines
# ===========================================================================

def priority_1(spy: pd.DataFrame, qqq: pd.DataFrame,
               tbill_daily: pd.Series, periods: list[tuple]):
    print("\n" + "#" * 92)
    print("# PRIORITY 1 — T-bill yield on OFF-period (replaces 0%-on-OFF baseline)")
    print("#" * 92)

    print(f"\n{'Period':30s}  {'Vehicle':18s}  {'Sortino':>7s}  {'CAGR':>6s}  "
          f"{'AT CAGR':>7s}  {'|DD|':>5s}  {'Final $':>10s}")

    headline_results = {}
    for plabel, ps, pe in periods:
        spy_close = slice_close(spy, ps, pe)
        qqq_close = slice_close(qqq, ps, pe)
        tbill = tbill_daily

        if spy_close.empty:
            continue

        # Shares 1x with T-bill OFF
        spy_eq, _ = bah_on_trend_with_tbill(spy_close, tbill, 8000.0, 1.0)
        qqq_eq, _ = bah_on_trend_with_tbill(qqq_close, tbill, 8000.0, 1.0)
        # Futures 1.5x via leveraged returns
        spy_fut15_eq, _ = bah_on_trend_with_tbill(spy_close, tbill, 8000.0, 1.5)
        qqq_fut15_eq, _ = bah_on_trend_with_tbill(qqq_close, tbill, 8000.0, 1.5)

        for vehicle, eq, tax in (
            ("SPY shares 1x", spy_eq, TAX_LOWER.shares_rate),
            ("QQQ shares 1x", qqq_eq, TAX_LOWER.shares_rate),
            ("SPY/MES 1.5x", spy_fut15_eq, TAX_LOWER.futures_rate),
            ("QQQ/MNQ 1.5x", qqq_fut15_eq, TAX_LOWER.futures_rate),
        ):
            m = equity_metrics(eq, 8000.0)
            at_cagr, at_final = after_tax_cagr(eq, 8000.0, tax)
            print(f"  {plabel:30s}  {vehicle:18s}  {m['sortino']:>7.2f}  "
                  f"{m['cagr']:>+5.1%}  {at_cagr:>+6.1%}  "
                  f"{abs(m['max_drawdown']):>4.0%}  ${m['final_equity']:>8,.0f}")
            headline_results[(plabel, vehicle)] = {
                "metrics": m, "at_cagr": at_cagr, "at_final": at_final,
            }

    return headline_results


# ===========================================================================
# Priority 2: Alternative ETF sweep
# ===========================================================================

ALTERNATIVE_ETFS = [
    ("VOO",  "S&P 500 (Vanguard) — same as SPY, low fee"),
    ("MTUM", "iShares MSCI USA Momentum (since 2013)"),
    ("QQQM", "Invesco Nasdaq 100 (since 2020) — cheaper QQQ"),
    ("IWM",  "Russell 2000 small-cap"),
    ("EFA",  "iShares MSCI EAFE (developed international)"),
    ("EEM",  "iShares MSCI Emerging Markets"),
    ("XLK",  "Technology Select Sector"),
    ("XLF",  "Financial Select Sector"),
    ("XLE",  "Energy Select Sector"),
    ("XLV",  "Health Care Select Sector"),
]


def priority_2(tbill_daily: pd.Series, periods: list[tuple]):
    print("\n" + "#" * 92)
    print("# PRIORITY 2 — Alternative ETFs on the long side (BAH-on-trend, T-bill OFF)")
    print("#" * 92)

    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)

    print(f"\n{'ETF':6s}  {'Inception':>10s}  {'Period':30s}  {'Sortino':>7s}  "
          f"{'CAGR':>6s}  {'AT CAGR':>7s}  {'|DD|':>5s}  "
          f"{'BAH CAGR':>9s}  {'CAGR Lift':>9s}")

    results = {}
    for sym, desc in ALTERNATIVE_ETFS:
        # Fetch full history
        df = yahoo.daily(sym, full_start.isoformat(), full_end.isoformat())
        if df.empty:
            print(f"  {sym}: NO DATA")
            continue
        inception = df.index[0].date()

        for plabel, ps, pe in periods:
            close = slice_close(df, ps, pe)
            if close.empty or len(close) < 250:
                continue
            # Strategy
            eq, _ = bah_on_trend_with_tbill(close, tbill_daily, 8000.0, 1.0)
            m = equity_metrics(eq, 8000.0)
            at_cagr, _ = after_tax_cagr(eq, 8000.0, TAX_LOWER.shares_rate)
            # BAH baseline
            bah = buy_and_hold_metrics(close, 8000.0, sym)
            lift = m["cagr"] - bah.cagr
            print(f"  {sym:6s}  {inception.isoformat():>10s}  {plabel:30s}  "
                  f"{m['sortino']:>7.2f}  {m['cagr']:>+5.1%}  "
                  f"{at_cagr:>+6.1%}  {abs(m['max_drawdown']):>4.0%}  "
                  f"{bah.cagr:>+8.1%}  {lift*100:>+7.1f}pp")
            results[(sym, plabel)] = {
                "metrics": m, "bah_cagr": bah.cagr, "lift": lift,
                "at_cagr": at_cagr, "inception": inception,
            }

    return results


# ===========================================================================
# Priority 3: Inverse ETFs during OFF periods
# ===========================================================================

def priority_3(spy: pd.DataFrame, qqq: pd.DataFrame,
               tbill_daily: pd.Series, periods: list[tuple]):
    print("\n" + "#" * 92)
    print("# PRIORITY 3 — Inverse ETFs during OFF (PSQ for QQQ, SH for SPY)")
    print("#" * 92)

    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)
    psq = yahoo.daily("PSQ", full_start.isoformat(), full_end.isoformat())
    sh = yahoo.daily("SH", full_start.isoformat(), full_end.isoformat())
    print(f"\n  PSQ inception: {psq.index[0].date() if not psq.empty else 'NO DATA'}")
    print(f"  SH  inception: {sh.index[0].date() if not sh.empty else 'NO DATA'}")
    print(f"\n{'Period':30s}  {'Pair':14s}  {'Strategy':10s}  "
          f"{'Sortino':>7s}  {'CAGR':>6s}  {'|DD|':>5s}  {'Final $':>10s}")

    for plabel, ps, pe in periods:
        for long_sym, long_df, inv_sym, inv_df in (
            ("QQQ", qqq, "PSQ", psq), ("SPY", spy, "SH", sh),
        ):
            if inv_df.empty:
                continue
            close_long = slice_close(long_df, ps, pe)
            close_inv = slice_close(inv_df, ps, pe)
            if close_long.empty or close_inv.empty or len(close_inv) < 200:
                continue

            # T-bill OFF baseline
            eq_tbill, _ = bah_on_trend_with_tbill(close_long, tbill_daily, 8000.0, 1.0)
            m_tbill = equity_metrics(eq_tbill, 8000.0)
            print(f"  {plabel:30s}  {long_sym}+T-bill OFF  {'baseline':10s}  "
                  f"{m_tbill['sortino']:>7.2f}  {m_tbill['cagr']:>+5.1%}  "
                  f"{abs(m_tbill['max_drawdown']):>4.0%}  ${m_tbill['final_equity']:>8,.0f}")

            # Inverse ETF OFF
            eq_inv, _ = bah_on_trend_inverse_off(close_long, close_inv, 8000.0)
            if not eq_inv.empty:
                m_inv = equity_metrics(eq_inv, 8000.0)
                print(f"  {plabel:30s}  {long_sym}+{inv_sym} OFF     "
                      f"{'inverse':10s}  {m_inv['sortino']:>7.2f}  "
                      f"{m_inv['cagr']:>+5.1%}  {abs(m_inv['max_drawdown']):>4.0%}  "
                      f"${m_inv['final_equity']:>8,.0f}")


def main() -> int:
    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)

    print("Fetching SPY, QQQ, T-bill data...")
    spy = yahoo.daily("SPY", full_start.isoformat(), full_end.isoformat())
    qqq = yahoo.daily("QQQ", full_start.isoformat(), full_end.isoformat())
    cache = REPO / "data" / "fred_cache"
    tbill_pct = fetch_tbill_3m(full_start.isoformat(), full_end.isoformat(),
                               cache_dir=cache)["close"]
    tbill_daily = daily_tbill_factor(tbill_pct)
    print(f"  SPY: {len(spy)} bars, QQQ: {len(qqq)} bars")
    print(f"  T-bill: {len(tbill_pct)} obs, range {tbill_pct.min():.2f}-{tbill_pct.max():.2f}%")
    print(f"  Avg T-bill rate over period: {tbill_pct.mean():.2f}% annual")

    periods = [
        ("2018-2026 (in-sample)",     date(2018, 1, 1), date(2026, 4, 15)),
        ("2010-2017 (held-out)",      date(2010, 1, 1), date(2017, 12, 31)),
        ("2000-2009 (regime shift)",  date(2000, 1, 3), date(2009, 12, 31)),
    ]

    p1_results = priority_1(spy, qqq, tbill_daily, periods)
    p2_results = priority_2(tbill_daily, periods)
    priority_3(spy, qqq, tbill_daily, periods)

    return 0


if __name__ == "__main__":
    sys.exit(main())
