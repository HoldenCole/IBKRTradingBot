"""Portfolio backtest engine for the commodity-trend research.

Turns (signals + covariance + returns) into a daily equity curve with:
  - full-covariance vol-targeting (inverse-vol scheme, target 15%, cap 25%)
  - per-roll transaction costs (per-sector bid-ask in bps, charged on the
    turnover of each instrument's weight, plus a roll cost each time a held
    instrument rolls contracts)
  - T-bill yield on capital not deployed to commodity positions
  - no same-bar look-ahead: signal/weights formed at close[t-1] drive the
    return earned over [t-1 -> t] (locked Q4)

Sizing convention:
  weights[t] are the target NAV fractions per instrument, formed from the
  covariance and signal mask available at the close of day t-1. The book
  earns sum_i weights[t,i] * instrument_return[t] on day t. Capital not in
  commodities (1 - gross_long, floored at 0) earns the daily T-bill rate.
  When gross_long > 1 (vol-targeting can lever up), the excess is funded at
  the T-bill rate (margin proxy) — symmetric and conservative.

Transaction costs:
  cost[t] = sum_i |weights[t,i] - weights_prev_i| * spread_bps_i/2
            + roll_cost_i  on days instrument i changes contract
  charged against the day's return.

Outputs an EngineResult with the equity curve, per-instrument P&L
attribution, gross/Net exposure history, turnover, and realized vol.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.commodity.vol import rolling_cov, vol_target_weights


# Per-sector round-trip bid-ask spread estimates (bps of notional), from the
# spec's guidance: energy rolls cost more, metals less. Charged as half-spread
# on each unit of weight turnover.
SECTOR_SPREAD_BPS = {
    "Energy": 8.0, "Precious": 3.0, "Industrial": 5.0,
    "Grains": 5.0, "Softs": 7.0,
}
# Roll cost (bps of the instrument's notional) charged once per contract roll
# while the position is held. Roughly one bid-ask crossing of the calendar
# spread; sector-scaled like the outright spread.
SECTOR_ROLL_BPS = {
    "Energy": 6.0, "Precious": 2.5, "Industrial": 4.0,
    "Grains": 4.0, "Softs": 5.0,
}


@dataclass
class EngineConfig:
    target_vol: float = 0.15
    max_weight: float = 0.25
    cov_lookback: int = 60
    scheme: str = "inverse_vol"
    tbill_annual: float = 0.0       # flat T-bill yield on idle capital (annual)
    apply_costs: bool = True


@dataclass
class EngineResult:
    equity: pd.Series                 # NAV index, starts at 1.0
    daily_returns: pd.Series          # net daily returns
    gross_long: pd.Series             # sum of long weights per day
    weights: pd.DataFrame             # date x symbol target weights
    turnover: pd.Series               # sum |dw| per day
    cost_drag: pd.Series              # daily cost in return terms
    per_instrument_pnl: pd.Series     # total contribution per symbol
    n_on: pd.Series                   # instruments ON per day
    config: EngineConfig
    meta: dict = field(default_factory=dict)


def _roll_dates_from_raw(raw_close_dir, symbols) -> dict[str, set]:
    """Best-effort: detect roll dates per instrument from the raw cache's
    instrument_id. Returns {symbol: set(of pd.Timestamp roll dates)}.
    If unavailable, returns empty sets (roll cost falls back to 0)."""
    from pathlib import Path
    out = {}
    for s in symbols:
        matches = sorted(Path(raw_close_dir).glob(f"{s}_v_0__*.csv"))
        if not matches:
            out[s] = set()
            continue
        df = pd.read_csv(matches[-1], parse_dates=["date"]).set_index("date")
        if "instrument_id" not in df.columns:
            out[s] = set()
            continue
        iid = df["instrument_id"]
        rolls = df.index[iid.ne(iid.shift(1)) & iid.shift(1).notna()]
        out[s] = set(rolls)
    return out


def run_backtest(
    close: pd.DataFrame,           # Panama-adjusted (for nothing here; kept for parity)
    returns: pd.DataFrame,         # adj.diff()/raw.shift() daily returns
    signal_on: pd.DataFrame,       # bool ON/OFF mask per instrument
    sectors: dict[str, str],
    config: EngineConfig | None = None,
    roll_dates: dict[str, set] | None = None,
) -> EngineResult:
    """Run the vol-targeted long/flat commodity-trend backtest for one signal."""
    cfg = config or EngineConfig()
    syms = list(returns.columns)
    idx = returns.index

    # Pre-compute rolling covariance once (reused across calls if desired).
    cov_hist = rolling_cov(returns, lookback=cfg.cov_lookback)
    cov_dates = sorted(cov_hist.keys())
    if not cov_dates:
        raise ValueError("no covariance matrices — insufficient return history")

    # Daily T-bill factor
    tbill_daily = (1.0 + cfg.tbill_annual) ** (1.0 / 252.0) - 1.0

    spread_half = {s: SECTOR_SPREAD_BPS.get(sectors.get(s, "?"), 5.0) / 2.0 / 1e4
                   for s in syms}
    roll_bps = {s: SECTOR_ROLL_BPS.get(sectors.get(s, "?"), 4.0) / 1e4 for s in syms}
    roll_dates = roll_dates or {s: set() for s in syms}

    # Iterate. weights formed at close[t-1] apply to return[t].
    weights_prev = pd.Series(0.0, index=syms)
    rows_w = {}
    daily_net = pd.Series(0.0, index=idx)
    gross_hist = pd.Series(0.0, index=idx)
    turn_hist = pd.Series(0.0, index=idx)
    cost_hist = pd.Series(0.0, index=idx)
    non_hist = pd.Series(0, index=idx)
    pnl_attr = pd.Series(0.0, index=syms)

    cov_lookup = cov_hist
    # map each date to the most recent available cov date < that date
    cov_idx_arr = np.array(cov_dates)

    for i, t in enumerate(idx):
        if i == 0:
            rows_w[t] = weights_prev.copy()
            continue
        tprev = idx[i - 1]
        # Covariance known at close[t-1]: latest cov date <= tprev
        pos = np.searchsorted(cov_idx_arr, tprev, side="right") - 1
        if pos < 0:
            rows_w[t] = pd.Series(0.0, index=syms)
            gross_hist[t] = 0.0
            non_hist[t] = 0
            # idle capital earns t-bill
            daily_net[t] = tbill_daily
            weights_prev = pd.Series(0.0, index=syms)
            continue
        cov = cov_lookup[cov_idx_arr[pos]]
        on_mask = signal_on.loc[tprev].reindex(cov.columns).fillna(False)
        w = vol_target_weights(cov, on_mask, target_vol=cfg.target_vol,
                               max_weight=cfg.max_weight, scheme=cfg.scheme)
        w = w.reindex(syms).fillna(0.0)

        # Return earned over [t-1 -> t]
        r_t = returns.loc[t].reindex(syms).fillna(0.0)
        gross_ret = float((w * r_t).sum())

        # Idle/levered capital vs T-bill
        gross_long = float(w.sum())
        idle = 1.0 - gross_long
        cash_ret = idle * tbill_daily      # >0 when underinvested, <0 funding when levered

        # Costs: weight turnover half-spread + roll cost on rolling held names
        cost = 0.0
        if cfg.apply_costs:
            dw = (w - weights_prev).abs()
            cost += float((dw * pd.Series(spread_half)).sum())
            # roll cost: instruments rolling on day t that we HELD at t-1
            for s in syms:
                if t in roll_dates.get(s, ()) and abs(weights_prev.get(s, 0.0)) > 0:
                    cost += abs(weights_prev[s]) * roll_bps[s]

        net = gross_ret + cash_ret - cost
        daily_net[t] = net
        gross_hist[t] = gross_long
        turn_hist[t] = float((w - weights_prev).abs().sum())
        cost_hist[t] = cost
        non_hist[t] = int((w > 0).sum())
        pnl_attr = pnl_attr.add(w * r_t, fill_value=0.0)
        rows_w[t] = w
        weights_prev = w

    equity = (1.0 + daily_net).cumprod()
    weights_df = pd.DataFrame(rows_w).T.reindex(idx).fillna(0.0)

    return EngineResult(
        equity=equity,
        daily_returns=daily_net,
        gross_long=gross_hist,
        weights=weights_df,
        turnover=turn_hist,
        cost_drag=cost_hist,
        per_instrument_pnl=pnl_attr,
        n_on=non_hist,
        config=cfg,
        meta={"cov_lookback": cfg.cov_lookback, "n_cov_matrices": len(cov_hist)},
    )
