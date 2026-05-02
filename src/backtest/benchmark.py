"""Buy-and-hold benchmark metrics.

Pure functions over a pandas close-price Series. Used as the baseline that
every backtest variant must compare against. The "tier" classifier in
src/backtest/tier.py reads `BenchmarkMetrics.total_return` and `.sharpe`
to decide whether a strategy clears the bar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BenchmarkMetrics:
    symbol: str
    period_start: str
    period_end: str
    years: float
    total_return: float
    cagr: float
    sharpe: float           # annualized, risk-free = 0
    sortino: float          # annualized, downside-only deviation
    max_drawdown: float     # negative number, e.g. -0.34
    final_equity: float


def buy_and_hold_metrics(
    closes: pd.Series,
    start_capital: float = 8000.0,
    symbol: str = "BENCHMARK",
) -> BenchmarkMetrics:
    """Compute buy-and-hold metrics from a close-price series."""
    if len(closes) < 2:
        raise ValueError("benchmark needs >=2 close prices")

    rets = closes.pct_change().dropna()
    total_return = float((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0])
    years = float((closes.index[-1] - closes.index[0]).days / 365.25)
    cagr = (closes.iloc[-1] / closes.iloc[0]) ** (1.0 / max(years, 1e-9)) - 1.0 if years > 0 else 0.0

    daily_mean = float(rets.mean())
    daily_std = float(rets.std(ddof=0))
    sharpe = (daily_mean / daily_std) * math.sqrt(252) if daily_std > 0 else 0.0

    neg = rets[rets < 0]
    if len(neg) and float(neg.std(ddof=0)) > 0:
        sortino = (daily_mean / float(neg.std(ddof=0))) * math.sqrt(252)
    else:
        sortino = 0.0

    eq = (closes / closes.iloc[0]) * start_capital
    rmax = eq.cummax()
    dd = (eq - rmax) / rmax
    max_dd = float(dd.min())
    final_equity = float(eq.iloc[-1])

    return BenchmarkMetrics(
        symbol=symbol,
        period_start=str(closes.index[0].date() if hasattr(closes.index[0], "date") else closes.index[0]),
        period_end=str(closes.index[-1].date() if hasattr(closes.index[-1], "date") else closes.index[-1]),
        years=years,
        total_return=total_return,
        cagr=float(cagr),
        sharpe=float(sharpe),
        sortino=float(sortino),
        max_drawdown=max_dd,
        final_equity=final_equity,
    )


def equity_metrics(
    equity: pd.Series,
    start_capital: float,
) -> dict:
    """Compute the same shape of metrics from any equity curve, used by the
    strategy result so it can be compared apples-to-apples to a benchmark.
    """
    if len(equity) < 2:
        return {
            "total_return": 0.0, "cagr": 0.0, "sharpe": 0.0, "sortino": 0.0,
            "max_drawdown": 0.0, "final_equity": float(equity.iloc[0] if len(equity) else start_capital),
        }
    rets = equity.pct_change().dropna()
    total_return = float((equity.iloc[-1] - equity.iloc[0]) / equity.iloc[0])
    years = float((equity.index[-1] - equity.index[0]).days / 365.25) if hasattr(equity.index[-1], "year") else len(equity) / 252.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / max(years, 1e-9)) - 1.0 if years > 0 else 0.0
    daily_std = float(rets.std(ddof=0))
    sharpe = (float(rets.mean()) / daily_std) * math.sqrt(252) if daily_std > 0 else 0.0
    neg = rets[rets < 0]
    sortino = (float(rets.mean()) / float(neg.std(ddof=0))) * math.sqrt(252) \
        if len(neg) and float(neg.std(ddof=0)) > 0 else 0.0
    rmax = equity.cummax()
    dd = (equity - rmax) / rmax
    max_dd = float(dd.min())
    return {
        "total_return": total_return,
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": max_dd,
        "final_equity": float(equity.iloc[-1]),
    }


def equity_metrics_subset(
    equity: pd.Series,
    date_filter,  # callable date -> bool
) -> dict:
    """Slice the equity curve by a date predicate and compute metrics on
    that subset. Used for per-year and per-regime Sortino reporting.

    Returns sharpe=0, sortino=0 etc. when the slice has fewer than 2 points.
    The 'subset' is a contiguous-or-not selection by date; daily returns
    are computed within the subset only (so a regime composed of multiple
    non-contiguous years will compute returns within each contiguous run
    correctly via pct_change).
    """
    if equity.empty:
        return _empty_metrics()
    mask = pd.Series(
        [date_filter(d.date() if hasattr(d, "date") else d) for d in equity.index],
        index=equity.index,
    )
    sub = equity.loc[mask]
    if len(sub) < 2:
        return _empty_metrics()
    rets = sub.pct_change().dropna()
    if rets.empty:
        return _empty_metrics()
    daily_std = float(rets.std(ddof=0))
    sharpe = (float(rets.mean()) / daily_std) * math.sqrt(252) if daily_std > 0 else 0.0
    neg = rets[rets < 0]
    sortino = (float(rets.mean()) / float(neg.std(ddof=0))) * math.sqrt(252) \
        if len(neg) and float(neg.std(ddof=0)) > 0 else 0.0
    rmax = sub.cummax()
    dd = (sub - rmax) / rmax
    return {
        "n_days": len(sub),
        "subset_return": float((sub.iloc[-1] - sub.iloc[0]) / sub.iloc[0]) if sub.iloc[0] else 0.0,
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(dd.min()),
    }


def _empty_metrics() -> dict:
    return {"n_days": 0, "subset_return": 0.0, "sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0}
