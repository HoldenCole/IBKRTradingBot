"""Test A — Faster-trigger variants for the BAH-on-trend rule.

Tests whether faster trigger rules better catch decline phases without
sacrificing CAGR. Locked decision criteria (all must hold for a variant
to win):
  1. Sortino improvement ≥ 0.3 over baseline
  2. After-tax CAGR ≥ baseline (whipsaws aren't eating gains)
  3. Max DD materially better
  4. Transition count ≤ 2x baseline (fewer = better tax/friction profile)

Variants:
  v1: 50/200 SMA crossover (baseline)
  v2: 20/100 SMA crossover (faster, same structure)
  v3: 50/200 + 10% DD circuit breaker (hybrid; OFF if 50/200 OFF OR
      QQQ < 60-day high - 10%)
  v4: 20/50 SMA crossover (much faster)
  v5: 50/200 + 2x ATR(20) drop-from-peak (OFF if 50/200 OFF OR QQQ <
      60-day high - 2*ATR20)
  v6: 50/200 + VIX circuit breaker (OFF if 50/200 OFF OR VIX > 30 AND
      VIX(5-day SMA) > VIX(20-day SMA))

Reporting per variant:
  - Sortino, CAGR, AT-CAGR, |DD|
  - OFF transitions per year
  - Behavior during 2000-2002, 2008, March 2020, 2022 declines
  - Specifically: % of March 2020 peak-to-trough drawdown avoided
  - Fraction of OFF days during decline phase (down >5% from 60-day high)
    vs. recovery phase (up >5% from 60-day low)

Cap gain tax: STCG 24% (Texas-resident, lower bracket).
T-bill interest: ordinary = STCG.
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
from src.data.fred import fetch_tbill_3m, fetch_vix


# ---------------------------------------------------------------------------
# Trigger functions — return a bool series (True = ON, False = OFF)
# ---------------------------------------------------------------------------

def trigger_sma_crossover(close: pd.Series, fast: int, slow: int) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def trigger_50_200_dd_breaker(close: pd.Series, dd_pct: float = 0.10,
                              lookback: int = 60) -> pd.Series:
    base = trigger_sma_crossover(close, 50, 200)
    high = close.rolling(lookback, min_periods=1).max()
    not_in_drawdown = (close >= high * (1 - dd_pct))
    return base & not_in_drawdown


def trigger_50_200_atr_breaker(high: pd.Series, low: pd.Series, close: pd.Series,
                               atr_mult: float = 2.0, atr_period: int = 20,
                               lookback: int = 60) -> pd.Series:
    base = trigger_sma_crossover(close, 50, 200)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period, min_periods=atr_period).mean()
    peak = close.rolling(lookback, min_periods=1).max()
    not_in_atr_drawdown = (close >= peak - atr_mult * atr)
    return (base & not_in_atr_drawdown).fillna(False)


def trigger_50_200_vix_breaker(close: pd.Series, vix: pd.Series,
                               vix_thresh: float = 30.0) -> pd.Series:
    base = trigger_sma_crossover(close, 50, 200)
    vix_aligned = vix.reindex(close.index).ffill()
    vix5 = vix_aligned.rolling(5, min_periods=5).mean()
    vix20 = vix_aligned.rolling(20, min_periods=20).mean()
    vix_panic = (vix_aligned > vix_thresh) & (vix5 > vix20)
    return (base & ~vix_panic.fillna(False))


# ---------------------------------------------------------------------------
# Backtest with T-bill OFF
# ---------------------------------------------------------------------------

def daily_tbill_factor(tbill_pct: pd.Series) -> pd.Series:
    rates = (tbill_pct / 100.0).reindex(tbill_pct.index).ffill().fillna(0.0)
    return (1.0 + rates) ** (1.0 / 252.0) - 1.0


def equity_curve(close: pd.Series, on_flags: pd.Series,
                 tbill_daily: pd.Series,
                 start_capital: float = 8000.0,
                 shift_flags: bool = False) -> pd.Series:
    """Backtest convention.

    shift_flags=False (default, matches prior framework):
        flag[t] determines whether we capture rets[t]. Achievable in practice
        only with MOC orders (submit before close based on intraday data).

    shift_flags=True (no-lookahead, decision-then-fill):
        flag[t-1] determines whether we capture rets[t]. Models a one-day
        decision-to-fill lag — decide at today's close, capture tomorrow's
        return.

    Faster-MA triggers benefit MORE from shift_flags=False than slower ones,
    so the convention can bias the comparison. Test A reports both.
    """
    rets = close.pct_change().fillna(0.0)
    tbill = tbill_daily.reindex(close.index).ffill().fillna(0.0)
    flags = on_flags.shift(1).fillna(False) if shift_flags else on_flags
    daily = rets.where(flags, tbill)
    return (1 + daily).cumprod() * start_capital


# ---------------------------------------------------------------------------
# Diagnostic: OFF days during decline vs recovery phase
# ---------------------------------------------------------------------------

def classify_phase(close: pd.Series, threshold: float = 0.05,
                   lookback: int = 60) -> pd.Series:
    """For each day, classify market phase:
       'decline' = close <= 60-day high * (1 - 5%)
       'recovery' = close >= 60-day low * (1 + 5%)
       'neutral' = neither
    """
    high = close.rolling(lookback, min_periods=1).max()
    low = close.rolling(lookback, min_periods=1).min()
    in_decline = close <= high * (1 - threshold)
    in_recovery = close >= low * (1 + threshold)
    out = pd.Series("neutral", index=close.index)
    out[in_decline] = "decline"
    # 'recovery' takes priority over 'decline' only if not in decline
    out[in_recovery & ~in_decline] = "recovery"
    return out


def transitions_per_year(on_flags: pd.Series) -> float:
    """Count OFF→anything transitions per calendar year."""
    flips = on_flags.ne(on_flags.shift(1))
    n_off_starts = int((flips & ~on_flags).sum())
    years = (on_flags.index[-1] - on_flags.index[0]).days / 365.25
    return n_off_starts / max(1e-9, years)


def off_during_decline_pct(on_flags: pd.Series, phase: pd.Series) -> float:
    """% of OFF days that fall during decline-phase (peak-to-trough decline)."""
    off = ~on_flags
    n_off = int(off.sum())
    if n_off == 0:
        return 0.0
    n_off_in_decline = int(((off) & (phase == "decline")).sum())
    return 100.0 * n_off_in_decline / n_off


def off_during_recovery_pct(on_flags: pd.Series, phase: pd.Series) -> float:
    off = ~on_flags
    n_off = int(off.sum())
    if n_off == 0:
        return 0.0
    n_in_recovery = int(((off) & (phase == "recovery")).sum())
    return 100.0 * n_in_recovery / n_off


# ---------------------------------------------------------------------------
# Specific decline-event analysis
# ---------------------------------------------------------------------------

DECLINE_EVENTS = [
    ("2000-2002 dotcom", date(2000, 3, 24), date(2002, 10, 9)),
    ("2008-2009 GFC",    date(2008, 9, 1),  date(2009, 3, 9)),
    ("March 2020 COVID", date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation",   date(2022, 1, 3),  date(2022, 10, 13)),
]


def event_dd_avoided(close: pd.Series, on_flags: pd.Series,
                     event_start: date, event_end: date,
                     tbill_daily: pd.Series) -> tuple[float, float, float]:
    """Returns (buy_and_hold_dd, strategy_dd, dd_avoided_pp).

    Computes the equity curve over [event_start, event_end] and reports
    peak-to-trough drawdown in that window for both BAH and strategy.
    """
    idx = [d.date() if hasattr(d, "date") else d for d in close.index]
    mask = pd.Series([event_start <= d <= event_end for d in idx], index=close.index)
    sub_close = close.loc[mask]
    sub_flags = on_flags.loc[mask]
    if sub_close.empty:
        return 0.0, 0.0, 0.0
    bah_curve = sub_close / float(sub_close.iloc[0])
    bah_max_dd = float(((bah_curve.cummax() - bah_curve) / bah_curve.cummax()).max())

    strat_eq = equity_curve(sub_close, sub_flags, tbill_daily, 1.0, shift_flags=True)
    strat_max_dd = float(((strat_eq.cummax() - strat_eq) / strat_eq.cummax()).max())
    return bah_max_dd, strat_max_dd, bah_max_dd - strat_max_dd


# ---------------------------------------------------------------------------
# After-tax CAGR
# ---------------------------------------------------------------------------

def after_tax_cagr(equity: pd.Series, start_capital: float, tax_rate: float
                   ) -> float:
    if equity.empty:
        return 0.0
    final = float(equity.iloc[-1])
    gain = final - start_capital
    tax = max(0, gain) * tax_rate
    after_tax = start_capital + (gain - tax)
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    return (after_tax / start_capital) ** (1.0 / max(1e-9, years)) - 1.0 \
           if after_tax > 0 else -1.0


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

def main() -> int:
    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)
    sym = "QQQ"

    print(f"Fetching {sym}, T-bill, VIX...")
    df = yahoo.daily(sym, full_start.isoformat(), full_end.isoformat())
    cache = REPO / "data" / "fred_cache"
    tbill_pct = fetch_tbill_3m(full_start.isoformat(), full_end.isoformat(),
                               cache_dir=cache)["close"]
    tbill_daily = daily_tbill_factor(tbill_pct)
    vix = fetch_vix(full_start.isoformat(), full_end.isoformat(),
                    cache_dir=cache)["close"]
    print(f"  {sym}: {len(df)} bars; VIX: {len(vix)} obs")

    close = df["close"]
    high = df["high"]
    low = df["low"]

    variants = {
        "v1: 50/200 SMA (baseline)":      trigger_sma_crossover(close, 50, 200),
        "v2: 20/100 SMA":                 trigger_sma_crossover(close, 20, 100),
        "v3: 50/200 + 10% DD breaker":    trigger_50_200_dd_breaker(close, 0.10, 60),
        "v4: 20/50 SMA":                  trigger_sma_crossover(close, 20, 50),
        "v5: 50/200 + 2× ATR(20) drop":   trigger_50_200_atr_breaker(high, low, close, 2.0, 20, 60),
        "v6: 50/200 + VIX > 30 panic":    trigger_50_200_vix_breaker(close, vix, 30.0),
    }

    phase = classify_phase(close, 0.05, 60)

    print("\n" + "#" * 100)
    print("# Test A — Faster-trigger variants | QQQ | 2000-01-03 → 2026-04-15 | T-bill OFF")
    print("#" * 100)

    results = {}  # results[(label, convention)] = {...}

    for shift_flags, conv_label in ((False, "Convention 1: flag[t] → ret[t] (MOC, prior framework)"),
                                     (True,  "Convention 2: flag[t-1] → ret[t] (no-lookahead, conservative)")):
        print(f"\n--- {conv_label} ---")
        print(f"{'Variant':30s}  {'Sortino':>7s}    {'CAGR':>6s}  {'AT CAGR':>7s}  "
              f"{'|DD|':>5s}  {'Trans/yr':>8s}  {'OFF in':>7s}  {'OFF in':>8s}")
        print(f"{'':30s}  {'':>7s}    {'':>6s}  {'':>7s}  "
              f"{'':>5s}  {'':>8s}  {'decline':>7s}  {'recovery':>8s}")

        for label, on_flags in variants.items():
            eq = equity_curve(close, on_flags, tbill_daily, 8000.0, shift_flags=shift_flags)
            m = equity_metrics(eq, 8000.0)
            at_cagr = after_tax_cagr(eq, 8000.0, 0.24)
            tpy = transitions_per_year(on_flags)
            off_dec = off_during_decline_pct(on_flags, phase)
            off_rec = off_during_recovery_pct(on_flags, phase)
            results[(label, shift_flags)] = {
                "metrics": m, "at_cagr": at_cagr, "transitions_per_year": tpy,
                "off_in_decline": off_dec, "off_in_recovery": off_rec,
                "on_flags": on_flags,
            }
            print(f"  {label:30s}  {m['sortino']:>5.2f}    {m['cagr']:>+5.1%}   "
                  f"{at_cagr:>+5.1%}    {abs(m['max_drawdown']):>4.0%}  "
                  f"{tpy:>5.2f}/yr  {off_dec:>5.0f}%   {off_rec:>5.0f}%")

    # ---- Per-event drawdown avoidance ----
    print("\n" + "#" * 100)
    print("# Decline-event drawdown avoidance (BAH max DD vs strategy max DD over event window)")
    print("#" * 100)

    print(f"\n{'Variant':30s}  ", end="")
    for ev_label, _, _ in DECLINE_EVENTS:
        print(f"{ev_label:18s}  ", end="")
    print()
    print(f"{'':30s}  ", end="")
    for _ in DECLINE_EVENTS:
        print(f"{'BAH→Strat (saved)':18s}  ", end="")
    print()

    for label, on_flags in variants.items():
        print(f"  {label:30s}  ", end="")
        for ev_label, ps, pe in DECLINE_EVENTS:
            bah_dd, strat_dd, saved = event_dd_avoided(
                close, on_flags, ps, pe, tbill_daily,
            )
            print(f"  {bah_dd*100:4.0f}%→{strat_dd*100:>3.0f}% ({saved*100:+4.0f}pp)  ",
                  end="")
        print()

    # ---- Locked-criteria evaluation: must pass under BOTH conventions ----
    print("\n" + "#" * 100)
    print("# Locked decision criteria (all 4 must hold) — applied under BOTH conventions")
    print("# A variant is robust only if it wins under both lookahead (1) and no-lookahead (2)")
    print("#" * 100)

    winners_per_conv: dict[bool, list[str]] = {False: [], True: []}
    for shift_flags, conv_name in ((False, "Convention 1 (lookahead, MOC)"),
                                    (True,  "Convention 2 (no-lookahead)")):
        print(f"\n  {conv_name}")
        baseline = results[("v1: 50/200 SMA (baseline)", shift_flags)]
        base_sortino = baseline["metrics"]["sortino"]
        base_at_cagr = baseline["at_cagr"]
        base_dd = abs(baseline["metrics"]["max_drawdown"])
        base_tpy = baseline["transitions_per_year"]

        print(f"    Baseline: Sortino {base_sortino:.2f}, AT-CAGR {base_at_cagr:+.1%}, "
              f"|DD| {base_dd:.0%}, Trans/yr {base_tpy:.2f}")
        print(f"    {'Variant':30s}  "
              f"{'ΔSortino':>9s}  {'ΔAT-CAGR':>9s}  {'ΔDD':>7s}  {'TPY≤2x':>7s}  {'PASS?':>6s}")

        for label in variants:
            if label == "v1: 50/200 SMA (baseline)":
                continue
            r = results[(label, shift_flags)]
            d_sortino = r["metrics"]["sortino"] - base_sortino
            d_at_cagr = r["at_cagr"] - base_at_cagr
            d_dd = abs(r["metrics"]["max_drawdown"]) - base_dd
            tpy_ok = r["transitions_per_year"] <= 2 * base_tpy

            c1 = d_sortino >= 0.3
            c2 = d_at_cagr >= 0
            c3 = d_dd <= -0.005
            c4 = tpy_ok
            passed = c1 and c2 and c3 and c4
            if passed:
                winners_per_conv[shift_flags].append(label)

            print(f"    {label:30s}  "
                  f"{'✓' if c1 else '✗':>1s} {d_sortino:>+5.2f}  "
                  f"{'✓' if c2 else '✗':>1s} {d_at_cagr*100:>+5.1f}pp "
                  f"{'✓' if c3 else '✗':>1s} {d_dd*100:>+4.0f}pp "
                  f"{'✓' if c4 else '✗':>5s}  "
                  f"{'WIN' if passed else 'fail':>5s}")

    robust = set(winners_per_conv[False]) & set(winners_per_conv[True])
    print(f"\n  Convention 1 winners: {winners_per_conv[False] or 'NONE'}")
    print(f"  Convention 2 winners: {winners_per_conv[True] or 'NONE'}")
    print(f"  Robust winners (both): {sorted(robust) or 'NONE'}")

    # ---- BAH sanity check: does the strategy still beat buy-and-hold? ----
    print("\n" + "#" * 100)
    print("# Buy-and-hold sanity check (no-lookahead convention)")
    print("# Does BAH-on-trend still beat straight buy-and-hold on Sortino under Convention 2?")
    print("#" * 100)

    qqq_bah_eq = (1 + close.pct_change().fillna(0.0)).cumprod() * 8000.0
    m_bah = equity_metrics(qqq_bah_eq, 8000.0)
    spy = yahoo.daily("SPY", full_start.isoformat(), full_end.isoformat())
    if not spy.empty:
        spy_bah_eq = (1 + spy["close"].pct_change().fillna(0.0)).cumprod() * 8000.0
        m_spy = equity_metrics(spy_bah_eq, 8000.0)
    else:
        m_spy = None

    print(f"\n  {'Vehicle':40s}  {'Sortino':>7s}    {'CAGR':>6s}  {'|DD|':>5s}    {'Final $':>12s}")
    print(f"  {'QQQ buy-and-hold (no strategy)':40s}  {m_bah['sortino']:>5.2f}    "
          f"{m_bah['cagr']:>+5.1%}   {abs(m_bah['max_drawdown']):>4.0%}     "
          f"${m_bah['final_equity']:>10,.0f}")
    if m_spy:
        print(f"  {'SPY buy-and-hold (benchmark)':40s}  {m_spy['sortino']:>5.2f}    "
              f"{m_spy['cagr']:>+5.1%}   {abs(m_spy['max_drawdown']):>4.0%}     "
              f"${m_spy['final_equity']:>10,.0f}")
    base_c2 = results[("v1: 50/200 SMA (baseline)", True)]
    print(f"  {'BAH-on-trend (Conv 2, no-lookahead)':40s}  "
          f"{base_c2['metrics']['sortino']:>5.2f}    "
          f"{base_c2['metrics']['cagr']:>+5.1%}   "
          f"{abs(base_c2['metrics']['max_drawdown']):>4.0%}     "
          f"${base_c2['metrics']['final_equity']:>10,.0f}")
    base_c1 = results[("v1: 50/200 SMA (baseline)", False)]
    print(f"  {'BAH-on-trend (Conv 1, prior framework)':40s}  "
          f"{base_c1['metrics']['sortino']:>5.2f}    "
          f"{base_c1['metrics']['cagr']:>+5.1%}   "
          f"{abs(base_c1['metrics']['max_drawdown']):>4.0%}     "
          f"${base_c1['metrics']['final_equity']:>10,.0f}")

    if not robust:
        print("\n  → No variant wins under both conventions.")
        print("    50/200 baseline holds. Lag is inherent to the strategy.")
    elif len(robust) > 1:
        best = max(robust, key=lambda lbl: results[(lbl, True)]["off_in_decline"])
        print(f"\n  → Multiple robust winners; tiebreaker on OFF-in-decline % "
              f"(no-lookahead): {best}")
    else:
        winner = list(robust)[0]
        print(f"\n  → Robust winner: {winner}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
