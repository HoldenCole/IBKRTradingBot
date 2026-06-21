"""Single-asset long-flat crypto backtest (the 'tame-the-drawdown' vehicle).

Holds the coin when the trend signal is ON, sits in T-bills when OFF. Models
the deployable reality for a US taxable brokerage account:

  - Vehicle: spot ETF (IBIT for BTC, ETHA for ETH). Modeled as the coin's
    spot return minus a continuous expense ratio while held.
  - Transition costs: each ON<->OFF flip pays a half-spread (bps).
  - OFF capital earns the T-bill rate (same treatment as the equity strategy's
    SGOV leg).
  - No same-bar look-ahead: signal at close[t-1] determines whether the coin
    return over [t-1 -> t] is captured (signal .shift(1)).

365-day annualization happens in the metrics layer; this module just produces
the daily net return + equity curve.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CryptoBTConfig:
    expense_ratio: float = 0.0025      # IBIT ~0.25%/yr, charged while held
    transition_bps: float = 10.0       # half-spread per ON<->OFF flip (bps)
    tbill_annual: float = 0.03         # OFF-capital yield
    apply_costs: bool = True


@dataclass
class CryptoBTResult:
    equity: pd.Series
    daily_returns: pd.Series
    on_fraction: float
    n_transitions: int
    transitions_per_year: float
    cost_drag_annual: float


def run_long_flat(close: pd.Series, signal_on: pd.Series,
                  config: CryptoBTConfig | None = None) -> CryptoBTResult:
    """Long-flat crypto backtest with costs, T-bill OFF, no look-ahead."""
    cfg = config or CryptoBTConfig()
    c = close.dropna()
    r = c.pct_change().fillna(0.0)
    on = signal_on.reindex(c.index).shift(1).fillna(False).astype(bool)  # no look-ahead

    days_per_year = 365
    expense_daily = cfg.expense_ratio / days_per_year
    tbill_daily = (1.0 + cfg.tbill_annual) ** (1.0 / days_per_year) - 1.0

    # Base daily return: coin return (minus expense) when ON, T-bill when OFF
    on_ret = r - (expense_daily if cfg.apply_costs else 0.0)
    daily = on_ret.where(on, tbill_daily)

    # Transition costs on flip days (buy or sell the ETF)
    n_trans = 0
    if cfg.apply_costs:
        flips = on.ne(on.shift(1)).fillna(False)
        n_trans = int(flips.sum())
        daily = daily - flips.astype(float) * (cfg.transition_bps / 1e4)

    equity = (1.0 + daily).cumprod()
    years = len(c) / days_per_year
    on_frac = float(on.mean())
    tpy = n_trans / years if years > 0 else 0.0
    # crude annual cost drag estimate (expense while held + transition bps)
    cost_annual = (cfg.expense_ratio * on_frac
                   + tpy * cfg.transition_bps / 1e4) if cfg.apply_costs else 0.0

    return CryptoBTResult(
        equity=equity, daily_returns=daily, on_fraction=on_frac,
        n_transitions=n_trans, transitions_per_year=tpy,
        cost_drag_annual=cost_annual,
    )


def buy_and_hold(close: pd.Series) -> pd.Series:
    """Daily returns of a passive long position (the benchmark)."""
    return close.dropna().pct_change().fillna(0.0)
