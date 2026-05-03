"""Realistic deployable backtest with commission, slippage, and proper timing.

Resolves the Convention 1 vs Convention 2 question raised in Test A. After
careful retracing:

- Convention 1 (`flag[t] → ret[t]`): pure lookahead, NOT achievable
  operationally. Today's flag is computed from today's close, which is
  the exact same close that's needed to determine whether the prior-day
  position captured today's return. To use flag[t] for ret[t] you'd need
  to know close[t] before close[t]. Discarded.

- Convention 2 (`flag[t-1] → ret[t]`): realistic MOC convention.
  Decide at close[t-1] using SMA computed from prior closes. Place MOC
  order. Fill near close[t-1]. From close[t-1] to close[t] you're long,
  capturing ret[t]. This IS achievable on IBKR — MOC orders for QQQ
  (NASDAQ) have a 15:50 ET cutoff. Use SMA computed at 15:45 from price
  at 15:45 as a proxy for close. Slippage between 15:45 and 16:00 close
  is small for liquid ETFs.

- Convention 3 (next-day open fill): more conservative than Conv 2.
  Decide at close[t-1], submit market-on-open for next day. Fill at
  open[t]. Captures open[t] → close[t] only on entry day; close[t-1] →
  open[t] gap is foregone. Symmetric on exit: held close[t-1] → open[t],
  then in cash open[t] → close[t]. Achievable in any account; doesn't
  require MOC familiarity.

This script reports Convention 2 and Convention 3 side-by-side for QQQ
(2000-2026) and ^GSPC (1928-2026), with explicit commission and slippage
modeling.

Commission model:
  - QQQ: $0 commission (IBKR Lite or commission-free brokers; competitive
    benchmark for retail)
  - SGOV (T-bill ETF): $0 commission (same)
  - Slippage on QQQ: 1 bp per fill (0.01%) — conservative for an ETF
    with median spread ~$0.01 on a ~$500 share
  - Slippage on SGOV: 1 bp per fill (similar liquidity profile)
  - Per round-trip (entry + exit): 2 bps total
  - Annual transaction friction at 6.28 transitions/yr (one transition =
    out + in for the leg switch): ~0.25% per year

The slippage estimate is conservative. QQQ in 2024-2025 has typical
spread of $0.01-$0.02 on >$500 shares = 0.2-0.4 bps. Times two for
round-trip = 0.4-0.8 bps. We use 1 bp per fill = 2 bps round-trip as
buffer for stress periods.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import numpy as np
import pandas as pd

from src.backtest.benchmark import equity_metrics
from src.data import yahoo
from src.data.fred import fetch_tbill_3m


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def daily_tbill_factor(tbill_pct: pd.Series, idx: pd.Index) -> pd.Series:
    rate = tbill_pct.reindex(idx, method="ffill").bfill().fillna(0.0)
    return (1.0 + rate / 100.0) ** (1.0 / 252.0) - 1.0


def transition_count(flags: pd.Series) -> int:
    """Number of OFF→ON or ON→OFF flips."""
    return int(flags.ne(flags.shift(1)).sum())


def backtest_conv2_with_costs(
    close: pd.Series,
    flags: pd.Series,
    tbill_daily: pd.Series,
    start_capital: float = 8000.0,
    slippage_bps_per_fill: float = 1.0,
    commission_per_trade: float = 0.0,
) -> tuple[pd.Series, dict]:
    """Convention 2 (MOC) with commission and slippage.

    Each transition (flag flip): subtract slippage_bps + commission from cash.
    """
    rets = close.pct_change().fillna(0.0)
    shifted = flags.shift(1).fillna(False).astype(bool)
    daily = rets.where(shifted, tbill_daily.reindex(close.index).fillna(0.0))

    # Apply transition costs on flip days. A flip means the position changed
    # going INTO day t (signal flipped at close[t-1]). The trade happens at
    # close[t-1] under MOC; we apply the friction to that day's return.
    flips = shifted.ne(shifted.shift(1)).fillna(False).astype(bool)
    flip_friction = -(slippage_bps_per_fill / 10000.0) * flips.astype(float)
    daily = daily + flip_friction

    eq = (1 + daily).cumprod() * start_capital
    # Apply per-trade commission as a flat dollar deduction on flip days
    if commission_per_trade > 0:
        for ts, is_flip in flips.items():
            if is_flip:
                eq.loc[ts:] *= (eq.loc[ts] - commission_per_trade) / eq.loc[ts]

    info = {
        "n_transitions": int(flips.sum()),
        "transitions_per_year": float(flips.sum() / max(1e-9, len(close) / 252)),
        "annual_friction_drag_bps": (
            float(flips.sum()) * slippage_bps_per_fill / max(1e-9, len(close) / 252)
        ),
    }
    return eq, info


def backtest_conv3_with_costs(
    df: pd.DataFrame,
    flags: pd.Series,
    tbill_daily: pd.Series,
    start_capital: float = 8000.0,
    slippage_bps_per_fill: float = 1.0,
) -> tuple[pd.Series, dict]:
    """Convention 3 (next-day open fill).

    Decision at close[t-1], submit MOO order, fill at open[t]. Returns:
      - On entry day (signal flipped to ON yesterday): captured open[t] → close[t]
      - On normal ON days: captured close[t-1] → close[t]
      - On exit day (signal flipped to OFF yesterday): captured close[t-1] → open[t]
        + open[t]-to-close[t] earns T-bill (cash from sale)
      - On normal OFF days: T-bill close[t-1] → close[t]
    """
    open_ = df["open"]
    close = df["close"]
    rets_close = close.pct_change().fillna(0.0)
    rets_open_to_close = (close / open_ - 1.0).fillna(0.0)
    rets_close_to_open = (open_ / close.shift(1) - 1.0).fillna(0.0)
    tbill = tbill_daily.reindex(close.index).fillna(0.0)

    shifted = flags.shift(1).fillna(False).astype(bool)
    twice_shifted = flags.shift(2).fillna(False).astype(bool)

    # Position state at start of day t is shifted[t]. State change days:
    entered_today = shifted & ~twice_shifted    # not long yesterday, long today
    exited_today = ~shifted & twice_shifted     # long yesterday, not long today

    daily = pd.Series(0.0, index=close.index)
    # Normal ON days (long all day): close-to-close
    daily[shifted & ~entered_today & ~exited_today] = \
        rets_close[shifted & ~entered_today & ~exited_today]
    # Normal OFF days
    daily[~shifted & ~entered_today & ~exited_today] = \
        tbill[~shifted & ~entered_today & ~exited_today]
    # Entry day: open-to-close on the long, close-to-open in T-bill
    daily[entered_today] = (
        (1 + tbill[entered_today]) * (1 + rets_open_to_close[entered_today]) - 1
    )
    # Exit day: close-to-open on the long, open-to-close in T-bill
    daily[exited_today] = (
        (1 + rets_close_to_open[exited_today]) * (1 + tbill[exited_today]) - 1
    )

    # Apply slippage on each transition (one fill per flip)
    flips = shifted.ne(shifted.shift(1)).fillna(False).astype(bool)
    flip_friction = -(slippage_bps_per_fill / 10000.0) * flips.astype(float)
    daily = daily + flip_friction

    eq = (1 + daily).cumprod() * start_capital
    info = {
        "n_transitions": int(flips.sum()),
        "transitions_per_year": float(flips.sum() / max(1e-9, len(close) / 252)),
    }
    return eq, info


def run_backtest_suite(label: str, df: pd.DataFrame, tbill_daily: pd.Series,
                        start_capital: float = 8000.0):
    close = df["close"]
    flags = filter_on_flags(close)

    print(f"\n{'='*100}")
    print(f"# {label}")
    print('='*100)

    print(f"\n{'Convention':40s}  {'Sortino':>7s}    {'CAGR':>6s}  {'AT-CAGR':>7s}  "
          f"{'|DD|':>5s}  {'Trans/yr':>8s}  {'Final $':>12s}")

    # Buy-and-hold baseline (no strategy)
    bah_eq = (1 + close.pct_change().fillna(0.0)).cumprod() * start_capital
    mb = equity_metrics(bah_eq, start_capital)
    print(f"  {'Buy-and-hold (no strategy)':40s}  {mb['sortino']:>5.2f}    "
          f"{mb['cagr']:>+5.1%}   {'(n/a)':>7s}    {abs(mb['max_drawdown']):>4.0%}  "
          f"{'  --':>8s}  ${mb['final_equity']:>10,.0f}")

    # Conv 2 — no costs
    eq_c2_zero, info_c2 = backtest_conv2_with_costs(
        close, flags, tbill_daily, start_capital, slippage_bps_per_fill=0.0,
    )
    m = equity_metrics(eq_c2_zero, start_capital)
    at_cagr = compute_at_cagr(eq_c2_zero, start_capital, tax_rate=0.24)
    print(f"  {'Conv 2 (MOC), zero costs':40s}  {m['sortino']:>5.2f}    "
          f"{m['cagr']:>+5.1%}   {at_cagr:>+5.1%}    {abs(m['max_drawdown']):>4.0%}  "
          f"{info_c2['transitions_per_year']:>5.2f}/yr  ${m['final_equity']:>10,.0f}")

    # Conv 2 — with 1bp slippage per fill
    eq_c2_bp, _ = backtest_conv2_with_costs(
        close, flags, tbill_daily, start_capital, slippage_bps_per_fill=1.0,
    )
    m = equity_metrics(eq_c2_bp, start_capital)
    at_cagr = compute_at_cagr(eq_c2_bp, start_capital, tax_rate=0.24)
    print(f"  {'Conv 2 (MOC), 1bp slippage/fill':40s}  {m['sortino']:>5.2f}    "
          f"{m['cagr']:>+5.1%}   {at_cagr:>+5.1%}    {abs(m['max_drawdown']):>4.0%}  "
          f"{info_c2['transitions_per_year']:>5.2f}/yr  ${m['final_equity']:>10,.0f}")

    # Conv 2 — with 5bp slippage per fill (stress)
    eq_c2_5bp, _ = backtest_conv2_with_costs(
        close, flags, tbill_daily, start_capital, slippage_bps_per_fill=5.0,
    )
    m = equity_metrics(eq_c2_5bp, start_capital)
    at_cagr = compute_at_cagr(eq_c2_5bp, start_capital, tax_rate=0.24)
    print(f"  {'Conv 2 (MOC), 5bp slippage/fill':40s}  {m['sortino']:>5.2f}    "
          f"{m['cagr']:>+5.1%}   {at_cagr:>+5.1%}    {abs(m['max_drawdown']):>4.0%}  "
          f"{info_c2['transitions_per_year']:>5.2f}/yr  ${m['final_equity']:>10,.0f}")

    # Conv 3 — next-day open
    if "open" in df.columns:
        eq_c3_zero, info_c3 = backtest_conv3_with_costs(
            df, flags, tbill_daily, start_capital, slippage_bps_per_fill=0.0,
        )
        m = equity_metrics(eq_c3_zero, start_capital)
        at_cagr = compute_at_cagr(eq_c3_zero, start_capital, tax_rate=0.24)
        print(f"  {'Conv 3 (next-day open), zero costs':40s}  {m['sortino']:>5.2f}    "
              f"{m['cagr']:>+5.1%}   {at_cagr:>+5.1%}    {abs(m['max_drawdown']):>4.0%}  "
              f"{info_c3['transitions_per_year']:>5.2f}/yr  ${m['final_equity']:>10,.0f}")

        eq_c3_bp, _ = backtest_conv3_with_costs(
            df, flags, tbill_daily, start_capital, slippage_bps_per_fill=1.0,
        )
        m = equity_metrics(eq_c3_bp, start_capital)
        at_cagr = compute_at_cagr(eq_c3_bp, start_capital, tax_rate=0.24)
        print(f"  {'Conv 3 (next-day open), 1bp slippage':40s}  {m['sortino']:>5.2f}    "
              f"{m['cagr']:>+5.1%}   {at_cagr:>+5.1%}    {abs(m['max_drawdown']):>4.0%}  "
              f"{info_c3['transitions_per_year']:>5.2f}/yr  ${m['final_equity']:>10,.0f}")

        eq_c3_5bp, _ = backtest_conv3_with_costs(
            df, flags, tbill_daily, start_capital, slippage_bps_per_fill=5.0,
        )
        m = equity_metrics(eq_c3_5bp, start_capital)
        at_cagr = compute_at_cagr(eq_c3_5bp, start_capital, tax_rate=0.24)
        print(f"  {'Conv 3 (next-day open), 5bp slippage':40s}  {m['sortino']:>5.2f}    "
              f"{m['cagr']:>+5.1%}   {at_cagr:>+5.1%}    {abs(m['max_drawdown']):>4.0%}  "
              f"{info_c3['transitions_per_year']:>5.2f}/yr  ${m['final_equity']:>10,.0f}")


def compute_at_cagr(equity: pd.Series, start_capital: float, tax_rate: float
                    ) -> float:
    if equity.empty:
        return 0.0
    final = float(equity.iloc[-1])
    gain = final - start_capital
    tax = max(0, gain) * tax_rate
    after_tax = start_capital + (gain - tax)
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    return (after_tax / start_capital) ** (1.0 / max(1e-9, years)) - 1.0 \
           if after_tax > 0 else -1.0


def main() -> int:
    cache = REPO / "data" / "fred_cache"

    # ===== QQQ 2000-2026 =====
    qqq_start = date(2000, 1, 3)
    qqq_end = date(2026, 4, 14)
    print("Fetching QQQ + T-bill...")
    qqq = yahoo.daily("QQQ", qqq_start.isoformat(), qqq_end.isoformat())
    tbill_pct = fetch_tbill_3m(qqq_start.isoformat(), qqq_end.isoformat(),
                               cache_dir=cache)["close"]
    tbill_daily = daily_tbill_factor(tbill_pct, qqq.index)
    run_backtest_suite("QQQ 2000-2026 (modern era, 26 years)", qqq, tbill_daily)

    # ===== ^GSPC 1928-2026 =====
    print("\nFetching ^GSPC + TB3MS for long history...")
    gspc = yahoo.daily("^GSPC", "1928-12-30", "2026-04-14")
    # Use TB3MS (monthly, 1934-onward) for long history
    from scripts.run_long_history import fetch_tb3ms
    tb3ms = fetch_tb3ms("1928-12-30", "2026-04-14", cache_dir=cache)
    tbill_daily_long = daily_tbill_factor(tb3ms, gspc.index)
    run_backtest_suite("^GSPC 1928-2026 (full 98-year history)", gspc, tbill_daily_long)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
