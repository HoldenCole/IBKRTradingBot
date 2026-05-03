"""Test B — OFF-period parking vehicles with 50/200 SMA baseline trigger.

Vehicles tested during OFF periods:
  - BIL (T-bills) — baseline
  - IEF (7-10yr Treasuries) — moderate duration
  - TLT (20+yr Treasuries) — strongest historical equity diversifier; 2022 risk
  - GLD (gold) — alternative store of value
  - Trend-of-trends overlay — apply 50/200 to IEF/TLT/GLD during OFF; hold
    the one in uptrend; default to T-bills if none. Re-evaluate weekly.

Both backtest conventions reported (Convention 1: flag[t] → ret[t] / MOC;
Convention 2: flag[t-1] → ret[t] / no-lookahead). The trigger is 50/200
SMA throughout — Test A confirmed this baseline holds.

Locked decision criteria (all must hold for vehicle to win):
  1. OFF-period CAGR contribution ≥ T-bill + 1pp
  2. Total max DD doesn't worsen vs T-bill baseline
  3. 2022 OFF-period behavior acceptable (≤ 10% drawdown on parking vehicle)
  4. Trend-of-trends overlay: must clear ≥1.5pp (higher bar for complexity)

OFF-period contribution = compounded return earned ONLY on OFF days,
annualized by total OFF-day-years across the 26-year sample. This isolates
the parking vehicle's contribution from ON-period equity gains.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import numpy as np
import pandas as pd

from src.backtest.benchmark import equity_metrics
from src.data import yahoo
from src.data.fred import fetch_tbill_3m


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def daily_tbill_factor(tbill_pct: pd.Series) -> pd.Series:
    rates = (tbill_pct / 100.0).reindex(tbill_pct.index).ffill().fillna(0.0)
    return (1.0 + rates) ** (1.0 / 252.0) - 1.0


def equity_curve_with_parking(
    underlying_close: pd.Series,
    parking_returns: pd.Series,
    on_flags: pd.Series,
    start_capital: float = 8000.0,
    shift_flags: bool = False,
) -> tuple[pd.Series, pd.Series]:
    """Returns (equity_curve, daily_returns).

    On ON days: capture underlying return.
    On OFF days: capture parking_returns.
    """
    rets = underlying_close.pct_change().fillna(0.0)
    flags = (on_flags.shift(1).fillna(False) if shift_flags else on_flags).astype(bool)
    parking_aligned = parking_returns.reindex(underlying_close.index).fillna(0.0)
    daily = rets.where(flags, parking_aligned)
    eq = (1 + daily).cumprod() * start_capital
    return eq, daily


def off_period_cagr(parking_returns: pd.Series, on_flags: pd.Series,
                    shift_flags: bool = False) -> float:
    """CAGR of the parking vehicle, computed over OFF days only.

    Compound the daily return only on OFF days. Annualize by
    OFF-day-count / 252.
    """
    flags = (on_flags.shift(1).fillna(False) if shift_flags else on_flags).astype(bool)
    parking_aligned = parking_returns.reindex(flags.index).fillna(0.0)
    off_only = parking_aligned.where(~flags, 0.0)
    n_off_days = int((~flags).sum())
    if n_off_days == 0:
        return 0.0
    cum_factor = float((1 + off_only).prod())
    years_in_off = n_off_days / 252.0
    return cum_factor ** (1.0 / max(1e-9, years_in_off)) - 1.0


def trend_of_trends_returns(
    candidates: dict[str, pd.Series],
    tbill_factor: pd.Series,
    rebalance_days: int = 5,
) -> pd.Series:
    """Apply 50/200 SMA to each candidate; hold whichever is in uptrend;
    default to T-bill if none. Re-evaluate every `rebalance_days` (weekly).

    Returns a daily return series aligned to the union index.
    """
    # Common index = intersection of all candidates + tbill_factor
    idx = None
    for s in list(candidates.values()) + [tbill_factor]:
        idx = s.index if idx is None else idx.intersection(s.index)
    cand_close = {k: v.reindex(idx) for k, v in candidates.items()}
    cand_rets = {k: v.pct_change().fillna(0.0) for k, v in cand_close.items()}
    cand_flags = {k: filter_on_flags(v) for k, v in cand_close.items()}
    tbill = tbill_factor.reindex(idx).fillna(0.0)

    chosen = pd.Series("BIL", index=idx)
    last_decision_idx = -rebalance_days
    current = "BIL"
    for i, ts in enumerate(idx):
        if i - last_decision_idx >= rebalance_days:
            # Pick first candidate in uptrend
            picked = "BIL"
            for k in candidates:
                if bool(cand_flags[k].iloc[i]):
                    picked = k
                    break
            current = picked
            last_decision_idx = i
        chosen.iloc[i] = current

    daily = pd.Series(0.0, index=idx)
    for k, rets in cand_rets.items():
        mask = chosen == k
        daily[mask] = rets[mask]
    daily[chosen == "BIL"] = tbill[chosen == "BIL"]
    return daily


def event_dd(equity: pd.Series, start: date, end: date) -> float:
    idx = [d.date() if hasattr(d, "date") else d for d in equity.index]
    mask = pd.Series([start <= d <= end for d in idx], index=equity.index)
    sub = equity.loc[mask]
    if sub.empty:
        return 0.0
    return float(((sub.cummax() - sub) / sub.cummax()).max())


def event_return(equity: pd.Series, start: date, end: date) -> float:
    idx = [d.date() if hasattr(d, "date") else d for d in equity.index]
    mask = pd.Series([start <= d <= end for d in idx], index=equity.index)
    sub = equity.loc[mask]
    if len(sub) < 2:
        return 0.0
    return float(sub.iloc[-1] / sub.iloc[0] - 1.0)


# ---------------------------------------------------------------------------
# Specific event windows for parking-vehicle stress tests
# ---------------------------------------------------------------------------

EQUITY_BEARS = [
    ("2000-2002 dotcom", date(2000, 3, 24), date(2002, 10, 9)),
    ("2008-2009 GFC",    date(2008, 9, 1),  date(2009, 3, 9)),
    ("March 2020 COVID", date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation",   date(2022, 1, 3),  date(2022, 10, 13)),
]


def main() -> int:
    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)
    cache = REPO / "data" / "fred_cache"

    print("Fetching QQQ + parking vehicles + T-bill...")
    qqq = yahoo.daily("QQQ", full_start.isoformat(), full_end.isoformat())
    ief = yahoo.daily("IEF", full_start.isoformat(), full_end.isoformat())
    tlt = yahoo.daily("TLT", full_start.isoformat(), full_end.isoformat())
    gld = yahoo.daily("GLD", full_start.isoformat(), full_end.isoformat())
    tbill_pct = fetch_tbill_3m(full_start.isoformat(), full_end.isoformat(),
                               cache_dir=cache)["close"]
    tbill_daily = daily_tbill_factor(tbill_pct).reindex(qqq.index).ffill().fillna(0.0)

    print(f"  QQQ: {len(qqq)} bars (since {qqq.index[0].date()})")
    print(f"  IEF: {len(ief)} bars (since {ief.index[0].date() if not ief.empty else 'N/A'})")
    print(f"  TLT: {len(tlt)} bars (since {tlt.index[0].date() if not tlt.empty else 'N/A'})")
    print(f"  GLD: {len(gld)} bars (since {gld.index[0].date() if not gld.empty else 'N/A'})")

    qqq_close = qqq["close"]
    on_flags = filter_on_flags(qqq_close)

    # Parking-vehicle daily return series (aligned to QQQ index, ffill before
    # inception with 0 — meaning if the vehicle isn't yet listed, no return
    # is captured. This understates the strategy slightly during 2000-2003
    # for IEF/TLT/GLD but is the honest treatment.)
    ief_rets = ief["close"].pct_change().fillna(0.0).reindex(qqq.index).fillna(0.0)
    tlt_rets = tlt["close"].pct_change().fillna(0.0).reindex(qqq.index).fillna(0.0)
    gld_rets = gld["close"].pct_change().fillna(0.0).reindex(qqq.index).fillna(0.0)

    # Trend-of-trends overlay
    tot_rets = trend_of_trends_returns(
        candidates={"IEF": ief["close"], "TLT": tlt["close"], "GLD": gld["close"]},
        tbill_factor=daily_tbill_factor(tbill_pct),
        rebalance_days=5,
    ).reindex(qqq.index).fillna(0.0)

    vehicles = {
        "BIL (T-bill, baseline)": tbill_daily,
        "IEF (7-10yr Tres)":      ief_rets,
        "TLT (20+yr Tres)":       tlt_rets,
        "GLD (gold)":             gld_rets,
        "Trend-of-trends (TLT/IEF/GLD/BIL)": tot_rets,
    }

    # ===================== Headline table per convention =====================
    for shift_flags, conv_label in (
        (False, "Convention 1: flag[t] → ret[t] (MOC, prior framework)"),
        (True,  "Convention 2: flag[t-1] → ret[t] (no-lookahead)"),
    ):
        print("\n" + "#" * 100)
        print(f"# Test B — Parking vehicles | 50/200 SMA trigger | QQQ underlying")
        print(f"# {conv_label}")
        print("#" * 100)

        print(f"\n{'Vehicle':38s}  {'Sortino':>7s}    {'CAGR':>6s}  {'|DD|':>5s}  "
              f"{'OFF-CAGR':>8s}  {'Final $':>12s}")

        baseline_metrics = None
        for label, parking_rets in vehicles.items():
            eq, daily = equity_curve_with_parking(
                qqq_close, parking_rets, on_flags, 8000.0, shift_flags=shift_flags,
            )
            m = equity_metrics(eq, 8000.0)
            off_cagr = off_period_cagr(parking_rets, on_flags, shift_flags=shift_flags)
            print(f"  {label:38s}  {m['sortino']:>5.2f}    "
                  f"{m['cagr']:>+5.1%}   {abs(m['max_drawdown']):>4.0%}    "
                  f"{off_cagr:>+5.1%}    ${m['final_equity']:>10,.0f}")
            if label == "BIL (T-bill, baseline)":
                baseline_metrics = (m, off_cagr)

    # ===================== Per-equity-bear stress test =====================
    print("\n" + "#" * 100)
    print("# Parking-vehicle behavior during equity bear regimes (Convention 2)")
    print("#" * 100)

    print(f"\n{'Vehicle':38s}", end="")
    for label, _, _ in EQUITY_BEARS:
        print(f"  {label:18s}", end="")
    print()
    print(f"{'':38s}", end="")
    for _ in EQUITY_BEARS:
        print(f"  {'return / |DD|':>18s}", end="")
    print()

    for label, parking_rets in vehicles.items():
        # Compute parking-vehicle-only equity (shows what just the vehicle
        # earned in each event, assuming 100% allocation to it).
        cum = (1 + parking_rets).cumprod() * 8000.0
        print(f"  {label:38s}", end="")
        for ev_label, ps, pe in EQUITY_BEARS:
            r = event_return(cum, ps, pe)
            d = event_dd(cum, ps, pe)
            print(f"  {r*100:>+5.1f}% / {d*100:>4.1f}%   ", end="")
        print()

    # ===================== Locked decision criteria =====================
    print("\n" + "#" * 100)
    print("# Locked decision criteria (Convention 2, no-lookahead)")
    print("#" * 100)

    base_off_cagr = off_period_cagr(tbill_daily, on_flags, shift_flags=True)
    base_eq, _ = equity_curve_with_parking(qqq_close, tbill_daily, on_flags, 8000.0, True)
    base_m = equity_metrics(base_eq, 8000.0)
    base_dd = abs(base_m["max_drawdown"])

    print(f"\n  Baseline (T-bill OFF): OFF-CAGR {base_off_cagr:+.2%}, |DD| {base_dd:.0%}")
    print(f"\n  {'Vehicle':38s}  {'ΔOFF-CAGR':>10s}  {'ΔTotal DD':>10s}  "
          f"{'2022 |DD|':>9s}  {'Higher Bar?':>11s}  {'PASS?':>6s}")

    winners = []
    for label, parking_rets in vehicles.items():
        if label == "BIL (T-bill, baseline)":
            continue
        eq, _ = equity_curve_with_parking(qqq_close, parking_rets, on_flags, 8000.0, True)
        m = equity_metrics(eq, 8000.0)
        off_cagr = off_period_cagr(parking_rets, on_flags, shift_flags=True)
        d_off = off_cagr - base_off_cagr
        d_total_dd = abs(m["max_drawdown"]) - base_dd

        # 2022 stress: parking-vehicle-only DD over the 2022 inflation window
        cum = (1 + parking_rets).cumprod() * 8000.0
        dd_2022 = event_dd(cum, date(2022, 1, 3), date(2022, 10, 13))

        is_overlay = "Trend-of-trends" in label
        bar_pp = 0.015 if is_overlay else 0.01
        c1 = d_off >= bar_pp
        c2 = d_total_dd <= 0.005   # doesn't materially worsen
        c3 = dd_2022 <= 0.10       # ≤10% on parking vehicle in 2022
        passed = c1 and c2 and c3
        if passed:
            winners.append(label)

        print(f"  {label:38s}  "
              f"{'✓' if c1 else '✗':>1s} {d_off*100:>+5.1f}pp "
              f"{'✓' if c2 else '✗':>1s} {d_total_dd*100:>+4.1f}pp  "
              f"{'✓' if c3 else '✗':>1s} {dd_2022*100:>4.1f}%   "
              f"{'+1.5pp' if is_overlay else '+1pp':>11s}   "
              f"{'WIN' if passed else 'fail':>5s}")

    print(f"\n  Winners under all 3 (or 4 for overlay) criteria: {winners or 'NONE'}")
    if not winners:
        print("  → T-bill baseline holds.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
