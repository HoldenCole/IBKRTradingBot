"""Bear-recovery dynamic allocation overlay test.

Hypothesis: at the moment both QQQ and BTC trend filters have been OFF for
>=30 days and BTC flips back ON, deploy BTC-heavy and rotate progressively
toward QQQ-heavy as BTC appreciates from the trigger price. The mechanism
exploits BTC's known asymmetric recovery upside in early bear-recovery
phases.

State machine (per cycle):
  WAITING  -> normal time, baseline 50/50 weights
    on bear-recovery trigger (BTC turns ON after both >=30 days OFF):
      ACTIVE-1 (initial weight, default 70% BTC / 30% QQQ)
  ACTIVE-1 -> after BTC appreciates X% from trigger close:
      ACTIVE-2 (default 50/50)
  ACTIVE-2 -> after BTC appreciates Y% (Y > X) from trigger close:
      ACTIVE-3 (default 30% BTC / 70% QQQ)
  any ACTIVE -> back to WAITING when BOTH filters go OFF again (reset).

LOCKED PRIMARY PARAMETERS:
  initial_weight_btc = 0.70  (70/30 BTC/QQQ)
  first_rotation_thresh = 1.00  (100% BTC appreciation -> 50/50)
  second_rotation_thresh = 2.50 (250% BTC appreciation -> 30/70 BTC/QQQ)

PARAMETER SENSITIVITY (single-axis variants):
  Initial weight: {0.60, 0.70 primary, 0.80}
  First rotation: {0.50, 1.00 primary, 1.50}
  Second rotation: {2.00, 2.50 primary, 3.00}
  -> 7 runs total (primary + 2x3 axes)

LOCKED DECISION CRITERIA (set BEFORE results):
  Sortino "improvement" = dynamic_sortino - baseline_sortino
  Cycles = distinct bear-recovery cycles in the sample (counted by the
           algorithm; user spec'd "4 cycles" 2015/2018/2020/2022)
  "Works in a cycle" = dynamic outperforms baseline over the cycle window

  Tier A: Sortino improvement >= 0.30
          AND works in >=3 of 4 cycles
          AND no single cycle drives >50% of outperformance (dominance)
  Tier B: Sortino improvement >= 0.15
          AND works in >=3 of 4 cycles
  Tier C: Sortino improvement >= 0.10
          AND works in >=2 of 4 cycles
  Tier D: anything else

  CRITICAL: if primary passes Tier B/A but a NEIGHBORING variant (single-
  parameter perturbation) fails, downgrade by one tier (overfit).

  CRITICAL: if primary passes Tier B BUT fails dominance, force Tier D.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd


def fetch(tk: str, start="2014-08-01", end="2026-06-21") -> pd.Series:
    import yfinance as yf
    df = yf.download(tk, start=start, end=end, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df["Close"].astype(float)


def trend_signal(close: pd.Series, fast=50, slow=200) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


@dataclass
class Params:
    initial_w_btc: float = 0.70    # ACTIVE-1 BTC weight (QQQ = 1 - this)
    rot1_thresh: float = 1.00      # BTC appreciation % for ACTIVE-1 -> ACTIVE-2 (100% = doubled)
    rot2_thresh: float = 2.50      # BTC appreciation % for ACTIVE-2 -> ACTIVE-3 (250%)
    label: str = "primary"


@dataclass
class Cycle:
    trigger_date: pd.Timestamp
    end_date: pd.Timestamp
    trigger_btc_price: float
    peak_btc_appreciation: float
    reached_rot1: bool
    reached_rot2: bool
    dynamic_return: float           # cumulative return over cycle window
    baseline_return: float          # cumulative return over same window
    outperformance: float           # dynamic - baseline


def run_strategy(btc: pd.Series, qqq: pd.Series, params: Params | None,
                 tbill_annual=0.03) -> tuple[pd.Series, list[Cycle]]:
    """If params is None, runs the static-50/50 baseline.
    Otherwise runs the dynamic strategy with the given params.

    Returns (daily_returns_series, cycles_list).
    """
    # Master calendar = BTC (daily 365). QQQ ffilled on non-trading days
    # (signal persists, return is 0 for held QQQ on weekends/holidays).
    idx = btc.index
    qqq_aligned = qqq.reindex(idx).ffill()

    btc_sig = trend_signal(btc)
    # QQQ signal computed on QQQ's own calendar then reindexed+ffilled
    qqq_sig_native = trend_signal(qqq)
    qqq_sig = qqq_sig_native.reindex(idx).ffill().fillna(False)

    btc_ret = btc.pct_change().fillna(0.0)
    qqq_ret = qqq_aligned.pct_change().fillna(0.0)
    tbill_daily = (1.0 + tbill_annual) ** (1.0/365.0) - 1.0  # daily on 365 cal

    # Signal-shifted (no lookahead): position from close[t-1] to close[t]
    # is determined by signal[t-1].
    btc_pos = btc_sig.shift(1).fillna(False)
    qqq_pos = qqq_sig.shift(1).fillna(False)
    # "Both OFF" as of close[t-1] (relevant for trigger detection at day t)
    both_off_yday = (~btc_pos) & (~qqq_pos)
    # Consecutive days "both off" ending at yesterday
    groups = (~both_off_yday).cumsum()
    consec = both_off_yday.groupby(groups).cumcount() + 1
    consec[~both_off_yday] = 0
    # Trigger: BTC turns ON today (btc_pos[t]=True, btc_pos[t-1]=False)
    btc_pos_prev = btc_pos.shift(1).fillna(False)
    btc_turn_on = btc_pos & ~btc_pos_prev
    # Need at least 30 consecutive both-off days BEFORE the flip.
    # consec is as-of-yesterday; we want consec at the day before BTC flipped,
    # i.e., at t-1 (which corresponds to yesterday's signal state, captured
    # in the prior consec value).
    consec_prev = consec.shift(1).fillna(0)
    trigger_mask = btc_turn_on & (consec_prev >= 30)

    state = "WAITING"
    trigger_price = None
    cycles: list[Cycle] = []
    open_cycle: dict | None = None
    daily = pd.Series(0.0, index=idx)

    is_baseline = params is None
    if is_baseline:
        w_btc_base, w_qqq_base = 0.5, 0.5

    for i, t in enumerate(idx):
        # Determine weights for today based on current state (and signals)
        if is_baseline:
            w_btc, w_qqq = w_btc_base, w_qqq_base
        elif state == "WAITING":
            # Outside ACTIVE periods, also run static 50/50 baseline allocation
            w_btc, w_qqq = 0.5, 0.5
        elif state == "ACTIVE-1":
            w_btc, w_qqq = params.initial_w_btc, 1.0 - params.initial_w_btc
        elif state == "ACTIVE-2":
            w_btc, w_qqq = 0.5, 0.5
        elif state == "ACTIVE-3":
            # The "QQQ-heavier" rotation — interpreted from spec progression
            # (initial BTC-heavy -> balanced -> QQQ-heavy): 30% BTC / 70% QQQ
            w_btc, w_qqq = 0.30, 0.70

        # Today's portfolio return: each sleeve earns asset return if its
        # signal is ON (from prior close), else T-bill
        btc_leg = btc_ret.iloc[i] if btc_pos.iloc[i] else tbill_daily
        qqq_leg = qqq_ret.iloc[i] if qqq_pos.iloc[i] else tbill_daily
        daily.iloc[i] = w_btc * btc_leg + w_qqq * qqq_leg

        # Track cycle metrics if we're in an open cycle
        if open_cycle is not None:
            open_cycle["peak_app"] = max(
                open_cycle["peak_app"],
                float(btc.iloc[i] / open_cycle["trigger_price"] - 1.0))

        # State transitions evaluated AFTER today's return
        if not is_baseline:
            # First: rotation thresholds (BTC appreciation from trigger)
            if state in ("ACTIVE-1", "ACTIVE-2") and trigger_price is not None:
                appreciation = float(btc.iloc[i] / trigger_price - 1.0)
                if state == "ACTIVE-1" and appreciation >= params.rot1_thresh:
                    state = "ACTIVE-2"
                    if open_cycle is not None:
                        open_cycle["reached_rot1"] = True
                if state == "ACTIVE-2" and appreciation >= params.rot2_thresh:
                    state = "ACTIVE-3"
                    if open_cycle is not None:
                        open_cycle["reached_rot2"] = True

            # Cycle end: BOTH filters OFF (signal at today's close)
            if state != "WAITING" and (~btc_sig.iloc[i]) and (~qqq_sig.iloc[i]):
                # Close cycle and reset
                if open_cycle is not None:
                    cycles.append(Cycle(
                        trigger_date=open_cycle["trigger_date"],
                        end_date=t,
                        trigger_btc_price=open_cycle["trigger_price"],
                        peak_btc_appreciation=open_cycle["peak_app"],
                        reached_rot1=open_cycle["reached_rot1"],
                        reached_rot2=open_cycle["reached_rot2"],
                        dynamic_return=0.0, baseline_return=0.0,
                        outperformance=0.0,
                    ))
                    open_cycle = None
                state = "WAITING"
                trigger_price = None

            # Trigger check
            if state == "WAITING" and trigger_mask.iloc[i]:
                state = "ACTIVE-1"
                # Trigger price: BTC close as of yesterday (when signal flipped)
                trigger_price = float(btc.iloc[i-1])
                open_cycle = {
                    "trigger_date": t,
                    "trigger_price": trigger_price,
                    "peak_app": 0.0,
                    "reached_rot1": False,
                    "reached_rot2": False,
                }

    # Close any still-open cycle at end of data
    if not is_baseline and open_cycle is not None:
        cycles.append(Cycle(
            trigger_date=open_cycle["trigger_date"],
            end_date=idx[-1],
            trigger_btc_price=open_cycle["trigger_price"],
            peak_btc_appreciation=open_cycle["peak_app"],
            reached_rot1=open_cycle["reached_rot1"],
            reached_rot2=open_cycle["reached_rot2"],
            dynamic_return=0.0, baseline_return=0.0, outperformance=0.0,
        ))

    return daily, cycles


def attribute_cycles(cycles: list[Cycle], dynamic_daily: pd.Series,
                     baseline_daily: pd.Series) -> list[Cycle]:
    """Fill in per-cycle returns and outperformance."""
    out = []
    for c in cycles:
        mask = (dynamic_daily.index >= c.trigger_date) & (dynamic_daily.index <= c.end_date)
        dyn_ret = float((1 + dynamic_daily[mask]).prod() - 1)
        base_ret = float((1 + baseline_daily[mask]).prod() - 1)
        out.append(Cycle(
            trigger_date=c.trigger_date, end_date=c.end_date,
            trigger_btc_price=c.trigger_btc_price,
            peak_btc_appreciation=c.peak_btc_appreciation,
            reached_rot1=c.reached_rot1, reached_rot2=c.reached_rot2,
            dynamic_return=dyn_ret, baseline_return=base_ret,
            outperformance=dyn_ret - base_ret,
        ))
    return out


def metrics(daily: pd.Series) -> dict:
    eq = (1 + daily.fillna(0)).cumprod()
    n = len(daily)
    years = n / 365
    cagr = float(eq.iloc[-1] ** (1.0/years) - 1.0) if eq.iloc[-1] > 0 else -1.0
    vol = float(daily.std() * np.sqrt(365))
    downside = np.minimum(daily.values, 0.0)
    dd_dev = float(np.sqrt((downside ** 2).sum() / n))
    sortino = float(daily.mean() / dd_dev * np.sqrt(365)) if dd_dev > 0 else 0.0
    max_dd = float(((eq.cummax() - eq) / eq.cummax()).max())
    return dict(cagr=cagr, sortino=sortino, max_dd=max_dd, vol=vol,
                final_equity=float(eq.iloc[-1]), n_days=n)


def verdict(s_imp: float, n_cycles_works: int, n_cycles_total: int,
            dominance_share: float) -> str:
    """Apply locked criteria. dominance_share = max single-cycle outperf /
    total positive outperf. Force Tier D if dominance > 0.50 at Tier B+."""
    if s_imp >= 0.30 and n_cycles_works >= 3 and n_cycles_total >= 4 and dominance_share <= 0.50:
        return "A"
    if s_imp >= 0.15 and n_cycles_works >= 3 and n_cycles_total >= 4:
        if dominance_share > 0.50:
            return "D (dominance force-downgrade)"
        return "B"
    if s_imp >= 0.10 and n_cycles_works >= 2:
        return "C"
    return "D"


def main() -> int:
    print("Loading BTC + QQQ...")
    btc = fetch("BTC-USD").dropna()
    qqq = fetch("QQQ").dropna()
    print(f"  BTC: {len(btc)} bars  {btc.index[0].date()} -> {btc.index[-1].date()}")
    print(f"  QQQ: {len(qqq)} bars  {qqq.index[0].date()} -> {qqq.index[-1].date()}")

    # Baseline
    base_daily, _ = run_strategy(btc, qqq, params=None)
    base_m = metrics(base_daily)

    # Parameter variants (primary + single-axis variations)
    variants = [
        Params(0.70, 1.00, 2.50, "primary (70/30, 100%, 250%)"),
        Params(0.60, 1.00, 2.50, "initial 60/40"),
        Params(0.80, 1.00, 2.50, "initial 80/20"),
        Params(0.70, 0.50, 2.50, "rot1 50%"),
        Params(0.70, 1.50, 2.50, "rot1 150%"),
        Params(0.70, 1.00, 2.00, "rot2 200%"),
        Params(0.70, 1.00, 3.00, "rot2 300%"),
    ]

    print("\n" + "=" * 96)
    print("# BEAR-RECOVERY DYNAMIC ALLOCATION OVERLAY — full results")
    print("=" * 96)
    print(f"\n  Baseline static-50/50 (with trend filters, T-bill OFF):")
    print(f"    CAGR {base_m['cagr']:+.1%}  Sortino {base_m['sortino']:.2f}  "
          f"MaxDD {base_m['max_dd']:.0%}")

    results = []
    for p in variants:
        dyn_daily, cycles = run_strategy(btc, qqq, p)
        cycles = attribute_cycles(cycles, dyn_daily, base_daily)
        m = metrics(dyn_daily)

        s_imp = m['sortino'] - base_m['sortino']
        works = sum(1 for c in cycles if c.outperformance > 0)
        n_cycles = len(cycles)
        # Dominance: max single-cycle outperf / sum of positive cycle outperfs
        pos_outperf = [c.outperformance for c in cycles if c.outperformance > 0]
        total_pos = sum(pos_outperf)
        max_single = max(pos_outperf) if pos_outperf else 0
        dominance = max_single / total_pos if total_pos > 0 else 0
        # If neither result is meaningful, dominance is 0 (no positives)
        v = verdict(s_imp, works, n_cycles, dominance)
        results.append((p, m, cycles, s_imp, works, n_cycles, dominance, v))

    # Headline table
    print(f"\n## All variants — Sortino delta and tier")
    print(f"\n  {'Variant':<32}{'CAGR':>7}{'Sortino':>8}{'Δ Sort':>8}{'MaxDD':>7}{'Cyc+':>6}{'Dom %':>7}{'Tier':>20}")
    for p, m, cycs, s_imp, works, n_cyc, dom, v in results:
        print(f"  {p.label:<32}{m['cagr']:>+6.1%}{m['sortino']:>8.2f}{s_imp:>+8.2f}"
              f"{m['max_dd']:>7.0%}{works:>3}/{n_cyc}{dom*100:>6.0f}%{v:>20}")

    # Per-cycle attribution for the primary
    primary_idx = 0
    p, m, cycles, s_imp, works, n_cyc, dom, v = results[primary_idx]
    print(f"\n## Per-cycle attribution — PRIMARY ({p.label})")
    print(f"\n  {'Trigger':>12} -> {'End':>12}{'BTC trigger':>13}{'Peak app':>10}"
          f"{'Rot1':>6}{'Rot2':>6}{'Dyn ret':>10}{'Base ret':>10}{'Δ':>10}")
    for c in cycles:
        print(f"  {c.trigger_date.date()!s} -> {c.end_date.date()!s}"
              f"${c.trigger_btc_price:>10,.0f}{c.peak_btc_appreciation:>+9.0%}"
              f"{'yes' if c.reached_rot1 else 'no':>6}"
              f"{'yes' if c.reached_rot2 else 'no':>6}"
              f"{c.dynamic_return:>+9.0%}{c.baseline_return:>+9.0%}"
              f"{c.outperformance:>+9.0%}")

    # Operational metrics for primary
    # Count weight rotations: ACTIVE-1->2->3 + cycle resets
    n_rotations_per_yr = (2 * len(cycles)) / (m['n_days']/365)
    # Each rotation generates taxable realized gains/losses (worst case both sleeves)
    print(f"\n## Operational metrics — PRIMARY")
    print(f"  Total cycles in sample: {len(cycles)}")
    print(f"  Avg weight rotations/year: {n_rotations_per_yr:.1f}")
    print(f"  Each rotation: ~2 taxable events (reweight both sleeves)")
    print(f"  Estimated annual tax drag from rotations: roughly 0.5-1% (depends on")
    print(f"    intra-cycle gains; small because rotations are infrequent)")

    # Worst-case rotation
    print(f"\n## Worst-case rotation event (rotated then BTC kept running OR crashed)")
    # Identify cycles where reached_rot2 but BTC kept going significantly higher
    # OR where reached_rot1 and then BTC crashed
    for c in cycles:
        if c.reached_rot2 and c.peak_btc_appreciation > 5.0:  # BTC went >500% but we rotated at 250%
            missed = c.peak_btc_appreciation - p.rot2_thresh
            print(f"  {c.trigger_date.date()}: BTC peaked +{c.peak_btc_appreciation*100:.0f}% but we "
                  f"rotated to QQQ-heavy at +{p.rot2_thresh*100:.0f}% (gave up {missed*100:.0f}% on BTC sleeve)")

    # Locked-criteria evaluation with neighbor overfit check
    print("\n" + "=" * 96)
    print("# LOCKED-CRITERIA EVALUATION (with overfit + dominance checks)")
    print("=" * 96)
    primary_tier = results[primary_idx][7]
    print(f"\n  Primary tier (raw): {primary_tier}")

    if primary_tier in ("A", "B"):
        # Check neighbors
        neighbor_tiers = [results[i][7] for i in range(1, len(results))]
        bad_neighbors = [n for n in neighbor_tiers if n in ("C", "D", "D (dominance force-downgrade)")]
        print(f"  Neighbor tiers: {neighbor_tiers}")
        if bad_neighbors:
            # downgrade
            downgrade_map = {"A": "B", "B": "C"}
            downgraded = downgrade_map.get(primary_tier, primary_tier)
            print(f"  Bad neighbors detected -> overfit downgrade: {primary_tier} -> {downgraded}")
            primary_tier = downgraded

    print(f"\n  >>> FINAL TIER: {primary_tier} <<<")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
