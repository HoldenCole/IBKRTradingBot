"""Three trend-signal variants for the commodity research.

All signals are LONG/FLAT (ON = hold long, OFF = flat → capital to T-bills),
matching the spec ("ON when... OFF otherwise" + "capital not deployed goes to
T-bills"). They key on the Panama-adjusted close (signals must be tradeable
across roll seams). Each returns a boolean DataFrame aligned to the input
(date × symbol); True = ON.

Locked signal definitions (NO parameter tuning — these are fixed):

  V1  Classic 50/200 SMA crossover
        ON  when close > SMA(50) AND SMA(50) > SMA(200)
        OFF otherwise

  V2  Donchian channel breakout (CTA-classic, asymmetric, STATEFUL)
        ENTER long when close > highest close of trailing 100 days
        EXIT to flat when close < lowest close of trailing 50 days
        Hold previous state between. Slower exit than entry "gives positions
        room to breathe."

  V3  Vol-adjusted (time-series) momentum
        ratio = 12-month return / 12-month annualized vol  (Sharpe-style)
        ON when ratio is in the top 50% of its trailing 24-month range.

Look-ahead discipline: every threshold uses only information available at the
prior close. Breakout bands and SMAs are computed on closes through t and
compared to close[t]; the resulting ON/OFF flag for date t is therefore known
at the close of t and is applied to NEXT bar's return by the engine (M6), so
there is no same-bar look-ahead in the backtest (locked Q4).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Per-instrument application
# --------------------------------------------------------------------------
# The panel uses a UNION calendar across instruments, so any single instrument
# has NaN rows on days it doesn't trade but another does (grains vs energy
# differ by ~240 days). Computing rolling signals on the union frame with
# min_periods=window makes those NaN-containing windows evaluate to NaN/False,
# which silently zeroed out grain signals. Correct approach: compute each
# signal on the instrument's OWN valid series, then reindex to the panel
# calendar carrying the signal state forward on non-trading days (the position
# persists when the market is closed for that contract).
def _per_instrument(frame: pd.DataFrame, fn) -> pd.DataFrame:
    out = {}
    for col in frame.columns:
        s = frame[col].dropna()
        if s.empty:
            out[col] = pd.Series(False, index=frame.index)
            continue
        sig = fn(s).reindex(frame.index).ffill().fillna(False)
        out[col] = sig.astype(bool)
    return pd.DataFrame(out, index=frame.index)


# --------------------------------------------------------------------------
# V1 — 50/200 SMA crossover
# --------------------------------------------------------------------------
def sma_crossover(close: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """ON when close > SMA(fast) AND SMA(fast) > SMA(slow). Per-instrument."""
    def _one(s: pd.Series) -> pd.Series:
        sma_f = s.rolling(fast, min_periods=fast).mean()
        sma_s = s.rolling(slow, min_periods=slow).mean()
        return (s > sma_f) & (sma_f > sma_s)
    return _per_instrument(close, _one)


# --------------------------------------------------------------------------
# V2 — Donchian breakout (stateful, asymmetric)
# --------------------------------------------------------------------------
def donchian_breakout(close: pd.DataFrame, entry: int = 100, exit: int = 50) -> pd.DataFrame:
    """Stateful long/flat Donchian.

    Enter long when close exceeds the highest close of the prior `entry` days;
    exit to flat when close falls below the lowest close of the prior `exit`
    days; hold otherwise.

    Vectorized via entry/exit event series forward-filled into a state. Uses
    `.shift(1)` on the rolling bands so the breakout is judged against PRIOR
    days only (no same-bar inclusion).
    """
    def _one(s: pd.Series) -> pd.Series:
        hi = s.rolling(entry, min_periods=entry).max().shift(1)
        lo = s.rolling(exit, min_periods=exit).min().shift(1)
        e = (s > hi).to_numpy()
        x = (s < lo).to_numpy()
        state = np.zeros(len(s), dtype=bool)
        cur = False
        for i in range(len(s)):
            if not cur and e[i]:
                cur = True
            elif cur and x[i]:
                cur = False
            state[i] = cur
        return pd.Series(state, index=s.index)
    return _per_instrument(close, _one)


# --------------------------------------------------------------------------
# V3 — Vol-adjusted time-series momentum
# --------------------------------------------------------------------------
def vol_adj_momentum(
    returns: pd.DataFrame,
    ret_window: int = 252,
    range_window: int = 504,
    annualization: int = 252,
    range_mode: str = "minmax",
) -> pd.DataFrame:
    """Vol-adjusted momentum gate. Computed per-instrument on its own returns.

    ratio_t = (12-month return) / (12-month annualized vol)
            = (TRI[t]/TRI[t-ret_window] - 1) / (std(r, ret_window) * sqrt(252))

    ON when ratio_t is in the top 50% of its trailing `range_window` window.

    range_mode:
      "minmax"  (default) — top 50% of the [min, max] RANGE:
                 ON when ratio > min_w + 0.5*(max_w - min_w).
                 Literal reading of "top 50% of its trailing 24-month range".
                 NOTE: because the gate is relative to the ratio's OWN recent
                 range, V3 is a momentum-ACCELERATION signal, not an absolute
                 trend signal — it is ON when risk-adjusted momentum is in the
                 upper half of its 2-year history, regardless of price level.
                 This makes it behave very differently from V1/V2, and notably
                 it is NOT suppressed by back-adjustment drift (which is why it
                 fires on grains where V1/V2 are quiet).
      "median"  — top 50% by RANK: ON when ratio > rolling median (ablation).

    Warmup: needs ret_window + range_window valid bars (~3 yrs), so on the
    2010-2026 panel momentum effectively starts ~mid-2013.
    """
    if range_mode not in {"minmax", "median"}:
        raise ValueError(f"unknown range_mode: {range_mode!r}")

    def _one(r: pd.Series) -> pd.Series:
        tri = (1.0 + r).cumprod()
        ret_12m = tri / tri.shift(ret_window) - 1.0
        vol_12m = r.rolling(ret_window, min_periods=int(ret_window * 0.8)).std() \
            * np.sqrt(annualization)
        ratio = ret_12m / vol_12m.replace(0.0, np.nan)
        if range_mode == "minmax":
            lo = ratio.rolling(range_window, min_periods=int(range_window * 0.8)).min()
            hi = ratio.rolling(range_window, min_periods=int(range_window * 0.8)).max()
            mid = lo + 0.5 * (hi - lo)
            return ratio > mid
        med = ratio.rolling(range_window, min_periods=int(range_window * 0.8)).median()
        return ratio > med

    return _per_instrument(returns, _one)


# --------------------------------------------------------------------------
# V3-LS — Long/short vol-adjusted momentum (Test 1, second pass)
# --------------------------------------------------------------------------
def vol_adj_momentum_ls(
    returns: pd.DataFrame,
    ret_window: int = 252,
    range_window: int = 504,
    annualization: int = 252,
    long_q: float = 2.0 / 3.0,
    short_q: float = 1.0 / 3.0,
) -> pd.DataFrame:
    """Long/short vol-adjusted momentum as a DIRECTION frame (-1/0/+1).

    Same ratio as the long-flat V3:
        ratio = 12m return / 12m annualized vol
    Gated on the trailing 24-month [min,max] range of the ratio:
        +1 (LONG)  when ratio > min + long_q * (max-min)   [top 1/3]
        -1 (SHORT) when ratio < min + short_q * (max-min)   [bottom 1/3]
         0 (FLAT)  in the middle third
    Computed per-instrument (NaN-safe via _per_instrument with object dtype).
    """
    def _one(r: pd.Series) -> pd.Series:
        tri = (1.0 + r).cumprod()
        ret_12m = tri / tri.shift(ret_window) - 1.0
        vol_12m = r.rolling(ret_window, min_periods=int(ret_window * 0.8)).std() \
            * np.sqrt(annualization)
        ratio = ret_12m / vol_12m.replace(0.0, np.nan)
        lo = ratio.rolling(range_window, min_periods=int(range_window * 0.8)).min()
        hi = ratio.rolling(range_window, min_periods=int(range_window * 0.8)).max()
        rng = (hi - lo)
        up = lo + long_q * rng
        dn = lo + short_q * rng
        dir_ = pd.Series(0.0, index=r.index)
        dir_[ratio > up] = 1.0
        dir_[ratio < dn] = -1.0
        # blank where thresholds undefined
        dir_[rng.isna() | ratio.isna()] = 0.0
        return dir_

    out = {}
    for col in returns.columns:
        s = returns[col].dropna()
        if s.empty:
            out[col] = pd.Series(0.0, index=returns.index)
            continue
        # direction is numeric; carry-forward on non-trading days, fill 0 in warmup
        d = _one(s).reindex(returns.index).ffill().fillna(0.0)
        out[col] = d
    return pd.DataFrame(out, index=returns.index)


# --------------------------------------------------------------------------
# Carry — term-structure roll-yield signal (Test 2, second pass)
# --------------------------------------------------------------------------
def carry_signal(
    front_close: pd.DataFrame,
    second_close: pd.DataFrame,
    short_threshold_monthly: float = -0.005,
) -> pd.DataFrame:
    """Term-structure carry as a DIRECTION frame (-1/0/+1).

    ratio = (front - second) / front     (positive => backwardation)
      +1 (LONG)  when ratio > 0           (backwardation, positive roll yield)
      -1 (SHORT) when ratio < short_threshold (deep contango)
       0 (FLAT)  otherwise

    The threshold is a per-period (≈monthly) carry; front/second are adjacent
    delivery months so the raw ratio is already ~monthly carry. Computed
    per-instrument; carried forward on non-trading days.
    """
    common = front_close.columns.intersection(second_close.columns)
    out = {}
    for s in common:
        f = front_close[s]
        sec = second_close[s].reindex(f.index)
        ratio = (f - sec) / f.replace(0.0, np.nan)
        d = pd.Series(0.0, index=f.index)
        d[ratio > 0] = 1.0
        d[ratio < short_threshold_monthly] = -1.0
        d = d.where(ratio.notna(), 0.0)
        out[s] = d.reindex(front_close.index).ffill().fillna(0.0)
    return pd.DataFrame(out, index=front_close.index)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
SIGNAL_LABELS = {
    "V1_sma_50_200": "Classic 50/200 SMA crossover",
    "V2_donchian_100_50": "Donchian 100/50 breakout (CTA-classic)",
    "V3_vol_adj_momentum": "Vol-adjusted 12m momentum",
}


def compute_all(close: pd.DataFrame, returns: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Compute all three signal masks. close = Panama-adjusted; returns =
    panel.returns() (adj.diff()/raw.shift)."""
    return {
        "V1_sma_50_200": sma_crossover(close, 50, 200),
        "V2_donchian_100_50": donchian_breakout(close, 100, 50),
        "V3_vol_adj_momentum": vol_adj_momentum(returns, 252, 504),
    }
