"""V2 reporting template.

Standard format for every backtest variant in the v2 validation plan:
  - Headline metrics
  - Per-year breakdown (with regime label)
  - Per-regime breakdown
  - Benchmark comparison (SPY buy-and-hold)
  - Tier verdict (A/B/C/D)
  - Holding-period P&L distribution
  - Exit reason breakdown

Used by Phase 1+ analyses. Same template every variant uses so cross-
variant comparison is clean.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date

import pandas as pd

from src.backtest.benchmark import BenchmarkMetrics, equity_metrics, equity_metrics_subset
from src.backtest.diversifier_check import (
    DiversifierVerdict,
    evaluate_diversifier,
    format_diversifier_verdict,
)
from src.backtest.tier import classify, TierVerdict


# Hand-labeled regime map (locked from DECISIONS.md)
REGIME_BY_YEAR = {
    2018: "chop_to_correction",
    2019: "bull",
    2020: "crisis_recovery",
    2021: "bull",
    2022: "bear",
    2023: "bull",
    2024: "bull",
    2025: "bull_chop",
    2026: "mixed",
}


def format_v2_report(
    label: str,
    trades: list,                  # list of ShareTrade or TradeRecord
    equity_curve: pd.Series,
    initial_capital: float,
    benchmark: BenchmarkMetrics,
    skipped: list[dict] | None = None,
    diversifier_benchmark_close: pd.Series | None = None,
) -> str:
    """Format a strategy backtest result against the v2 reporting template."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"{label}")
    lines.append("=" * 72)

    # --- Headline ---
    sm = equity_metrics(equity_curve, initial_capital)
    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    total_pnl = sum(t.pnl for t in trades)
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0.0
    win_rate = (len(wins) / n) if n else 0.0
    gw = sum(t.pnl for t in wins)
    gl = -sum(t.pnl for t in losses)
    pf = gw / gl if gl > 0 else (float("inf") if gw > 0 else 0.0)
    expectancy = total_pnl / n if n else 0.0

    lines.append("\n[Headline]")
    lines.append(f"  Trades:        {n} ({len(wins)}W / {len(losses)}L, win%={win_rate:.0%})")
    lines.append(f"  Total PnL:     ${total_pnl:+,.2f}")
    lines.append(f"  Total return:  {sm['total_return']:+.1%}")
    lines.append(f"  CAGR:          {sm['cagr']:+.1%}")
    lines.append(f"  Sharpe (ann):  {sm['sharpe']:.2f}")
    lines.append(f"  Sortino:       {sm['sortino']:.2f}")
    lines.append(f"  Max drawdown:  {sm['max_drawdown']:.1%}")
    lines.append(f"  Profit factor: {pf:.2f}")
    lines.append(f"  Expectancy:    ${expectancy:+.2f}/trade")
    lines.append(f"  Avg win:       ${avg_win:+.2f}")
    lines.append(f"  Avg loss:      ${avg_loss:+.2f}")

    # --- Benchmark comparison ---
    lines.append("\n[Benchmark vs SPY buy-and-hold]")
    lines.append(f"  Strategy:  ret {sm['total_return']:+.1%}  Sharpe {sm['sharpe']:.2f}  |DD| {abs(sm['max_drawdown']):.0%}")
    lines.append(f"  {benchmark.symbol:9s}: ret {benchmark.total_return:+.1%}  Sharpe {benchmark.sharpe:.2f}  |DD| {abs(benchmark.max_drawdown):.0%}")
    delta_ret = sm["total_return"] - benchmark.total_return
    delta_sharpe = sm["sharpe"] - benchmark.sharpe
    lines.append(f"  Delta:    ret {delta_ret:+.1%}  Sharpe {delta_sharpe:+.2f}")

    # --- Tier verdict ---
    verdict = classify(
        strategy_sharpe=sm["sharpe"],
        strategy_max_dd=sm["max_drawdown"],
        strategy_total_return=sm["total_return"],
        bench_sharpe=benchmark.sharpe,
        bench_total_return=benchmark.total_return,
        strategy_sortino=sm["sortino"],
    )
    # --- Diversifier criteria (Rule 2) — only emitted when caller passes
    # the benchmark close-price series for daily-return correlation. ---
    diversifier_block = ""
    if diversifier_benchmark_close is not None and not diversifier_benchmark_close.empty:
        dv = evaluate_diversifier(
            strategy_equity=equity_curve,
            n_trades=n,
            benchmark_close=diversifier_benchmark_close,
            sortino=sm["sortino"],
        )
        diversifier_block = "\n\n" + format_diversifier_verdict(dv)
    lines.append("\n[Tier verdict]")
    lines.append(f"  TIER {verdict.tier}  ({verdict.rationale})")

    # --- Per-year ---
    lines.append("\n[Per-year]")
    lines.append(f"  {'Year':>6s}  {'Regime':22s}  {'N':>4s}  {'Win%':>5s}  "
                 f"{'Total':>10s}  {'PF':>5s}  {'Sharpe':>6s}  {'Sortino':>7s}")
    by_year: dict[int, list] = defaultdict(list)
    for t in trades:
        by_year[t.entry_date.year if hasattr(t, "entry_date") else t.entry_time.year].append(t)
    for y in sorted(by_year):
        ts = by_year[y]
        regime = REGIME_BY_YEAR.get(y, "?")
        wins = [t for t in ts if t.pnl > 0]
        losses = [t for t in ts if t.pnl <= 0]
        gw = sum(t.pnl for t in wins); gl = -sum(t.pnl for t in losses)
        pfy = gw / gl if gl > 0 else (float("inf") if gw > 0 else 0.0)
        pfy_s = f"{pfy:.2f}" if pfy != float("inf") else " inf"
        total = sum(t.pnl for t in ts)
        wr = len(wins) / len(ts) if ts else 0
        sub = equity_metrics_subset(equity_curve, lambda d, _y=y: d.year == _y)
        lines.append(f"  {y:>6d}  {regime:22s}  {len(ts):>4d}  {wr:>4.0%}  "
                     f"${total:>+8.0f}  {pfy_s:>5s}  {sub['sharpe']:>5.2f}   {sub['sortino']:>5.2f}")

    # --- Per-regime ---
    lines.append("\n[Per-regime]")
    lines.append(f"  {'Regime':22s}  {'N':>4s}  {'Win%':>5s}  {'Total':>10s}  "
                 f"{'PF':>5s}  {'Sharpe':>6s}  {'Sortino':>7s}")
    by_regime: dict[str, list] = defaultdict(list)
    by_regime_years: dict[str, set] = defaultdict(set)
    for t in trades:
        y = t.entry_date.year if hasattr(t, "entry_date") else t.entry_time.year
        regime = REGIME_BY_YEAR.get(y, "?")
        by_regime[regime].append(t)
        by_regime_years[regime].add(y)
    for regime, ts in sorted(by_regime.items(), key=lambda x: -len(x[1])):
        wins = [t for t in ts if t.pnl > 0]
        losses = [t for t in ts if t.pnl <= 0]
        gw = sum(t.pnl for t in wins); gl = -sum(t.pnl for t in losses)
        pfr = gw / gl if gl > 0 else (float("inf") if gw > 0 else 0.0)
        pfr_s = f"{pfr:.2f}" if pfr != float("inf") else " inf"
        total = sum(t.pnl for t in ts)
        wr = len(wins) / len(ts) if ts else 0
        years = by_regime_years[regime]
        sub = equity_metrics_subset(equity_curve, lambda d, _ys=years: d.year in _ys)
        lines.append(f"  {regime:22s}  {len(ts):>4d}  {wr:>4.0%}  ${total:>+8.0f}  "
                     f"{pfr_s:>5s}  {sub['sharpe']:>5.2f}   {sub['sortino']:>5.2f}")

    # --- Holding-period ---
    lines.append("\n[Holding-period P&L]")
    buckets = {"0d": [], "1d": [], "2d": [], "3d": [], "4d": [], "5+d": []}
    for t in trades:
        d = t.days_held if hasattr(t, "days_held") else (t.exit_time - t.entry_time).days
        key = "5+d" if d >= 5 else f"{d}d"
        buckets[key].append(t.pnl)
    lines.append(f"  {'Hold':6s}  {'N':>4s}  {'Win%':>5s}  {'Total':>10s}  {'Avg':>7s}")
    for k, ps in buckets.items():
        if not ps:
            continue
        wins = sum(1 for p in ps if p > 0)
        wr = wins / len(ps)
        lines.append(f"  {k:6s}  {len(ps):>4d}  {wr:>4.0%}  ${sum(ps):>+8.0f}  ${sum(ps)/len(ps):>+5.0f}")

    # --- Exit reasons ---
    lines.append("\n[Exit reasons]")
    rcounts = Counter(t.reason for t in trades)
    for r, c in rcounts.most_common():
        ps = [t.pnl for t in trades if t.reason == r]
        avg = sum(ps) / len(ps) if ps else 0
        total = sum(ps)
        lines.append(f"  {r:35s} n={c:3d}  avg=${avg:>+5.0f}  total=${total:>+8.0f}")

    # --- Skipped ---
    if skipped:
        lines.append(f"\n[Suppressed signals: {len(skipped)}]")
        for r, c in Counter(s["reason"] for s in skipped).most_common():
            lines.append(f"  {r:35s} {c}")

    return "\n".join(lines) + diversifier_block
