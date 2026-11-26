"""Minute-bar execution simulator for the intraday forex harness.

Prices are mid OHLC from the feed's bid and ask; every fill crosses the
effective half spread h[bar] from costs.py. Rules hand the engine trades as
arrays (entry bar, side, stop, target, last bar); the engine finds each exit.

Fill rules, all conservative:
  - market entries and time exits fill at the bar OPEN of the given bar;
  - a long's stop triggers when the effective bid low (mid low - h) reaches it,
    a short's when the effective ask high does; fill at the stop minus slippage,
    or at the bar open if price gapped through;
  - targets are limit orders: fill at the target, or at the open if gapped through;
  - stop and target touched in the same minute: the stop is taken;
  - stop-entry trades (breakouts) check only the stop in the trigger bar.
"""
from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
import pandas as pd

from research.fx_intraday import costs
from research.fx_intraday.data import pip

STOP, TARGET, TIME = 0, 1, 2


@dataclass
class Bars:
    pair: str
    time: pd.DatetimeIndex          # UTC, one per minute bar
    mid_o: np.ndarray
    mid_h: np.ndarray
    mid_l: np.ndarray
    mid_c: np.ndarray
    spread: np.ndarray              # feed spread at the bar open (ask_o - bid_o)

    @classmethod
    def from_frame(cls, pair: str, df: pd.DataFrame) -> "Bars":
        return cls(pair=pair, time=df.index,
                   mid_o=((df["bid_o"] + df["ask_o"]) / 2).to_numpy(),
                   mid_h=((df["bid_h"] + df["ask_h"]) / 2).to_numpy(),
                   mid_l=((df["bid_l"] + df["ask_l"]) / 2).to_numpy(),
                   mid_c=((df["bid_c"] + df["ask_c"]) / 2).to_numpy(),
                   spread=(df["ask_o"] - df["bid_o"]).to_numpy())

    def __len__(self) -> int:
        return len(self.mid_o)

    def index_at(self, times: pd.DatetimeIndex | pd.Series) -> np.ndarray:
        """Index of the first bar at or after each time."""
        return np.searchsorted(self.time.asi8, pd.DatetimeIndex(times).asi8, side="left")


@numba.njit(cache=True)
def _exits(entry_idx, side, stop, target, last_idx, intrabar, mid_o, mid_h, mid_l, h, slip):
    n = entry_idx.shape[0]
    out_idx = np.empty(n, np.int64)
    out_px = np.empty(n, np.float64)
    out_kind = np.empty(n, np.int8)
    out_slip = np.zeros(n, np.float64)
    for k in range(n):
        i = entry_idx[k]
        s = side[k]
        lim = last_idx[k]
        done = False
        for j in range(i, lim):
            hj = h[j]
            first = j == i
            if s == 1:
                op = mid_o[j] - hj
                lo = mid_l[j] - hj
                hi = mid_h[j] - hj
                if not first and op <= stop[k]:
                    out_idx[k] = j; out_px[k] = op - slip; out_kind[k] = 0; out_slip[k] = slip; done = True; break
                if lo <= stop[k]:
                    out_idx[k] = j; out_px[k] = stop[k] - slip; out_kind[k] = 0; out_slip[k] = slip; done = True; break
                if first and intrabar[k]:
                    continue
                if not first and op >= target[k]:
                    out_idx[k] = j; out_px[k] = op; out_kind[k] = 1; done = True; break
                if hi >= target[k]:
                    out_idx[k] = j; out_px[k] = target[k]; out_kind[k] = 1; done = True; break
            else:
                op = mid_o[j] + hj
                lo = mid_l[j] + hj
                hi = mid_h[j] + hj
                if not first and op >= stop[k]:
                    out_idx[k] = j; out_px[k] = op + slip; out_kind[k] = 0; out_slip[k] = slip; done = True; break
                if hi >= stop[k]:
                    out_idx[k] = j; out_px[k] = stop[k] + slip; out_kind[k] = 0; out_slip[k] = slip; done = True; break
                if first and intrabar[k]:
                    continue
                if not first and op <= target[k]:
                    out_idx[k] = j; out_px[k] = op; out_kind[k] = 1; done = True; break
                if lo <= target[k]:
                    out_idx[k] = j; out_px[k] = target[k]; out_kind[k] = 1; done = True; break
        if not done:
            out_idx[k] = lim
            out_px[k] = mid_o[lim] - s * h[lim]
            out_kind[k] = 2
    return out_idx, out_px, out_kind, out_slip


@numba.njit(cache=True)
def _stop_entries(start_idx, end_idx, buy_level, sell_level, mid_o, mid_h, mid_l, h, slip):
    """First bar in [start, end) where a buy stop or sell stop triggers; -1 if none or both in one bar."""
    n = start_idx.shape[0]
    idx = np.full(n, -1, np.int64)
    side = np.zeros(n, np.int8)
    px = np.zeros(n, np.float64)
    for k in range(n):
        for j in range(start_idx[k], end_idx[k]):
            ask_hi = mid_h[j] + h[j]
            bid_lo = mid_l[j] - h[j]
            up = ask_hi >= buy_level[k]
            dn = bid_lo <= sell_level[k]
            if up and dn:
                break                                   # ambiguous minute: skip the day
            if up:
                idx[k] = j; side[k] = 1
                px[k] = max(buy_level[k], mid_o[j] + h[j]) + slip
                break
            if dn:
                idx[k] = j; side[k] = -1
                px[k] = min(sell_level[k], mid_o[j] - h[j]) - slip
                break
    return idx, side, px


def simulate(bars: Bars, entry_idx, side, stop, target, last_idx, stress: float = 1.0,
             entry_px=None, entry_slip=None, intrabar=None) -> pd.DataFrame:
    """Run trades whose entries are known. Market entries fill at the entry bar open
    unless entry_px is given (stop entries). Returns one row per trade."""
    entry_idx = np.asarray(entry_idx, np.int64)
    side = np.asarray(side, np.int8)
    stop = np.asarray(stop, np.float64)
    target = np.asarray(target, np.float64)
    last_idx = np.minimum(np.asarray(last_idx, np.int64), len(bars) - 1)
    h = costs.half_spread(bars.spread, bars.pair, stress)
    slip = costs.stop_slip(bars.pair, stress)
    if intrabar is None:
        intrabar = np.zeros(len(entry_idx), np.bool_)
    ok = last_idx > entry_idx
    entry_idx, side, stop, target, last_idx, intrabar = (a[ok] for a in (entry_idx, side, stop, target, last_idx, np.asarray(intrabar, np.bool_)))
    if entry_px is None:
        e_px = bars.mid_o[entry_idx] + side * h[entry_idx]
        e_slip = np.zeros(len(entry_idx))
    else:
        e_px = np.asarray(entry_px, np.float64)[ok]
        e_slip = np.asarray(entry_slip, np.float64)[ok]
    x_idx, x_px, kind, x_slip = _exits(entry_idx, side, stop, target, last_idx, intrabar,
                                       bars.mid_o, bars.mid_h, bars.mid_l, h, slip)
    ref = bars.mid_o[entry_idx]
    # mid-equivalent prices: strip the spread and slippage actually paid
    e_mid = e_px - side * (h[entry_idx] + e_slip)
    x_mid = x_px + side * (h[x_idx] + x_slip)
    net = side * (x_px - e_px) / ref * 1e4
    gross = side * (x_mid - e_mid) / ref * 1e4
    risk = np.abs(e_mid - stop) / ref * 1e4
    return pd.DataFrame({
        "entry_time": bars.time[entry_idx], "exit_time": bars.time[x_idx],
        "entry_idx": entry_idx, "exit_idx": x_idx, "side": side,
        "entry_px": e_px, "exit_px": x_px, "kind": kind,
        "net_bp": net, "gross_bp": gross, "cost_bp": gross - net,
        "risk_bp": risk, "R": np.where(risk > 0, net / np.where(risk > 0, risk, 1), np.nan),
        "entry_mid": ref, "stop": stop, "target": target, "last_idx": last_idx,
    })


def one_at_a_time(trades: pd.DataFrame) -> pd.DataFrame:
    """Keep trades in entry order, skipping any that enters before the previous kept one has exited."""
    if trades.empty:
        return trades
    tr = trades.sort_values("entry_idx")
    keep = np.zeros(len(tr), bool)
    last_exit = -1
    for k, (e, x) in enumerate(zip(tr["entry_idx"].to_numpy(), tr["exit_idx"].to_numpy())):
        if e > last_exit:
            keep[k] = True
            last_exit = x
    return tr[keep].reset_index(drop=True)


def stop_entries(bars: Bars, start_idx, end_idx, buy_level, sell_level, stress: float = 1.0):
    h = costs.half_spread(bars.spread, bars.pair, stress)
    slip = costs.stop_slip(bars.pair, stress)
    return _stop_entries(np.asarray(start_idx, np.int64), np.asarray(end_idx, np.int64),
                         np.asarray(buy_level, np.float64), np.asarray(sell_level, np.float64),
                         bars.mid_o, bars.mid_h, bars.mid_l, h, slip) + (slip,)


def pips(bars: Bars, x: float) -> float:
    return x * pip(bars.pair)
