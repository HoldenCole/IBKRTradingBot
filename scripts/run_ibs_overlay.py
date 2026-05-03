"""Priority 4: IBS-shorts overlay on QQQ during OFF regime only.

Spec (locked):
  - Trade IBS short signals on QQQ shares ONLY during OFF-regime periods
    (BAH-on-trend filter is OFF: SMA(50) <= SMA(200) OR close <= SMA(50)).
  - Entry: IBS > 0.80 AND prior IBS <= 0.80 AND close < SMA200 AND no
    open position (no stacking).
  - Exit: IBS < 0.30 at close (signal flip) OR regime turns ON (force-close).
  - Cash earns T-bill (FRED DGS3MO) when not in a short position.
  - Tax: STCG (= ordinary). Sample size is small (~3-5 sustained bears in
    the 26-year window) so per-regime N is reported explicitly.

Bear-regime breakouts (defined by widely-recognized peak-to-trough windows):
  2000-2002 dotcom unwind  (2000-03-24 → 2002-10-09)
  2008-2009 GFC            (2008-09-01 → 2009-03-09)
  2018-Q4 sell-off         (2018-10-01 → 2018-12-24)
  2020 COVID crash          (2020-02-19 → 2020-04-07)
  2022 inflation bear       (2022-01-03 → 2022-10-13)

Position sizing: 100% of cash on each short entry (overlay is meant to
work residual cash in an OFF-regime). Short P&L per day = -delta_close *
shares. We mark to market daily.

Output:
  - Headline: 26-year strategy performance (Sortino, CAGR, |DD|, final $).
  - Per-bear-regime: N trades, win rate, total $ P&L, avg trade.
  - Sortino lift vs. T-bill-only baseline (which is what you'd hold
    without the overlay).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import equity_metrics
from src.data import yahoo
from src.data.fred import fetch_tbill_3m


@dataclass
class IBSShortTrade:
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    pnl_pct: float            # short return = -(exit/entry - 1)
    pnl_dollars: float
    reason: str
    hold_days: int
    ibs_at_entry: float
    ibs_at_exit: float


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    sma_fast = close.rolling(fast, min_periods=fast).mean()
    sma_slow = close.rolling(slow, min_periods=slow).mean()
    return ((close > sma_fast) & (sma_fast > sma_slow)).fillna(False)


def daily_tbill_factor(tbill_pct: pd.Series) -> pd.Series:
    rates = (tbill_pct / 100.0).reindex(tbill_pct.index).ffill().fillna(0.0)
    return (1.0 + rates) ** (1.0 / 252.0) - 1.0


def compute_ibs(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    rng = (high - low).replace(0.0, float("nan"))
    return ((close - low) / rng).fillna(0.5)


def run_ibs_overlay(
    df: pd.DataFrame,
    tbill_daily: pd.Series,
    start_capital: float = 8000.0,
    short_thresh: float = 0.80,
    exit_thresh: float = 0.30,
    sma_long: int = 200,
) -> tuple[pd.Series, list[IBSShortTrade]]:
    """Run the IBS-shorts overlay daily simulation.

    Equity is composed of cash that earns the T-bill rate on idle days
    plus a single open short (when in trade) marked daily.
    """
    high, low, close = df["high"], df["low"], df["close"]
    ibs = compute_ibs(high, low, close)
    sma200 = close.rolling(sma_long, min_periods=sma_long).mean()
    on_flags = filter_on_flags(close)
    tbill = tbill_daily.reindex(close.index).ffill().fillna(0.0)

    cash = start_capital
    in_short = False
    short_entry_price = 0.0
    short_shares = 0.0
    short_entry_date: date | None = None
    short_entry_ibs = 0.0
    equity_by_date: dict[pd.Timestamp, float] = {}
    trades: list[IBSShortTrade] = []
    prev_close: float | None = None
    prev_ibs: float | None = None

    for i, ts in enumerate(close.index):
        c = float(close.iloc[i])
        ibs_today = float(ibs.iloc[i])
        sma = sma200.iloc[i]
        on_today = bool(on_flags.iloc[i])
        tbill_factor = float(tbill.iloc[i])

        # Mark-to-market the short before evaluating exit
        if in_short and prev_close is not None:
            # short P&L = -(c - prev_close) * shares
            cash += -(c - prev_close) * short_shares

        # Cash interest on idle (apply only if not in trade)
        if not in_short:
            cash *= (1.0 + tbill_factor)

        # Exit logic — applied on close
        exit_reason: str | None = None
        if in_short:
            if on_today:
                exit_reason = "regime_on"
            elif ibs_today < exit_thresh:
                exit_reason = "ibs_below_30"

        if in_short and exit_reason is not None:
            short_pnl_pct = -(c / short_entry_price - 1.0)
            short_pnl_dollars = (short_entry_price - c) * short_shares
            trades.append(IBSShortTrade(
                entry_date=short_entry_date,
                exit_date=ts.date(),
                entry_price=short_entry_price,
                exit_price=c,
                pnl_pct=short_pnl_pct,
                pnl_dollars=short_pnl_dollars,
                reason=exit_reason,
                hold_days=(ts.date() - short_entry_date).days,
                ibs_at_entry=short_entry_ibs,
                ibs_at_exit=ibs_today,
            ))
            in_short = False
            short_shares = 0.0

        # Entry logic — only if currently flat AND OFF AND IBS criteria
        if (not in_short
                and not on_today
                and not pd.isna(sma) and c < float(sma)
                and prev_ibs is not None
                and ibs_today > short_thresh
                and prev_ibs <= short_thresh):
            # Enter short at close: shares = cash / price (100% notional)
            short_shares = cash / c
            short_entry_price = c
            short_entry_date = ts.date()
            short_entry_ibs = ibs_today
            in_short = True

        equity_by_date[ts] = cash
        prev_close = c
        prev_ibs = ibs_today

    # Force-close at end of backtest if still in a short
    if in_short and short_entry_date is not None:
        last_ts = close.index[-1]
        c = float(close.iloc[-1])
        short_pnl_dollars = (short_entry_price - c) * short_shares
        trades.append(IBSShortTrade(
            entry_date=short_entry_date,
            exit_date=last_ts.date(),
            entry_price=short_entry_price,
            exit_price=c,
            pnl_pct=-(c / short_entry_price - 1.0),
            pnl_dollars=short_pnl_dollars,
            reason="end_of_backtest",
            hold_days=(last_ts.date() - short_entry_date).days,
            ibs_at_entry=short_entry_ibs,
            ibs_at_exit=float(ibs.iloc[-1]),
        ))
        equity_by_date[last_ts] = cash

    eq = pd.Series(equity_by_date).sort_index()
    return eq, trades


def cash_only_baseline(close_idx: pd.DatetimeIndex,
                        tbill_daily: pd.Series,
                        start_capital: float = 8000.0) -> pd.Series:
    """T-bill-only baseline: idle cash earning T-bill, no positions taken."""
    tbill = tbill_daily.reindex(close_idx).ffill().fillna(0.0)
    eq = (1 + tbill).cumprod() * start_capital
    return eq


def bah_on_trend_baseline(close: pd.Series, tbill_daily: pd.Series,
                          start_capital: float = 8000.0) -> pd.Series:
    """Long underlying when ON, T-bill when OFF — the existing v2 winner."""
    rets = close.pct_change().fillna(0.0)
    flags = filter_on_flags(close)
    tbill = tbill_daily.reindex(close.index).ffill().fillna(0.0)
    daily = rets.where(flags, tbill)
    return (1 + daily).cumprod() * start_capital


def run_combined_overlay(
    df: pd.DataFrame,
    tbill_daily: pd.Series,
    start_capital: float = 8000.0,
    short_thresh: float = 0.80,
    exit_thresh: float = 0.30,
) -> tuple[pd.Series, list[IBSShortTrade]]:
    """Combined: long underlying when ON, IBS shorts when OFF + signal,
    T-bill on idle cash otherwise. Returns equity_curve + trade list.

    Implementation: composition of daily returns to match the BAH-on-trend
    baseline convention (today's flag drives today's return).

    Per day:
      ON:  return = rets[t]                  (long underlying)
      OFF, in short:  return = -rets[t]      (short P&L)
      OFF, idle:  return = tbill_daily[t]    (cash earning T-bill)

    Short state machine (transitions evaluated at end of each day):
      - if on_today: short forced flat (regime change to ON)
      - if in_short and ibs[t] < 0.30: exit at close
      - if idle and ibs[t] > 0.80 and prev_ibs <= 0.80 and close < sma200:
            enter short at close (today's return for newly-entered short = 0)
    """
    high, low, close = df["high"], df["low"], df["close"]
    rets = close.pct_change().fillna(0.0)
    ibs = compute_ibs(high, low, close)
    sma200 = close.rolling(200, min_periods=200).mean()
    on_flags = filter_on_flags(close)
    tbill = tbill_daily.reindex(close.index).ffill().fillna(0.0)

    in_short = False
    short_entry_price = 0.0
    short_entry_date: date | None = None
    short_entry_ibs = 0.0
    short_entry_equity = 0.0  # equity at moment of entry (used to compute pnl_dollars for trade log)
    daily_ret = pd.Series(0.0, index=close.index)
    trades: list[IBSShortTrade] = []
    prev_ibs: float | None = None

    for i, ts in enumerate(close.index):
        c = float(close.iloc[i])
        ibs_today = float(ibs.iloc[i])
        sma = sma200.iloc[i]
        on_today = bool(on_flags.iloc[i])
        r_today = float(rets.iloc[i])
        tbill_today = float(tbill.iloc[i])

        # Today's return based on incoming state (set at yesterday's close)
        if on_today:
            daily_ret.iloc[i] = r_today
        elif in_short:
            daily_ret.iloc[i] = -r_today
        else:
            daily_ret.iloc[i] = tbill_today

        # State transitions evaluated AFTER today's return
        # (1) regime turned ON → close any short
        if on_today and in_short:
            trades.append(IBSShortTrade(
                entry_date=short_entry_date, exit_date=ts.date(),
                entry_price=short_entry_price, exit_price=c,
                pnl_pct=-(c / short_entry_price - 1.0),
                pnl_dollars=(short_entry_price - c) * (short_entry_equity / short_entry_price),
                reason="regime_on",
                hold_days=(ts.date() - short_entry_date).days,
                ibs_at_entry=short_entry_ibs, ibs_at_exit=ibs_today,
            ))
            in_short = False

        # (2) IBS exit
        if in_short and not on_today and ibs_today < exit_thresh:
            trades.append(IBSShortTrade(
                entry_date=short_entry_date, exit_date=ts.date(),
                entry_price=short_entry_price, exit_price=c,
                pnl_pct=-(c / short_entry_price - 1.0),
                pnl_dollars=(short_entry_price - c) * (short_entry_equity / short_entry_price),
                reason="ibs_below_30",
                hold_days=(ts.date() - short_entry_date).days,
                ibs_at_entry=short_entry_ibs, ibs_at_exit=ibs_today,
            ))
            in_short = False

        # (3) IBS short entry — at end of day t (today's return already booked)
        if (not on_today and not in_short
                and not pd.isna(sma) and c < float(sma)
                and prev_ibs is not None
                and ibs_today > short_thresh
                and prev_ibs <= short_thresh):
            in_short = True
            short_entry_price = c
            short_entry_date = ts.date()
            short_entry_ibs = ibs_today
            # cumulative equity to date for trade-log dollar P&L
            short_entry_equity = float(start_capital * (1 + daily_ret.iloc[: i + 1]).prod())

        prev_ibs = ibs_today

    # Force-close at end
    if in_short and short_entry_date is not None:
        last_ts = close.index[-1]
        c = float(close.iloc[-1])
        trades.append(IBSShortTrade(
            entry_date=short_entry_date, exit_date=last_ts.date(),
            entry_price=short_entry_price, exit_price=c,
            pnl_pct=-(c / short_entry_price - 1.0),
            pnl_dollars=(short_entry_price - c) * (short_entry_equity / short_entry_price),
            reason="end_of_backtest",
            hold_days=(last_ts.date() - short_entry_date).days,
            ibs_at_entry=short_entry_ibs,
            ibs_at_exit=float(ibs.iloc[-1]),
        ))

    eq = (1 + daily_ret).cumprod() * start_capital
    return eq, trades


BEAR_REGIMES = [
    ("2000-2002 dotcom", date(2000, 3, 24), date(2002, 10, 9)),
    ("2008-2009 GFC",    date(2008, 9, 1),  date(2009, 3, 9)),
    ("2018-Q4 selloff",  date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 COVID",       date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation",   date(2022, 1, 3),  date(2022, 10, 13)),
]


def per_regime_breakdown(trades: list[IBSShortTrade]) -> None:
    print(f"\n{'Bear regime':22s}  {'Window':25s}  {'N':>3s}  "
          f"{'Win %':>6s}  {'Total P&L':>10s}  {'Avg Trade':>10s}  "
          f"{'Avg Hold':>8s}")
    for label, ps, pe in BEAR_REGIMES:
        in_window = [t for t in trades if ps <= t.entry_date <= pe]
        n = len(in_window)
        if n == 0:
            print(f"  {label:22s}  {ps.isoformat()}→{pe.isoformat()[5:]}      0  "
                  f"{'N/A':>6s}  {'N/A':>10s}  {'N/A':>10s}  {'N/A':>8s}")
            continue
        wins = sum(1 for t in in_window if t.pnl_dollars > 0)
        total = sum(t.pnl_dollars for t in in_window)
        avg = total / n
        avg_hold = sum(t.hold_days for t in in_window) / n
        print(f"  {label:22s}  {ps.isoformat()}→{pe.isoformat()[5:]}  {n:>3d}  "
              f"{wins/n:>5.0%}  ${total:>+8,.0f}  ${avg:>+8,.0f}  "
              f"{avg_hold:>5.1f} d")


def run_for_symbol(sym: str, start: date, end: date,
                   tbill_daily: pd.Series, start_capital: float) -> None:
    df = yahoo.daily(sym, start.isoformat(), end.isoformat())
    if df.empty:
        print(f"  {sym}: NO DATA")
        return

    print(f"\n{'='*92}")
    print(f"# {sym} IBS-shorts overlay (OFF-regime only) | "
          f"{start.isoformat()} → {end.isoformat()}")
    print('='*92)

    overlay_eq, trades = run_ibs_overlay(df, tbill_daily, start_capital)
    baseline_eq = cash_only_baseline(df.index, tbill_daily, start_capital)
    bah_eq = bah_on_trend_baseline(df["close"], tbill_daily, start_capital)
    combined_eq, combined_trades = run_combined_overlay(df, tbill_daily, start_capital)

    m_overlay = equity_metrics(overlay_eq, start_capital)
    m_base = equity_metrics(baseline_eq, start_capital)
    m_bah = equity_metrics(bah_eq, start_capital)
    m_combined = equity_metrics(combined_eq, start_capital)

    print(f"\n  {'Strategy':32s}  {'Sortino':>7s}    {'CAGR':>6s}  {'Max|DD|':>7s}    "
          f"{'Final $':>10s}    {'N trades':>9s}")
    print(f"  {'T-bill only':32s}   {m_base['sortino']:>5.2f}    "
          f"{m_base['cagr']:>+5.1%}     {abs(m_base['max_drawdown']):>4.0%}     "
          f"${m_base['final_equity']:>8,.0f}        --")
    print(f"  {'BAH-on-trend long (T-bill OFF)':32s}   {m_bah['sortino']:>5.2f}    "
          f"{m_bah['cagr']:>+5.1%}     {abs(m_bah['max_drawdown']):>4.0%}     "
          f"${m_bah['final_equity']:>8,.0f}        --")
    print(f"  {'IBS shorts (OFF only)':32s}   {m_overlay['sortino']:>5.2f}    "
          f"{m_overlay['cagr']:>+5.1%}     {abs(m_overlay['max_drawdown']):>4.0%}     "
          f"${m_overlay['final_equity']:>8,.0f}    {len(trades):>6d}")
    print(f"  {'Combined: BAH long + IBS shorts':32s}   {m_combined['sortino']:>5.2f}    "
          f"{m_combined['cagr']:>+5.1%}     {abs(m_combined['max_drawdown']):>4.0%}     "
          f"${m_combined['final_equity']:>8,.0f}    {len(combined_trades):>6d}")

    if trades:
        wins = sum(1 for t in trades if t.pnl_dollars > 0)
        avg_pnl = sum(t.pnl_dollars for t in trades) / len(trades)
        avg_hold = sum(t.hold_days for t in trades) / len(trades)
        avg_ret = sum(t.pnl_pct for t in trades) / len(trades)
        print(f"\n  Total trades: {len(trades)}  |  Win rate: {wins/len(trades):.0%}  "
              f"|  Avg P&L: ${avg_pnl:+.0f}  |  Avg return: {avg_ret*100:+.2f}%  "
              f"|  Avg hold: {avg_hold:.1f} days")

    per_regime_breakdown(trades)


def main() -> int:
    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)

    print("Fetching QQQ + SPY + T-bill...")
    tbill_pct = fetch_tbill_3m(
        full_start.isoformat(), full_end.isoformat(),
        cache_dir=REPO / "data" / "fred_cache",
    )["close"]
    tbill_daily = daily_tbill_factor(tbill_pct)

    for sym in ("QQQ", "SPY"):
        run_for_symbol(sym, full_start, full_end, tbill_daily, 8000.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
