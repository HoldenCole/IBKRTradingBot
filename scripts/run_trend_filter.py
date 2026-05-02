"""Trend filter (Filter 1) analysis on IBS-LS QQQ trade ledger.

User spec (2026-05-02): single asymmetric multi-timeframe trend filter,
no tuning, one analysis, decision applied.

Filter:
  ON when QQQ close > SMA(50) AND SMA(50) > SMA(200)
  OFF otherwise

Test plan:
  - Re-run IBS-LS QQQ over 2018-2026 with filter ON (engine-level gate
    at signal-day, drops the entry).
  - Re-run unfiltered baseline (no filter) for comparison.
  - Report full / train (2018-2022) / test (2023-2026).
  - Compute Sortino lift, return lift, max-DD lift, trade count delta.
  - Compute QQQ buy-and-hold benchmark on FILTER-ON-DAYS-ONLY (cash
    return when filter is OFF) — this is the "would I have been better
    off just holding QQQ during ON regimes" comparison.
  - Per-regime breakdown: which trades got dropped, by hand-labeled
    regime year.

Methodology note: pure trade-level gating ("just drop trades whose
entry day had filter=OFF") under-counts the filter's effect because
the original engine had max_concurrent=1, so dropping a trade can
free capacity for a next-signal trade that was previously blocked.
Engine-level gating (filter passed to SharesBacktestEngine) handles
this correctly. We use engine-level gating throughout this analysis
and document the difference.

Decision criteria (locked before seeing results, per user):
  Useful if:
    - Sortino lift positive in BOTH train and test
    - Filtered Sortino > QQQ-BAH-on-ON-days Sortino (same period)
    - Trade count drop < 50%
  Decisive if all above AND filtered Sortino > 1.0 standalone.
  Otherwise: not useful. Do not tune. Decide what to do next.
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

import numpy as np
import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics
from src.backtest.regime_filter import BullishTrendFilter
from src.backtest.shares_engine import SharesBacktestConfig, SharesBacktestEngine
from src.backtest.v2_report import REGIME_BY_YEAR
from src.backtest.walk_forward import single_fold
from src.data.fmp import FMPHistorical
from src.strategies.ibs import IBSStrategy


def slice_close(df: pd.DataFrame, start: date, end: date) -> pd.Series:
    idx = [d.date() if hasattr(d, "date") else d for d in df.index]
    mask = pd.Series([start <= d <= end for d in idx], index=df.index)
    return df.loc[mask, "close"]


def slice_df(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    idx = [d.date() if hasattr(d, "date") else d for d in df.index]
    mask = pd.Series([start <= d <= end for d in idx], index=df.index)
    return df.loc[mask]


def run_ibs_ls(daily: dict, start: date, end: date, regime_filter=None):
    """Run IBS-LS QQQ shares with optional regime filter at engine level."""
    cfg = SharesBacktestConfig(
        start=start, end=end, initial_capital=8000.0,
        allocation_pct=1.0, max_concurrent=1,
        slippage_bps=5.0, time_stop_days=5,
        regime_filter=regime_filter,
    )
    sliced = {"SPY": pd.DataFrame(), "QQQ": daily["QQQ"]}
    eng = SharesBacktestEngine(
        config=cfg,
        strategies=[IBSStrategy(sqqq_short_enabled=True, long_enabled=True)],
        daily_bars=sliced,
    )
    return eng.run()


def bah_on_filter_days(close: pd.Series, daily_qqq: pd.DataFrame,
                      filter_obj: BullishTrendFilter,
                      start_capital: float = 8000.0) -> dict:
    """Buy-and-hold metrics computed only on filter-ON days; cash on OFF days.

    For each day in `close`, check filter status on that day. ON -> capture
    QQQ's daily return. OFF -> 0% return (cash).
    """
    if close.empty:
        return {"sortino": 0.0, "sharpe": 0.0, "total_return": 0.0,
                "max_drawdown": 0.0, "n_on_days": 0, "n_total_days": 0}

    rets = close.pct_change().fillna(0.0)
    on_flags = []
    for ts in close.index:
        d = ts.date() if hasattr(ts, "date") else ts
        on_flags.append(filter_obj.is_active(daily_qqq, d))
    on_flags = pd.Series(on_flags, index=close.index)

    # Synthetic equity curve: invest in QQQ on ON-days, cash (0%) on OFF-days
    masked_rets = rets.where(on_flags, 0.0)
    equity = (1 + masked_rets).cumprod() * start_capital
    m = equity_metrics(equity, start_capital)
    m["n_on_days"] = int(on_flags.sum())
    m["n_total_days"] = int(len(on_flags))
    return m


def metrics_with_count(result, start_capital=8000.0):
    m = equity_metrics(result.equity_curve, start_capital)
    m["n_trades"] = len(result.trades)
    return m


def per_regime_drop(unfiltered, filter_obj, daily_qqq):
    """Of the unfiltered trades, classify each by filter status on its
    entry date. Cannot match by trade_id because the filtered engine run
    generates new uuids; instead we ask the filter directly per entry day.
    """
    by_regime: dict[str, dict] = defaultdict(
        lambda: {"n_total": 0, "pnl_total": 0.0, "n_dropped": 0, "pnl_dropped": 0.0}
    )
    for t in unfiltered.trades:
        regime = REGIME_BY_YEAR.get(t.entry_date.year, "?")
        by_regime[regime]["n_total"] += 1
        by_regime[regime]["pnl_total"] += t.pnl
        # Filter is checked on signal day = entry day - 1 trading day.
        # Approximate by using entry_date directly; SMA values change slowly
        # enough that signal-day vs entry-day usually agree for SMA-based
        # filters. Acceptable for a per-regime summary.
        if not filter_obj.is_active(daily_qqq, t.entry_date):
            by_regime[regime]["n_dropped"] += 1
            by_regime[regime]["pnl_dropped"] += t.pnl
    return by_regime


def main() -> int:
    api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        print("ERROR: FMP_API_KEY not set", file=sys.stderr)
        return 1

    fmp = FMPHistorical(api_key=api_key)
    full_start = date(2018, 1, 1)
    full_end = date(2026, 4, 15)
    fold = single_fold(full_start, full_end, train_years=5, test_years=3)

    buf = (full_start - timedelta(days=600)).isoformat()
    end_iso = full_end.isoformat()
    daily = {
        "SPY": fmp.daily("SPY", buf, end_iso),
        "QQQ": fmp.daily("QQQ", buf, end_iso),
    }

    filter_obj = BullishTrendFilter(fast_sma=50, slow_sma=200)

    print("# Filter 1 — Bullish multi-timeframe trend on QQQ shares")
    print(f"# Filter: ON when close > SMA(50) > SMA(200), OFF otherwise")
    print(f"# Period: {full_start} -> {full_end}")
    print(f"# Strategy: IBS-LS QQQ shares (long+short, sqqq_short_enabled=True)")
    print(f"# Methodology: engine-level gating (filter blocks signals at queue time)\n")

    slices = [
        ("FULL",  full_start,        full_end),
        ("TRAIN", fold.train_start,  fold.train_end),
        ("TEST",  fold.test_start,   fold.test_end),
    ]

    rows = []
    for name, s_start, s_end in slices:
        unfiltered = run_ibs_ls(daily, s_start, s_end, regime_filter=None)
        filtered = run_ibs_ls(daily, s_start, s_end, regime_filter=filter_obj)

        u_m = metrics_with_count(unfiltered)
        f_m = metrics_with_count(filtered)
        bah_close = slice_close(daily["QQQ"], s_start, s_end)
        bah_full = buy_and_hold_metrics(bah_close, 8000.0, "QQQ")
        bah_on = bah_on_filter_days(bah_close, daily["QQQ"], filter_obj)

        rows.append({
            "name": name, "start": s_start, "end": s_end,
            "u_m": u_m, "f_m": f_m,
            "bah_full": bah_full, "bah_on": bah_on,
            "unfiltered": unfiltered, "filtered": filtered,
        })

    # === Comparison table ===
    print("=" * 96)
    print("COMPARISON TABLE — unfiltered baseline vs filtered, with benchmarks")
    print("=" * 96)
    for row in rows:
        u, f, b_full, b_on = row["u_m"], row["f_m"], row["bah_full"], row["bah_on"]
        print(f"\n--- {row['name']} ({row['start']} to {row['end']}) ---")
        print(f"  {'Metric':22s}  {'Unfilt':>9s}  {'Filtered':>9s}  {'Lift':>9s}  "
              f"{'BAH-full':>9s}  {'BAH-ON-only':>11s}")
        print(f"  {'Sortino':22s}  "
              f"{u['sortino']:>9.2f}  {f['sortino']:>9.2f}  "
              f"{f['sortino']-u['sortino']:>+9.2f}  "
              f"{b_full.sortino:>9.2f}  {b_on['sortino']:>11.2f}")
        print(f"  {'Sharpe':22s}  "
              f"{u['sharpe']:>9.2f}  {f['sharpe']:>9.2f}  "
              f"{f['sharpe']-u['sharpe']:>+9.2f}  "
              f"{b_full.sharpe:>9.2f}  {b_on['sharpe']:>11.2f}")
        print(f"  {'Total return':22s}  "
              f"{u['total_return']*100:>+8.1f}%  {f['total_return']*100:>+8.1f}%  "
              f"{(f['total_return']-u['total_return'])*100:>+8.1f}pp  "
              f"{b_full.total_return*100:>+8.1f}%  {b_on['total_return']*100:>+10.1f}%")
        print(f"  {'Max drawdown':22s}  "
              f"{u['max_drawdown']*100:>+8.1f}%  {f['max_drawdown']*100:>+8.1f}%  "
              f"{(f['max_drawdown']-u['max_drawdown'])*100:>+8.1f}pp  "
              f"{b_full.max_drawdown*100:>+8.1f}%  {b_on['max_drawdown']*100:>+10.1f}%")
        print(f"  {'Trades':22s}  {u['n_trades']:>9d}  {f['n_trades']:>9d}  "
              f"{f['n_trades']-u['n_trades']:>+9d}  "
              f"{'-':>9s}  {'-':>11s}")
        if u['n_trades'] > 0:
            drop_pct = (u['n_trades'] - f['n_trades']) / u['n_trades']
            print(f"  {'Trade drop %':22s}  {drop_pct:>9.1%}")
        print(f"  {'BAH-ON days':22s}  "
              f"{'-':>9s}  {'-':>9s}  {'-':>9s}  "
              f"{'-':>9s}  {b_on['n_on_days']}/{b_on['n_total_days']} "
              f"({b_on['n_on_days']/max(1,b_on['n_total_days']):.0%})")

    # === Per-regime drop ===
    print("\n" + "=" * 96)
    print("PER-REGIME DROP — full period only")
    print("=" * 96)
    full_row = rows[0]
    drop = per_regime_drop(full_row["unfiltered"], filter_obj, daily["QQQ"])
    print(f"\n  {'Regime':22s}  {'N_total':>7s}  {'N_kept':>7s}  {'N_drop':>7s}  "
          f"{'Drop_pnl':>10s}  {'Kept_pnl':>10s}")
    for regime in sorted(drop, key=lambda r: -drop[r]["n_total"]):
        d = drop[regime]
        n_kept = d["n_total"] - d["n_dropped"]
        pnl_kept = d["pnl_total"] - d["pnl_dropped"]
        print(f"  {regime:22s}  {d['n_total']:>7d}  {n_kept:>7d}  {d['n_dropped']:>7d}  "
              f"${d['pnl_dropped']:>+8.0f}  ${pnl_kept:>+8.0f}")

    # === Decision rule application ===
    print("\n" + "=" * 96)
    print("DECISION RULE APPLICATION — locked criteria from user spec")
    print("=" * 96)
    train, test, full = rows[1], rows[2], rows[0]

    sortino_lift_train = train["f_m"]["sortino"] - train["u_m"]["sortino"]
    sortino_lift_test = test["f_m"]["sortino"] - test["u_m"]["sortino"]
    crit_1 = sortino_lift_train > 0 and sortino_lift_test > 0

    f_sort_full = full["f_m"]["sortino"]
    bah_on_sort_full = full["bah_on"]["sortino"]
    crit_2 = f_sort_full > bah_on_sort_full

    drop_pct_full = ((full["u_m"]["n_trades"] - full["f_m"]["n_trades"])
                     / max(1, full["u_m"]["n_trades"]))
    crit_3 = drop_pct_full < 0.50

    print(f"\n  Criterion 1 — Sortino lift positive in BOTH train and test:")
    print(f"    Train lift: {sortino_lift_train:+.2f}  "
          f"(required: > 0)  {'PASS' if sortino_lift_train > 0 else 'FAIL'}")
    print(f"    Test lift:  {sortino_lift_test:+.2f}  "
          f"(required: > 0)  {'PASS' if sortino_lift_test > 0 else 'FAIL'}")
    print(f"    Overall: {'PASS' if crit_1 else 'FAIL'}")

    print(f"\n  Criterion 2 — Filtered Sortino > BAH-on-ON-days Sortino (full):")
    print(f"    Filtered: {f_sort_full:.2f}  vs  BAH-ON-only: {bah_on_sort_full:.2f}  "
          f"{'PASS' if crit_2 else 'FAIL'}")

    print(f"\n  Criterion 3 — Trade drop < 50%:")
    print(f"    Drop: {drop_pct_full:.1%}  (required: < 50%)  "
          f"{'PASS' if crit_3 else 'FAIL'}")

    useful = crit_1 and crit_2 and crit_3
    decisive = useful and f_sort_full > 1.0

    print(f"\n  --- VERDICT ---")
    if decisive:
        print(f"  DECISIVE: all three useful criteria pass AND filtered Sortino "
              f"{f_sort_full:.2f} > 1.0")
    elif useful:
        print(f"  USEFUL: all three criteria pass; filtered Sortino "
              f"{f_sort_full:.2f} <= 1.0")
    else:
        print(f"  NOT USEFUL — at least one criterion failed.")
        print(f"  Per validation discipline: do NOT tune MA windows.")
        print(f"  Trend-only does not capture the failure regimes for IBS-LS QQQ.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
