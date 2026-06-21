"""Crypto-aware performance metrics.

Differences from the commodity metrics:
  - Annualization uses 365 (crypto trades 24/7), not 252.
  - Adds Calmar ratio (CAGR / |max DD|) — the key statistic for the
    "tame the drawdown" question, since crypto's whole problem is 80%
    drawdowns on buy-and-hold.
  - Tax is plain capital-gains (spot crypto is property: short-term =
    ordinary, long-term = LTCG), NOT Section 1256. Tax modeling is left
    light for the characterization round (no deployment mandate yet).

Standard Sortino convention retained (downside dev = sqrt(sum(min(r,0)^2)/N),
target 0).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_DAYS = 365


@dataclass
class CryptoMetrics:
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    vol: float
    final_equity: float
    n_days: int

    def fmt(self) -> str:
        return (f"CAGR {self.cagr:+.0%}  Sharpe {self.sharpe:.2f}  "
                f"Sortino {self.sortino:.2f}  Calmar {self.calmar:.2f}  "
                f"MaxDD {self.max_drawdown:.0%}  Vol {self.vol:.0%}")


def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((peak - equity) / peak).max())


def compute(daily_returns: pd.Series, equity: pd.Series | None = None
            ) -> CryptoMetrics:
    r = daily_returns.dropna()
    if equity is None:
        equity = (1.0 + r).cumprod()
    n = len(r)
    if n == 0 or equity.empty:
        return CryptoMetrics(0, 0, 0, 0, 0, 0, 1.0, 0)

    years = n / _DAYS
    final = float(equity.iloc[-1])
    cagr = final ** (1.0 / years) - 1.0 if final > 0 and years > 0 else -1.0
    vol = float(r.std() * np.sqrt(_DAYS))
    sharpe = float(r.mean() / r.std() * np.sqrt(_DAYS)) if r.std() > 0 else 0.0
    downside = np.minimum(r.values, 0.0)
    dd_dev = np.sqrt(np.sum(downside ** 2) / n)
    sortino = float(r.mean() / dd_dev * np.sqrt(_DAYS)) if dd_dev > 0 else 0.0
    max_dd = _max_dd(equity)
    calmar = float(cagr / max_dd) if max_dd > 0 else 0.0

    return CryptoMetrics(
        cagr=cagr, sharpe=sharpe, sortino=sortino, calmar=calmar,
        max_drawdown=max_dd, vol=vol, final_equity=final, n_days=n,
    )


def correlation(a: pd.Series, b: pd.Series, min_overlap: int = 30) -> float:
    j = pd.concat([a, b], axis=1).dropna()
    if len(j) < min_overlap:
        return float("nan")
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))
