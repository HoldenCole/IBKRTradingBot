"""Phase 1.5: IBS long+short on QQQ shares (clean, with corrected shorts).

Three variants over 2018-2026 plus 2018-2022 train / 2023-2026 test:
  - LONG-ONLY  (long_enabled=True,  sqqq_short_enabled=False)
  - SHORT-ONLY (long_enabled=False, sqqq_short_enabled=True)
  - COMBINED   (both enabled)

Every variant uses the corrected shares engine (shorts now produce
correctly-signed equity curve while position is open).

Per-regime breakdown of long vs short contribution emitted at the
end so we can evaluate whether shorts add edge in specific regimes
(particularly bear) without contaminating the long-only signal in
other regimes.

Usage (with FMP_API_KEY in env or .env):
    python scripts/run_phase1_5.py
"""
from __future__ import annotations

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

from src.backtest.benchmark import buy_and_hold_metrics
from src.backtest.shares_engine import SharesBacktestConfig, SharesBacktestEngine
from src.backtest.v2_report import REGIME_BY_YEAR, format_v2_report
from src.backtest.walk_forward import single_fold
from src.data.fmp import FMPHistorical
from src.strategies.ibs import IBSStrategy


def fetch_bars(api_key: str) -> dict:
    fmp = FMPHistorical(api_key=api_key)
    buf = (date(2018, 1, 1) - timedelta(days=600)).isoformat()
    end_iso = date(2026, 4, 15).isoformat()
    return {
        "SPY": fmp.daily("SPY", buf, end_iso),
        "QQQ": fmp.daily("QQQ", buf, end_iso),
    }


def slice_bench(daily: dict, start: date, end: date):
    spy = daily["SPY"]
    mask = pd.Series(
        [start <= (d.date() if hasattr(d, "date") else d) <= end
         for d in spy.index],
        index=spy.index,
    )
    return buy_and_hold_metrics(spy.loc[mask]["close"], 8000.0, "SPY")


def run_variant(
    label: str,
    daily: dict,
    start: date,
    end: date,
    long_on: bool,
    short_on: bool,
    benchmark,
):
    cfg = SharesBacktestConfig(
        start=start, end=end, initial_capital=8000.0,
        allocation_pct=1.0, max_concurrent=1,
        slippage_bps=5.0, time_stop_days=5,
    )
    sliced = {"SPY": pd.DataFrame(), "QQQ": daily["QQQ"]}
    eng = SharesBacktestEngine(
        config=cfg,
        strategies=[IBSStrategy(
            sqqq_short_enabled=short_on,
            long_enabled=long_on,
        )],
        daily_bars=sliced,
    )
    result = eng.run()
    print(format_v2_report(
        label=label,
        trades=result.trades,
        equity_curve=result.equity_curve,
        initial_capital=cfg.initial_capital,
        benchmark=benchmark,
        skipped=result.skipped_signals,
    ))
    return result


def per_regime_split(label: str, result):
    """Long vs short contribution per regime."""
    print(f"\n[{label} — long vs short by regime]")
    by_regime_long: dict[str, list] = defaultdict(list)
    by_regime_short: dict[str, list] = defaultdict(list)
    for t in result.trades:
        regime = REGIME_BY_YEAR.get(t.entry_date.year, "?")
        if t.direction == "long":
            by_regime_long[regime].append(t.pnl)
        else:
            by_regime_short[regime].append(t.pnl)
    print(f"  {'Regime':22s}  {'L_n':>4s}  {'L_pnl':>8s}  "
          f"{'S_n':>4s}  {'S_pnl':>8s}")
    regimes = sorted(set(by_regime_long) | set(by_regime_short))
    for r in regimes:
        ln = len(by_regime_long[r]); lp = sum(by_regime_long[r])
        sn = len(by_regime_short[r]); sp = sum(by_regime_short[r])
        print(f"  {r:22s}  {ln:>4d}  ${lp:>+6.0f}  {sn:>4d}  ${sp:>+6.0f}")


def main() -> int:
    api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        print("ERROR: FMP_API_KEY not set", file=sys.stderr)
        return 1

    daily = fetch_bars(api_key)
    full_start = date(2018, 1, 1)
    full_end = date(2026, 4, 15)
    fold = single_fold(full_start, full_end, train_years=5, test_years=3)

    bench_full = slice_bench(daily, full_start, full_end)
    bench_train = slice_bench(daily, fold.train_start, fold.train_end)
    bench_test = slice_bench(daily, fold.test_start, fold.test_end)

    print(f"\n# PHASE 1.5 — IBS long/short on QQQ shares")
    print(f"# Period: {full_start} -> {full_end}\n"
          f"# Benchmark (full): SPY return {bench_full.total_return:+.1%}  "
          f"Sharpe {bench_full.sharpe:.2f}  |DD| {abs(bench_full.max_drawdown):.0%}\n")

    runs: dict[str, dict] = {}

    runs["L_full"] = run_variant(
        "L_full — IBS LONG only on QQQ shares (2018-2026)",
        daily, full_start, full_end, True, False, bench_full,
    )
    runs["S_full"] = run_variant(
        "S_full — IBS SHORT only on QQQ shares (2018-2026)",
        daily, full_start, full_end, False, True, bench_full,
    )
    runs["LS_full"] = run_variant(
        "LS_full — IBS LONG+SHORT combined on QQQ shares (2018-2026)",
        daily, full_start, full_end, True, True, bench_full,
    )

    runs["L_train"] = run_variant(
        f"L_train — IBS LONG only on QQQ shares ({fold.train_label})",
        daily, fold.train_start, fold.train_end, True, False, bench_train,
    )
    runs["L_test"] = run_variant(
        f"L_test — IBS LONG only on QQQ shares ({fold.test_label})",
        daily, fold.test_start, fold.test_end, True, False, bench_test,
    )
    runs["S_train"] = run_variant(
        f"S_train — IBS SHORT only on QQQ shares ({fold.train_label})",
        daily, fold.train_start, fold.train_end, False, True, bench_train,
    )
    runs["S_test"] = run_variant(
        f"S_test — IBS SHORT only on QQQ shares ({fold.test_label})",
        daily, fold.test_start, fold.test_end, False, True, bench_test,
    )
    runs["LS_train"] = run_variant(
        f"LS_train — IBS LONG+SHORT on QQQ shares ({fold.train_label})",
        daily, fold.train_start, fold.train_end, True, True, bench_train,
    )
    runs["LS_test"] = run_variant(
        f"LS_test — IBS LONG+SHORT on QQQ shares ({fold.test_label})",
        daily, fold.test_start, fold.test_end, True, True, bench_test,
    )

    # Per-regime split for the full-period combined run
    per_regime_split("LS_full", runs["LS_full"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
