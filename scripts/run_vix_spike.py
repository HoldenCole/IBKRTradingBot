"""VIX spike fade backtest runner. Three signal variants, full + walk-forward.

Evaluated as DIVERSIFIER (Rule 2 from DECISIONS.md): correlation < 0.30
with QQQ BAH, profitable during QQQ drawdowns, standalone Sortino > 1.0,
>=30 trades.

Uses FRED for VIX (free, no API key required) and FMP for VXX/SPY bars.

Usage:
    FMP_API_KEY=... python scripts/run_vix_spike.py
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

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics
from src.backtest.diversifier_check import (
    evaluate_diversifier,
    format_diversifier_verdict,
)
from src.backtest.v2_report import format_v2_report
from src.backtest.vix_spike_engine import (
    SignalVariant,
    VixSpikeConfig,
    VixSpikeFadeEngine,
)
from src.backtest.walk_forward import single_fold
from src.data.fmp import FMPHistorical
from src.data.fred import fetch_vix


def slice_close(df: pd.DataFrame, start: date, end: date) -> pd.Series:
    idx = [d.date() if hasattr(d, "date") else d for d in df.index]
    mask = pd.Series([start <= d <= end for d in idx], index=df.index)
    return df.loc[mask, "close"]


def run_variant(label, cfg, vix, vxx, spy, qqq_close, qqq_bench):
    eng = VixSpikeFadeEngine(config=cfg, vix=vix, vxx=vxx, spy=spy)
    result = eng.run()
    print(format_v2_report(
        label=label, trades=result.trades,
        equity_curve=result.equity_curve,
        initial_capital=cfg.initial_capital,
        benchmark=qqq_bench, skipped=result.skipped_signals,
        diversifier_benchmark_close=qqq_close,
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

    full_start = date(2018, 1, 1)
    full_end = date(2026, 4, 15)
    fold = single_fold(full_start, full_end, train_years=5, test_years=3)

    # Fetch VIX from FRED (free, no auth)
    print("Fetching VIX from FRED...")
    cache = REPO / "data" / "fred_cache"
    vix = fetch_vix(full_start.isoformat(), full_end.isoformat(), cache_dir=cache)
    print(f"  {len(vix)} VIX observations from {vix.index[0].date()} to {vix.index[-1].date()}")
    print(f"  VIX min={vix['close'].min():.1f} max={vix['close'].max():.1f} "
          f"median={vix['close'].median():.1f}")

    # Fetch VXX, SPY, QQQ from FMP
    print("\nFetching VXX, SPY, QQQ from FMP...")
    fmp = FMPHistorical(api_key=api_key)
    buf = (full_start - timedelta(days=10)).isoformat()
    end_iso = full_end.isoformat()
    vxx = fmp.daily("VXX", buf, end_iso)
    spy = fmp.daily("SPY", buf, end_iso)
    qqq = fmp.daily("QQQ", buf, end_iso)
    if vxx.empty:
        print("ERROR: VXX bars empty from FMP", file=sys.stderr)
        return 1
    print(f"  VXX: {len(vxx)} bars, range ${vxx['close'].min():.2f}-${vxx['close'].max():.2f}")
    print(f"  SPY: {len(spy)} bars")
    print(f"  QQQ: {len(qqq)} bars")

    qqq_bench_full = buy_and_hold_metrics(
        slice_close(qqq, full_start, full_end), 8000.0, "QQQ",
    )
    qqq_close_full = slice_close(qqq, full_start, full_end)
    qqq_close_train = slice_close(qqq, fold.train_start, fold.train_end)
    qqq_close_test = slice_close(qqq, fold.test_start, fold.test_end)

    print(f"\n# VIX SPIKE FADE — diversifier candidate")
    print(f"# Period: {full_start} -> {full_end}")
    print(f"# QQQ bench full: ret {qqq_bench_full.total_return:+.1%}  "
          f"Sortino {qqq_bench_full.sortino:.2f}\n")

    runs = {}
    for variant in (SignalVariant.V0_THRESHOLD,
                    SignalVariant.V1_SPIKE_RATE,
                    SignalVariant.V2_SPX_DOWN):
        # Full period
        cfg = VixSpikeConfig(start=full_start, end=full_end, variant=variant)
        runs[f"{variant.value}_full"] = run_variant(
            f"{variant.value}_full",
            cfg, vix, vxx, spy, qqq_close_full, qqq_bench_full,
        )
        # Train slice
        cfg_train = VixSpikeConfig(start=fold.train_start, end=fold.train_end,
                                   variant=variant)
        bench_train = buy_and_hold_metrics(
            slice_close(qqq, fold.train_start, fold.train_end), 8000.0, "QQQ",
        )
        runs[f"{variant.value}_train"] = run_variant(
            f"{variant.value}_train",
            cfg_train, vix, vxx, spy, qqq_close_train, bench_train,
        )
        # Test slice
        cfg_test = VixSpikeConfig(start=fold.test_start, end=fold.test_end,
                                  variant=variant)
        bench_test = buy_and_hold_metrics(
            slice_close(qqq, fold.test_start, fold.test_end), 8000.0, "QQQ",
        )
        runs[f"{variant.value}_test"] = run_variant(
            f"{variant.value}_test",
            cfg_test, vix, vxx, spy, qqq_close_test, bench_test,
        )

    # Cross-variant summary
    print("\n" + "=" * 88)
    print("SUMMARY — VIX spike fade variants vs diversifier criteria")
    print("=" * 88)
    print(f"\n{'Variant':22s}  {'N':>4s}  {'Win%':>5s}  {'Sortino':>7s}  "
          f"{'Return':>7s}  {'Corr':>5s}  {'DD$':>7s}  {'Verdict':>8s}")
    for label, r in runs.items():
        m = equity_metrics(r.equity_curve, 8000.0)
        n = len(r.trades)
        wins = sum(1 for t in r.trades if t.pnl > 0)
        wr = wins / n if n else 0
        # Pick the right benchmark close series for this variant's period
        if "_full" in label:
            qc = qqq_close_full
        elif "_train" in label:
            qc = qqq_close_train
        else:
            qc = qqq_close_test
        v = evaluate_diversifier(
            strategy_equity=r.equity_curve, n_trades=n,
            benchmark_close=qc, sortino=m["sortino"],
        )
        verdict = "PASS" if v.passed else "FAIL"
        print(f"{label:22s}  {n:>4d}  {wr:>4.0%}  {m['sortino']:>5.2f}    "
              f"{m['total_return']:>+5.0%}   {v.correlation:>+4.2f}  "
              f"${v.drawdown_pnl:>+5.0f}  {verdict:>7s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
