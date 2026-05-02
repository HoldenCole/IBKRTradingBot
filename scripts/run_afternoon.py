"""Phase 5: Afternoon reversion on shares.

Runs when the IBKR 5-min cache (data/intraday/{SPY,QQQ}/) is populated.
Long-only first per spec; if it clears Tier C, we test long+short.

Long-only is evaluated against:
  - Rule 1 (lift over QQQ BAH on same-day-close-to-close basis)
  - Rule 2 (diversifier criteria)
The strategy is intraday-only so per Rule 3 it gets BOTH views.

Usage (with intraday cache populated):
    FMP_API_KEY=... python scripts/run_afternoon.py
    FMP_API_KEY=... python scripts/run_afternoon.py --universe QQQ --start 2024-01-01

Will print a clear error if the cache is missing or sparse.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics
from src.backtest.intraday_engine import IntradayBacktestEngine, IntradayConfig
from src.backtest.v2_report import format_v2_report
from src.backtest.walk_forward import single_fold
from src.data.fmp import FMPHistorical


def slice_close(df, start, end):
    idx = [d.date() if hasattr(d, "date") else d for d in df.index]
    mask = pd.Series([start <= d <= end for d in idx], index=df.index)
    return df.loc[mask, "close"]


def check_cache(universe: str, start: date, end: date, cache_dir: Path) -> int:
    """Return number of cached parquet files in [start, end] for universe."""
    sym_dir = cache_dir / universe
    if not sym_dir.exists():
        return 0
    n = 0
    d = start
    while d <= end:
        if (sym_dir / f"{d.isoformat()}.parquet").exists():
            n += 1
        d += timedelta(days=1)
    return n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--universe", choices=("SPY", "QQQ"), default="QQQ")
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2026-04-15")
    p.add_argument("--cache-dir", default=str(REPO / "data" / "intraday"))
    args = p.parse_args()

    api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        print("ERROR: FMP_API_KEY not set", file=sys.stderr)
        return 1

    full_start = date.fromisoformat(args.start)
    full_end = date.fromisoformat(args.end)
    cache_dir = Path(args.cache_dir)

    n_cached = check_cache(args.universe, full_start, full_end, cache_dir)
    expected = max(1, int((full_end - full_start).days * 5 / 7))  # ~5 trading days/wk
    print(f"Intraday cache: {n_cached} files in {cache_dir / args.universe}")
    print(f"Expected ~{expected} trading days; coverage {n_cached/expected:.0%}")
    if n_cached < 30:
        print(f"\nERROR: insufficient intraday cache ({n_cached} files).", file=sys.stderr)
        print(f"Run scripts/pull_ibkr_5min.py first to populate "
              f"{cache_dir / args.universe}/.", file=sys.stderr)
        return 2

    # Daily bars from FMP for ATR computation + benchmark
    print(f"\nFetching {args.universe} daily bars from FMP for ATR + benchmark...")
    fmp = FMPHistorical(api_key=api_key)
    buf = (full_start - timedelta(days=60)).isoformat()
    daily = {args.universe: fmp.daily(args.universe, buf, full_end.isoformat())}
    if args.universe != "QQQ":
        daily["QQQ"] = fmp.daily("QQQ", buf, full_end.isoformat())
    qqq = daily.get("QQQ")
    if qqq is None:
        qqq = fmp.daily("QQQ", buf, full_end.isoformat())

    qqq_bench_full = buy_and_hold_metrics(
        slice_close(qqq, full_start, full_end), 8000.0, "QQQ",
    )
    qqq_close_full = slice_close(qqq, full_start, full_end)

    fold = single_fold(full_start, full_end, train_years=5, test_years=3)
    qqq_bench_train = buy_and_hold_metrics(
        slice_close(qqq, fold.train_start, fold.train_end), 8000.0, "QQQ",
    )
    qqq_bench_test = buy_and_hold_metrics(
        slice_close(qqq, fold.test_start, fold.test_end), 8000.0, "QQQ",
    )
    qqq_close_train = slice_close(qqq, fold.train_start, fold.train_end)
    qqq_close_test = slice_close(qqq, fold.test_start, fold.test_end)

    print(f"\n# AFTERNOON REVERSION on {args.universe} shares")
    print(f"# Period: {full_start} -> {full_end}")
    print(f"# QQQ bench full: ret {qqq_bench_full.total_return:+.1%}  "
          f"Sortino {qqq_bench_full.sortino:.2f}\n")

    runs = {}
    for slice_name, slice_start, slice_end, bench, qc in (
        ("full",  full_start,        full_end,        qqq_bench_full,  qqq_close_full),
        ("train", fold.train_start, fold.train_end,  qqq_bench_train, qqq_close_train),
        ("test",  fold.test_start,  fold.test_end,   qqq_bench_test,  qqq_close_test),
    ):
        cfg = IntradayConfig(
            start=slice_start, end=slice_end, universe=args.universe,
            initial_capital=8000.0, bar_dir=cache_dir,
        )
        eng = IntradayBacktestEngine(config=cfg, daily_bars=daily)
        result = eng.run()
        label = f"{args.universe}_afternoon_{slice_name}"
        runs[label] = result
        print(format_v2_report(
            label=label, trades=result.trades,
            equity_curve=result.equity_curve,
            initial_capital=cfg.initial_capital,
            benchmark=bench, skipped=result.skipped_signals,
            diversifier_benchmark_close=qc,
        ))

    # Cross-variant summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n{'Variant':30s}  {'N':>4s}  {'Sortino':>7s}  {'Return':>7s}  {'|DD|':>5s}")
    for label, r in runs.items():
        m = equity_metrics(r.equity_curve, 8000.0)
        n = len(r.trades)
        print(f"{label:30s}  {n:>4d}  {m['sortino']:>5.2f}    "
              f"{m['total_return']:>+5.0%}    {abs(m['max_drawdown']):>3.0%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
