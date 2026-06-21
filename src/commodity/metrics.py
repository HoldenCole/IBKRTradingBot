"""Performance metrics for the commodity backtest.

Reuses the conventions established in the equities work (standard Sortino:
downside deviation = sqrt(sum of negative-return squares / N_total), target 0).
Adds Sharpe and Section-1256 after-tax CAGR (60% LTCG / 40% STCG for futures).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_DAYS = 252


@dataclass
class PerfMetrics:
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    vol: float
    final_equity: float
    n_days: int
    after_tax_cagr: float

    def as_row(self) -> dict:
        return {
            "CAGR": self.cagr, "Sharpe": self.sharpe, "Sortino": self.sortino,
            "MaxDD": self.max_drawdown, "Vol": self.vol,
            "AT_CAGR": self.after_tax_cagr, "FinalEq": self.final_equity,
            "Days": self.n_days,
        }


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (peak - equity) / peak
    return float(dd.max())


def compute(daily_returns: pd.Series, equity: pd.Series | None = None,
            ltcg: float = 0.20, stcg: float = 0.37,
            rf_daily: float = 0.0) -> PerfMetrics:
    """Metrics from a daily return series.

    Section 1256 blended rate = 0.6*ltcg + 0.4*stcg applied to total gain for
    the after-tax CAGR. Default brackets are the higher-bracket pair; the
    report can pass the lower pair too.
    """
    r = daily_returns.dropna()
    if equity is None:
        equity = (1.0 + r).cumprod()
    n = len(r)
    if n == 0 or equity.empty:
        return PerfMetrics(0, 0, 0, 0, 0, 1.0, 0, 0)

    years = n / _DAYS
    final = float(equity.iloc[-1])
    cagr = final ** (1.0 / years) - 1.0 if final > 0 and years > 0 else -1.0

    excess = r - rf_daily
    vol = float(r.std() * np.sqrt(_DAYS))
    sharpe = float(excess.mean() / r.std() * np.sqrt(_DAYS)) if r.std() > 0 else 0.0

    # Standard Sortino: downside dev = sqrt(sum(min(r,0)^2)/N_total), target 0
    downside = np.minimum(r.values, 0.0)
    dd_dev = np.sqrt(np.sum(downside ** 2) / n)
    sortino = float(r.mean() / dd_dev * np.sqrt(_DAYS)) if dd_dev > 0 else 0.0

    max_dd = _max_drawdown(equity)

    # After-tax: Section 1256 blended on total gain
    blended = 0.6 * ltcg + 0.4 * stcg
    gain = final - 1.0
    at_final = 1.0 + gain * (1.0 - blended) if gain > 0 else final
    at_cagr = at_final ** (1.0 / years) - 1.0 if at_final > 0 and years > 0 else -1.0

    return PerfMetrics(
        cagr=cagr, sharpe=sharpe, sortino=sortino, max_drawdown=max_dd,
        vol=vol, final_equity=final, n_days=n, after_tax_cagr=at_cagr,
    )


def correlation(a: pd.Series, b: pd.Series) -> float:
    """Daily-return correlation on the overlapping window."""
    j = pd.concat([a, b], axis=1).dropna()
    if len(j) < 30:
        return float("nan")
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))
