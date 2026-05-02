"""Regime-filter validation against the existing IBS LS_full backtest.

Runs the IBS LONG+SHORT combined strategy on QQQ shares over 2018-2026
under each candidate filter, plus the no-filter baseline. Reports
headline metrics and tier verdicts. The hypothesis: a filter that
excludes 2018 (chop_to_correction) and 2026 (mixed) regime days
mechanically lifts overall Sortino into Tier C+ territory.

Filters tested:
  baseline    — no filter
  V0          — DrawdownFilter (30d drawdown < -7%)
  V1          — Sma200BandFilter (close within 5% of SMA200)
  V2          — TrendCoherenceFilter (price-SMA50-SMA200 alignment)
  V0+V2 (or)  — either drawdown OR chop -> off (blocks more days)
  V2 only     — pure trend-coherence

If any candidate clears Tier B (Sortino > 1.0), document and recommend.
If the best clears Tier C, that's a multi-strategy-portfolio component.
If none lift the metric meaningfully, the regime split was overfit.
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
from src.backtest.regime_filter import (
    CompositeOrFilter,
    DrawdownFilter,
    NoFilter,
    Sma200BandFilter,
    TrendCoherenceFilter,
    YearExclusionFilter,
)
from src.backtest.shares_engine import SharesBacktestConfig, SharesBacktestEngine
from src.backtest.v2_report import format_v2_report
from src.data.fmp import FMPHistorical
from src.strategies.ibs import IBSStrategy


def slice_bench(daily, start, end):
    spy = daily["SPY"]
    mask = pd.Series(
        [start <= (d.date() if hasattr(d, "date") else d) <= end for d in spy.index],
        index=spy.index,
    )
    return buy_and_hold_metrics(spy.loc[mask]["close"], 8000.0, "SPY")


def run_one(label, daily, start, end, regime_filter, benchmark):
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
    buf = (date(2018, 1, 1) - timedelta(days=600)).isoformat()
    end_iso = date(2026, 4, 15).isoformat()
    daily = {
        "SPY": fmp.daily("SPY", buf, end_iso),
        "QQQ": fmp.daily("QQQ", buf, end_iso),
    }

    full_start = date(2018, 1, 1)
    full_end = date(2026, 4, 15)
    bench = slice_bench(daily, full_start, full_end)

    print(f"\n# REGIME FILTER VALIDATION — IBS LS on QQQ shares")
    print(f"# Period: {full_start} -> {full_end}")
    print(f"# Bench: SPY return {bench.total_return:+.1%}  Sharpe {bench.sharpe:.2f}  "
          f"Sortino {bench.sortino:.2f}  |DD| {abs(bench.max_drawdown):.0%}\n")

    candidates = [
        ("BASELINE — no filter (LS_full reproduction)", None),
        ("V0 — DrawdownFilter(30d, -7%)",
         DrawdownFilter(lookback=30, threshold=-0.07)),
        ("V0_5pct — DrawdownFilter(30d, -5%)",
         DrawdownFilter(lookback=30, threshold=-0.05)),
        ("V1 — Sma200BandFilter(5%)",
         Sma200BandFilter(band=0.05)),
        ("V2 — TrendCoherenceFilter(50/200)",
         TrendCoherenceFilter()),
        ("V0+V2 OR (drawdown -7% OR chop blocked)",
         CompositeOrFilter(filters=[
             DrawdownFilter(lookback=30, threshold=-0.07),
             TrendCoherenceFilter(),
         ])),
        ("DIAG — exclude 2018 + 2026 by year (hindsight)",
         YearExclusionFilter(excluded_years={2018, 2026})),
        ("DIAG — exclude only 2018",
         YearExclusionFilter(excluded_years={2018})),
        ("DIAG — exclude only 2026",
         YearExclusionFilter(excluded_years={2026})),
    ]

    results = {}
    for label, f in candidates:
        results[label] = run_one(label, daily, full_start, full_end, f, bench)

    # Summary table
    print("\n" + "=" * 72)
    print("SUMMARY — all candidates")
    print("=" * 72)
    from src.backtest.benchmark import equity_metrics
    print(f"\n{'Filter':50s}  {'N':>4s}  {'Sharpe':>6s}  {'Sortino':>7s}  "
          f"{'Return':>7s}  {'|DD|':>5s}")
    for label, r in results.items():
        m = equity_metrics(r.equity_curve, 8000.0)
        short = label.split(" — ")[0]
        n = len(r.trades)
        print(f"{short:50s}  {n:>4d}  {m['sharpe']:>5.2f}   {m['sortino']:>5.2f}    "
              f"{m['total_return']:>+5.0%}    {abs(m['max_drawdown']):>3.0%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
