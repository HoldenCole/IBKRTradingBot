"""The pre-registered rules (PREREGISTRATION.md). Each returns a trades frame from engine.simulate.

Nothing here reads a bar that has not closed: hourly signals use completed
hourly bars and enter at the first minute bar at or after the hour's close;
the breakout's range closes before its trigger window opens.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.fx_intraday import costs
from research.fx_intraday.data import pip
from research.fx_intraday.engine import Bars, one_at_a_time, simulate, stop_entries

NY, LDN, BER = "America/New_York", "Europe/London", "Europe/Berlin"
MR_GRID = [(k, m, T) for k in (2.0, 2.5) for m in (1.0, 2.0) for T in (4, 8)]
RN_GRID_PIPS = 50
RN_NEAR_PIPS = 10
RN_CONTROL_OFFSETS = (13, 27, 37)
CATASTROPHE_STOP = 0.01
MAX_LATE = pd.Timedelta(minutes=5)


def holiday(local: pd.DatetimeIndex) -> np.ndarray:
    m, d = local.month, local.day
    return np.asarray(((m == 12) & (d >= 24)) | ((m == 1) & (d <= 2)))


def next_flat(entry_utc: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The next 16:45 New York at or after each entry."""
    ny = entry_utc.tz_convert(NY)
    cand = ny.normalize() + pd.Timedelta(hours=16, minutes=45)
    cand = cand.where(ny < cand, cand + pd.Timedelta(days=1))
    return cand.tz_convert("UTC")


def _usd_side(pair: str) -> int:
    """+1 if a stronger dollar means buying the pair (USDxxx), -1 if selling it (xxxUSD)."""
    return 1 if pair.startswith("USD") else -1


# ---------------------------------------------------------------- 1. session drift
def drift_specs(bars: Bars, leg: str) -> dict:
    days = pd.date_range(bars.time[0].normalize().tz_localize(None), bars.time[-1].normalize().tz_localize(None), freq="B")
    if leg == "A":
        tz = BER
        entry = (days + pd.Timedelta(hours=8)).tz_localize(tz).tz_convert("UTC")
        exit_ = (days + pd.Timedelta(hours=14, minutes=15)).tz_localize(tz).tz_convert("UTC")
        side = _usd_side(bars.pair)
    else:
        entry = (days + pd.Timedelta(hours=16)).tz_localize(LDN).tz_convert("UTC")
        exit_ = (days + pd.Timedelta(hours=16, minutes=45)).tz_localize(NY).tz_convert("UTC")
        side = -_usd_side(bars.pair)
    ei = bars.index_at(entry)
    xi = bars.index_at(exit_)
    n = len(bars)
    ok = (ei < n) & (xi < n) & (xi > ei)
    ei, xi, entry, exit_, days = ei[ok], xi[ok], entry[ok], exit_[ok], days[ok]
    late_e = bars.time[ei] - entry
    late_x = bars.time[xi] - exit_
    ok = (late_e <= MAX_LATE) & (late_x <= pd.Timedelta(minutes=30))
    ok &= ~holiday(entry.tz_convert(NY))
    ok &= costs.spread_ok(bars.spread[ei], bars.pair)
    ei, xi = ei[ok], xi[ok]
    sides = np.full(len(ei), side, np.int8)
    mid = bars.mid_o[ei]
    return {"entry_idx": ei, "side": sides, "stop": mid * (1 - sides * CATASTROPHE_STOP),
            "target": np.where(sides == 1, 1e9, -1e9), "last_idx": xi}


def drift(bars: Bars, leg: str, stress: float = 1.0) -> pd.DataFrame:
    legs = ["A", "B"] if leg == "AB" else [leg]
    parts = []
    for lg in legs:
        sp = drift_specs(bars, lg)
        t = simulate(bars, stress=stress, **sp)
        t["leg"] = lg
        parts.append(t)
    return pd.concat(parts).sort_values("entry_idx").reset_index(drop=True)


# ---------------------------------------------------------------- 2-3. hourly mean reversion
def hourly(bars: Bars) -> pd.DataFrame:
    m = pd.DataFrame({"o": bars.mid_o, "h": bars.mid_h, "l": bars.mid_l, "c": bars.mid_c}, index=bars.time)
    hb = m.resample("1h", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    sma = hb["c"].rolling(20).mean()
    sd = hb["c"].rolling(20).std(ddof=0)
    prev_c = hb["c"].shift(1)
    tr = pd.concat([hb["h"] - hb["l"], (hb["h"] - prev_c).abs(), (hb["l"] - prev_c).abs()], axis=1).max(axis=1)
    hb["sma"] = sma
    hb["z"] = (hb["c"] - sma) / sd
    hb["atr"] = tr.rolling(14).mean()
    return hb


def mr_candidates(bars: Bars, hb: pd.DataFrame, k: float) -> pd.DataFrame:
    sig = hb[(hb["z"].abs() > k) & hb["atr"].notna()].copy()
    sig["side"] = np.where(sig["z"] < 0, 1, -1).astype(np.int8)
    entry_t = sig.index + pd.Timedelta(hours=1)
    ei = bars.index_at(entry_t)
    ok = ei < len(bars)
    sig, ei, entry_t = sig[ok], ei[ok], entry_t[ok]
    ok = (bars.time[ei] - entry_t) <= pd.Timedelta(minutes=15)
    sig, ei, entry_t = sig[ok], ei[ok], entry_t[ok]
    ny = bars.time[ei].tz_convert(NY)
    hr, dow = ny.hour, ny.day_of_week
    ok = ~((hr >= 15) & (hr < 19)) & ~((dow == 4) & (hr >= 12)) & (dow != 5) & ~holiday(ny)
    ok &= costs.spread_ok(bars.spread[ei], bars.pair)
    sig = sig[np.asarray(ok)]
    sig["entry_idx"] = ei[np.asarray(ok)]
    return sig


def eligible_mr_minutes(bars: Bars) -> np.ndarray:
    ny = bars.time.tz_convert(NY)
    hr, dow = ny.hour, ny.day_of_week
    ok = ~((hr >= 15) & (hr < 19)) & ~((dow == 4) & (hr >= 12)) & (dow != 5) & ~holiday(ny)
    return np.asarray(ok) & costs.spread_ok(bars.spread, bars.pair)


def round_filter(bars: Bars, cand: pd.DataFrame, offset_pips: float = 0.0) -> pd.DataFrame:
    p = pip(bars.pair)
    grid = RN_GRID_PIPS * p
    off = offset_pips * p
    px = bars.mid_o[cand["entry_idx"].to_numpy()]
    below = np.floor((px - off) / grid) * grid + off
    above = np.ceil((px - off) / grid) * grid + off
    near = RN_NEAR_PIPS * p + 1e-12
    side = cand["side"].to_numpy()
    keep = np.where(side == 1, (px - below) <= near, (above - px) <= near)
    return cand[keep]


def mr_trades(bars: Bars, cand: pd.DataFrame, m: float, T: int, stress: float = 1.0) -> pd.DataFrame:
    if cand.empty:
        return pd.DataFrame()
    ei = cand["entry_idx"].to_numpy()
    side = cand["side"].to_numpy()
    mid = bars.mid_o[ei]
    stop = mid - side * m * cand["atr"].to_numpy()
    target = cand["sma"].to_numpy()
    entry_t = bars.time[ei]
    last_t = np.minimum((entry_t + pd.Timedelta(hours=T)).asi8, next_flat(entry_t).asi8)
    li = np.searchsorted(bars.time.asi8, last_t, side="left")
    t = simulate(bars, ei, side, stop, target, li, stress=stress)
    return one_at_a_time(t)


def mean_reversion(bars: Bars, k, m, T, stress=1.0, hb=None, round_offset=None) -> pd.DataFrame:
    hb = hourly(bars) if hb is None else hb
    cand = mr_candidates(bars, hb, k)
    if round_offset is not None:
        cand = round_filter(bars, cand, round_offset)
    return mr_trades(bars, cand, m, T, stress)


# ---------------------------------------------------------------- 4. London breakout
def london_breakout(bars: Bars, stress: float = 1.0) -> pd.DataFrame:
    p = pip(bars.pair)
    days = pd.date_range(bars.time[0].normalize().tz_localize(None), bars.time[-1].normalize().tz_localize(None), freq="B")
    r0 = days.tz_localize(LDN).tz_convert("UTC")
    r1 = (days + pd.Timedelta(hours=7)).tz_localize(LDN).tz_convert("UTC")
    w1 = (days + pd.Timedelta(hours=12)).tz_localize(LDN).tz_convert("UTC")
    fl = (days + pd.Timedelta(hours=16, minutes=45)).tz_localize(NY).tz_convert("UTC")
    i0, i1, iw, il = (bars.index_at(x) for x in (r0, r1, w1, fl))
    n = len(bars)
    ok = (i1 > i0 + 60) & (iw > i1) & (il > iw) & (il < n) & ~holiday(r1.tz_convert(NY))
    i0, i1, iw, il = i0[ok], i1[ok], iw[ok], il[ok]
    hi = np.array([bars.mid_h[a:b].max() for a, b in zip(i0, i1)])
    lo = np.array([bars.mid_l[a:b].min() for a, b in zip(i0, i1)])
    width = hi - lo
    ok = (width >= 3 * p) & (width <= 100 * p)
    i1, iw, il, hi, lo, width = i1[ok], iw[ok], il[ok], hi[ok], lo[ok], width[ok]
    idx, side, px, slip = stop_entries(bars, i1, iw, hi + p, lo - p, stress)
    hit = idx >= 0
    ei, side, px = idx[hit], side[hit], px[hit]
    hi, lo, width, il = hi[hit], lo[hit], width[hit], il[hit]
    ok = costs.spread_ok(bars.spread[ei], bars.pair)
    ei, side, px, hi, lo, width, il = ei[ok], side[ok], px[ok], hi[ok], lo[ok], width[ok], il[ok]
    stop = np.where(side == 1, lo, hi)
    target = px + side * width
    return simulate(bars, ei, side, stop, target, il, stress=stress, entry_px=px,
                    entry_slip=np.full(len(ei), slip), intrabar=np.ones(len(ei), bool))


# ---------------------------------------------------------------- registry of the 20 trials
def trial_ids() -> list[str]:
    ids = ["drift_A", "drift_B", "drift_AB"]
    ids += [f"mr_k{k}_m{m}_T{T}" for k, m, T in MR_GRID]
    ids += [f"rn_k{k}_m{m}_T{T}" for k, m, T in MR_GRID]
    ids += ["london_breakout"]
    return ids


def run_trial(bars: Bars, tid: str, stress: float = 1.0, hb=None, round_offset: float | None = None) -> pd.DataFrame:
    if tid.startswith("drift_"):
        return drift(bars, tid.split("_")[1], stress)
    if tid == "london_breakout":
        return london_breakout(bars, stress)
    fam, k, m, T = tid.split("_")
    k, m, T = float(k[1:]), float(m[1:]), int(T[1:])
    off = (0.0 if round_offset is None else round_offset) if fam == "rn" else None
    return mean_reversion(bars, k, m, T, stress, hb=hb, round_offset=off)


def family(tid: str) -> str:
    return {"drift": "session drift", "mr": "hourly mean reversion", "rn": "round-number filter",
            "london": "London breakout"}[tid.split("_")[0]]
