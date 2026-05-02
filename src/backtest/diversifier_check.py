"""Diversifier-criteria evaluation per the locked v2 rules.

Implements the four mechanical pass/fail criteria for diversifier
candidates from DECISIONS.md (Rule 2):

  1. correlation(strategy_daily_returns, qqq_bah_daily_returns) < 0.30
  2. strategy P&L during QQQ drawdown periods (>5% from rolling high) > 0
  3. strategy Sortino > 1.0 standalone
  4. >= 30 trades over the evaluation window

A candidate must pass ALL FOUR to earn a portfolio slot. Failing any
one drops the candidate (or forces a tightening conversation).

Used by v2_report when a strategy is being evaluated as a diversifier
(typically: VIX spike fade, vol breakouts, defensive rotation). NOT
used for buy-and-hold-lift candidates (those use rule 1, the lift
table emitted in the standard report).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class DiversifierVerdict:
    passed: bool
    correlation: float
    correlation_threshold: float
    correlation_pass: bool
    drawdown_pnl: float
    drawdown_pnl_pass: bool
    sortino: float
    sortino_threshold: float
    sortino_pass: bool
    n_trades: int
    n_trades_threshold: int
    n_trades_pass: bool
    failures: list[str] = field(default_factory=list)


def _daily_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def correlation_with_benchmark(
    strategy_equity: pd.Series,
    benchmark_close: pd.Series,
) -> float:
    """Pearson correlation of daily-return series. Aligns indices on
    intersection. Returns 0.0 if either series is empty or non-varying.
    """
    if strategy_equity.empty or benchmark_close.empty:
        return 0.0
    s_ret = _daily_returns(strategy_equity)
    b_ret = _daily_returns(benchmark_close)
    # Align by index
    df = pd.DataFrame({"s": s_ret, "b": b_ret}).dropna()
    if len(df) < 5:
        return 0.0
    if df["s"].std() == 0 or df["b"].std() == 0:
        return 0.0
    return float(df["s"].corr(df["b"]))


def drawdown_period_pnl(
    strategy_equity: pd.Series,
    benchmark_close: pd.Series,
    drawdown_threshold: float = -0.05,
) -> float:
    """Sum of strategy equity-curve daily $ change on days when the
    benchmark is in drawdown >= threshold from rolling-max-high.

    Positive = strategy made money during benchmark drawdowns (hedging).
    Negative = strategy lost money during benchmark drawdowns (amplifying).
    """
    if strategy_equity.empty or benchmark_close.empty:
        return 0.0
    bench_max = benchmark_close.cummax()
    dd_pct = (benchmark_close - bench_max) / bench_max
    in_dd = dd_pct <= drawdown_threshold
    # Strategy's daily $ change
    s_diff = strategy_equity.diff()
    # Align indices
    df = pd.DataFrame({"diff": s_diff, "in_dd": in_dd}).dropna()
    if df.empty:
        return 0.0
    return float(df.loc[df["in_dd"], "diff"].sum())


def evaluate_diversifier(
    strategy_equity: pd.Series,
    n_trades: int,
    benchmark_close: pd.Series,
    sortino: float,
    correlation_threshold: float = 0.30,
    drawdown_threshold: float = -0.05,
    sortino_threshold: float = 1.0,
    n_trades_threshold: int = 30,
) -> DiversifierVerdict:
    """Apply all four diversifier criteria. Returns a verdict with each
    criterion's pass/fail and a list of failure reasons."""
    corr = correlation_with_benchmark(strategy_equity, benchmark_close)
    dd_pnl = drawdown_period_pnl(strategy_equity, benchmark_close, drawdown_threshold)

    correlation_pass = corr < correlation_threshold
    drawdown_pnl_pass = dd_pnl > 0
    sortino_pass = sortino > sortino_threshold
    n_trades_pass = n_trades >= n_trades_threshold

    failures: list[str] = []
    if not correlation_pass:
        failures.append(
            f"correlation {corr:.2f} >= threshold {correlation_threshold:.2f}"
        )
    if not drawdown_pnl_pass:
        failures.append(
            f"drawdown-period P&L ${dd_pnl:.0f} <= 0 (does not hedge benchmark drawdowns)"
        )
    if not sortino_pass:
        failures.append(
            f"Sortino {sortino:.2f} <= threshold {sortino_threshold:.2f}"
        )
    if not n_trades_pass:
        failures.append(
            f"n_trades {n_trades} < threshold {n_trades_threshold} (statistical insufficiency)"
        )

    return DiversifierVerdict(
        passed=not failures,
        correlation=corr,
        correlation_threshold=correlation_threshold,
        correlation_pass=correlation_pass,
        drawdown_pnl=dd_pnl,
        drawdown_pnl_pass=drawdown_pnl_pass,
        sortino=sortino,
        sortino_threshold=sortino_threshold,
        sortino_pass=sortino_pass,
        n_trades=n_trades,
        n_trades_threshold=n_trades_threshold,
        n_trades_pass=n_trades_pass,
        failures=failures,
    )


def format_diversifier_verdict(v: DiversifierVerdict) -> str:
    """Human-readable verdict block for inclusion in v2 reports."""
    lines = []
    lines.append("[Diversifier criteria — Rule 2]")
    lines.append(f"  Correlation with benchmark BAH:  {v.correlation:>+5.2f}  "
                 f"(< {v.correlation_threshold:.2f}? {'PASS' if v.correlation_pass else 'FAIL'})")
    lines.append(f"  P&L during benchmark drawdowns:  ${v.drawdown_pnl:>+7.0f}  "
                 f"(> 0? {'PASS' if v.drawdown_pnl_pass else 'FAIL'})")
    lines.append(f"  Standalone Sortino:              {v.sortino:>5.2f}  "
                 f"(> {v.sortino_threshold:.2f}? {'PASS' if v.sortino_pass else 'FAIL'})")
    lines.append(f"  Trade count:                     {v.n_trades:>5d}  "
                 f"(>= {v.n_trades_threshold}? {'PASS' if v.n_trades_pass else 'FAIL'})")
    overall = "PASS" if v.passed else "FAIL"
    lines.append(f"  Overall:                         {overall}")
    if v.failures:
        for f in v.failures:
            lines.append(f"    - {f}")
    return "\n".join(lines)
