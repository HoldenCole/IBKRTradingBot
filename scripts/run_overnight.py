"""Phase: Overnight drift on SPY and QQQ shares (Priority 3 candidate).

Tests the well-documented edge that overnight (close-to-open) returns
on SPY/QQQ have historically been positive ~57-60% of the time, while
day-session contributes ~0% on average.

Critical question: has the edge weakened post-2022? Walk-forward
2018-2022 train vs 2023-2026 test is the test. If the edge is gone
out-of-sample, the strategy is dead.

Reports per the v2 standard: headline + per-year + per-regime +
benchmark vs SPY + tier verdict + holding-period (always 1d for
overnight) + exit reasons.

Usage:
    FMP_API_KEY=... python scripts/run_overnight.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics
from src.backtest.overnight_engine import OvernightConfig, OvernightDriftEngine
from src.backtest.v2_report import format_v2_report
from src.backtest.walk_forward import single_fold
from src.data.fmp import FMPHistorical


def slice_bench(daily, start, end, label="SPY"):
    spy = daily[label]
    mask = pd.Series(
        [start <= (d.date() if hasattr(d, "date") else d) <= end
         for d in spy.index],
        index=spy.index,
    )
    return buy_and_hold_metrics(spy.loc[mask]["close"], 8000.0, label)


def run_one(label, daily, universe, start, end, benchmark, slippage_bps=1.0):
    """Slippage default = 1 bp each side for MOC/MOO on highly-liquid ETFs.
    This is realistic for SPY/QQQ where reference-auction prices are tight."""
    cfg = OvernightConfig(
        start=start, end=end, universe=universe,
        initial_capital=8000.0, slippage_bps=slippage_bps,
    )
    eng = OvernightDriftEngine(cfg, daily)
    result = eng.run()
    print(format_v2_report(
        label=label, trades=result.trades,
        equity_curve=result.equity_curve,
        initial_capital=cfg.initial_capital,
        benchmark=benchmark, skipped=result.skipped_signals,
    ))
    return result


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
    buf = (date(2018, 1, 1) - timedelta(days=10)).isoformat()
    end_iso = date(2026, 4, 15).isoformat()
    daily = {
        "SPY": fmp.daily("SPY", buf, end_iso),
        "QQQ": fmp.daily("QQQ", buf, end_iso),
    }

    full_start = date(2018, 1, 1)
    full_end = date(2026, 4, 15)
    fold = single_fold(full_start, full_end, train_years=5, test_years=3)

    spy_bench_full = slice_bench(daily, full_start, full_end, "SPY")
    spy_bench_train = slice_bench(daily, fold.train_start, fold.train_end, "SPY")
    spy_bench_test = slice_bench(daily, fold.test_start, fold.test_end, "SPY")
    qqq_bench_full = slice_bench(daily, full_start, full_end, "QQQ")
    qqq_bench_train = slice_bench(daily, fold.train_start, fold.train_end, "QQQ")
    qqq_bench_test = slice_bench(daily, fold.test_start, fold.test_end, "QQQ")

    print(f"\n# OVERNIGHT DRIFT — SPY + QQQ shares")
    print(f"# Period: {full_start} -> {full_end}")
    print(f"# SPY bench (full): ret {spy_bench_full.total_return:+.1%}  "
          f"Sharpe {spy_bench_full.sharpe:.2f}  "
          f"Sortino {spy_bench_full.sortino:.2f}  "
          f"|DD| {abs(spy_bench_full.max_drawdown):.0%}")
    print(f"# QQQ bench (full): ret {qqq_bench_full.total_return:+.1%}  "
          f"Sharpe {qqq_bench_full.sharpe:.2f}  "
          f"Sortino {qqq_bench_full.sortino:.2f}  "
          f"|DD| {abs(qqq_bench_full.max_drawdown):.0%}\n")

    # SPY/QQQ full + train + test, at realistic 1bp/side slippage
    # plus zero-slippage upper bound for diagnostic comparison.
    runs = {}
    for slip, suffix in ((1.0, ""), (0.0, "_NO_SLIP")):
        runs[f"SPY_full{suffix}"] = run_one(
            f"SPY_full{suffix} — Overnight SPY (2018-2026, slip={slip}bp)",
            daily, "SPY", full_start, full_end, spy_bench_full, slippage_bps=slip,
        )
        runs[f"SPY_train{suffix}"] = run_one(
            f"SPY_train{suffix} — Overnight SPY ({fold.train_label}, slip={slip}bp)",
            daily, "SPY", fold.train_start, fold.train_end, spy_bench_train,
            slippage_bps=slip,
        )
        runs[f"SPY_test{suffix}"] = run_one(
            f"SPY_test{suffix} — Overnight SPY ({fold.test_label}, slip={slip}bp)",
            daily, "SPY", fold.test_start, fold.test_end, spy_bench_test,
            slippage_bps=slip,
        )
        runs[f"QQQ_full{suffix}"] = run_one(
            f"QQQ_full{suffix} — Overnight QQQ (2018-2026, slip={slip}bp)",
            daily, "QQQ", full_start, full_end, qqq_bench_full, slippage_bps=slip,
        )
        runs[f"QQQ_train{suffix}"] = run_one(
            f"QQQ_train{suffix} — Overnight QQQ ({fold.train_label}, slip={slip}bp)",
            daily, "QQQ", fold.train_start, fold.train_end, qqq_bench_train,
            slippage_bps=slip,
        )
        runs[f"QQQ_test{suffix}"] = run_one(
            f"QQQ_test{suffix} — Overnight QQQ ({fold.test_label}, slip={slip}bp)",
            daily, "QQQ", fold.test_start, fold.test_end, qqq_bench_test,
            slippage_bps=slip,
        )

    # Benchmark comparison + lift table — the strategy must beat the
    # corresponding underlying's buy-and-hold Sortino in the same period.
    # Otherwise you should just hold the underlying.
    print("\n" + "=" * 80)
    print("LIFT vs BENCHMARK — overnight drift Sortino minus same-period")
    print("buy-and-hold Sortino on the same underlying (1bp/side slippage)")
    print("=" * 80)
    benches = {
        "SPY_full": spy_bench_full,
        "SPY_train": spy_bench_train,
        "SPY_test": spy_bench_test,
        "QQQ_full": qqq_bench_full,
        "QQQ_train": qqq_bench_train,
        "QQQ_test": qqq_bench_test,
    }
    from src.backtest.benchmark import equity_metrics
    print(f"\n{'Variant':14s}  {'Bench Sortino':>13s}  {'Strat Sortino':>13s}  "
          f"{'Lift':>7s}  {'Bench Return':>12s}  {'Strat Return':>12s}  "
          f"{'Lift (pp)':>9s}")
    for key, bench in benches.items():
        m = equity_metrics(runs[key].equity_curve, 8000.0)
        sortino_lift = m["sortino"] - bench.sortino
        return_lift_pp = (m["total_return"] - bench.total_return) * 100
        print(f"{key:14s}  {bench.sortino:>13.2f}  {m['sortino']:>13.2f}  "
              f"{sortino_lift:>+6.2f}  {bench.total_return:>+11.1%}  "
              f"{m['total_return']:>+11.1%}  {return_lift_pp:>+8.1f}")

    # Cross-variant summary (kept from before)
    print("\n" + "=" * 72)
    print("SUMMARY — overnight drift, all variants")
    print("=" * 72)
    print(f"\n{'Variant':22s}  {'N':>4s}  {'Win%':>5s}  {'Sharpe':>6s}  "
          f"{'Sortino':>7s}  {'Return':>7s}  {'|DD|':>5s}  {'Final $':>9s}")
    for label, r in runs.items():
        m = equity_metrics(r.equity_curve, 8000.0)
        n = len(r.trades)
        wins = sum(1 for t in r.trades if t.pnl > 0)
        wr = wins / n if n else 0
        print(f"{label:22s}  {n:>4d}  {wr:>4.0%}  {m['sharpe']:>5.2f}   "
              f"{m['sortino']:>5.2f}    {m['total_return']:>+5.0%}    "
              f"{abs(m['max_drawdown']):>3.0%}   ${m['final_equity']:>7.0f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
