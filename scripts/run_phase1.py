"""Phase 1 of the v2 validation plan: IBS on shares.

Runs A1 (SPY) and A2 (QQQ) over 2018-2026, plus the signal-only baselines
(no time stop) and the walk-forward in-sample/out-of-sample split.

Output is the standard v2 report per variant + a summary table at the end.

Usage (from repo root, with FMP_API_KEY in env or .env):
    .venv/Scripts/python.exe scripts/run_phase1.py        # Windows
    python scripts/run_phase1.py                          # Linux/Mac
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()  # silence per-trade INFO chatter; we just want reports

from src.backtest.benchmark import buy_and_hold_metrics
from src.backtest.shares_engine import SharesBacktestConfig, SharesBacktestEngine
from src.backtest.v2_report import format_v2_report
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


def run_variant(
    label: str,
    universe_sym: str,
    daily_bars: dict,
    start: date,
    end: date,
    enable_signal_only: bool,
    benchmark,
):
    cfg = SharesBacktestConfig(
        start=start,
        end=end,
        initial_capital=8000.0,
        allocation_pct=1.0,
        max_concurrent=1,
        slippage_bps=5.0,
        time_stop_days=5,
        enable_signal_only_mode=enable_signal_only,
    )
    # Restrict the strategy universe to the single underlying for this run.
    # Easiest way: just pass only that symbol's bars; the strategy iterates
    # ("SPY", "QQQ") and skips missing keys. We emulate that by zeroing the
    # other key with an empty DataFrame.
    import pandas as pd
    sliced = {
        "SPY": daily_bars["SPY"] if universe_sym == "SPY" else pd.DataFrame(),
        "QQQ": daily_bars["QQQ"] if universe_sym == "QQQ" else pd.DataFrame(),
    }
    # Long-side IBS only — the v1.1 default and what Phase 1 actually
    # specifies. Disabling the SHORT_FADE branch means the strategy only
    # emits long signals, so A2 numbers are clean "IBS-long-on-shares".
    eng = SharesBacktestEngine(
        config=cfg,
        strategies=[IBSStrategy(sqqq_short_enabled=False)],
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


def main() -> int:
    api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        # Allow .env loading as a convenience
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        print("ERROR: FMP_API_KEY not set", file=sys.stderr)
        return 1

    daily = fetch_bars(api_key)
    full_start = date(2018, 1, 1)
    full_end = date(2026, 4, 15)

    # Pre-compute SPY benchmark for the 8-year period (used for tier verdicts)
    spy_close_in_window = daily["SPY"][[
        d.date() if hasattr(d, "date") else d
        for d in daily["SPY"].index
    ].__class__([
        full_start <= (d.date() if hasattr(d, "date") else d) <= full_end
        for d in daily["SPY"].index
    ])]
    # ^ that line attempted clever boolean indexing; do it more directly
    import pandas as pd
    mask = pd.Series(
        [full_start <= (d.date() if hasattr(d, "date") else d) <= full_end
         for d in daily["SPY"].index],
        index=daily["SPY"].index,
    )
    spy_in_window = daily["SPY"].loc[mask]
    spy_bench_full = buy_and_hold_metrics(
        spy_in_window["close"], start_capital=8000.0, symbol="SPY",
    )

    print(f"\n# PHASE 1 — IBS on SPY/QQQ shares\n"
          f"# Backtest period: {full_start} -> {full_end}\n"
          f"# Benchmark: SPY buy-and-hold "
          f"(return {spy_bench_full.total_return:+.1%}, "
          f"Sharpe {spy_bench_full.sharpe:.2f}, "
          f"|DD| {abs(spy_bench_full.max_drawdown):.0%})\n")

    # === A1: SPY shares, full period ===
    run_variant(
        "A1 — IBS on SPY shares (full period 2018-2026, time stop 5d)",
        "SPY", daily, full_start, full_end, False, spy_bench_full,
    )

    # === A1 signal-only baseline ===
    run_variant(
        "A1-SIG-ONLY — IBS on SPY shares (full period, NO time stop)",
        "SPY", daily, full_start, full_end, True, spy_bench_full,
    )

    # === A1 walk-forward train (2018-2022) ===
    fold = single_fold(full_start, full_end, train_years=5, test_years=3)
    # SPY bench for the train sub-period
    train_mask = pd.Series(
        [fold.train_start <= (d.date() if hasattr(d, "date") else d) <= fold.train_end
         for d in daily["SPY"].index],
        index=daily["SPY"].index,
    )
    spy_bench_train = buy_and_hold_metrics(
        daily["SPY"].loc[train_mask]["close"], start_capital=8000.0, symbol="SPY",
    )
    test_mask = pd.Series(
        [fold.test_start <= (d.date() if hasattr(d, "date") else d) <= fold.test_end
         for d in daily["SPY"].index],
        index=daily["SPY"].index,
    )
    spy_bench_test = buy_and_hold_metrics(
        daily["SPY"].loc[test_mask]["close"], start_capital=8000.0, symbol="SPY",
    )

    run_variant(
        f"A1-TRAIN — IBS on SPY shares ({fold.train_label}, time stop 5d)",
        "SPY", daily, fold.train_start, fold.train_end, False, spy_bench_train,
    )
    run_variant(
        f"A1-TEST — IBS on SPY shares ({fold.test_label}, time stop 5d)",
        "SPY", daily, fold.test_start, fold.test_end, False, spy_bench_test,
    )

    # === A2: QQQ shares, full period ===
    run_variant(
        "A2 — IBS on QQQ shares (full period 2018-2026, time stop 5d)",
        "QQQ", daily, full_start, full_end, False, spy_bench_full,
    )

    # === A2 signal-only baseline ===
    run_variant(
        "A2-SIG-ONLY — IBS on QQQ shares (full period, NO time stop)",
        "QQQ", daily, full_start, full_end, True, spy_bench_full,
    )

    # === A2 walk-forward ===
    run_variant(
        f"A2-TRAIN — IBS on QQQ shares ({fold.train_label}, time stop 5d)",
        "QQQ", daily, fold.train_start, fold.train_end, False, spy_bench_train,
    )
    run_variant(
        f"A2-TEST — IBS on QQQ shares ({fold.test_label}, time stop 5d)",
        "QQQ", daily, fold.test_start, fold.test_end, False, spy_bench_test,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
